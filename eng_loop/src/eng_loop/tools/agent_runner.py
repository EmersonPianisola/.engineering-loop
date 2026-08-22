from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from rich.panel import Panel

from eng_loop.tools.agent_lifecycle import AgentLifecycleManager, DistilledState
from eng_loop.tools.json_parse import extract_json
from eng_loop.tools.parse_retry import retry_with_correction, validate_against_schema
from eng_loop.tools.progress import (
    _get_active_spinner,
    _get_active_stage_ctx,
    log_model_done,
    log_model_invoke,
    log_stage_complete,
    log_stage_fail,
    ui,
)
from eng_loop.tools.stall_detector import SAFE_READ_TOOLS, StallDetector, _is_safe_inspection, create_stall_detector

if TYPE_CHECKING:
    ProgressCallback = Callable[[str, str], None]


# Global lifecycle manager — shared across all agent invocations in a run
_lifecycle_manager: AgentLifecycleManager | None = None


def get_lifecycle_manager(config: dict[str, Any] | None = None) -> AgentLifecycleManager:
    """Get or create the global lifecycle manager."""
    global _lifecycle_manager
    if _lifecycle_manager is None and config:
        _lifecycle_manager = AgentLifecycleManager(config)
    elif _lifecycle_manager is None:
        _lifecycle_manager = AgentLifecycleManager({})
    return _lifecycle_manager


def reset_lifecycle_manager() -> None:
    """Reset the global lifecycle manager (called between runs)."""
    global _lifecycle_manager
    _lifecycle_manager = None


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


# ============================================================
# COMMAND HISTORY BUFFER — prevents redundant inspection loops
# ============================================================
# Tracks all inspection/read commands per stage. When the agent
# attempts to re-execute a command whose output is already in
# context, intercepts and injects a steering ToolMessage instead
# of running the command again.
# ============================================================

STEERING_REPEAT_THRESHOLD = 2  # Intercept on 2nd repeat (3rd execution total)
READONLY_READ_THRESHOLD = 5  # Higher tolerance for read-only stages (init, design, arch)


class CommandHistoryBuffer:
    """Tracks inspection commands per stage to prevent redundant re-execution.

    Normalizes commands/args, tracks repeat count, and generates
    steering messages when redundancy is detected.

    For read-only stages (init, design, arch), uses a higher threshold
    for read tools — the agent's primary job IS to read files.
    """

    def __init__(self, repeat_threshold: int = STEERING_REPEAT_THRESHOLD, has_productive_tools: bool = True):
        self._history: dict[str, int] = {}
        self._repeat_threshold = repeat_threshold
        self._has_productive_tools = has_productive_tools

    @staticmethod
    def normalize(tool_name: str, tool_args: dict) -> str:
        """Create a normalized key for a tool call — combines all relevant args.

        grep "query-1" src/ ≠ grep "query-2" src/ (different patterns)
        grep "foo" src/   ≠ grep "foo" lib/   (different paths)
        """
        if tool_name == "bash":
            command = ""
            for key in ("command", "__arg1", "cmd"):
                if key in tool_args:
                    command = str(tool_args[key]).strip().lower()
                    break
            return f"bash:{command}"
        elif tool_name == "grep":
            parts = []
            for key in ("pattern", "path", "filePath", "include"):
                if key in tool_args:
                    parts.append(str(tool_args[key]).strip().lower())
            return f"grep:{'|'.join(parts)}"
        elif tool_name in ("read", "glob"):
            parts = []
            for key in ("filePath", "path", "pattern", "file_path"):
                if key in tool_args:
                    parts.append(str(tool_args[key]).strip().lower())
            return f"{tool_name}:{'|'.join(parts)}"
        return f"{tool_name}:{json.dumps(tool_args, sort_keys=True, default=str).lower()}"

    def record(self, tool_name: str, tool_args: dict) -> int:
        """Record a tool call. Returns current repeat count (0 = first time)."""
        key = self.normalize(tool_name, tool_args)
        count = self._history.get(key, 0)
        self._history[key] = count + 1
        return count

    def get_repeat_count(self, tool_name: str, tool_args: dict) -> int:
        """Get current execution count without recording."""
        key = self.normalize(tool_name, tool_args)
        return self._history.get(key, 0)

    def should_intercept(self, tool_name: str, tool_args: dict) -> bool:
        """Check if this call should be intercepted (already seen enough times)."""
        if not _is_safe_inspection(tool_name, tool_args):
            return False
        count = self.get_repeat_count(tool_name, tool_args)
        # Read-only stages (init, design, arch): higher threshold for read tools.
        # The agent's primary job IS to read files — don't block exploration.
        effective_threshold = self._repeat_threshold
        if not self._has_productive_tools and tool_name in SAFE_READ_TOOLS:
            effective_threshold = READONLY_READ_THRESHOLD
        return count >= effective_threshold

    def steering_message(self, tool_name: str, tool_args: dict) -> str:
        """Generate a steering message for a redundant inspection."""
        count = self.get_repeat_count(tool_name, tool_args)
        key = self.normalize(tool_name, tool_args)
        target = key.split(":", 1)[1] if ":" in key else key
        return (
            f"[System Notice] You have already executed this inspection "
            f"({tool_name}: {target}) {count} times in this task. "
            f"The output is available in your context above — do not run it again. "
            f"Use the information you've gathered and proceed to the next step "
            f"(write code, edit files, or produce your output)."
        )

    def reset(self) -> None:
        """Reset buffer (called after steering injection to allow fresh exploration)."""
        self._history.clear()

    def get_stats(self) -> dict:
        return {
            "total_unique": len(self._history),
            "repeats": sum(1 for c in self._history.values() if c > 1),
        }


def run_agent(
    model: ChatOpenAI,
    tools: list[Tool],
    prompt: str,
    stage_id: str,
    output_schema: type[BaseModel] | None = None,
    max_iterations: int = 25,
    system_message: str = "",
    *,
    config: dict[str, Any] | None = None,
    progress_cb: ProgressCallback | None = None,
    budget_manager: Any | None = None,
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
    # Store prompt for Node Inspector X-Ray
    if ui.is_hud_active() and ui._normalizer:
        ui._normalizer.store_input_prompt(stage_id, prompt[:8000])
    t0 = time.monotonic()
    import logging as _logging

    _dbg = _logging.getLogger(__name__)
    _dbg.debug(
        "[DEBUG] agent_runner: stage=%s, backend=langchain, max_iterations=%d, tools=%s",
        stage_id,
        max_iterations,
        [t.name for t in tools],
    )

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
        # Override thresholds — agent legitimately reads many files before writing.
        # Documentation tasks (summary, report) can require 15+ reads to gather info.
        stall_cfg = dict(agent_cfg)
        stall_cfg["stall_detection"] = dict(agent_cfg.get("stall_detection", {}))
        stall_cfg["stall_detection"]["no_progress_threshold"] = max(
            stall_cfg["stall_detection"].get("no_progress_threshold", 8),
            30,  # Allow up to 30 reads before flagging no-progress
        )
        # same_tool_threshold: 15 — reading 10-15 files consecutively is normal
        # for documentation/exploration tasks before writing output.
        stall_cfg["stall_detection"]["same_tool_threshold"] = max(
            stall_cfg["stall_detection"].get("same_tool_threshold", 10),
            15,
        )
        # window_size: 20 — must be >= same_tool_threshold for it to trigger
        stall_cfg["stall_detection"]["window_size"] = max(
            stall_cfg["stall_detection"].get("window_size", 10),
            20,
        )
    else:
        # Read-only stages (init, design, arch): exploration naturally reads many files.
        # But a read-only agent CAN get stuck — it may read forever without producing
        # a final answer. Use elevated thresholds instead of disabling entirely.
        stall_cfg = dict(agent_cfg)
        stall_cfg["stall_detection"] = dict(agent_cfg.get("stall_detection", {}))
        stall_cfg["stall_detection"]["enabled"] = True
        # Higher thresholds: read-only stages legitimately explore 10-20 files.
        stall_cfg["stall_detection"]["no_progress_threshold"] = max(
            stall_cfg["stall_detection"].get("no_progress_threshold", 8),
            20,
        )
        stall_cfg["stall_detection"]["exact_repeat_threshold"] = max(
            stall_cfg["stall_detection"].get("exact_repeat_threshold", 3),
            5,
        )
        stall_cfg["stall_detection"]["same_tool_threshold"] = max(
            stall_cfg["stall_detection"].get("same_tool_threshold", 10),
            15,
        )
        stall_cfg["stall_detection"]["window_size"] = max(
            stall_cfg["stall_detection"].get("window_size", 10),
            20,
        )
    stall_detector: StallDetector = create_stall_detector(stall_cfg)

    # Command history buffer — tracks inspections, injects steering on redundant repeats
    cmd_history = CommandHistoryBuffer(has_productive_tools=has_productive)

    # Steering injection counter — escalate: soft → strong → force answer
    _steering_injection_count = 0
    _STEERING_MAX_INJECTIONS = 3  # After 3 steering attempts, force final answer
    _steering_forced_answer = False  # Track whether we already forced the agent to answer

    # Tool result cache — eliminates redundant read/glob/grep calls within a stage
    tool_cache = ToolResultCache()

    # Read-loop breaker — injects a reminder after consecutive reads
    _read_streak = 0
    _read_reminder_threshold = 3
    _read_reminder_cooldown = 0  # prevent spamming: only remind once per N iterations
    _has_graphify_tools = bool({t.name for t in tools} & {"graphify_query", "graphify_explain", "graphify_path"})

    # Read-only stage safety — force final answer after too many iterations of just reading
    _read_only_answer_threshold = 15  # After 15 iterations, force the agent to answer
    _read_only_answer_injected = False

    # Ask-user rate limiter — prevent spam of user input requests
    _ask_user_count = 0
    _ASK_USER_MAX = 3  # Max 3 ask_user calls per stage

    # Agent lifecycle management — track token budget, orchestrate spawn transitions
    lifecycle = get_lifecycle_manager(config)
    agent_id = lifecycle.register_agent(stage_id)
    _dbg.debug(
        "[LIFECYCLE] Registered agent %s for stage %s (limit=%d tokens, parallel=%d)",
        agent_id,
        stage_id,
        lifecycle.config.agent_context_limit,
        lifecycle.config.max_parallel_agents,
    )

    for iteration in range(1, max_iterations + 1):
        iter_start = time.monotonic()
        _dbg.debug(
            "[DEBUG] agent_runner: stage=%s iteration=%d/%d, messages=%d",
            stage_id,
            iteration,
            max_iterations,
            len(messages),
        )

        # LAST ITERATION: Force the agent to stop calling tools and provide an answer
        if iteration == max_iterations:
            _dbg.warning("[DEBUG] agent_runner: stage=%s LAST ITERATION — forcing final answer", stage_id)
            messages.append(
                HumanMessage(
                    content=(
                        "CRITICAL: You have exhausted your remaining tool calls. "
                        "STOP calling tools immediately. "
                        "Provide your final answer NOW as a JSON object. "
                        "Do NOT call any more tools. Your response must be valid JSON."
                    )
                )
            )

        # CONTEXT BUDGET — pre-call check
        if budget_manager:
            _budget_result = _check_context_budget(
                budget_manager,
                stage_id,
                messages,
                model,
            )
            if not _budget_result["allowed"]:
                elapsed = time.monotonic() - t0
                log_model_done(stage_id, elapsed)
                log_stage_fail(stage_id, _budget_result["reason"])
                return AgentResult(
                    data={},
                    conversation=list(messages),
                    tool_calls_made=tool_calls_total,
                    iterations=iteration,
                    elapsed=elapsed,
                    error=_budget_result["reason"],
                )
            messages = _budget_result["messages"]

        # Set up idle/hard watchdog for the stream call
        # The opencode path has built-in watchdogs; the LangChain path did not.
        idle_timeout = config.get("hardware", {}).get("idle_timeout_seconds", 180)
        hard_timeout = config.get("hardware", {}).get("stage_timeout_seconds", 600)
        timed_out = [False]
        last_activity = [time.monotonic()]

        def _hard_watchdog(
            _ht=hard_timeout,
            _to=timed_out,
            _sid=stage_id,
        ):
            time.sleep(_ht)
            if not _to[0]:
                _to[0] = True
                raise TimeoutError(f"Stage {_sid} exceeded hard timeout ({_ht}s)")

        threading.Thread(target=_hard_watchdog, daemon=True).start()

        try:
            # Stream tokens for HUD visibility, then aggregate into final response
            merged_chunk = None
            for chunk in model_with_tools.stream(messages):
                if timed_out[0]:
                    raise TimeoutError(f"Stage {stage_id} idle timeout ({idle_timeout}s) -- no tokens produced")
                # Accumulate chunks using + operator
                if merged_chunk is None:
                    merged_chunk = chunk
                else:
                    merged_chunk = merged_chunk + chunk
                # Push tokens to HUD in real-time
                if chunk.content and ui.is_hud_active() and ui._normalizer:
                    ui._normalizer.token_streamed(stage_id, chunk.content)
                last_activity[0] = time.monotonic()
            # Convert merged chunk to final response
            merged = merged_chunk if merged_chunk else AIMessageChunk(content="")
            response = AIMessage(content=merged.content, tool_calls=merged.tool_calls or [])
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

        # Extract token usage for HUD telemetry
        _report_token_usage(stage_id, response)
        # Record in context budget manager
        _record_context_budget(stage_id, response, messages, budget_manager)

        iter_elapsed = time.monotonic() - iter_start
        if isinstance(response, AIMessage):
            if response.tool_calls:
                _dbg.debug(
                    "[DEBUG] agent_runner: stage=%s iteration=%d, tool_calls=%d, names=%s, iter_time=%.1fs",
                    stage_id,
                    iteration,
                    len(response.tool_calls),
                    [tc["name"] for tc in response.tool_calls],
                    iter_elapsed,
                )
                # Execute each tool call
                for tc in response.tool_calls:
                    tool_name = tc["name"]
                    tool_args = tc.get("args", {})

                    # Intercept ask_user — collect input from terminal
                    if tool_name == "ask_user":
                        _dbg.debug(
                            "[DEBUG] agent_runner: stage=%s INTERCEPTING ask_user, questions=%d",
                            stage_id,
                            len(tool_args.get("questions", [])),
                        )
                        _ask_user_count += 1
                        if _ask_user_count > _ASK_USER_MAX:
                            messages.append(response)
                            messages.append(
                                ToolMessage(
                                    content=(
                                        f"BLOCKED: You have already used ask_user {_ask_user_count - 1} times. "
                                        f"Maximum {_ASK_USER_MAX} uses per stage. "
                                        f"Work with the information you have and proceed."
                                    ),
                                    tool_call_id=tc["id"],
                                )
                            )
                            tool_calls_total += 1
                            continue
                        answers = _collect_user_input(tool_args, stage_id)
                        messages.append(response)
                        messages.append(
                            ToolMessage(
                                content=json.dumps(answers, ensure_ascii=False),
                                tool_call_id=tc["id"],
                            )
                        )
                        tool_calls_total += 1
                        # Record interaction in state for audit
                        if config:
                            config.setdefault("user_interactions", []).append(
                                {
                                    "stage": stage_id,
                                    "questions": tool_args.get("questions", []),
                                    "answers": answers.get("answers", []),
                                }
                            )
                        continue

                    # Phase 4: Compliance — verify tool is allowed for this stage
                    allowed_tools = _get_allowed_tools(stage_id, tools)
                    if tool_name not in allowed_tools:
                        messages.append(response)
                        messages.append(
                            ToolMessage(
                                content=(
                                    f"BLOCKED: Tool '{tool_name}' is not permitted in stage '{stage_id}'. "
                                    f"Allowed tools: {allowed_tools}. "
                                    f"Report your current status and failure reason using an allowed tool."
                                ),
                                tool_call_id=tc["id"],
                            )
                        )
                        tool_calls_total += 1
                        continue

                    # Command history buffer — intercept redundant inspection repeats
                    if cmd_history.should_intercept(tool_name, tool_args):
                        _dbg.debug(
                            "[DEBUG] agent_runner: stage=%s INTERCEPTING redundant %s (repeat #%d)",
                            stage_id,
                            tool_name,
                            cmd_history.get_repeat_count(tool_name, tool_args),
                        )
                        # Emit command history event for HUD visibility
                        if ui.is_hud_active() and ui._normalizer:
                            _cmd_target = _extract_tool_target(tool_name, tool_args)
                            _cmd_count = cmd_history.get_repeat_count(tool_name, tool_args)
                            ui._normalizer.command_history_update(
                                stage_id, tool_name, _cmd_target, _cmd_count, is_intercepted=True
                            )
                        _steering_injection_count += 1
                        if _steering_injection_count >= _STEERING_MAX_INJECTIONS:
                            if _steering_forced_answer:
                                # Agent already forced to answer but still repeating — abort
                                elapsed = time.monotonic() - t0
                                log_model_done(stage_id, elapsed)
                                log_stage_fail(
                                    stage_id,
                                    f"agent_stalled: redundant inspection loop detected "
                                    f"({_steering_injection_count} steering attempts exhausted)",
                                )
                                return AgentResult(
                                    data={},
                                    conversation=list(messages),
                                    tool_calls_made=tool_calls_total,
                                    iterations=iteration,
                                    elapsed=elapsed,
                                    error=(
                                        f"agent_stalled: redundant inspection loop "
                                        f"({_steering_injection_count} steering attempts exhausted)"
                                    ),
                                )
                            # First time reaching max: force the agent to produce an answer
                            _steering_forced_answer = True
                            _dbg.warning(
                                "[DEBUG] agent_runner: stage=%s FORCING final answer after %d steering attempts",
                                stage_id,
                                _steering_injection_count,
                            )
                            messages.append(response)
                            messages.append(
                                ToolMessage(
                                    content=cmd_history.steering_message(tool_name, tool_args),
                                    tool_call_id=tc["id"],
                                )
                            )
                            messages.append(
                                HumanMessage(
                                    content=(
                                        "CRITICAL: You are stuck in a redundant inspection loop. "
                                        "STOP calling tools immediately. "
                                        "Provide your final answer NOW as a JSON object. "
                                        "Do NOT call any more tools. Your response must be valid JSON."
                                    )
                                )
                            )
                            tool_calls_total += 1
                            cmd_history.reset()
                            stall_detector.reset()
                            _read_streak = 0
                            continue
                        # Inject steering as ToolMessage (agent sees it as tool result)
                        messages.append(response)
                        messages.append(
                            ToolMessage(
                                content=cmd_history.steering_message(tool_name, tool_args),
                                tool_call_id=tc["id"],
                            )
                        )
                        tool_calls_total += 1
                        cmd_history.reset()
                        stall_detector.reset()
                        _read_streak = 0
                        continue

                    # Record in command history (first time or allowed repeat)
                    _recorded_count = cmd_history.record(tool_name, tool_args)
                    # Emit command history event for HUD visibility
                    if ui.is_hud_active() and ui._normalizer:
                        _cmd_target = _extract_tool_target(tool_name, tool_args)
                        ui._normalizer.command_history_update(stage_id, tool_name, _cmd_target, _recorded_count + 1)

                    tool_result = _execute_tool_cached(tools, tool_name, tool_args, tool_cache)

                    # Phase 5: Summarize large error outputs to protect context
                    if _is_error_output(tool_result) and len(tool_result) > 2000:
                        tool_result = _summarize_error(tool_result)

                    messages.append(response)
                    messages.append(
                        ToolMessage(
                            content=tool_result,
                            tool_call_id=tc["id"],
                        )
                    )
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

                    # Track consecutive reads — break blind read loops
                    if tool_name in ("read", "glob", "grep"):
                        _read_streak += 1
                    else:
                        _read_streak = 0

                # Stall detection — soft stalls get steering, hard stalls abort
                stall_report = stall_detector.check()
                if stall_report:
                    if stall_report.severity == "soft":
                        _dbg.debug(
                            "[DEBUG] agent_runner: stage=%s SOFT stall — injecting steering: %s",
                            stage_id,
                            stall_report.message,
                        )
                        _steering_injection_count += 1
                        if _steering_injection_count >= _STEERING_MAX_INJECTIONS:
                            if _steering_forced_answer:
                                # Agent already forced to answer but still stalling — abort
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
                            # First time reaching max: force the agent to produce an answer
                            _steering_forced_answer = True
                            _dbg.warning(
                                "[DEBUG] agent_runner: stage=%s FORCING final answer after %d steering attempts",
                                stage_id,
                                _steering_injection_count,
                            )
                            messages.append(
                                HumanMessage(
                                    content=(
                                        "CRITICAL: You are stuck in a redundant inspection loop. "
                                        "STOP calling tools immediately. "
                                        "Provide your final answer NOW as a JSON object. "
                                        "Do NOT call any more tools. Your response must be valid JSON."
                                    )
                                )
                            )
                            stall_detector.reset()
                            cmd_history.reset()
                            _read_streak = 0
                            continue
                        messages.append(
                            HumanMessage(
                                content=(
                                    f"[System Notice] {stall_report.message}. "
                                    f"You have gathered enough context from {stall_report.tool_name} calls. "
                                    f"Stop repeating the same inspections and proceed to write/edit code or produce output."
                                )
                            )
                        )
                        stall_detector.reset()
                        cmd_history.reset()
                        _read_streak = 0
                    else:
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

                # Read-loop breaker — inject reminder after consecutive reads
                if _read_streak >= _read_reminder_threshold and _read_reminder_cooldown <= 0:
                    _dbg.debug(
                        "[DEBUG] agent_runner: stage=%s read-loop breaker triggered (streak=%d)", stage_id, _read_streak
                    )
                    if _has_graphify_tools:
                        reminder_text = (
                            f"You have made {_read_streak} consecutive read/search calls "
                            "without writing anything. "
                            "You have graphify tools available. Use `graphify_query` to get architectural "
                            "context for your task, then use `graphify_explain` on specific entities "
                            "before reading more files. Focus on reading only files directly relevant "
                            "to your current task."
                        )
                    else:
                        reminder_text = (
                            f"You have made {_read_streak} consecutive read/search calls "
                            "without making progress. "
                            "You have gathered enough context — stop reading the same files repeatedly. "
                            "Synthesize what you've learned and produce your output."
                        )
                    messages.append(HumanMessage(content=reminder_text))
                    # Reset stall detector to break exact-repeat streak
                    stall_detector.reset()
                    _read_streak = 0
                    _read_reminder_cooldown = 3  # Don't remind again for 3 iterations
                if _read_reminder_cooldown > 0:
                    _read_reminder_cooldown -= 1

                # Read-only stage safety — force final answer after too many iterations
                if not has_productive and not _read_only_answer_injected and iteration >= _read_only_answer_threshold:
                    _dbg.warning(
                        "[DEBUG] agent_runner: stage=%s READ-ONLY SAFETY — forcing final answer after %d iterations of tool calls",
                        stage_id,
                        iteration,
                    )
                    messages.append(
                        HumanMessage(
                            content=(
                                f"CRITICAL: You have used {iteration} iterations calling tools. "
                                f"You have gathered enough information. "
                                f"STOP calling tools immediately. "
                                f"Provide your final answer NOW as a JSON object. "
                                f"Do NOT call any more tools."
                            )
                        )
                    )
                    _read_only_answer_injected = True

                # Agent lifecycle check — track budget and decide whether to continue or distill+spawn
                is_prod = tool_name in ("write", "edit", "bash") if "tool_name" in dir() else False
                action, agent_stats = lifecycle.record_iteration(
                    stage_id,
                    input_tokens=0,  # estimated; real count comes from model response metadata
                    output_tokens=0,
                    tool_call_name=tool_name if "tool_name" in dir() else "",
                    is_productive=is_prod,
                )

                if action == "distill_and_spawn":
                    _dbg.warning(
                        "[LIFECYCLE] Agent %s budget exhausted (iterations=%d). Distilling and spawning.",
                        agent_stats.agent_id,
                        agent_stats.iterations,
                    )
                    distilled = lifecycle.build_distilled_state(stage_id, messages, tool_cache.get_stats())
                    new_agent_id, new_agent = lifecycle.spawn_next_agent(stage_id, distilled)

                    # Inject distilled state as context for the new agent
                    distilled_prompt = _build_distilled_context(distilled, stage_id)
                    messages.append(HumanMessage(content=distilled_prompt))
                    # Reset message list to just the distilled context + system + original objective
                    # This gives the new agent a clean budget
                    messages = [m for m in messages if isinstance(m, (SystemMessage, HumanMessage))]
                    # Re-inject the original work item
                    messages.append(HumanMessage(content=distilled_prompt))
                    agent_id = new_agent_id
                    _read_streak = 0
                    stall_detector.reset()
                    cmd_history.reset()
                    tool_cache.clear()

                # Legacy compaction is now disabled — lifecycle manager handles context overflow
                # if len(messages) > 80:
                #     messages = _compact_messages(messages)
            else:
                # No more tool calls — agent has its final answer
                _dbg.debug(
                    "[DEBUG] agent_runner: stage=%s FINAL ANSWER at iteration=%d, content length=%d, preview=%r",
                    stage_id,
                    iteration,
                    len(response.content),
                    response.content[:200],
                )
                elapsed = time.monotonic() - t0
                log_model_done(stage_id, elapsed)

                # Extract structured output from the final answer
                data = _extract_structured_output(
                    model,
                    response.content,
                    stage_id,
                    output_schema,
                    messages,
                )
                stall_stats = stall_detector.get_stats()
                cache_stats = tool_cache.get_stats()
                tools_summary = ", ".join(f"{k}={v}" for k, v in stall_stats.get("tools_used", {}).items())
                parts = [f"{iteration} iterations"]
                if tools_summary:
                    parts.append(tools_summary)
                parts.append(f"cache: {cache_stats['hits']}h/{cache_stats['misses']}m")
                summary_text = ", ".join(parts)
                # When trace_node spinner is active, defer rendering to the decorator
                # to avoid duplicate panels. Store iteration/summary for trace_node.
                active_ctx = _get_active_stage_ctx()
                if active_ctx is not None:
                    active_ctx.iterations = iteration
                    active_ctx.summary = summary_text
                else:
                    log_stage_complete(
                        stage_id,
                        duration=elapsed,
                        tool_calls=tool_calls_total,
                        summary=summary_text,
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
    _dbg.error(
        "[DEBUG] agent_runner: stage=%s EXHAUSTED iterations=%d, total_tool_calls=%d, total_time=%.1fs",
        stage_id,
        max_iterations,
        tool_calls_total,
        elapsed,
    )
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
    output_schema: type[BaseModel] | None = None,
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
    # Store prompt for Node Inspector X-Ray
    if ui.is_hud_active() and ui._normalizer:
        ui._normalizer.store_input_prompt(stage_id, prompt[:8000])
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

        # Graphify bash wrapper — enables graphify queries via bash in opencode mode
        graphify_bash_hint = ""
        graphify_state = (config or {}).get("graphify", {})
        if graphify_state.get("built", False):
            graphify_bash_hint = (
                "\n\n## GRAPHIFY VIA BASH\n"
                "A knowledge graph is available. Use bash to query it:\n"
                '- `graphify query "your question"` — get architecture context\n'
                "- `graphify explain EntityName` — understand an entity's structure\n"
                "- `graphify path Source Dest` — trace connections between entities\n"
                "Use these BEFORE reading many files to understand the codebase structure."
            )

        # Extract work item from prompt if present (between ## WORK ITEM markers)
        import re as _re

        wi_match = _re.search(r"## WORK ITEM\s*\n(.*?)(?:\n##|\Z)", prompt, _re.DOTALL)
        work_item_text = wi_match.group(1).strip() if wi_match else ""

        # Compact prompt: keep WORK ITEM, instructions, and key context.
        # Compact SKILL to ~50 lines (preserves Rules, Anti-Patterns, Execution Protocol).
        # Strip ARCHITECTURE CONTEXT and CONFIRMED LESSONS (agent can read files directly).
        compact_prompt = prompt
        if work_item_text:
            # Compact SKILL section instead of stripping — preserves critical guidance
            compact_prompt = _inject_compact_skill(compact_prompt, max_skill_lines=50)
            # Keep PROCEDURE — it contains the actual task instructions
            # Remove ARCHITECTURE CONTEXT (agent reads files directly)
            compact_prompt = _re.sub(r"## ARCHITECTURE CONTEXT\s*\n.*?(?=\n##)", "", compact_prompt, flags=_re.DOTALL)
            # Remove CONFIRMED LESSONS (agent can read lessons file if needed)
            compact_prompt = _re.sub(r"## CONFIRMED LESSONS\s*\n.*?(?=\n##)", "", compact_prompt, flags=_re.DOTALL)
            # Collapse multiple blank lines
            compact_prompt = _re.sub(r"\n{3,}", "\n\n", compact_prompt).strip()

        output_prompt = (
            f"{output_instruction}\n\n{graphify_bash_hint}\n\n---\n\n{compact_prompt}\n\n---\n\n{output_instruction}"
        )

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
            "opencode",
            "run",
            "--dir",
            str(project_root),
            "--auto",
            "--format",
            "json",
            cli_message,
        ]

        if model_name:
            cmd.extend(["--model", model_name])

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr→stdout to avoid _readerthread exceptions on Windows when proc.kill() is called
                cwd=str(project_root),
                encoding="utf-8",
                errors="replace",
            )

            last_activity = time.monotonic()
            last_progress = time.monotonic()
            time.monotonic()
            timed_out = [False]
            tool_count = [0]
            stall_error = [None]  # captured stall report for timeout handler
            text_accumulator = []  # collect text events as fallback for missing output file
            no_write_count = [0]  # tool calls since last write/edit/bash (enforce output budget)
            NO_WRITE_KILL = 45  # kill if 45+ tool calls without any write/edit/bash
            read_streak = [0]  # consecutive read/glob/grep calls (catch blind read loops early)
            READ_LOOP_KILL = 15  # kill if 15+ consecutive reads — agent is lost
            # Soft stall tracking — log warnings instead of killing for safe inspections
            _soft_stall_warnings = [0]
            _SOFT_STALL_MAX = 4  # After 4 soft stall warnings, escalate to kill

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
                            read_streak[0] = 0  # Reset read streak on productive work
                        else:
                            no_write_count[0] += 1
                            if no_write_count[0] >= NO_WRITE_KILL:
                                _print_warning(
                                    stage_id, f"no write/edit/bash in {no_write_count[0]} tool calls, killing"
                                )
                                stall_error[0] = (
                                    f"agent_stalled: {no_write_count[0]} tool calls without write/edit/bash"
                                )
                                timed_out[0] = True
                                proc.kill()
                                break
                        # Track consecutive reads — catch blind read loops early
                        if tool_name in ("read", "glob", "grep"):
                            read_streak[0] += 1
                            if read_streak[0] >= READ_LOOP_KILL:
                                _print_warning(
                                    stage_id, f"read loop detected: {read_streak[0]} consecutive reads, killing"
                                )
                                stall_error[0] = (
                                    f"agent_stalled: {read_streak[0]} consecutive read/glob/grep calls without progress. "
                                    f"Agent appeared to be blindly exploring files. "
                                    f"Retry will include pre-computed graph context."
                                )
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
                        else:
                            read_streak[0] = 0  # Reset on productive work
                        # Track consecutive reads — catch blind read loops early
                        if tool_name in ("read", "glob", "grep"):
                            read_streak[0] += 1
                            if read_streak[0] >= READ_LOOP_KILL:
                                _print_warning(
                                    stage_id, f"read loop detected: {read_streak[0]} consecutive reads, killing"
                                )
                                stall_error[0] = (
                                    f"agent_stalled: {read_streak[0]} consecutive read calls without progress. "
                                    f"Agent appeared to be blindly exploring files."
                                )
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
                        _dbg.debug(
                            "[DEBUG] agent_runner: stage=%s tool #%d, total_time=%.1fs, idle=%.1fs",
                            stage_id,
                            tool_count[0],
                            time.monotonic() - t0,
                            time.monotonic() - last_activity,
                        )
                    # Push tool event to HUD for casting bar visibility
                    if ui.is_hud_active() and ui._normalizer:
                        ui._normalizer.tool_started(stage_id, tool_name, inp)

                    # Record for stall detection — catch infinite read loops early
                    stall_detector.record(tool_name, inp)
                    stall_report = stall_detector.check()
                    if stall_report:
                        if stall_report.severity == "soft":
                            _soft_stall_warnings[0] += 1
                            _print_warning(stage_id, f"soft stall #{_soft_stall_warnings[0]}: {stall_report.message}")
                            if _soft_stall_warnings[0] >= _SOFT_STALL_MAX:
                                _print_warning(
                                    stage_id, f"soft stall limit reached ({_SOFT_STALL_MAX}), escalating to kill"
                                )
                                stall_error[0] = (
                                    f"agent_stalled: {stall_report.message} "
                                    f"(after {_SOFT_STALL_MAX} soft stall warnings)"
                                )
                                timed_out[0] = True
                                proc.kill()
                                break
                        else:
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
                        _dbg.debug(
                            "[DEBUG] agent_runner: stage=%s text event, length=%d, preview=%r",
                            stage_id,
                            len(text_content),
                            text_content[:150],
                        )
                        # Stream to HUD for real-time visibility
                        if ui.is_hud_active() and ui._normalizer:
                            ui._normalizer.token_streamed(stage_id, text_content)

                elif event_type == "step_finish":
                    reason = part.get("reason", "")
                    if reason == "error":
                        _print_error(stage_id, part.get("error", "unknown error"))

                # Progress heartbeat — only when no spinner callback
                now = time.monotonic()
                if now - last_progress > 5 and not effective_cb:
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
            _dbg.debug(
                "[DEBUG] agent_runner: stage=%s opencode finished, rc=%d, output_file=%s, exists=%s, text_events=%d, tool_count=%d",
                stage_id,
                proc.returncode,
                output_file,
                Path(output_file).exists(),
                len(text_accumulator),
                tool_count[0],
            )
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
                    _dbg.error(
                        "[DEBUG] agent_runner: stage=%s OUTPUT FILE MISSING! text_events=%d, accumulated_length=%d, last_text=%r",
                        stage_id,
                        len(text_accumulator),
                        len(fallback_text),
                        fallback_text[:300],
                    )
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
            active_ctx = _get_active_stage_ctx()
            if active_ctx is not None:
                active_ctx.iterations = 1
                active_ctx.summary = "opencode agent completed"
            else:
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


def _extract_from_opencode_output(stdout, output_schema: type[BaseModel] | None) -> dict[str, Any]:
    """Fallback: extract structured JSON from opencode output."""
    return {"complete": True}


def _print_tool(stage_id: str, tool: str, path: str, status: str) -> None:
    """Print a tool call event, mimicking opencode TUI style."""
    import sys as _sys

    # Silent when spinner is active — it handles visual feedback
    from eng_loop.tools.progress import _get_active_spinner

    if _get_active_spinner():
        return

    icon = {"read": "R", "write": "W", "edit": "E", "bash": "$", "glob": "G", "grep": "S"}.get(tool, "?")
    path_str = f" {path}" if path else ""
    _sys.stdout.write(f"  \033[90m[{stage_id}]\033[0m \033[36m{icon}\033[0m {tool}{path_str}\n")
    _sys.stdout.flush()


def _print_text(stage_id: str, text: str) -> None:
    """Print LLM text output, truncated."""
    import sys as _sys

    # Silent when spinner is active
    from eng_loop.tools.progress import _get_active_spinner

    if _get_active_spinner():
        return

    # Only print if it's substantive (not just "OK" or similar)
    if len(text) < 10:
        return
    # Print first line only
    first_line = text.split("\n")[0][:120]
    _sys.stdout.write(f"  \033[90m[{stage_id}]\033[0m \033[2m{first_line}\033[0m\n")
    _sys.stdout.flush()


def _print_error(stage_id: str, error: str) -> None:
    """Print an error event with proper panel formatting."""
    from eng_loop.tools.progress import _get_active_spinner, ui

    spinner = _get_active_spinner()
    if spinner:
        # Spinner is active — let it handle the display
        return

    # Use Rich panel for errors — consistent with rest of CLI
    ui.console.print(
        Panel(
            f"[bold red]Error in {stage_id}[/bold red]\n[dim]{error}[/dim]",
            title="[bold red]\u2717 Error[/bold red]",
            border_style="red",
        )
    )


def _print_progress(stage_id: str, elapsed: float) -> None:
    """Print a progress heartbeat with wall-clock time."""
    from eng_loop.tools.progress import _get_active_spinner
    from eng_loop.tools.timing import get_global_wall_formatted

    if _get_active_spinner():
        return

    import sys as _sys

    wall = get_global_wall_formatted()
    _sys.stdout.write(f"  \033[90m[{stage_id}] ... {elapsed:.0f}s (wall: {wall})\033[0m\n")
    _sys.stdout.flush()


def _print_warning(stage_id: str, message: str) -> None:
    """Print a warning message with proper panel formatting."""
    from eng_loop.tools.progress import _get_active_spinner, ui

    if _get_active_spinner():
        return

    ui.console.print(
        Panel(
            f"[yellow]{stage_id}[/yellow]\n[dim]{message}[/dim]",
            title="[bold yellow]\u26a0 Warning[/bold yellow]",
            border_style="yellow",
        )
    )


def _build_agent_prompt(prompt: str, tools: list[Tool], output_schema: type[BaseModel] | None = None) -> str:
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
            elif hasattr(field_info.annotation, "__origin__") and field_info.annotation.__origin__ in (list, tuple):
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
        # Always dispatch via kwargs — preserves parameter names from LLM tool calls.
        # Never use positional dispatch (broken: discards arg key names, relies on
        # coincidence that positional order matches the tool function's signature).
        result = tool.func(**args)
        # Truncate long outputs
        if isinstance(result, str) and len(result) > 10000:
            return result[:10000] + "\n... [output truncated, 10000 char limit]"
        return str(result)
    except Exception as e:
        return f"Error executing {name}: {e}"


# ============================================================
# TOOL RESULT CACHE — eliminates redundant read/glob/grep calls
# ============================================================
# Caches results of idempotent tools (read, glob, grep) within a single agent run.
# Invalidated when write/edit/bash tools modify files.
# ============================================================

# Tools whose results are safe to cache (idempotent reads)
CACHABLE_TOOLS = {"read", "glob", "grep"}
# Tools that invalidate the cache (mutating operations)
INVALIDATING_TOOLS = {"write", "edit", "bash"}


class ToolResultCache:
    """In-memory cache for tool results within a single agent execution.

    Prevents the LLM from wasting tool-calls re-reading the same files
    or re-running the same glob/grep patterns within a stage.
    """

    def __init__(self):
        self._cache: dict[str, str] = {}
        self._hits = 0
        self._misses = 0
        self._invalidations = 0

    def get(self, tool_name: str, args: dict[str, Any]) -> str | None:
        """Return cached result if available, else None."""
        if tool_name not in CACHABLE_TOOLS:
            return None
        key = self._make_key(tool_name, args)
        result = self._cache.get(key)
        if result is not None:
            self._hits += 1
        return result

    def set(self, tool_name: str, args: dict[str, Any], result: str) -> None:
        """Cache a tool result."""
        if tool_name not in CACHABLE_TOOLS:
            return
        key = self._make_key(tool_name, args)
        # Cap individual entries at 8000 chars to prevent memory bloat
        cached_result = result[:8000] if len(result) > 8000 else result
        self._cache[key] = cached_result
        self._misses += 1

    def invalidate_on_mutation(self, tool_name: str, args: dict[str, Any]) -> None:
        """Invalidate cache entries affected by a mutating tool."""
        if tool_name not in INVALIDATING_TOOLS:
            return

        modified_path = self._extract_path(args)

        if modified_path:
            # Targeted invalidation: remove read/glob/grep entries for affected paths
            to_remove = []
            for key in self._cache:
                if self._key_affected_by(key, modified_path):
                    to_remove.append(key)
            for key in to_remove:
                del self._cache[key]
            self._invalidations += len(to_remove)
        elif tool_name == "bash":
            # Bash can modify anything — full invalidation
            self._cache.clear()
            self._invalidations += 1

    def get_stats(self) -> dict[str, int]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "invalidations": self._invalidations,
            "entries": len(self._cache),
        }

    def _make_key(self, tool_name: str, args: dict[str, Any]) -> str:
        return f"{tool_name}:{json.dumps(args, sort_keys=True, default=str)}"

    def _extract_path(self, args: dict[str, Any]) -> str | None:
        """Extract the file path from tool args."""
        for key in ("file_path", "path", "old_string"):
            if key in args:
                return args[key]
        # For single-arg tools, the path is the value
        if len(args) == 1:
            val = next(iter(args.values()))
            if isinstance(val, str) and (".ts" in val or ".js" in val or ".py" in val or "/" in val or "\\" in val):
                return val
        return None

    def _key_affected_by(self, key: str, modified_path: str) -> bool:
        """Check if a cached key might be affected by a file modification."""
        # If the modified path appears in the cached key, invalidate it
        return modified_path in key


def _execute_tool_cached(
    tools: list[Tool],
    name: str,
    args: dict[str, Any],
    cache: ToolResultCache,
) -> str:
    """Execute a tool with caching. Returns cached result for idempotent tools."""
    # Try cache first for read-only tools
    cached = cache.get(name, args)
    if cached is not None:
        return cached

    # Execute the tool
    result = _execute_tool(tools, name, args)

    # Cache the result for idempotent tools
    if name in CACHABLE_TOOLS:
        cache.set(name, args, result)
    elif name in INVALIDATING_TOOLS:
        # Invalidate affected cache entries
        cache.invalidate_on_mutation(name, args)

    return result


def _extract_structured_output(
    model: ChatOpenAI,
    answer_content: str,
    stage_id: str,
    output_schema: type[BaseModel] | None,
    conversation: list[Any],
) -> dict[str, Any]:
    """Extract structured output from the agent's final answer.

    Strategy:
    1. Try to parse JSON directly from the answer
    2. If parse fails, retry with correction prompt (NEW)
    3. If schema provided, try model.with_structured_output() on conversation
    4. Fall back to best-effort JSON extraction
    """
    import logging as _logging

    _dbg = _logging.getLogger(__name__)
    _dbg.debug(
        "[DEBUG] _extract_structured_output: stage=%s, content length=%d, schema=%s",
        stage_id,
        len(answer_content),
        output_schema.__name__ if output_schema else None,
    )

    # Strategy 1: Direct JSON parse of answer
    parse_error = None
    try:
        data = extract_json(answer_content)
        _dbg.debug("[DEBUG] _extract_structured_output: strategy 1 (extract_json) succeeded: %s", str(data)[:200])
    except ValueError as e:
        parse_error = str(e)
        data = None
        _dbg.debug("[DEBUG] _extract_structured_output: strategy 1 (extract_json) failed: %s", parse_error)

    if data and isinstance(data, dict) and data:
        # Validate against schema if provided
        if output_schema:
            is_valid, validation_error = validate_against_schema(data, output_schema, stage_id)
            if not is_valid:
                _dbg.warning("[DEBUG] _extract_structured_output: schema validation failed: %s", validation_error)
                # Continue to retry with correction
                parse_error = validation_error
                data = None
        if data:
            return data

    # Strategy 1.5: Retry with correction prompt (NEW)
    if parse_error:
        _dbg.info("[DEBUG] _extract_structured_output: attempting retry with correction for stage %s", stage_id)
        corrected_data = retry_with_correction(
            model=model,
            original_content=answer_content,
            error_message=parse_error,
            output_schema=output_schema,
            stage_id=stage_id,
        )
        if corrected_data:
            # Validate corrected data against schema
            if output_schema:
                is_valid, validation_error = validate_against_schema(corrected_data, output_schema, stage_id)
                if is_valid:
                    _dbg.info("[DEBUG] _extract_structured_output: retry with correction succeeded")
                    return corrected_data

    # Strategy 2: Structured output from conversation
    if output_schema:
        _dbg.debug(
            "[DEBUG] _extract_structured_output: strategy 2 (structured_output), schema=%s", output_schema.__name__
        )
        try:
            structured_model = model.with_structured_output(output_schema)
            # Add a system prompt to guide the final extraction
            extraction_messages = [
                SystemMessage(
                    content="Extract the stage result as a JSON object from the conversation above. Return only the JSON, nothing else."
                ),
            ] + conversation
            response = structured_model.invoke(extraction_messages)
            if hasattr(response, "model_dump"):
                _dbg.debug("[DEBUG] _extract_structured_output: strategy 2 succeeded via model_dump")
                return response.model_dump()
            _dbg.debug("[DEBUG] _extract_structured_output: strategy 2 succeeded via dict")
            return dict(response)
        except Exception as e:
            _dbg.debug("[DEBUG] _extract_structured_output: strategy 2 failed: %s", e)

    # Strategy 3: Best effort from answer text
    _dbg.debug("[DEBUG] _extract_structured_output: strategy 3 (best-effort fallback)")
    return _extract_from_text(answer_content, output_schema)


def _extract_from_text(
    text: str,
    output_schema: type[BaseModel] | None,
) -> dict[str, Any]:
    """Last-resort JSON extraction from text.

    NOTE: This is a fallback that should ideally not be reached if
    retry_with_correction is working properly. Returns raw_output
    only when all parsing strategies have been exhausted.
    """
    import logging as _logging

    _dbg = _logging.getLogger(__name__)
    try:
        data = extract_json(text)
        _dbg.debug("[_extract_from_text] Successfully extracted JSON")
    except ValueError as e:
        data = None
        _dbg.error("[_extract_from_text] All parsing strategies failed: %s", str(e)[:200])

    if data and isinstance(data, dict):
        return data

    # Final fallback - log warning that we're returning raw output
    _dbg.warning(
        "[_extract_from_text] Returning raw_output fallback - parsing completely failed. "
        "This indicates a serious issue with LLM output formatting."
    )
    return {
        "raw_output": text[:5000],
        "complete": True,
        "parse_warning": "JSON parsing failed, using raw output",
        "debug_hint": "Consider checking LLM prompt or model capabilities",
    }


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
    output_schema: type[BaseModel] | None,
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
            _dbg.debug(
                "[DEBUG] _extract_best_effort: trying AI message with tool_calls, length=%d, preview=%r",
                len(content),
                content[:120],
            )
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


def _compact_skill(skill_text: str, max_lines: int = 50) -> str:
    """Compact a SKILL.md section to preserve critical instructions within a token budget.

    Strategy:
    1. Extract and condense YAML frontmatter to key metadata
    2. Keep critical sections: Rules, Anti-Patterns, Execution Protocol
    3. Keep section headers with brief context
    4. Skip verbose examples, long tables, detailed explanations
    5. Hard limit to max_lines
    """
    if not skill_text.strip():
        return ""

    lines = skill_text.split("\n")
    result = []
    in_frontmatter = False
    frontmatter_done = False

    def is_section_header(line: str) -> bool:
        return line.startswith("## ") and not line.startswith("### ")

    def is_subsection_header(line: str) -> bool:
        return line.startswith("### ")

    def is_code_fence(line: str) -> bool:
        return line.strip().startswith("```")

    def is_table_separator(line: str) -> bool:
        return line.strip().startswith("|") and "-" in line.strip()

    i = 0
    while i < len(lines) and len(result) < max_lines:
        line = lines[i]

        # Handle YAML frontmatter
        if line.strip() == "---":
            if not frontmatter_done:
                in_frontmatter = not in_frontmatter
                frontmatter_done = in_frontmatter is False
                if frontmatter_done:
                    result.append("---")
                i += 1
                continue
            else:
                result.append(line)
                i += 1
                continue

        if in_frontmatter:
            if ":" in line and not line.startswith(" "):
                key, _, val = line.partition(":")
                key = key.strip().lower()
                if key in ("name", "version", "role", "domain", "type", "description", "stage", "id"):
                    result.append(line)
            i += 1
            continue

        # Skip empty lines at the start
        if not result and not line.strip():
            i += 1
            continue

        # Main title
        if line.startswith("# ") and not line.startswith("## "):
            result.append(line)
            i += 1
            continue

        # Section headers — always keep them
        if is_section_header(line):
            result.append(line)
            i += 1
            continue

        # Subsection headers — keep if we haven't hit the limit
        if is_subsection_header(line):
            if len(result) < max_lines - 3:
                result.append(line)
            i += 1
            continue

        # Code blocks — skip verbose examples, keep short ones
        if is_code_fence(line):
            code_lines = [line]
            i += 1
            while i < len(lines) and not is_code_fence(lines[i]):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                code_lines.append(lines[i])  # closing fence
                i += 1
            # Keep code blocks only if short (<=8 lines) and we have room
            if len(code_lines) <= 8 and len(result) + len(code_lines) < max_lines - 5:
                result.extend(code_lines)
            continue

        # Table separators — skip
        if is_table_separator(line):
            i += 1
            continue

        # Table headers — keep first line of tables
        if line.strip().startswith("|") and line.strip().endswith("|"):
            if len(result) < max_lines - 5:
                result.append(line)
            i += 1
            # Skip table separator line
            if i < len(lines) and is_table_separator(lines[i]):
                i += 1
            # Keep one data row as example
            if i < len(lines) and lines[i].strip().startswith("|") and len(result) < max_lines - 3:
                result.append(lines[i])
                i += 1
            # Skip remaining table rows
            while i < len(lines) and lines[i].strip().startswith("|"):
                i += 1
            continue

        # Bullet points — keep if in a high-priority section
        if line.strip().startswith("- ") or line.strip().startswith("* "):
            if len(result) < max_lines - 2:
                result.append(line)
            i += 1
            continue

        # Numbered lists — keep
        stripped_check = line.strip()
        if stripped_check and stripped_check[0].isdigit() and len(stripped_check) > 1 and stripped_check[1] == ".":
            if len(result) < max_lines - 2:
                result.append(line)
            i += 1
            continue

        # Regular text — keep if brief and meaningful
        stripped = line.strip()
        if stripped and len(stripped) < 120:
            if len(result) < max_lines - 2:
                result.append(line)
        i += 1
        continue

    compacted = "\n".join(result[:max_lines])
    if len(lines) > max_lines:
        original_lines = len(lines)
        compacted += (
            f"\n\n[Skill compacted from {original_lines} to {max_lines} lines. Full skill available at source.]"
        )

    return compacted


def _build_distilled_context(distilled: DistilledState, stage_id: str) -> str:
    """Build a prompt section from distilled agent state.

    This is injected into the new agent's context as a HumanMessage,
    giving it full awareness of what the predecessor accomplished.
    """
    parts = [
        f"[LIFECYCLE HANDOFF from agent {distilled.predecessor_agent_id}]",
        f"Stage: {stage_id}",
        f"Tokens consumed by predecessor: {distilled.total_tokens_consumed}",
    ]

    if distilled.work_completed:
        parts.append("Work completed by predecessor:")
        for item in distilled.work_completed:
            parts.append(f"  [DONE] {item}")

    if distilled.files_modified:
        parts.append("Files touched by predecessor:")
        for fp in distilled.files_modified:
            parts.append(f"  {fp}")

    if distilled.errors_encountered:
        parts.append("Errors encountered (predecessor worked around these):")
        for err in distilled.errors_encountered:
            parts.append(f"  [ERROR] {err}")

    if distilled.key_findings:
        parts.append("Key findings from predecessor:")
        for finding in distilled.key_findings:
            parts.append(f"  [FINDING] {finding}")

    if distilled.remaining_work:
        parts.append("Remaining work (carry over):")
        for item in distilled.remaining_work:
            parts.append(f"  [TODO] {item}")

    parts.append("")
    parts.append("Continue the work from where the predecessor left off. Do NOT re-do work that is marked [DONE].")

    return "\n".join(parts)


def _inject_compact_skill(prompt: str, max_skill_lines: int = 50) -> str:
    """Replace the ## SKILL section in a prompt with a compacted version.

    Instead of stripping the SKILL section entirely (which loses critical
    execution guidance), this compacts it to preserve Rules, Anti-Patterns,
    Execution Protocol, and key metadata within a token budget.
    """
    import re as _re

    skill_match = _re.search(r"(## SKILL\s*\n)((?:.*\n)*?)(?=\n\n##|\Z)", prompt, _re.DOTALL)
    if not skill_match:
        return prompt

    skill_text = skill_match.group(2).strip()
    # Strip trailing sections that leaked in (## PROCEDURE, ## DECISIONS, etc.)
    # These are prompt-level sections, not part of the skill content.
    LEAKED_SECTIONS = (
        "PROCEDURE",
        "WORK ITEM",
        "DECISIONS",
        "IDEATION",
        "PROJECT ROOT",
        "COMPLEXITY",
        "WORK TYPE",
        "UI PROJECT",
        "ARCHITECTURE CONTEXT",
        "CONFIRMED LESSONS",
        "PRIOR STAGE HANDOFFS",
    )
    leaked_content = ""
    for section in LEAKED_SECTIONS:
        boundary = f"\n## {section}"
        idx = skill_text.find(boundary)
        if idx != -1:
            leaked_content = skill_text[idx:]
            skill_text = skill_text[:idx].rstrip()
            break

    compacted = _compact_skill(skill_text, max_skill_lines)
    replacement = f"## SKILL\n{compacted}" + leaked_content

    return prompt[: skill_match.start()] + replacement + prompt[skill_match.end() :]


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
    tool_calls = sum(1 for m in messages if isinstance(m, ToolMessage))

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
        "Traceback",
        "Error:",
        "Exception",
        "FAILED",
        "failed",
        "STATUS_ACCESS_VIOLATION",
        "ERR_",
        "ECONNREFUSED",
        "SyntaxError",
        "TypeError",
        "ReferenceError",
        "Exit code",
        "exit 1",
        "npm ERR",
        "E2E test",
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
        text,
        re.IGNORECASE,
    )
    if test_match:
        # Extract all test summary lines
        summary_lines = [
            l.strip() for l in lines if re.search(r"\d+\s*(failed|passed|skipped|pending|error)", l, re.IGNORECASE)
        ]
        if summary_lines:
            return "[ERROR_SUMMARY — test output truncated]\n" + "\n".join(summary_lines[:5])

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
        return f"[ERROR_SUMMARY — traceback truncated from {len(traceback_lines)} lines]\n" + "\n".join(
            traceback_lines[-max_lines:]
        )

    # Strategy 4: Generic — last N non-empty lines
    non_empty = [l for l in lines if l.strip()]
    return f"[ERROR_SUMMARY — output truncated from {len(lines)} lines]\n" + "\n".join(non_empty[-max_lines:])


def _extract_tool_target(tool_name: str, tool_args: dict) -> str:
    """Extract a short target identifier from tool args for HUD display."""
    if tool_name == "bash":
        for key in ("command", "__arg1", "cmd"):
            if key in tool_args:
                cmd = str(tool_args[key]).strip()
                return cmd[:60] if len(cmd) > 60 else cmd
        return ""
    elif tool_name in ("read", "glob", "grep"):
        for key in ("filePath", "path", "pattern", "file_path"):
            if key in tool_args:
                val = str(tool_args[key])
                # Extract basename for file paths
                if "/" in val or "\\" in val:
                    return val.split("/")[-1].split("\\")[-1]
                return val[:40]
        return ""
    else:
        for key in ("filePath", "path", "pattern", "file_path", "command"):
            if key in tool_args:
                val = str(tool_args[key])
                if "/" in val or "\\" in val:
                    return val.split("/")[-1].split("\\")[-1]
                return val[:40]
        return ""


def _report_token_usage(stage_id: str, response: Any) -> None:
    """Extract token usage from LLM response and report to HUD normalizer and global tracker."""
    try:
        metadata = getattr(response, "response_metadata", None) or {}
        usage = metadata.get("usage", {})
        if not usage:
            usage = metadata.get("token_usage", {})
        if not usage:
            llm_output = metadata.get("llm_output", {})
            usage = llm_output.get("token_usage", {})
        if not usage:
            return
        inp = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
        out = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
        cached_details = usage.get("prompt_tokens_details", {})
        cached = cached_details.get("cached_tokens", 0)

        # Always record to global token tracker (mode-agnostic)
        from eng_loop.tools.timing import token_tracker

        token_tracker.record(stage_id, inp, out, cached)

        # Also report to HUD normalizer if active
        if not ui.is_hud_active():
            return
        normalizer = ui._normalizer
        if not normalizer and ui._hud:
            normalizer = getattr(ui._hud, "normalizer", None)
        if normalizer:
            normalizer.tokens_consumed(stage_id, inp, out, cached)
    except Exception:
        pass


def _collect_user_input(
    tool_args: dict,
    stage_id: str,
) -> dict[str, Any]:
    """Collect user input via the interaction handler.

    Called when the agent invokes ask_user. Pauses execution,
    presents questions to the user, and returns their answers.
    """
    from eng_loop.tools.interaction_handler import get_interaction_handler

    questions = tool_args.get("questions", [])
    context = tool_args.get("context", "")

    handler = get_interaction_handler()

    if not handler.is_available():
        return {
            "status": "non_interactive",
            "message": (
                "Non-interactive environment — cannot collect user input. "
                "Proceed with the information available or make a reasonable assumption "
                "and document it."
            ),
            "answers": [],
        }

    answers = handler.collect_questions(questions, context, stage_id)

    if not answers and not handler.is_available():
        return {
            "status": "cancelled",
            "message": "User cancelled the input request. Proceed with available information.",
            "answers": [],
        }

    # Build structured response: map questions to answers
    paired = []
    for i, q in enumerate(questions):
        ans = answers[i] if i < len(answers) else ""
        paired.append(
            {
                "question": q,
                "answer": ans if ans else "[skipped]",
            }
        )

    return {
        "status": "success",
        "message": "User provided the following answers:",
        "answers": answers,
        "paired": paired,
    }


def _check_context_budget(
    budget_manager: Any,
    stage_id: str,
    messages: list[Any],
    model: ChatOpenAI,
) -> dict[str, Any]:
    """Pre-call context budget check.

    Returns dict with:
      - allowed: bool
      - messages: list (possibly compacted)
      - reason: str (if not allowed)
    """
    from eng_loop.tools.context_budget import CompactionMode, ContextPressure
    from eng_loop.tools.token_counter import TokenCounter

    model_name = getattr(model, "model_name", getattr(model, "model", "unknown"))
    token_counter = TokenCounter(model_name)

    estimated_input = token_counter.estimate_messages_input(messages)
    estimated_output = getattr(model, "max_tokens", 4096) or 4096

    result = budget_manager.check_before_call(stage_id, estimated_input, estimated_output)

    if not result.allowed:
        # Try auto-compaction
        if budget_manager._compaction_mode == CompactionMode.AUTO:
            compacted, record = budget_manager.compact_messages(stage_id, messages, token_counter)
            if record:
                _dbg = __import__("logging").getLogger(__name__)
                _dbg.warning(
                    "[DEBUG] agent_runner: stage=%s COMPACTED %d→%d tokens (saved %d)",
                    stage_id,
                    record.tokens_before,
                    record.tokens_after,
                    record.tokens_saved,
                )
            # Re-check after compaction
            new_estimate = token_counter.estimate_messages_input(compacted)
            result = budget_manager.check_before_call(stage_id, new_estimate, estimated_output)
            if not result.allowed:
                return {
                    "allowed": False,
                    "messages": messages,
                    "reason": result.reason,
                }
            return {
                "allowed": True,
                "messages": compacted,
                "reason": "",
            }
        return {
            "allowed": False,
            "messages": messages,
            "reason": result.reason,
        }

    # Check if compaction is needed proactively
    # NOTE: compact_messages now returns messages unchanged (lifecycle manager handles overflow).
    # This block is kept for API compatibility but is a no-op.
    if result.pressure == ContextPressure.PRESSURE:
        compacted, record = budget_manager.compact_messages(stage_id, messages, token_counter)
        if record:
            _dbg = __import__("logging").getLogger(__name__)
            _dbg.warning(
                "[DEBUG] agent_runner: stage=%s PRESSURE — COMPACTED %d→%d tokens",
                stage_id,
                record.tokens_before,
                record.tokens_after,
            )
        # Bug fix: use is not None check instead of truthiness
        # (empty list [] is falsy in Python, which would incorrectly fall back to original messages)
        return {
            "allowed": True,
            "messages": compacted if compacted is not None else messages,
            "reason": "",
        }

    return {
        "allowed": True,
        "messages": messages,
        "reason": "",
    }


def _record_context_budget(
    stage_id: str,
    response: Any,
    messages: list[Any],
    budget_manager: Any | None,
) -> None:
    """Record token usage in the context budget manager after an LLM call."""
    if not budget_manager:
        return

    from eng_loop.tools.context_budget import CallBreakdown
    from eng_loop.tools.token_counter import TokenCounter

    try:
        metadata = getattr(response, "response_metadata", None) or {}
        usage = metadata.get("usage", {})
        if not usage:
            usage = metadata.get("token_usage", {})
        if not usage:
            llm_output = metadata.get("llm_output", {})
            usage = llm_output.get("token_usage", {})

        if not usage:
            return

        inp = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
        out = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
        cached_details = usage.get("prompt_tokens_details", {})
        cached = cached_details.get("cached_tokens", 0)

        # Build breakdown from messages
        model_name = getattr(response, "response_metadata", {}).get("model_name", "unknown")
        token_counter = TokenCounter(model_name)
        breakdown = token_counter.count_messages(messages)

        call_breakdown = CallBreakdown(
            system_prompt=breakdown.system_prompt,
            stage_instructions=breakdown.stage_instructions,
            conversation=breakdown.conversation,
            tool_results=breakdown.tool_results,
            previous_outputs=breakdown.ai_output,
            other=breakdown.other,
            input_total=inp,
            output_tokens=out,
            cached_tokens=cached,
        )
        budget_manager.record_call(stage_id, call_breakdown)

        # Also emit to HUD normalizer if active
        if ui.is_hud_active() and ui._normalizer:
            ui._normalizer.context_budget_record(
                stage_id,
                inp,
                out,
                cached,
                breakdown={
                    "system_prompt": breakdown.system_prompt,
                    "stage_instructions": breakdown.stage_instructions,
                    "conversation": breakdown.conversation,
                    "tool_results": breakdown.tool_results,
                    "previous_outputs": breakdown.ai_output,
                    "other": breakdown.other,
                },
            )
    except Exception:
        pass


__all__ = ["AgentResult", "run_agent"]
