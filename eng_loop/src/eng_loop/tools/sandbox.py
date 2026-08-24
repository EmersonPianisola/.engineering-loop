"""Tool sandboxing — contain file tools and guard shell commands (C4).

File tools (read/write/edit/glob/grep) resolve their paths against the
project root and reject escapes (`..` traversal or absolute paths outside
the root). The bash tool is screened against RISK_KEYWORDS plus a small
denylist of catastrophic patterns.

Config (explicit opt-out):
    agent:
      tools:
        sandbox:
          enabled: true
          allow_out_of_root: false
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SANDBOX_CONFIG_DEFAULTS: dict[str, bool] = {
    "enabled": True,
    "allow_out_of_root": False,
}


def sandbox_config(config: dict[str, Any] | None) -> dict[str, bool]:
    """Read agent.tools.sandbox settings with safe defaults."""
    cfg = (config or {}).get("agent", {}).get("tools", {}).get("sandbox", {})
    if not isinstance(cfg, dict):
        cfg = {}
    return {
        "enabled": bool(cfg.get("enabled", SANDBOX_CONFIG_DEFAULTS["enabled"])),
        "allow_out_of_root": bool(cfg.get("allow_out_of_root", SANDBOX_CONFIG_DEFAULTS["allow_out_of_root"])),
    }


def build_sandbox(root: str | Path, config: dict[str, Any] | None) -> dict[str, Any] | None:
    """Build the sandbox context handed to tool factories.

    Returns None when sandboxing is disabled (tools keep legacy behavior).
    """
    settings = sandbox_config(config)
    if not settings["enabled"]:
        return None
    return {
        "enabled": True,
        "root": str(root),
        "allow_out_of_root": settings["allow_out_of_root"],
    }


def resolve_in_root(p: str | Path, root: str | Path) -> Path | None:
    """Resolve p (relative to root) and return it only if it stays inside root.

    Returns None for escapes: `..` traversal or absolute paths outside the
    root. The root itself is allowed.
    """
    root_p = Path(root).resolve()
    candidate = Path(p)
    if not candidate.is_absolute():
        candidate = root_p / candidate
    try:
        resolved = candidate.resolve()
        if resolved.is_relative_to(root_p):
            return resolved
    except (OSError, RuntimeError):
        pass
    return None


def check_path(p: str | Path, sandbox: dict[str, Any] | None) -> Path | None:
    """Containment check for file tools.

    Returns the resolved path when allowed, None when the path escapes the
    sandbox. A None/disabled sandbox or allow_out_of_root=True means no
    containment (legacy behavior, path returned as Path(p)).
    """
    if not sandbox or not sandbox.get("enabled") or sandbox.get("allow_out_of_root"):
        return Path(p)
    return resolve_in_root(p, sandbox.get("root", "."))


# ── Bash command guard ────────────────────────────────────────────


def _load_risk_keywords() -> list[str]:
    """RISK_KEYWORDS as command filters.

    "rm -rf" is excluded: a plain substring match would block legitimate
    cleanup commands (`rm -rf ./build`). Dangerous rm targets (/, ~, $HOME)
    are covered by DESTRUCTIVE_PATTERNS with target awareness.
    """
    from eng_loop.tools.policy_resolver import RISK_KEYWORDS

    return [kw for kw in RISK_KEYWORDS if kw != "rm -rf"]


DESTRUCTIVE_PATTERNS: list[str] = [
    # rm <flags> <target> where the target starts with / , ~ or $HOME
    # (covers rm -rf /, rm -r -f /etc, rm -rf ~, rm --no-preserve-root -rf /)
    # NOTE: commands are lowercased before matching — hence lowercase $home.
    r"\brm\s+(?:--no-preserve-root\s+)?(?:-\w+\s+)+(/|~|\$home)\S*",
    # fork bomb
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",
    # filesystem / raw device destruction
    r"\bmkfs(\.[a-z0-9]+)?\b",
    r"\bdd\s+.*\bof=/dev/",
    r">\s*/dev/(sd[a-z]|nvme|disk|hd[a-z])",
]

_DESTRUCTIVE_REGEX = [re.compile(p) for p in DESTRUCTIVE_PATTERNS]


def check_bash_command(command: str, sandbox: dict[str, Any] | None) -> str | None:
    """Screen a shell command. Returns an error string when blocked, None to allow.

    Applies RISK_KEYWORDS (shared with the topology firewall) plus a minimal
    denylist of catastrophic patterns. A None/disabled sandbox means no guard.
    """
    if not sandbox or not sandbox.get("enabled"):
        return None
    lowered = command.lower()

    for keyword in _load_risk_keywords():
        if keyword in lowered:
            logger.warning("sandbox: blocking bash command — risk keyword %r: %s", keyword, command[:300])
            return (
                f"BLOCKED: command matches risk keyword '{keyword}'. "
                f"This operation is not permitted by the tool sandbox."
            )

    for regex in _DESTRUCTIVE_REGEX:
        if regex.search(lowered):
            logger.warning("sandbox: blocking bash command — destructive pattern: %s", command[:300])
            return "BLOCKED: command matches a destructive pattern (e.g. recursive delete of a system path). This operation is not permitted by the tool sandbox."

    return None
