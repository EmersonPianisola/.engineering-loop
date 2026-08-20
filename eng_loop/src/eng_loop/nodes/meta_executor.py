from __future__ import annotations

import logging
import time
from typing import Any

from langgraph.types import Command

from eng_loop.model import create_model_from_config
from eng_loop.schemas import DynamicRuntime, ValidationRule
from eng_loop.tools.agent_runner import AgentResult, run_agent
from eng_loop.tools.dynamic_validation import evaluate_validation_rules
from eng_loop.tools.node_helpers import build_node_prompt
from eng_loop.tools.policy_resolver import SAFE_TOOL_POOL, get_tools_by_names
from eng_loop.tools.progress import log_stage_done, log_stage_fail, ui
from eng_loop.tools.timing import format_time, token_tracker

logger = logging.getLogger(__name__)


def meta_node_executor_node(state: dict[str, Any]) -> Command[str]:
    """Sequential executor for dynamic blueprint steps.

    Consumes the immutable dynamic_plan and advances through steps
    using a cursor in dynamic_runtime. Maintains strict attempt
    counting and typed validation per step.
    """
    plan = state.get("dynamic_plan")
    if not plan or plan.get("trigger") == "none":
        return Command(goto="init")

    runtime = _load_runtime(state)
    steps = plan.get("steps", [])

    try:
        runtime.validate_invariants(len(steps))
    except ValueError as e:
        log_stage_fail("meta.executor", f"Runtime invariant violation: {e}")
        return Command(
            update={
                "status": "blocked",
                "blocking_condition": f"Dynamic runtime error: {e}",
            },
            goto="__end__",
        )

    if runtime.cursor >= len(steps):
        runtime.status = "completed"
        return Command(
            update={"dynamic_runtime": runtime.model_dump()},
            goto="init",
        )

    current_step = steps[runtime.cursor]
    step_id = current_step["step_id"]
    max_attempts = current_step.get("max_attempts", 3)

    current_attempts = runtime.attempts.get(step_id, 0) + 1

    if current_attempts > max_attempts:
        runtime.failed.append(step_id)
        runtime.status = "blocked"
        log_stage_fail("meta.executor", f"Step '{step_id}' exceeded max_attempts ({max_attempts})")
        return Command(
            update={
                "dynamic_runtime": runtime.model_dump(),
                "status": "blocked",
                "blocking_condition": f"Dynamic step '{step_id}' exceeded max_attempts ({max_attempts})",
            },
            goto="__end__",
        )

    runtime.attempts[step_id] = current_attempts

    allowed_tools = _resolve_step_tools(current_step, state)
    prompt = _build_step_prompt(current_step, state)

    config = state.get("config", {})
    model = create_model_from_config(config, step_id)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 25)

    # Emit step start event and console output
    step_num = runtime.cursor + 1
    total_steps = len(steps)
    _log_step_start(step_id, step_num, total_steps, current_attempts, max_attempts)

    start_time = time.monotonic()
    agent_result: AgentResult = run_agent(
        model=model,
        tools=allowed_tools,
        prompt=prompt,
        stage_id=step_id,
        max_iterations=max_agent_iterations,
        config=config,
    )
    finish_time = time.monotonic()

    is_valid, err = evaluate_validation_rules(
        agent_result.data,
        tuple(ValidationRule.model_validate(r) for r in current_step.get("validation_rules", [])),
        state.get("paths", {}).get("project_root", "."),
        state,
    )

    audit_entry = {
        "plan_id": plan.get("plan_id", ""),
        "step_id": step_id,
        "attempt": current_attempts,
        "status": "success" if is_valid else "failed",
        "started_at": start_time,
        "finished_at": finish_time,
        "error": err if not is_valid else None,
    }
    runtime.step_audit.append(audit_entry)

    if not is_valid:
        step_duration = finish_time - start_time
        if current_attempts < max_attempts:
            _log_step_fail(step_id, step_num, total_steps, current_attempts, max_attempts, step_duration, err)
            log_stage_fail("meta.executor", f"Step '{step_id}' attempt {current_attempts}/{max_attempts} failed: {err}")
            return Command(
                update={"dynamic_runtime": runtime.model_dump(), "errors": [err]},
                goto="meta-executor",
            )
        else:
            runtime.failed.append(step_id)
            runtime.status = "blocked"
            _log_step_fail(step_id, step_num, total_steps, current_attempts, max_attempts, step_duration, err)
            log_stage_fail("meta.executor", f"Step '{step_id}' exhausted {current_attempts} attempts: {err}")
            return Command(
                update={
                    "dynamic_runtime": runtime.model_dump(),
                    "status": "blocked",
                    "blocking_condition": f"Dynamic step '{step_id}' failed after {current_attempts} attempts: {err}",
                },
                goto="__end__",
            )

    step_duration = finish_time - start_time
    _log_step_complete(step_id, step_num, total_steps, current_attempts, step_duration, agent_result.tool_calls_made)
    runtime.completed.append(step_id)
    runtime.cursor += 1
    log_stage_done("meta.executor", f"Step '{step_id}' completed (attempt {current_attempts})")

    return Command(
        update={"dynamic_runtime": runtime.model_dump()},
        goto="meta-executor",
    )


def _load_runtime(state: dict[str, Any]) -> DynamicRuntime:
    """Load dynamic runtime from state, returning a validated DynamicRuntime."""
    raw = state.get("dynamic_runtime", {})
    if isinstance(raw, DynamicRuntime):
        return raw.model_copy(deep=True)
    if isinstance(raw, dict):
        return DynamicRuntime(**raw)
    return DynamicRuntime()


def _resolve_step_tools(
    step: dict[str, Any],
    state: dict[str, Any],
) -> list:
    """Resolve and sandbox tool capabilities for a dynamic step."""
    requested = step.get("required_tools", step.get("requested_capabilities", []))
    if isinstance(requested, tuple):
        requested = list(requested)

    approved = [t for t in requested if t in SAFE_TOOL_POOL]
    if not approved:
        approved = ["read", "glob"]

    return get_tools_by_names(approved, state)


def _build_step_prompt(
    step: dict[str, Any],
    state: dict[str, Any],
) -> str:
    """Build execution prompt for a dynamic step."""
    config = state.get("config", {})
    paths = state.get("paths", {})

    return build_node_prompt(
        step["step_id"],
        state,
        paths,
        config,
        role_description=step.get("role_description", "Dynamic task executor"),
        instructions=(
            f"Execute this dynamic step. Project root: {paths.get('project_root', '.')}\n\n"
            "Use your available tools to complete the task. "
            "When finished, provide your final answer as a JSON object."
        ),
    )


def _log_step_start(
    step_id: str,
    step_num: int,
    total_steps: int,
    attempt: int,
    max_attempts: int,
) -> None:
    """Log step start with visibility info."""
    # Emit event for CLI v2
    if ui._event_bus:
        from eng_loop.tools.cli_events import attempt_started

        ui._event_bus.emit(
            attempt_started(
                graph_id="",
                node_id=step_id,
                attempt=attempt,
            )
        )

    # Console output — always visible
    attempt_str = f" (attempt {attempt}/{max_attempts})" if attempt > 1 else ""
    ui.console.print(f"  [bold cyan]Step {step_num}/{total_steps}[/bold cyan] >> [bold]{step_id}[/bold]{attempt_str}")


def _log_step_complete(
    step_id: str,
    step_num: int,
    total_steps: int,
    attempt: int,
    duration: float,
    tool_calls: int,
) -> None:
    """Log step completion with visibility info."""
    # Emit event for CLI v2
    if ui._event_bus:
        from eng_loop.tools.cli_events import node_completed

        ui._event_bus.emit(
            node_completed(
                graph_id="",
                node_id=step_id,
                duration_ms=int(duration * 1000),
                tool_count=tool_calls,
            )
        )

    # Console output — always visible
    tok = token_tracker.get_stage_total(step_id)
    tok_str = f" [yellow]{token_tracker._format_tokens(tok)} tokens[/yellow]" if tok else ""
    ui.console.print(
        f"  [bold green]Step {step_num}/{total_steps}[/bold green] "
        f"done [green]{step_id}[/green] "
        f"[dim]({format_time(duration)}, {tool_calls} tools{tok_str})[/dim]"
    )


def _log_step_fail(
    step_id: str,
    step_num: int,
    total_steps: int,
    attempt: int,
    max_attempts: int,
    duration: float,
    error: str,
) -> None:
    """Log step failure with visibility info."""
    # Emit event for CLI v2
    if ui._event_bus:
        from eng_loop.tools.cli_events import node_failed

        ui._event_bus.emit(
            node_failed(
                graph_id="",
                node_id=step_id,
                error=error,
            )
        )

    # Console output — always visible
    ui.console.print(
        f"  [bold red]Step {step_num}/{total_steps}[/bold red] "
        f"fail [red]{step_id}[/red] "
        f"[dim](attempt {attempt}/{max_attempts}, {format_time(duration)})[/dim]"
    )
    if error:
        ui.console.print(f"         [dim]{error}[/dim]")
