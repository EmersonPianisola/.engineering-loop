from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

# Tools that constitute "productive" work (modify state or execute commands)
DEFAULT_PRODUCTIVE_TOOLS = {"write", "edit", "bash"}

# Args keys to ignore when computing exact-match hash (pagination, limits, etc.)
IGNORED_ARG_KEYS = {"limit", "offset", "max_lines", "start_line", "end_line"}

# Safe inspection commands — repeats are annoying but not dangerous
SAFE_INSPECTION_COMMANDS = {
    "ls",
    "ls -la",
    "ls -l",
    "ls -a",
    "dir",
    "dir /s",
    "cat",
    "head",
    "tail",
    "wc",
    "tree",
    "pwd",
    "whoami",
    "find",
    "grep",
    "git status",
    "git diff",
    "git log",
    "echo",
    "test",
    "stat",
    "file",
    "which",
    "type",
}

# Read-only tools that are safe to repeat (inspection/exploration)
SAFE_READ_TOOLS = {"read", "glob", "grep"}

# Idempotent bash commands — safe to repeat, shouldn't hard-kill the agent
SAFE_IDEMPOTENT_COMMANDS = {
    "mkdir",
    "touch",
    "chmod",
    "chown",
    "cp",
    "mv",
    "ln",
    "install",
    "tee",
}


def _is_safe_inspection(tool_name: str, tool_args: dict) -> bool:
    """Determine if a tool call is safe to repeat.

    Returns True for read/glob/grep tools, read-only bash inspections
    (ls, cat, grep, find, git status, etc.), and idempotent bash commands
    (mkdir, touch, chmod, cp, mv, etc.) that won't cause harm on retry.
    """
    if tool_name in SAFE_READ_TOOLS:
        return True

    if tool_name == "bash":
        command = ""
        for key in ("command", "__arg1", "cmd"):
            if key in tool_args:
                command = str(tool_args[key]).strip()
                break
        if command:
            tokens = command.lower().split()
            # Match safe commands by whole-token prefix — never substrings, so
            # "catfish x" does not match "cat" and "lsblk" does not match "ls".
            # Multi-token entries (e.g. "git status") match their token sequence
            # ("git status --short" is still a safe inspection).
            for safe_cmd in SAFE_INSPECTION_COMMANDS:
                safe_tokens = safe_cmd.lower().split()
                if tokens[: len(safe_tokens)] == safe_tokens:
                    return True
            if tokens and tokens[0] in SAFE_IDEMPOTENT_COMMANDS:
                return True

    return False


@dataclass
class StallReport:
    stall_type: str  # "exact_repeat" | "same_tool_repeat" | "no_progress"
    tool_name: str
    count: int
    message: str
    severity: str = "hard"  # "soft" — can be handled with steering prompt instead of abort


@dataclass
class _ToolCall:
    name: str
    args_hash: str
    args_raw: dict


class StallDetector:
    """Detects agent stalling by analyzing consecutive tool call patterns.

    Three detection modes:
    1. exact_repeat — same tool + same args (normalized) N times consecutively
    2. same_tool_repeat — same tool N times consecutively (args may vary)
    3. no_progress — N consecutive calls without any productive tool (write/edit/bash)
    """

    def __init__(
        self,
        window_size: int = 10,
        exact_threshold: int = 3,
        same_tool_threshold: int = 10,
        no_progress_threshold: int = 8,
        productive_tools: set[str] | None = None,
        enabled: bool = True,
    ):
        self.window_size = window_size
        self.exact_threshold = exact_threshold
        self.same_tool_threshold = same_tool_threshold
        self.no_progress_threshold = no_progress_threshold
        self.productive_tools = productive_tools or DEFAULT_PRODUCTIVE_TOOLS
        self.enabled = enabled
        self._calls: list[_ToolCall] = []
        self._non_productive_streak = 0

    def record(self, tool_name: str, tool_args: dict) -> None:
        """Record a tool call for stall analysis."""
        if not self.enabled:
            return

        args_hash = self._compute_hash(tool_name, tool_args)
        self._calls.append(_ToolCall(name=tool_name, args_hash=args_hash, args_raw=tool_args))

        # Track non-productive streak separately (not bounded by window)
        if tool_name in self.productive_tools:
            self._non_productive_streak = 0
        else:
            self._non_productive_streak += 1

        # Keep window bounded
        if len(self._calls) > self.window_size * 2:
            self._calls = self._calls[-self.window_size :]

    def check(self) -> StallReport | None:
        """Check current window for stall patterns. Returns StallReport if stalled, None if OK."""
        if not self.enabled or len(self._calls) < self.exact_threshold:
            return None

        window = self._calls[-self.window_size :]

        # Check 1: Exact repeat (same tool + same normalized args)
        exact = self._detect_exact_repeat(window)
        if exact:
            return exact

        # Check 2: Same tool repeat (same tool, args may vary)
        same_tool = self._detect_same_tool_repeat(window)
        if same_tool:
            return same_tool

        # Check 3: No progress (no productive tools in window)
        no_progress = self._detect_no_progress(window)
        if no_progress:
            return no_progress

        return None

    def _compute_hash(self, tool_name: str, tool_args: dict) -> str:
        """Compute a normalized hash of tool call for exact-repeat detection."""
        normalized = {k: v for k, v in tool_args.items() if k not in IGNORED_ARG_KEYS}
        raw = json.dumps({"tool": tool_name, "args": normalized}, sort_keys=True)
        return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()

    def _detect_exact_repeat(self, window: list[_ToolCall]) -> StallReport | None:
        """Detect when the same tool with same args is called repeatedly."""
        if len(window) < self.exact_threshold:
            return None

        # Check if the last N calls have the same hash
        last_hash = window[-1].args_hash
        consecutive = 0
        for call in reversed(window):
            if call.args_hash == last_hash:
                consecutive += 1
            else:
                break

        if consecutive >= self.exact_threshold:
            last = window[-1]
            sample_args = self._summarize_args(last.args_raw)
            severity = "soft" if _is_safe_inspection(last.name, last.args_raw) else "hard"
            return StallReport(
                stall_type="exact_repeat",
                tool_name=last.name,
                count=consecutive,
                message=(f"agent_stalled: exact repeat of '{last.name}' {consecutive} times (args: {sample_args})"),
                severity=severity,
            )
        return None

    def _detect_same_tool_repeat(self, window: list[_ToolCall]) -> StallReport | None:
        """Detect when the same tool is called repeatedly (args may differ)."""
        if len(window) < self.same_tool_threshold:
            return None

        # Check if the last N calls are the same tool
        last_name = window[-1].name
        consecutive = 0
        for call in reversed(window):
            if call.name == last_name:
                consecutive += 1
            else:
                break

        if consecutive >= self.same_tool_threshold:
            last = window[-1]
            run = window[-consecutive:]
            distinct_args = {c.args_hash for c in run}
            # Varying args across the run means the agent is actually making
            # progress (scaffolding, exploring) — steer, don't abort.
            severity = "soft" if len(distinct_args) > 1 or _is_safe_inspection(last_name, last.args_raw) else "hard"
            return StallReport(
                stall_type="same_tool_repeat",
                tool_name=last_name,
                count=consecutive,
                message=(f"agent_stalled: '{last_name}' called {consecutive} times consecutively without progress"),
                severity=severity,
            )
        return None

    def _detect_no_progress(self, window: list[_ToolCall]) -> StallReport | None:
        """Detect when no productive tool has been called for N consecutive calls."""
        if self._non_productive_streak < self.no_progress_threshold:
            return None

        tools_seen = sorted({c.name for c in self._calls[-self.no_progress_threshold :]})
        return StallReport(
            stall_type="no_progress",
            tool_name="multiple",
            count=self._non_productive_streak,
            message=(
                f"agent_stalled: {self._non_productive_streak} iterations without productive tool"
                f" (saw: {', '.join(tools_seen)}; expected: {', '.join(sorted(self.productive_tools))})"
            ),
        )

    def _summarize_args(self, args: dict) -> str:
        """Create a readable summary of tool args for error messages."""
        if not args:
            return "{}"
        # Show first 2 keys max, truncate values
        items = []
        for k, v in list(args.items())[:2]:
            v_str = str(v)[:60]
            items.append(f"{k}: {v_str}")
        summary = ", ".join(items)
        if len(args) > 2:
            summary += f", ... ({len(args) - 2} more)"
        return "{" + summary + "}"

    def get_stats(self) -> dict:
        """Return current detection stats for logging."""
        if not self._calls:
            return {"total_calls": 0}

        tool_counts = {}
        for c in self._calls:
            tool_counts[c.name] = tool_counts.get(c.name, 0) + 1

        return {
            "total_calls": len(self._calls),
            "tools_used": tool_counts,
            "non_productive_streak": self._non_productive_streak,
        }

    def reset(self) -> None:
        """Reset detector state (for retries)."""
        self._calls.clear()
        self._non_productive_streak = 0


def create_stall_detector(config: dict | None = None) -> StallDetector:
    """Create a StallDetector from config dict (agent.stall_detection section)."""
    if not config:
        return StallDetector()

    stall_cfg = config.get("stall_detection", {})
    enabled = stall_cfg.get("enabled", True)

    return StallDetector(
        enabled=enabled,
        window_size=stall_cfg.get("window_size", 10),
        exact_threshold=stall_cfg.get("exact_repeat_threshold", 3),
        same_tool_threshold=stall_cfg.get("same_tool_threshold", 10),
        no_progress_threshold=stall_cfg.get("no_progress_threshold", 8),
        productive_tools=set(stall_cfg.get("productive_tools", ["write", "edit", "bash"])),
    )
