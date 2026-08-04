from __future__ import annotations

import re
from typing import Any


def extract_decisions(text: str) -> list[str]:
    pattern = r"AD-\d+"
    found = re.findall(pattern, text)
    return list(dict.fromkeys(found))


def next_ad_number(decisions: list[str]) -> str:
    if not decisions:
        return "AD-001"
    numbers = []
    for d in decisions:
        match = re.match(r"AD-(\d+)", d)
        if match:
            numbers.append(int(match.group(1)))
    return f"AD-{max(numbers) + 1:03d}"


def record_decision(state: dict[str, Any], decision_text: str) -> str:
    ad_id = next_ad_number(state.get("decisions", []))
    entry = f"{ad_id}: {decision_text}"
    if "decisions" not in state:
        state["decisions"] = []
    state["decisions"].append(entry)
    return entry


def write_decisions_to_state_md(context_file: str, decisions: list[str]) -> str:
    lines = ["## Decisions", ""]
    for d in decisions:
        lines.append(f"- {d}")
    lines.append("")
    lines.append("## Handoff")
    lines.append("")
    return "\n".join(lines)
