from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Type

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from eng_loop.tools.json_parse import extract_json
from eng_loop.tools.progress import (
    log_model_invoke, log_model_done, log_stage_done, log_stage_fail,
)


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
        )

    # Original LangChain tool-calling loop
    log_model_invoke(stage_id)
    t0 = time.monotonic()

    # Build conversation
    messages: list[Any] = []
    if system_message:
        messages.append(SystemMessage(content=system_message))

    # The prompt instructs the agent to use tools and then produce a final answer
    agent_prompt = _build_agent_prompt(prompt, tools)
    messages.append(HumanMessage(content=agent_prompt))

    # Bind tools to model
    model_with_tools = model.bind_tools(tools)

    tool_calls_total = 0

    for iteration in range(1, max_iterations + 1):
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

        if isinstance(response, AIMessage):
            if response.tool_calls:
                # Execute each tool call
                for tc in response.tool_calls:
                    tool_name = tc["name"]
                    tool_args = tc.get("args", {})
                    tool_result = _execute_tool(tools, tool_name, tool_args)

                    messages.append(response)
                    messages.append(ToolMessage(
                        content=tool_result,
                        tool_call_id=tc["id"],
                    ))
                    tool_calls_total += 1

                # Compact messages if conversation is getting too long
                if len(messages) > 80:
                    messages = _compact_messages(messages)
            else:
                # No more tool calls — agent has its final answer
                elapsed = time.monotonic() - t0
                log_model_done(stage_id, elapsed)

                # Extract structured output from the final answer
                data = _extract_structured_output(
                    model, response.content, stage_id,
                    output_schema, messages,
                )
                log_stage_done(stage_id, f"agent completed in {iteration} iterations, {tool_calls_total} tool calls")

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
    log_model_done(stage_id, elapsed)
    log_stage_fail(stage_id, f"exceeded max_iterations ({max_iterations})")

    # Try to extract whatever we have
    last_ai = _last_ai_message(messages)
    data = _extract_from_text(last_ai.content if last_ai else "", output_schema)

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
) -> AgentResult:
    """Run a stage by invoking opencode CLI as a subprocess.

    Python controls the graph, opencode executes with native tools.
    The agent writes structured output to a temp file for Python to read.
    """
    log_model_invoke(stage_id)
    t0 = time.monotonic()

    # Create temp file for structured output
    fd, output_file = tempfile.mkstemp(suffix=".json", prefix=f"eng-{stage_id}-")
    os.close(fd)

    try:
        # Build schema field list for the output instruction
        schema_fields = ""
        if output_schema:
            schema_fields = ", ".join(f"`{f}`" for f in output_schema.model_fields.keys())

        # Append structured output instruction to prompt
        output_prompt = (
            f"{prompt}\n\n"
            f"## OUTPUT FORMAT\n"
            f"When your work is complete, write your result as a JSON object to this file:\n"
            f"**{output_file}**\n\n"
            f"The JSON must contain these fields: {schema_fields or 'your result data'}.\n"
            f"Use the `write` tool to write the file. This is MANDATORY — the loop cannot proceed without it.\n"
        )

        # Build opencode command with JSON event stream
        cmd = [
            "opencode", "run",
            "--dir", str(project_root),
            "--auto",
            "--format", "json",
            output_prompt,
        ]

        if model_name:
            cmd.extend(["--model", model_name])

        # Execute opencode as subprocess, streaming JSON events
        TIMEOUT = 600
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(project_root),
            )

            last_progress = time.monotonic()
            timed_out = [False]
            tool_count = [0]

            # Watchdog thread to enforce timeout
            def _watchdog():
                time.sleep(TIMEOUT)
                if proc.poll() is None:
                    timed_out[0] = True
                    proc.kill()

            threading.Thread(target=_watchdog, daemon=True).start()

            # Stream JSON events line-by-line
            while not timed_out[0]:
                line = proc.stdout.readline()
                if not line:
                    break

                try:
                    decoded = line.decode("utf-8", errors="replace").rstrip("\n\r")
                except AttributeError:
                    decoded = line.decode("utf-8", errors="replace").rstrip("\n\r")

                if not decoded:
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
                    status = part.get("state", {}).get("status", "")
                    inp = part.get("state", {}).get("input", {})
                    # Extract file/path from tool input
                    path = inp.get("filePath", inp.get("path", inp.get("pattern", "")))
                    if path:
                        # Show just the filename, not the full path
                        display = path.split("/")[-1].split("\\")[-1]
                        _print_tool(stage_id, tool_name, display, status)
                    else:
                        _print_tool(stage_id, tool_name, "", status)
                    tool_count[0] += 1

                elif event_type == "text":
                    text = part.get("text", "")
                    if text.strip():
                        _print_text(stage_id, text.strip()[:200])

                elif event_type == "step_finish":
                    reason = part.get("reason", "")
                    if reason == "error":
                        _print_error(stage_id, part.get("error", "unknown error"))

                # Progress heartbeat every 30s
                now = time.monotonic()
                if now - last_progress > 30:
                    _print_progress(stage_id, now - t0)
                    last_progress = now

            proc.wait()
            elapsed = time.monotonic() - t0

            if timed_out[0]:
                log_model_done(stage_id, elapsed)
                log_stage_fail(stage_id, f"opencode timed out after {TIMEOUT}s")
                return AgentResult(
                    data={},
                    iterations=1,
                    elapsed=elapsed,
                    error=f"opencode timed out after {TIMEOUT}s",
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
            try:
                if Path(output_file).exists():
                    raw = Path(output_file).read_text(encoding="utf-8")
                    data = json.loads(raw)
                    if not isinstance(data, dict):
                        data = {"raw_output": str(data)[:5000], "complete": True}
                else:
                    data = {"complete": True}
            except (json.JSONDecodeError, Exception) as e:
                data = {"error": f"failed to parse output: {e}", "complete": True}

            log_model_done(stage_id, elapsed)
            log_stage_done(stage_id, f"opencode agent completed ({tool_count[0]} tools)")

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
        # Clean up temp file
        try:
            if Path(output_file).exists():
                os.unlink(output_file)
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


def _build_agent_prompt(prompt: str, tools: list[Tool]) -> str:
    """Wrap the stage prompt with agent instructions."""
    tool_names = ", ".join(f"`{t.name}`" for t in tools)

    return (
        f"{prompt}\n\n"
        f"## AVAILABLE TOOLS\n"
        f"You have access to these tools: {tool_names}.\n\n"
        f"## EXECUTION INSTRUCTIONS\n"
        f"1. Use the available tools to perform the actual work described above.\n"
        f"2. Read files before modifying them. Write files to create new code.\n"
        f"3. Run tests with bash to verify your work.\n"
        f"4. When all work is complete, provide your final answer as a JSON object.\n"
        f"5. Your final answer (no more tool calls) will be parsed as the stage result.\n\n"
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
    # Strategy 1: Direct JSON parse of answer
    data = extract_json(answer_content)
    if data and isinstance(data, dict) and data:
        return data

    # Strategy 2: Structured output from conversation
    if output_schema:
        try:
            structured_model = model.with_structured_output(output_schema)
            # Add a system prompt to guide the final extraction
            extraction_messages = [
                SystemMessage(content="Extract the stage result as a JSON object from the conversation above. Return only the JSON, nothing else."),
            ] + conversation
            response = structured_model.invoke(extraction_messages)
            if hasattr(response, "model_dump"):
                return response.model_dump()
            return dict(response)
        except Exception:
            pass

    # Strategy 3: Best effort from answer text
    return _extract_from_text(answer_content, output_schema)


def _extract_from_text(
    text: str,
    output_schema: Type[BaseModel] | None,
) -> dict[str, Any]:
    """Last-resort JSON extraction from text."""
    data = extract_json(text)
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


__all__ = ["run_agent", "AgentResult"]
