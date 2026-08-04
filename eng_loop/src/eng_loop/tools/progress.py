from __future__ import annotations

import sys
import time
from functools import wraps
from typing import Any, Callable

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    elif hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def log_stage_enter(stage_id: str, iteration: int = 0) -> None:
    _print(f"[iter {iteration}] >> {stage_id}", "cyan")


def log_model_invoke(stage_id: str) -> None:
    _print(f"  model -> {stage_id} ...", "yellow")


def log_model_done(stage_id: str, elapsed: float) -> None:
    _print(f"  model <- {stage_id} ({elapsed:.1f}s)", "green")


def log_stage_done(stage_id: str, result: str = "") -> None:
    _print(f"  done   {stage_id}", "green")
    if result:
        truncated = result[:120]
        if len(result) > 120:
            truncated += "..."
        _print(f"         {truncated}", "white")


def log_stage_skip(stage_id: str) -> None:
    _print(f"  skip   {stage_id} (already done)", "dim")


def log_stage_fail(stage_id: str, reason: str) -> None:
    _print(f"  fail   {stage_id}: {reason}", "red")


def log_stage_retry(stage_id: str, attempt: int) -> None:
    _print(f"  retry  {stage_id} (attempt {attempt})", "yellow")


def log_artifact(stage_id: str, path: str) -> None:
    _print(f"  file   {path}", "dim")


def log_complexity(complexity: str, ui_project: bool) -> None:
    _print(f"  complexity={complexity}  ui_project={ui_project}", "cyan")


def log_blocked(reason: str) -> None:
    _print(f"  blocked: {reason}", "red")


def log_decision(text: str) -> None:
    _print(f"  decision: {text}", "magenta")


def log_iteration(iteration: int, current_stage: str) -> None:
    _print(f"\n{'-'*50}", "dim")
    _print(f"[iter {iteration}] stage={current_stage}", "cyan")


def trace_node(stage_id: str):
    """Decorator that logs stage entry, model call timing, and completion."""
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(state: dict[str, Any], *args, **kwargs):
            iteration = state.get("iteration", 0)
            log_stage_enter(stage_id, iteration)
            t0 = time.monotonic()
            try:
                result = fn(state, *args, **kwargs)
                elapsed = time.monotonic() - t0
                _print(f"  <- {stage_id} ({elapsed:.1f}s)", "green")
                return result
            except Exception as e:
                elapsed = time.monotonic() - t0
                log_stage_fail(stage_id, f"{e} ({elapsed:.1f}s)")
                raise
        return wrapper
    return decorator


def _print(text: str, color: str = "white") -> None:
    codes = {
        "cyan": "\033[36m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "red": "\033[31m",
        "magenta": "\033[35m",
        "dim": "\033[2m",
        "white": "\033[0m",
    }
    c = codes.get(color, "")
    reset = "\033[0m"
    sys.stdout.write(f"{c}{text}{reset}\n")
    sys.stdout.flush()
