from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Type

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from eng_loop.tools.json_parse import extract_json
from eng_loop.tools.progress import (
    _get_active_spinner, log_model_invoke, log_model_done, log_stage_complete, log_stage_done, log_stage_fail,
    log_stall_warning,
)
from eng_loop.tools.stall_detector import create_stall_detector, StallDetector

if TYPE_CHECKING:
    ProgressCallback = Callable[[str, str], None]


class AgentResult:
    """Result from an agent execution."""
    def __init__(
        self,
        data: dict[str, Any],
        conversation: list[Any] | None = None,
        tool_calls_made: int = 0,
        iterations: int = 0,
        elapsed: float = 0.0,
        error: str | None = None,
    ):
        self.data = data
        self.conversation = conversation or []
        self.tool_calls_made = tool_calls_made
        self.iterations = iterations
        self.elapsed = elapsed
        self.error = error


def run_agent(
    model: ChatOpenAI,
    tools: list[Tool],
    prompt: str,
    stage_id: str,
    output_schema: Type[BaseModel] | None = None,
    max_iterations: int = 25,
    system_message: str = "",
    *,
    config: dict[str, Any] | None = None,
    progress_cb: ProgressCallback | None = None,
) -> AgentResult:
    """Run an agentic loop: LLM calls tools until work is complete, then extracts structured output.

    When ENG_AGENT_BACKEND=opencode, delegates to opencode CLI which uses native tools.
    Otherwise, uses LangChain tool-calling loop.

    Flow (LangChain mode):
    1. Bind tools to model
    2. Loop: invoke → check for tool_calls → execute tools → append results
    3. When no more tool calls: extract structured output via final invocation

    Flow (opencode mode):
    1. Invoke opencode run with stage prompt as subprocess
    2. opencode executes with native tools (read, write, edit, bash, glob, grep)
    3. Parse structured output from result file
    """
    backend = os.environ.get("ENG_AGENT_BACKEND", "langchain")
    if backend == "opencode" and config:
        project_root = config.get("paths", {}).get("project_root", ".")
        model_cfg = config.get("model", {})
        return run_agent_via_opencode(
            prompt=prompt,
            stage_id=stage_id,
            output_schema=output_schema,
            project_root=project_root,
            model_name=model_cfg.get("model", ""),
            config=config,
            progress_cb=progress_cb,
        )

    # Original LangChain tool-calling loop
    # Resolve progress callback: explicit > thread-local spinner > None
    effective_cb = progress_cb
    if effective_cb is None:
        spinner = _get_active_spinner()
        if spinner:
            effective_cb = spinner.update

    log_model_invoke(stage_id)
    t0 = time.monotonic()
    import logging as _logging
    _dbg = _logging.getLogger(__name__)
    _dbg.debug("[DEBUG] agent_runner: stage=%s, backend=langchain, max_iterations=%d, tools=%s",
               stage_id, max_iterations, [t.name for t in tools])

    # Build conversation
    messages: list[Any] = []
    if system_message:
        messages.append(SystemMessage(content=system_message))

    # The prompt instructs the agent to use tools and then produce a final answer
    agent_prompt = _build_agent_prompt(prompt, tools, output_schema)
    messages.append(HumanMessage(content=agent_prompt))

    # Bind tools to model
    model_with_tools = model.bind_tools(tools)

    tool_calls_total = 0

    # Stall detector — only for stages that have productive tools
    # Read-only stages (init, design, arch) legitimately read many files.
    # For them, only detect exact_repeat (same file read N times).
    # Disable same_tool_repeat and no_progress — they fire on normal exploration.
    agent_cfg = config.get("agent", {}) if config else {}
    tool_names = {t.name for t in tools}
    has_productive = bool(tool_names & {"write", "edit", "bash"})
    if has_productive:
        # Override no_progress_threshold — 8 is too aggressive.
        # Agent legitimately reads many files before writing.
        # Opencode has its own iteration limit as safety net.
        stall_cfg = dict(agent_cfg)
        stall_cfg["stall_detection"] = dict(agent_cfg.get("stall_detection", {}))
        stall_cfg["stall_detection"]["no_progress_threshold"] = max(
            stall_cfg["stall_detection"].get("no_progress_threshold", 8),
            30  # Allow up to 30 reads before flagging no-progress
        )
    else:
        # Read-only stages (init, design, arch): exploration naturally re-reads files.
        # Disable stall detection entirely — these stages can't get stuck in the same
        # way as write stages. The idle timeout and max_iterations are sufficient safety.
        stall_cfg = {
            "stall_detection": {
                "enabled": False,
            }
        }
    stall_detector: StallDetector = create_stall_detector(stall_cfg)

    for iteration in range(1, max_iterations + 1):
        iter_start = time.monotonic()
        _dbg.debug("[DEBUG] agent_runner: stage=%s iteration=%d/%d, messages=%d",
                    stage_id, iteration, max_iterations, len(messages))

        # LAST ITERATION: Force the agent to stop calling tools and provide an answer
        if iteration == max_iterations:
            _dbg.warning("[DEBUG] agent_runner: stage=%s LAST ITERATION — forcing final answer", stage_id)
            messages.append(HumanMessage(
                content=(
                    "CRITICAL: You have exhausted your remaining tool calls. "
                    "STOP calling tools immediately. "
                    "Provide your final answer NOW as a JSON object. "
                    "Do NOT call any more tools. Your response must be valid JSON."
                )
            ))

        try:
            response = model_with_tools.invoke(messages)
        except Exception as e:
            elapsed = time.monotonic() - t0
            log_model_done(stage_id, elapsed)
            log_stage_fail(stage_id, f"LLM error on iteration {iteration}: {e}")
            return AgentResult(
                data={},
                iterations=iteration,
                elapsed=elapsed,
                error=f"LLM error: {e}",
            )

        iter_elapsed = time.monotonic() - iter_start
        if isinstance(response, AIMessage):
            if response.tool_calls:
                _dbg.debug("[DEBUG] agent_runner: stage=%s iteration=%d, tool_calls=%d, names=%s, iter_time=%.1fs",
                            stage_id, iteration, len(response.tool_calls),
                            [tc["name"] for tc in response.tool_calls], iter_elapsed)
                # Execute each tool call
                for tc in response.tool_calls:
                    tool_name = tc["name"]
                    tool_args = tc.get("args", {})

                    # Phase 4: Compliance — verify tool is allowed for this stage
                    allowed_tools = _get_allowed_tools(stage_id, tools)
                    if tool_name not in allowed_tools:
                        messages.append(response)
                        messages.append(ToolMessage(
                            content=(
                                f"BLOCKED: Tool '{tool_name}' is not permitted in stage '{stage_id}'. "
                                f"Allowed tools: {allowed_tools}. "
                                f"Report your current status and failure reason using an allowed tool."
                            ),
                            tool_call_id=tc["id"],
                        ))
                        tool_calls_total += 1
                        continue

                    tool_result = _execute_tool(tools, tool_name, tool_args)

                    # Phase 5: Summarize large error outputs to protect context
                    if _is_error_output(tool_result) and len(tool_result) > 2000:
                        tool_result = _summarize_error(tool_result)

                    messages.append(response)
                    messages.append(ToolMessage(
                        content=tool_result,
                        tool_call_id=tc["id"],
                    ))
                    tool_calls_total += 1

                    # Phase 3: Spinner callback — update in-place, no new lines
                    if effective_cb:
                        target = ""
                        for v in tool_args.values():
                            if isinstance(v, str) and ("path" in str(v).lower() or "/" in v or "\\" in v):
                                target = str(v).split("/")[-1].split("\\")[-1]
                                break
                        effective_cb(tool_name, target)

                    # Record for stall detection
                    stall_detector.record(tool_name, tool_args)

                # Stall detection — abort early if agent is spinning
                stall_report = stall_detector.check()
                if stall_report:
                    elapsed = time.monotonic() - t0
                    log_model_done(stage_id, elapsed)
                    log_stage_fail(stage_id, stall_report.message)
                    return AgentResult(
                        data={},
                        conversation=list(messages),
                        tool_calls_made=tool_calls_total,
                        iterations=iteration,
                        elapsed=elapsed,
                        error=stall_report.message,
                    )

                # Compact messages if conversation is getting too long
                if len(messages) > 80:
                    messages = _compact_messages(messages)
            else:
                # No more tool calls — agent has its final answer
                _dbg.debug("[DEBUG] agent_runner: stage=%s FINAL ANSWER at iteration=%d, content length=%d, preview=%r",
                            stage_id, iteration, len(response.content), response.content[:200])
                elapsed = time.monotonic() - t0
                log_model_done(stage_id, elapsed)

                # Extract structured output from the final answer
                data = _extract_structured_output(
                    model, response.content, stage_id,
                    output_schema, messages,
                )
                stall_stats = stall_detector.get_stats()
                tools_summary = ", ".join(
                    f"{k}={v}" for k, v in stall_stats.get("tools_used", {}).items()
                )
                log_stage_complete(
                    stage_id,
                    duration=elapsed,
                    tool_calls=tool_calls_total,
                    summary=f"{iteration} iterations, {tools_summary}",
                    iterations=iteration,
                )

                return AgentResult(
                    data=data,
                    conversation=list(messages),
                    tool_calls_made=tool_calls_total,
                    iterations=iteration,
                    elapsed=elapsed,
                )
        else:
            # Unexpected response type
            elapsed = time.monotonic() - t0
            log_model_done(stage_id, elapsed)
            log_stage_fail(stage_id, f"unexpected response type: {type(response)}")
            return AgentResult(
                data={},
                iterations=iteration,
                elapsed=elapsed,
                error=f"unexpected response type: {type(response)}",
            )

    # Exceeded max iterations
    elapsed = time.monotonic() - t0
    _dbg.error("[DEBUG] agent_runner: stage=%s EXHAUSTED iterations=%d, total_tool_calls=%d, total_time=%.1fs",
                stage_id, max_iterations, tool_calls_total, elapsed)
    _dbg.error("[DEBUG] agent_runner: stage=%s last 3 messages:", stage_id)
    for _m in messages[-3:]:
        _content = getattr(_m, "content", str(_m))
        _dbg.error("[DEBUG]   %s: %r", type(_m).__name__, str(_content)[:300])
    log_model_done(stage_id, elapsed)
    log_stage_fail(stage_id, f"exceeded max_iterations ({max_iterations})")

    # Try to extract from best available AI message
    data = _extract_best_effort_from_messages(messages, output_schema, stage_id)

    return AgentResult(
        data=data,
        conversation=list(messages),
        tool_calls_made=tool_calls_total,
        iterations=max_iterations,
        elapsed=elapsed,
        error=f"exceeded max_iterations ({max_iterations})",
    )


def run_agent_via_opencode(
    prompt: str,
    stage_id: str,
    output_schema: Type[BaseModel] | None = None,
    project_root: str = ".",
    model_name: str = "",
    *,
    config: dict[str, Any] | None = None,
    progress_cb: ProgressCallback | None = None,
) -> AgentResult:
    """Run a stage by invoking opencode CLI as a subprocess.

    Python controls the graph, opencode executes with native tools.
    The agent writes structured output to a temp file for Python to read.

    Timeout strategy: monitor streaming events. Only kill when the model
    stops producing tokens (idle timeout). Hard timeout is last-resort fallback.
    """
    # Resolve progress callback: explicit > thread-local spinner > None
    effective_cb = progress_cb
    if effective_cb is None:
        spinner = _get_active_spinner()
        if spinner:
            effective_cb = spinner.update

    log_model_invoke(stage_id)
    t0 = time.monotonic()
    import logging as _logging
    _dbg = _logging.getLogger(__name__)
    _dbg.debug("[DEBUG] agent_runner: stage=%s, backend=opencode, model=%s", stage_id, model_name)

    # Read timeout config: idle (no-progress) and hard fallback
    hardware = (config or {}).get("hardware", {})
    HARD_TIMEOUT = hardware.get("stage_timeout_seconds", 600)
    IDLE_TIMEOUT = hardware.get("idle_timeout_seconds", 180)
    _dbg.debug("[DEBUG] agent_runner: stage=%s timeouts: idle=%ds, hard=%ds", stage_id, IDLE_TIMEOUT, HARD_TIMEOUT)

    # Stall detection — only for stages that have productive tools
    # Read-only stages (init, design, arch) legitimately read many files
    agent_cfg = config.get("agent", {}) if config else {}
    from eng_loop.tools.agent_tools import STAGE_TOOLS

    stage_tool_names = STAGE_TOOLS.get(stage_id, [])
    has_productive = bool(set(stage_tool_names) & {"write", "edit", "bash"})
    if has_productive:
        # Productive stages: allow exploration reads before flagging no-progress.
        stall_cfg = dict(agent_cfg)
        stall_cfg["stall_detection"] = dict(agent_cfg.get("stall_detection", {}))
        # no_progress: 15 — catches agents that read 15+ files without writing
        stall_cfg["stall_detection"]["no_progress_threshold"] = max(
            stall_cfg["stall_detection"].get("no_progress_threshold", 8),
            15,
        )
        # exact_repeat: 5 (reading same file 3-5x is normal for verification)
        stall_cfg["stall_detection"]["exact_repeat_threshold"] = max(
            stall_cfg["stall_detection"].get("exact_repeat_threshold", 3),
            5,
        )
        # same_tool: 12 — must be > window_size (10) to trigger, but not so high
        # that it never fires. Catches agents stuck re-reading the same tool.
        stall_cfg["stall_detection"]["same_tool_threshold"] = max(
            stall_cfg["stall_detection"].get("same_tool_threshold", 10),
            12,
        )
        # window_size: 20 — large enough for same_tool_threshold to trigger
        stall_cfg["stall_detection"]["window_size"] = 20
    else:
        # Read-only stages (init, design, arch): exploration naturally re-reads files.
        # But we still need stall detection to catch infinite read loops — idle timeout
        # alone is insufficient because it only fires when the model stops producing tokens.
        stall_cfg = dict(agent_cfg)
        stall_cfg["stall_detection"] = dict(agent_cfg.get("stall_detection", {}))
        # Higher thresholds for read-only stages — they legitimately read many files.
        stall_cfg["stall_detection"]["no_progress_threshold"] = 25
        stall_cfg["stall_detection"]["exact_repeat_threshold"] = 6
        stall_cfg["stall_detection"]["same_tool_threshold"] = 15
        stall_cfg["stall_detection"]["window_size"] = 20
    stall_detector: StallDetector = create_stall_detector(stall_cfg)

    # Create temp file for structured output
    fd, output_file = tempfile.mkstemp(suffix=".json", prefix=f"eng-{stage_id}-")
    os.close(fd)
    prompt_file = ""  # initialized before try, cleaned in finally

    try:
        # Build JSON output template from schema — gives agent exact structure to fill
        json_template = ""
        if output_schema:
            field_lines = []
            for field_name, field_info in output_schema.model_fields.items():
                ann = field_info.annotation
                if ann == bool:
                    field_lines.append(f'  "{field_name}": false')
                elif ann == int:
                    field_lines.append(f'  "{field_name}": 0')
                elif ann == float:
                    field_lines.append(f'  "{field_name}": 0.0')
                elif ann == str:
                    field_lines.append(f'  "{field_name}": ""')
                else:
                    # List, Dict, Optional, etc. — use empty container
                    field_lines.append(f'  "{field_name}": ""')
            json_template = (
                "\n## JSON OUTPUT TEMPLATE\n"
                "Write this exact JSON structure to the output file:\n"
                "```\n{\n" + ",\n".join(field_lines) + "\n}\n```\n"
            )

        # Output instruction — placed at TOP so agent knows about it from the start.
        # Without this, the agent exhausts all iterations exploring files and never
        # reaches the output instruction appended at the end.
        output_instruction = (
            f"## ⚠ CRITICAL: MANDATORY OUTPUT FILE\n"
            f"BEFORE you finish, you MUST write a JSON result to this file:\n"
            f"**{output_file}**\n\n"
            f"Use the `write` tool. DO NOT finish without writing this file.\n"
            f"If you do not write this file, your work will be LOST and you will have to start over.\n"
            f"Write this file as your LAST action after completing all other work.\n"
            f"{json_template}"
        )

        # Extract work item from prompt if present (between ## WORK ITEM markers)
        import re as _re
        wi_match = _re.search(r'## WORK ITEM\s*\n(.*?)(?:\n##|\Z)', prompt, _re.DOTALL)
        work_item_text = wi_match.group(1).strip() if wi_match else ""

        # Compact prompt: keep WORK ITEM, instructions, and key context.
        # Strip SKILL (too verbose for opencode) but keep PROCEDURE (contains task instructions).
        # Strip ARCHITECTURE CONTEXT and CONFIRMED LESSONS (agent can read files directly).
        compact_prompt = prompt
        if work_item_text:
            # Remove SKILL section (guidance, not task-critical)
            compact_prompt = _re.sub(r'## SKILL\s*\n.*?(?=\n##)', '', compact_prompt, flags=_re.DOTALL)
            # Keep PROCEDURE — it contains the actual task instructions
            # Remove ARCHITECTURE CONTEXT (agent reads files directly)
            compact_prompt = _re.sub(r'## ARCHITECTURE CONTEXT\s*\n.*?(?=\n##)', '', compact_prompt, flags=_re.DOTALL)
            # Remove CONFIRMED LESSONS (agent can read lessons file if needed)
            compact_prompt = _re.sub(r'## CONFIRMED LESSONS\s*\n.*?(?=\n##)', '', compact_prompt, flags=_re.DOTALL)
            # Collapse multiple blank lines
            compact_prompt = _re.sub(r'\n{3,}', '\n\n', compact_prompt).strip()

        output_prompt = f"{output_instruction}\n\n---\n\n{compact_prompt}\n\n---\n\n{output_instruction}"

        # Write prompt to temp file to avoid Windows command-line length limits (WinError 206)
        prompt_fd, prompt_file = tempfile.mkstemp(suffix=".md", prefix="eng-prompt-")
        os.write(prompt_fd, output_prompt.encode("utf-8"))
        os.close(prompt_fd)

        # Build opencode command — include output file in CLI message so agent
        # sees it before even reading the prompt file
        cli_message = (
            f"Read the task instructions from this file, then execute them: {prompt_file}. "
            f"Your first action MUST be to read that file with the `read` tool. "
            f"IMPORTANT: When done, you MUST write your JSON result to {output_file} using the `write` tool."
        )

        cmd = [
            "opencode", "run",
            "--dir", str(project_root),
            "--auto",
            "--format", "json",
            cli_message,
        ]

        if model_name:
            cmd.extend(["--model", model_name])

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(project_root),
            )

            last_activity = time.monotonic()
            last_progress = time.monotonic()
            last_tool_log = time.monotonic()
            timed_out = [False]
            tool_count = [0]
            stall_error = [None]  # captured stall report for timeout handler
            text_accumulator = []  # collect text events as fallback for missing output file
            no_write_count = [0]  # tool calls since last write/edit/bash (enforce output budget)
            NO_WRITE_KILL = 25  # kill if 25+ tool calls without any write/edit/bash

            # Hard fallback watchdog — only fires if everything else fails
            def _hard_watchdog():
                time.sleep(HARD_TIMEOUT)
                if proc.poll() is None:
                    timed_out[0] = True
                    proc.kill()

            threading.Thread(target=_hard_watchdog, daemon=True).start()

            # Stream JSON events line-by-line, monitoring for idle model
            while not timed_out[0]:
                line = proc.stdout.readline()
                if not line:
                    break

                try:
                    decoded = line.decode("utf-8", errors="replace").rstrip("\n\r")
                except AttributeError:
                    decoded = line.decode("utf-8", errors="replace").rstrip("\n\r")

                if not decoded:
                    # No output — check for idle timeout
                    now = time.monotonic()
                    idle_seconds = now - last_activity
                    if idle_seconds > IDLE_TIMEOUT:
                        _print_progress(stage_id, now - t0)
                        _print_warning(stage_id, f"model idle for {idle_seconds:.0f}s, killing process")
                        timed_out[0] = True
                        proc.kill()
                        break
                    continue

                # Parse JSON event
                try:
                    event = json.loads(decoded)
                except json.JSONDecodeError:
                    continue

                part = event.get("part", {})
                event_type = event.get("type", "")

                if event_type == "tool_use":
                    tool_name = part.get("tool", "?")

                    # Reset idle timer: for productive stages, only on write/edit/bash
                    # (catches infinite exploration loops). For read-only stages,
                    # reset on ANY tool — stall detector handles actual stalls.
                    if has_productive:
                        if tool_name in ("write", "edit", "bash"):
                            last_activity = time.monotonic()
                            no_write_count[0] = 0  # Reset: agent is producing output
                        else:
                            no_write_count[0] += 1
                            if no_write_count[0] >= NO_WRITE_KILL:
                                _print_warning(stage_id, f"no write/edit/bash in {no_write_count[0]} tool calls, killing")
                                stall_error[0] = f"agent_stalled: {no_write_count[0]} tool calls without write/edit/bash"
                                timed_out[0] = True
                                proc.kill()
                                break
                    else:
                        # Read-only stage: reset on any tool activity
                        last_activity = time.monotonic()
                        # Still track no_write_count — read-only stages must write output JSON
                        if tool_name not in ("write", "edit", "bash"):
                            no_write_count[0] += 1
                            if no_write_count[0] >= NO_WRITE_KILL:
                                _print_warning(stage_id, f"no write in {no_write_count[0]} tool calls, killing")
                                stall_error[0] = f"agent_stalled: {no_write_count[0]} tool calls without write"
                                timed_out[0] = True
                                proc.kill()
                                break
                    status = part.get("state", {}).get("status", "")
                    inp = part.get("state", {}).get("input", {})
                    # Extract file/path from tool input
                    path = inp.get("filePath", inp.get("path", inp.get("pattern", "")))
                    if path:
                        # Show just the filename, not the full path
                        display = path.split("/")[-1].split("\\")[-1]
                        if effective_cb:
                            effective_cb(tool_name, display)
                        else:
                            _print_tool(stage_id, tool_name, display, status)
                    else:
                        if effective_cb:
                            effective_cb(tool_name, "")
                        else:
                            _print_tool(stage_id, tool_name, "", status)
                    tool_count[0] += 1
                    if tool_count[0] % 5 == 0:
                        _dbg.debug("[DEBUG] agent_runner: stage=%s tool #%d, total_time=%.1fs, idle=%.1fs",
                                    stage_id, tool_count[0], time.monotonic() - t0,
                                    time.monotonic() - last_activity)

                    # Record for stall detection — catch infinite read loops early
                    stall_detector.record(tool_name, inp)
                    stall_report = stall_detector.check()
                    if stall_report:
                        _print_warning(stage_id, stall_report.message)
                        stall_error[0] = stall_report.message
                        timed_out[0] = True
                        proc.kill()
                        break

                elif event_type == "text":
                    # Accumulate text for fallback when output file is missing
                    text_content = part.get("content", part.get("text", ""))
                    if text_content:
                        text_accumulator.append(text_content)
                        _dbg.debug("[DEBUG] agent_runner: stage=%s text event, length=%d, preview=%r",
                                    stage_id, len(text_content), text_content[:150])

                elif event_type == "step_finish":
                    reason = part.get("reason", "")
                    if reason == "error":
                        _print_error(stage_id, part.get("error", "unknown error"))

                # Progress heartbeat — only when no spinner callback
                now = time.monotonic()
                if now - last_progress > 30 and not effective_cb:
                    _print_progress(stage_id, now - t0)
                    last_progress = now

            proc.wait()
            elapsed = time.monotonic() - t0

            if timed_out[0]:
                log_model_done(stage_id, elapsed)

                # Stall detection triggered — report specific error
                if stall_error[0]:
                    log_stage_fail(stage_id, stall_error[0])
                    return AgentResult(
                        data={},
                        iterations=1,
                        elapsed=elapsed,
                        error=stall_error[0],
                    )

                # Hard timeout or idle timeout fallback
                log_stage_fail(stage_id, f"opencode timed out (hard fallback after {HARD_TIMEOUT}s)")
                fallback_text = "\n".join(text_accumulator)
                return AgentResult(
                    data={
                        "raw_output": fallback_text[:10000],
                        "ideation_results": fallback_text[:5000],
                    },
                    iterations=1,
                    elapsed=elapsed,
                    error=f"opencode timed out after {HARD_TIMEOUT}s",
                )

            if proc.returncode != 0:
                log_stage_fail(stage_id, f"opencode exited with code {proc.returncode}")
                return AgentResult(
                    data={},
                    iterations=1,
                    elapsed=elapsed,
                    error=f"opencode exit {proc.returncode}",
                )

            # Read structured output from file
            _dbg.debug("[DEBUG] agent_runner: stage=%s opencode finished, rc=%d, output_file=%s, exists=%s, text_events=%d, tool_count=%d",
                        stage_id, proc.returncode, output_file, Path(output_file).exists(), len(text_accumulator), tool_count[0])
            try:
                if Path(output_file).exists():
                    raw = Path(output_file).read_text(encoding="utf-8")
                    data = json.loads(raw)
                    if not isinstance(data, dict):
                        data = {"raw_output": str(data)[:5000], "complete": True}
                else:
                    # Agent exhausted iterations before writing output file.
                    # Return error so calling node can retry.
                    fallback_text = "\n".join(text_accumulator)
                    _dbg.error("[DEBUG] agent_runner: stage=%s OUTPUT FILE MISSING! text_events=%d, accumulated_length=%d, last_text=%r",
                                stage_id, len(text_accumulator), len(fallback_text), fallback_text[:300])
                    log_stage_fail(stage_id, "agent exhausted iterations before writing output")
                    return AgentResult(
                        data={},
                        iterations=1,
                        elapsed=elapsed,
                        error=(
                            f"output file not written — agent likely exhausted iterations "
                            f"({tool_count[0]} tool calls made, last: {fallback_text[:200]})"
                        ),
                    )
            except (json.JSONDecodeError, Exception) as e:
                # Even on parse error, try to preserve accumulated text
                fallback_text = "\n".join(text_accumulator)
                data = {
                    "error": f"failed to parse output: {e}",
                    "complete": True,
                    "raw_output": fallback_text[:10000],
                }

            log_model_done(stage_id, elapsed)
            log_stage_complete(
                stage_id,
                duration=elapsed,
                tool_calls=tool_count[0],
                summary="opencode agent completed",
            )

            return AgentResult(
                data=data,
                iterations=1,
                tool_calls_made=tool_count[0],
                elapsed=elapsed,
            )

        except Exception as e:
            elapsed = time.monotonic() - t0
            log_model_done(stage_id, elapsed)
            log_stage_fail(stage_id, str(e))
            return AgentResult(
                data={},
                iterations=1,
                elapsed=elapsed,
                error=str(e),
            )

    finally:
        # Clean up temp files
        try:
            if Path(output_file).exists():
                os.unlink(output_file)
        except OSError:
            pass
        try:
            if Path(prompt_file).exists():
                os.unlink(prompt_file)
        except OSError:
            pass


def _extract_from_opencode_output(stdout, output_schema: Type[BaseModel] | None) -> dict[str, Any]:
    """Fallback: extract structured JSON from opencode output."""
    return {"complete": True}


def _print_tool(stage_id: str, tool: str, path: str, status: str) -> None:
    """Print a tool call event, mimicking opencode TUI style."""
    import sys as _sys
    icon = {"read": "R", "write": "W", "edit": "E", "bash": "$", "glob": "G", "grep": "S"}.get(tool, "?")
    path_str = f" {path}" if path else ""
    _sys.stdout.write(f"  \033[90m[{stage_id}]\033[0m \033[36m{icon}\033[0m {tool}{path_str}\n")
    _sys.stdout.flush()


def _print_text(stage_id: str, text: str) -> None:
    """Print LLM text output, truncated."""
    import sys as _sys
    # Only print if it's substantive (not just "OK" or similar)
    if len(text) < 10:
        return
    # Print first line only
    first_line = text.split("\n")[0][:120]
    _sys.stdout.write(f"  \033[90m[{stage_id}]\033[0m \033[2m{first_line}\033[0m\n")
    _sys.stdout.flush()


def _print_error(stage_id: str, error: str) -> None:
    """Print an error event."""
    import sys as _sys
    _sys.stdout.write(f"  \033[90m[{stage_id}]\033[0m \033[31merror: {error}\033[0m\n")
    _sys.stdout.flush()


def _print_progress(stage_id: str, elapsed: float) -> None:
    """Print a progress heartbeat."""
    import sys as _sys
    _sys.stdout.write(f"  \033[90m[{stage_id}] ... {elapsed:.0f}s\033[0m\n")
    _sys.stdout.flush()


def _print_warning(stage_id: str, message: str) -> None:
    """Print a warning message."""
    import sys as _sys
    _sys.stdout.write(f"  \033[90m[{stage_id}]\033[0m \033[33mwarn: {message}\033[0m\n")
    _sys.stdout.flush()


def _build_agent_prompt(prompt: str, tools: list[Tool], output_schema: Type[BaseModel] | None = None) -> str:
    """Wrap the stage prompt with agent instructions.

    Includes a concrete JSON template when a schema is provided, so the agent
    knows exactly what fields to produce. This eliminates the common failure
    mode where the agent outputs prose instead of structured JSON.
    """
    tool_names = ", ".join(f"`{t.name}`" for t in tools)

    # Build JSON template from schema
    json_template = ""
    if output_schema:
        fields = []
        for field_name, field_info in output_schema.model_fields.items():
            # Infer a sensible default/example per type
            if field_info.default is not None:
                default = field_info.default
            elif field_info.annotation == bool:
                default = "true"
            elif field_info.annotation == int:
                default = "0"
            elif field_info.annotation == float:
                default = "0.0"
            elif hasattr(field_info.annotation, "__origin__") and field_info.annotation.__origin__ == list:
                default = "[]"
            elif hasattr(field_info.annotation, "__origin__") and field_info.annotation.__origin__ == dict:
                default = "{}"
            else:
                default = '""'
            fields.append(f'  "{field_name}": {default}')
        json_template = (
            "\n## JSON OUTPUT TEMPLATE\n"
            "Your final answer MUST be a JSON object matching this exact structure:\n"
            "```\n{\n" + ",\n".join(fields) + "\n}\n```\n"
            "Do NOT include any text before or after the JSON object.\n"
            "Do NOT wrap the JSON in markdown unless it is a code block."
        )

    return (
        f"{prompt}\n\n"
        f"## AVAILABLE TOOLS\n"
        f"You have access to these tools: {tool_names}.\n\n"
        f"## EXECUTION INSTRUCTIONS\n"
        f"1. Use the available tools to perform the actual work described above.\n"
        f"2. Read files before modifying them. Write files to create new code.\n"
        f"3. Run tests with bash to verify your work.\n"
        f"4. When all work is complete, provide your final answer as a JSON object.\n"
        f"5. Your final answer (no more tool calls) will be parsed as the stage result.\n"
        f"{json_template}\n"
        f"IMPORTANT: Stop calling tools and provide your final answer when the work is done.\n"
        f"Do NOT continue calling tools after completing the task."
    )


def _execute_tool(tools: list[Tool], name: str, args: dict[str, Any]) -> str:
    """Execute a tool by name with given arguments."""
    tool_map = {t.name: t for t in tools}
    tool = tool_map.get(name)
    if not tool:
        return f"Error: tool '{name}' not found. Available: {list(tool_map.keys())}"

    try:
        if len(args) == 1:
            # Single argument — pass the value directly
            value = list(args.values())[0]
            result = tool.func(value)
        else:
            # Multiple arguments — call with kwargs
            result = tool.func(**args)
        # Truncate long outputs
        if isinstance(result, str) and len(result) > 10000:
            return result[:10000] + "\n... [output truncated, 10000 char limit]"
        return str(result)
    except Exception as e:
        return f"Error executing {name}: {e}"


def _extract_structured_output(
    model: ChatOpenAI,
    answer_content: str,
    stage_id: str,
    output_schema: Type[BaseModel] | None,
    conversation: list[Any],
) -> dict[str, Any]:
    """Extract structured output from the agent's final answer.

    Strategy:
    1. Try to parse JSON directly from the answer
    2. If schema provided, try model.with_structured_output() on conversation
    3. Fall back to best-effort JSON extraction
    """
    import logging as _logging
    _dbg = _logging.getLogger(__name__)
    _dbg.debug("[DEBUG] _extract_structured_output: stage=%s, content length=%d, schema=%s",
                stage_id, len(answer_content), output_schema.__name__ if output_schema else None)

    # Strategy 1: Direct JSON parse of answer
    try:
        data = extract_json(answer_content)
        _dbg.debug("[DEBUG] _extract_structured_output: strategy 1 (extract_json) succeeded: %s", str(data)[:200])
    except ValueError:
        data = None
        _dbg.debug("[DEBUG] _extract_structured_output: strategy 1 (extract_json) failed")
    if data and isinstance(data, dict) and data:
        return data

    # Strategy 2: Structured output from conversation
    if output_schema:
        _dbg.debug("[DEBUG] _extract_structured_output: strategy 2 (structured_output), schema=%s", output_schema.__name__)
        try:
            structured_model = model.with_structured_output(output_schema)
            # Add a system prompt to guide the final extraction
            extraction_messages = [
                SystemMessage(content="Extract the stage result as a JSON object from the conversation above. Return only the JSON, nothing else."),
            ] + conversation
            response = structured_model.invoke(extraction_messages)
            if hasattr(response, "model_dump"):
                _dbg.debug("[DEBUG] _extract_structured_output: strategy 2 succeeded via model_dump")
                return response.model_dump()
            _dbg.debug("[DEBUG] _extract_structured_output: strategy 2 succeeded via dict")
            return dict(response)
        except Exception as e:
            _dbg.debug("[DEBUG] _extract_structured_output: strategy 2 failed: %s", e)
            pass

    # Strategy 3: Best effort from answer text
    _dbg.debug("[DEBUG] _extract_structured_output: strategy 3 (best-effort fallback)")
    return _extract_from_text(answer_content, output_schema)


def _extract_from_text(
    text: str,
    output_schema: Type[BaseModel] | None,
) -> dict[str, Any]:
    """Last-resort JSON extraction from text."""
    try:
        data = extract_json(text)
    except ValueError:
        data = None
    if data and isinstance(data, dict):
        return data
    return {"raw_output": text[:5000], "complete": True}


def _last_ai_message(messages: list[Any]) -> AIMessage | None:
    """Find the last AI message that is not followed by tool messages."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            return msg
    # Fallback: any AI message
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return msg
    return None


def _extract_best_effort_from_messages(
    messages: list[Any],
    output_schema: Type[BaseModel] | None,
    stage_id: str,
) -> dict[str, Any]:
    """When agent exhausts iterations, find the best AI message to extract from.

    Strategy:
    1. AI messages WITHOUT tool_calls (final answers) — try each, newest first
    2. AI messages WITH tool_calls but substantial text content — try each
    3. Return raw_output fallback
    """
    import logging as _logging
    _dbg = _logging.getLogger(__name__)

    ai_msgs = [m for m in messages if isinstance(m, AIMessage)]
    _dbg.debug("[DEBUG] _extract_best_effort: found %d AI messages in conversation", len(ai_msgs))

    # Priority 1: AI messages without tool_calls (actual final answers)
    for msg in reversed(ai_msgs):
        if not getattr(msg, "tool_calls", None):
            content = msg.content if isinstance(msg.content, str) else ""
            if len(content) > 10:
                _dbg.debug("[DEBUG] _extract_best_effort: trying clean AI message, length=%d", len(content))
                try:
                    data = extract_json(content)
                    if data and isinstance(data, dict):
                        return data
                except ValueError:
                    pass

    # Priority 2: AI messages with tool_calls but meaningful text
    for msg in reversed(ai_msgs):
        content = msg.content if isinstance(msg.content, str) else ""
        if len(content) > 50:
            _dbg.debug("[DEBUG] _extract_best_effort: trying AI message with tool_calls, length=%d, preview=%r",
                        len(content), content[:120])
            try:
                data = extract_json(content)
                if data and isinstance(data, dict):
                    return data
            except ValueError:
                pass

    # Priority 3: Return best text we have
    best_text = ""
    for msg in reversed(ai_msgs):
        content = msg.content if isinstance(msg.content, str) else ""
        if len(content) > len(best_text):
            best_text = content

    if best_text:
        _dbg.debug("[DEBUG] _extract_best_effort: falling back to best text, length=%d", len(best_text))
        return {"raw_output": best_text[:5000], "complete": True}

    _dbg.warning("[DEBUG] _extract_best_effort: no AI messages with text found")
    return {}


def _compact_messages(messages: list[Any]) -> list[Any]:
    """Compact a long conversation by summarizing old tool exchanges."""
    if len(messages) <= 40:
        return messages

    # Keep system + first human + last 30 messages
    system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
    first_human = next((m for m in messages if isinstance(m, HumanMessage)), None)

    kept = list(system_msgs)
    if first_human:
        kept.append(first_human)

    # Add a summary of what was done
    tool_calls = sum(
        1 for m in messages
        if isinstance(m, ToolMessage)
    )

    summary = HumanMessage(
        content=f"[Conversation summary: {tool_calls} tool calls were made. "
                f"Earlier tool interactions have been compacted for context window management.]"
    )
    kept.append(summary)

    # Keep last 25 messages
    kept.extend(messages[-25:])

    return kept


def _get_allowed_tools(stage_id: str, tools: list[Tool]) -> list[str]:
    """Get the list of tool names that are allowed for a stage."""
    return [t.name for t in tools]


def _is_error_output(text: str) -> bool:
    """Heuristic: does this output look like an error or stack trace?"""
    if len(text) < 100:
        return False
    error_indicators = [
        "Traceback", "Error:", "Exception", "FAILED", "failed",
        "STATUS_ACCESS_VIOLATION", "ERR_", "ECONNREFUSED",
        "SyntaxError", "TypeError", "ReferenceError",
        "Exit code", "exit 1", "npm ERR", "E2E test",
    ]
    return any(kw in text for kw in error_indicators)


def _summarize_error(text: str, max_lines: int = 10) -> str:
    """Extract key signal from large error output.

    Strategies:
    1. If JSON error: extract error.message
    2. If test output: extract summary line (X failed, Y passed)
    3. If Python traceback: extract last frame (file:line + exception)
    4. Generic: extract last N non-empty lines
    """
    import json as _json
    import re

    lines = text.strip().split("\n")

    # Strategy 1: JSON error
    try:
        data = _json.loads(text)
        if "error" in data or "message" in data or "errors" in data:
            msg = data.get("message", data.get("error", str(data)))
            return f"[ERROR_SUMMARY — JSON error]\n{msg}"
    except (_json.JSONDecodeError, TypeError):
        pass

    # Strategy 2: Test summary (Playwright, pytest, jest, npm test)
    test_match = re.search(
        r"(\d+)\s*(failed|passed|skipped|pending)",
        text, re.IGNORECASE,
    )
    if test_match:
        # Extract all test summary lines
        summary_lines = [
            l.strip() for l in lines
            if re.search(r"\d+\s*(failed|passed|skipped|pending|error)", l, re.IGNORECASE)
        ]
        if summary_lines:
            return f"[ERROR_SUMMARY — test output truncated]\n" + "\n".join(summary_lines[:5])

    # Strategy 3: Python traceback — extract last meaningful frame
    traceback_lines = []
    in_traceback = False
    for line in lines:
        if "Traceback" in line:
            in_traceback = True
        if in_traceback:
            traceback_lines.append(line.strip())
        if re.match(r"^\w+Error:", line) or re.match(r"^\w+Exception:", line):
            # End of traceback — exception line
            traceback_lines.append(line.strip())
            break

    if traceback_lines:
        # Get last 5 lines of traceback
        return (
            f"[ERROR_SUMMARY — traceback truncated from {len(traceback_lines)} lines]\n"
            + "\n".join(traceback_lines[-max_lines:])
        )

    # Strategy 4: Generic — last N non-empty lines
    non_empty = [l for l in lines if l.strip()]
    return (
        f"[ERROR_SUMMARY — output truncated from {len(lines)} lines]\n"
        + "\n".join(non_empty[-max_lines:])
    )


__all__ = ["run_agent", "AgentResult"]
