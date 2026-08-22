from __future__ import annotations

import datetime
import json
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from rich import box
from rich.panel import Panel
from rich.text import Text

_MAX_TRACE_LINES = 200
_TRUNCATE_AT = 4000
_TRACE_LOCK = threading.Lock()


class TraceLogger:
    """Assertive trace logger that writes JSONL to file and optionally renders a live HUD panel.

    Independent of Python logging — not affected by HUD/TUI NullHandler suppression.
    Thread-safe. Initialized once at CLI startup.
    """

    def __init__(self) -> None:
        self.enabled = False
        self.level: int = 2
        self.file_path: str | None = None
        self.console_panel: bool = True
        self.include_prompts: bool = True
        self.include_responses: bool = True
        self.include_tool_results: bool = True
        self.max_file_size_mb: int = 50
        self._file: Any = None
        self._lock = threading.RLock()
        self._console_lines: deque[str] = deque(maxlen=12)
        self._wall_start = time.time()
        self._event_count = 0

    def init(
        self,
        artifact_root: str | Path,
        level: str = "full",
        console_panel: bool = True,
        include_prompts: bool = True,
        include_responses: bool = True,
        include_tool_results: bool = True,
        max_file_size_mb: int = 50,
    ) -> None:
        level_map = {"debug": 0, "minimal": 1, "essential": 2, "full": 3}
        self.level = level_map.get(level.lower(), 2)
        self.enabled = self.level >= 1
        self.console_panel = console_panel
        self.include_prompts = include_prompts
        self.include_responses = include_responses
        self.include_tool_results = include_tool_results
        self.max_file_size_mb = max_file_size_mb

        trace_dir = Path(artifact_root)
        trace_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        trace_file = trace_dir / f"trace-{ts}.jsonl"
        self.file_path = str(trace_file)

        try:
            self._file = open(trace_file, "a", encoding="utf-8")  # noqa: SIM115 — intentionally kept open for duration of run
        except OSError:
            self._file = None

    def _elapsed(self) -> float:
        return round(time.time() - self._wall_start, 3)

    def _ts(self) -> str:
        return datetime.datetime.now().strftime("%H:%M:%S")

    def _write_file(self, event: dict[str, Any]) -> None:
        if not self._file:
            return
        try:
            self._file.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
            self._file.flush()
            file_size = self._file.tell()
            if file_size > self.max_file_size_mb * 1024 * 1024:
                self._file.close()
                self._file = None
        except OSError:
            if self._file:
                self._file.close()
                self._file = None

    def _truncate(self, s: str, limit: int = _TRUNCATE_AT) -> str:
        s = str(s)
        if len(s) > limit:
            return s[:limit] + f"... ({len(s) - limit} more chars)"
        return s

    def _emit(self, category: str, _level: int, message: str, **kwargs: Any) -> None:
        if not self.enabled or _level < self.level:
            return
        with self._lock:
            self._event_count += 1
            event = {
                "ts": self._ts(),
                "elapsed": self._elapsed(),
                "seq": self._event_count,
                "category": category,
                "level": _level,
                "message": message,
            }
            event.update(kwargs)
            self._write_file(event)
            console_line = self._format_console(category, message, kwargs)
            self._console_lines.append(console_line)

    @staticmethod
    def _format_console(category: str, message: str, kwargs: dict[str, Any]) -> str:
        cat_icons = {
            "STAGE": "S",
            "LLM": "L",
            "TOOL": "T",
            "ROUTE": "R",
            "STALL": "!",
            "ERROR": "E",
            "SYSTEM": "sys",
            "CONTEXT": "C",
            "RECOVERY": "rec",
        }
        icon = cat_icons.get(category, ".")
        return f"[{icon}] {message}"

    # ─── Public API ─────────────────────────────────────────────

    def stage_enter(self, stage_id: str, iteration: int = 0) -> None:
        self._emit("STAGE", 2, f"ENTER {stage_id} (iter={iteration})")

    def stage_exit(
        self,
        stage_id: str,
        status: str,
        duration: float = 0.0,
        tool_calls: int = 0,
        summary: str = "",
    ) -> None:
        self._emit(
            "STAGE",
            2,
            f"EXIT {stage_id} status={status} dur={duration:.1f}s tools={tool_calls}",
            summary=self._truncate(summary, 500),
        )

    def stage_skip(self, stage_id: str, reason: str = "") -> None:
        self._emit("STAGE", 2, f"SKIP {stage_id}: {reason}")

    def stage_fail(self, stage_id: str, error: str) -> None:
        self._emit("ERROR", 2, f"FAIL {stage_id}: {self._truncate(error, 1000)}", error=error, stage=stage_id)

    def llm_invoke(
        self,
        stage_id: str,
        prompt: str,
        tools: list[str],
        messages_count: int = 0,
        system_prompt: str = "",
    ) -> None:
        prompt_trunc = self._truncate(prompt, 6000) if self.include_prompts else "[prompt hidden]"
        system_trunc = self._truncate(system_prompt, 3000) if self.include_prompts else ""
        self._emit(
            "LLM",
            2,
            f"INVOKE stage={stage_id} msgs={messages_count} tools={len(tools)}",
            tools=tools,
            prompt=prompt_trunc,
            system_prompt=system_trunc,
        )

    def llm_iteration(
        self,
        stage_id: str,
        iteration: int,
        max_iterations: int,
        messages_count: int,
    ) -> None:
        self._emit(
            "LLM",
            2,
            f"ITER {iteration}/{max_iterations} stage={stage_id} msgs={messages_count}",
        )

    def llm_response(
        self,
        stage_id: str,
        iteration: int,
        tool_calls: list[dict[str, Any]] | None = None,
        content: str = "",
        tokens_in: int = 0,
        tokens_out: int = 0,
        elapsed: float = 0.0,
    ) -> None:
        content_trunc = self._truncate(content, 6000) if self.include_responses else "[response hidden]"
        self._emit(
            "LLM",
            2,
            f"RESP stage={stage_id} iter={iteration} tool_calls={len(tool_calls) if tool_calls else 0} "
            f"tok_in={tokens_in} tok_out={tokens_out} dur={elapsed:.1f}s",
            tool_calls=tool_calls or [],
            content=content_trunc,
        )

    def llm_error(self, stage_id: str, iteration: int, error: str) -> None:
        self._emit(
            "ERROR",
            2,
            f"LLM_ERROR stage={stage_id} iter={iteration}: {self._truncate(error, 2000)}",
            error=error,
        )

    def tool_call(
        self,
        stage_id: str,
        tool_name: str,
        args: dict[str, Any] | None = None,
        result_size: int = 0,
        elapsed: float = 0.0,
        cached: bool = False,
    ) -> None:
        args_display = self._truncate(json.dumps(args, default=str, ensure_ascii=False), 3000) if args else "{}"
        suffix = " [CACHE HIT]" if cached else ""
        self._emit(
            "TOOL",
            2,
            f"{tool_name} stage={stage_id} size={result_size} dur={elapsed:.2f}s{suffix}",
            tool=tool_name,
            args=args_display,
            result_size=result_size,
            cached=cached,
        )

    def tool_error(self, stage_id: str, tool_name: str, error: str) -> None:
        self._emit(
            "ERROR",
            2,
            f"TOOL_ERROR {tool_name} stage={stage_id}: {self._truncate(error, 2000)}",
            tool=tool_name,
            error=error,
        )

    def tool_intercepted(
        self,
        stage_id: str,
        tool_name: str,
        args: dict[str, Any] | None = None,
        reason: str = "",
    ) -> None:
        self._emit(
            "TOOL",
            2,
            f"INTERCEPT {tool_name} stage={stage_id}: {reason}",
            tool=tool_name,
            args=self._truncate(json.dumps(args, default=str, ensure_ascii=False), 1000) if args else None,
            reason=reason,
        )

    def route_decision(
        self,
        function: str,
        decision: str,
        reason: str = "",
        state_snippet: dict[str, Any] | None = None,
    ) -> None:
        self._emit(
            "ROUTE",
            2,
            f"{function} -> {decision}: {reason}",
            function=function,
            decision=decision,
            reason=reason,
            state=state_snippet,
        )

    def stall_detected(
        self,
        stage_id: str,
        stall_type: str,
        count: int,
        action: str,
    ) -> None:
        self._emit(
            "STALL",
            2,
            f"STALL {stage_id} type={stall_type} count={count} action={action}",
            stall_type=stall_type,
            count=count,
            action=action,
        )

    def context_budget(
        self,
        stage_id: str,
        tokens_used: int,
        budget_remaining: float,
        status: str = "",
    ) -> None:
        self._emit(
            "CONTEXT",
            2,
            f"BUDGET {stage_id} used={tokens_used} remaining={budget_remaining:.1%} status={status}",
        )

    def system_event(self, message: str, **kwargs: Any) -> None:
        self._emit("SYSTEM", 2, message, **kwargs)

    def recovery_event(self, message: str, **kwargs: Any) -> None:
        self._emit("RECOVERY", 2, message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._emit("SYSTEM", 0, f"[debug] {message}", **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._emit("SYSTEM", 1, message, **kwargs)

    def warn(self, message: str, **kwargs: Any) -> None:
        self._emit("SYSTEM", 2, f"[WARN] {message}", **kwargs)

    # ─── HUD Panel ────────────────────────────────────────────────

    def render_panel(self, max_lines: int = 12) -> Panel:
        with self._lock:
            lines = list(self._console_lines)

        styled_lines = []
        for line in lines:
            parts = line.split("]", 1)
            if len(parts) == 2:
                icon = parts[0] + "]"
                msg = parts[1]
                color_map = {
                    "[S]": "cyan",
                    "[L]": "blue",
                    "[T]": "green",
                    "[R]": "magenta",
                    "[!]": "yellow",
                    "[E]": "red",
                    "[sys]": "dim",
                    "[C]": "white",
                    "[rec]": "bright_yellow",
                }
                color = color_map.get(icon, "white")
                styled_lines.append(f"[{color}]{icon}[/] {msg}")
            else:
                styled_lines.append(line)

        if not styled_lines:
            styled_lines.append("[dim]Waiting for trace events...[/dim]")

        text = "\n".join(styled_lines)
        return Panel(
            Text.from_markup(text),
            title=f"[grey15] TRACE LOG ({self._event_count} events)[/grey15]",
            title_align="left",
            box=box.SQUARE,
            border_style="grey50",
        )

    def get_trace_file(self) -> str | None:
        return self.file_path

    def render_summary_panel(self) -> Panel:
        return Panel(
            f"[dim]Trace file:[/dim] [cyan]{self.file_path or 'N/A'}[/cyan]\n"
            f"[dim]Total events:[/dim] [bold]{self._event_count}[/bold]",
            title="[grey15] TRACE SUMMARY[/grey15]",
            title_align="left",
            box=box.SQUARE,
            border_style="grey50",
        )

    def stop(self) -> None:
        if self._file:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None


trace = TraceLogger()
