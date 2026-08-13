from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import Any


def get_editor_command() -> list[str]:
    """Resolve editor command with fallback chain.

    Priority: $EDITOR > vim > nano > code --wait > notepad.exe
    """
    editor = os.environ.get("EDITOR")
    if editor:
        return editor.split()

    for candidate in ["vim", "nano"]:
        if shutil.which(candidate):
            return [candidate]

    if shutil.which("code"):
        return ["code", "--wait"]

    if shutil.which("notepad.exe") or os.name == "nt":
        return ["notepad.exe"]

    return ["vim"]


def build_editable_slice(state: dict[str, Any], node_id: str) -> dict[str, Any]:
    """Build a focused slice of state for manual editing.

    Includes only what's needed for surgical debugging:
    stage status, errors, handoffs, topology context, work item.
    Excludes messages, full artifacts, and other noisy fields.
    """
    stages = state.get("stages", {})
    return {
        "stage_id": node_id,
        "stage_status": stages.get(node_id, {}),
        "status": state.get("status", ""),
        "blocking_condition": state.get("blocking_condition", ""),
        "errors_or_findings": state.get("errors", []),
        "handoffs": state.get("handoffs", {}),
        "active_nodes": state.get("active_nodes", []),
        "work_item_context": state.get("work_item", ""),
    }


def merge_slice_back(state: dict[str, Any], edited_slice: dict[str, Any]) -> dict[str, Any]:
    """Merge an edited slice back into the full state.

    Only merges fields that exist in the slice template.
    """
    node_id = edited_slice.get("stage_id", "")
    if not node_id:
        return state

    if "stage_status" in edited_slice:
        stages = state.setdefault("stages", {})
        stages[node_id] = edited_slice["stage_status"]

    for key in ("status", "blocking_condition"):
        if key in edited_slice:
            state[key] = edited_slice[key]

    if "errors_or_findings" in edited_slice:
        state["errors"] = edited_slice["errors_or_findings"]

    if "handoffs" in edited_slice:
        state["handoffs"] = edited_slice["handoffs"]

    return state


def validate_edited_json(filepath: str) -> tuple[dict[str, Any], str | None]:
    """Read and validate edited JSON file. Returns (data, error)."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return {}, "File is empty"
        data = json.loads(content)
        if not isinstance(data, dict):
            return {}, "Root must be a JSON object"
        return data, None
    except json.JSONDecodeError as e:
        return {}, f"Invalid JSON: {e}"


def edit_state_in_editor(state: dict[str, Any], node_id: str, max_attempts: int = 3) -> dict[str, Any]:
    """State Slicing + $EDITOR workflow.

    1. Build editable slice
    2. Write to temp file
    3. Launch $EDITOR (blocking)
    4. Read back, validate, merge
    5. Retry on invalid JSON (up to max_attempts)

    Returns updated state.
    """
    editor_cmd = get_editor_command()

    for attempt in range(1, max_attempts + 1):
        slice_data = build_editable_slice(state, node_id)

        fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix=f"eng-loop-{node_id}-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(slice_data, tmp, indent=2, ensure_ascii=False, default=str)

            subprocess.run(editor_cmd + [tmp_path], check=False)

            edited, error = validate_edited_json(tmp_path)
            if error:
                from eng_loop.tools.progress import ui
                ui.console.print(f"\n  [bold red]JSON error (attempt {attempt}/{max_attempts}):[/bold red] {error}")
                if attempt < max_attempts:
                    ui.console.print("  [yellow]Reopening editor. Fix the JSON and save.[/yellow]")
                continue

            return merge_slice_back(state, edited)

        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    from eng_loop.tools.progress import ui
    ui.console.print("\n  [bold red]Editor validation failed after 3 attempts. Aborting edit.[/bold red]")
    return state
