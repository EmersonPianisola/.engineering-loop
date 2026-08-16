from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from eng_loop.state import STAGE_ORDER
from eng_loop.tools.file_ops import load_json, save_json


def get_history_dir(paths: dict[str, str], config: dict[str, Any] | None = None) -> Path:
    """Resolve the history directory path."""
    config = config or {}
    history_dir = config.get("state_history", {}).get("history_dir", ".eng/history")
    artifact_root = paths.get("artifact_root", "artifacts")
    loop_root = Path(artifact_root).parent
    return Path(os.path.join(str(loop_root), history_dir))


def get_retention(paths: dict[str, str], config: dict[str, Any] | None = None) -> int:
    """Get max snapshots to retain per stage."""
    config = config or {}
    return config.get("state_history", {}).get("retention_per_stage", 5)


def is_enabled(config: dict[str, Any]) -> bool:
    return config.get("state_history", {}).get("enabled", True)


def _make_snapshot_filename(stage_id: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_id = stage_id.replace(".", "-").replace("_", "-")
    return f"state_after_{safe_id}_{ts}.json"


def save_snapshot(
    state: dict[str, Any], paths: dict[str, str], stage_id: str, config: dict[str, Any] | None = None
) -> Path | None:
    """Save a state snapshot after a stage completes.

    Returns the path to the saved snapshot, or None if history is disabled.
    Enforces per-stage retention policy.
    """
    if not is_enabled(config or {}):
        return None

    history_dir = get_history_dir(paths, config)
    history_dir.mkdir(parents=True, exist_ok=True)

    saveable = _make_saveable(state)
    filename = _make_snapshot_filename(stage_id)
    snapshot_path = history_dir / filename
    save_json(str(snapshot_path), saveable)

    _enforce_retention(stage_id, history_dir, paths, config)
    return snapshot_path


def _make_saveable(state: dict[str, Any]) -> dict[str, Any]:
    """Build a clean snapshot from pipeline state, excluding non-serializable fields."""
    return {
        "iteration": state.get("iteration", 0),
        "status": state.get("status", "running"),
        "blocking_condition": state.get("blocking_condition", ""),
        "complexity": state.get("complexity", "unset"),
        "work_type": state.get("work_type", "feature"),
        "work_item": state.get("work_item", ""),
        "ideation": state.get("ideation"),
        "ui_project": state.get("ui_project", False),
        "stages": state.get("stages", {}),
        "decisions": state.get("decisions", []),
        "stage_artifacts": state.get("stage_artifacts", {}),
        "lessons": state.get("lessons", []),
        "errors": state.get("errors", []),
        "handoffs": state.get("handoffs", {}),
        "context_tiers": state.get("context_tiers", {}),
        "tags": state.get("tags", []),
        "active_nodes": state.get("active_nodes", []),
        "graph_topology": state.get("graph_topology", {}),
        "parallel_groups": state.get("parallel_groups", {}),
        "timing": state.get("timing", {}),
        "current_stage": state.get("current_stage", ""),
        "fix_tasks": state.get("fix_tasks", []),
        "fix_iteration": state.get("fix_iteration", 0),
        "rollback_target": state.get("rollback_target", ""),
        "explorer_evidence": state.get("explorer_evidence", []),
        "codebase_facts": state.get("codebase_facts", {}),
        "dynamic_plan": state.get("dynamic_plan"),
        "dynamic_runtime": state.get("dynamic_runtime", {}),
    }


def _enforce_retention(
    stage_id: str, history_dir: Path, paths: dict[str, str], config: dict[str, Any] | None = None
) -> None:
    """Remove oldest snapshots for a stage if retention limit exceeded."""
    retention = get_retention(paths, config)
    safe_id = stage_id.replace(".", "-").replace("_", "-")
    prefix = f"state_after_{safe_id}_"

    matches = sorted(history_dir.glob(f"{prefix}*.json"))
    while len(matches) > retention:
        oldest = matches.pop(0)
        try:
            oldest.unlink()
        except OSError:
            pass


def list_snapshots(paths: dict[str, str], config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """List all state snapshots, sorted by filename (oldest first).

    Returns list of dicts with keys: path, stage_id, timestamp, size.
    """
    history_dir = get_history_dir(paths, config)
    if not history_dir.exists():
        return []

    results = []
    for fp in sorted(history_dir.glob("state_after_*.json")):
        stage_id = _extract_stage_id(fp.name)
        timestamp = _extract_timestamp(fp.name)
        results.append(
            {
                "path": str(fp),
                "stage_id": stage_id,
                "timestamp": timestamp,
                "size": fp.stat().st_size,
            }
        )
    return results


def _extract_stage_id(filename: str) -> str:
    # "state_after_impl-code_20260812_143022_123456.json" -> "impl.code"
    # Timestamp suffix: _YYYYMMDD_HHMMSS_ffffff (23 chars)
    core = filename[len("state_after_") : -len(".json")]
    if len(core) > 23 and core[-23:].startswith("_"):
        node_part = core[:-23]
        return node_part.replace("-", ".")
    # Fallback for old format: _YYYYMMDD_HHMMSS (16 chars)
    if len(core) > 16 and core[-16:].startswith("_"):
        node_part = core[:-16]
        return node_part.replace("-", ".")
    return core


def _extract_timestamp(filename: str) -> str:
    # "state_after_impl-code_20260812_143022_123456.json" -> "2026-08-12 14:30:22"
    core = filename[len("state_after_") : -len(".json")]
    # Try new format first: _YYYYMMDD_HHMMSS_ffffff (23 chars)
    if len(core) > 23 and core[-23:].startswith("_"):
        ts_str = core[-22:]  # "YYYYMMDD_HHMMSS_ffffff"
        try:
            dt = datetime.strptime(ts_str[:15], "%Y%m%d_%H%M%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return ts_str
    # Fallback for old format
    if len(core) > 16 and core[-16:].startswith("_"):
        ts_str = core[-15:]
        try:
            dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return ts_str
    return ""


def get_snapshot_before(stage_id: str, paths: dict[str, str], config: dict[str, Any] | None = None) -> Path | None:
    """Find the latest snapshot taken before (or at) the given stage.

    Uses STAGE_ORDER to determine which stages come before stage_id.
    """
    target_idx = None
    try:
        target_idx = STAGE_ORDER.index(stage_id)
    except ValueError:
        pass

    if target_idx is None:
        return None

    target_stages = STAGE_ORDER[: target_idx + 1]
    history_dir = get_history_dir(paths, config)
    if not history_dir.exists():
        return None

    candidates = []
    for fp in history_dir.glob("state_after_*.json"):
        sid = _extract_stage_id(fp.name)
        if sid in target_stages:
            candidates.append(fp)

    if not candidates:
        return None

    return max(candidates, key=lambda p: p.stat().st_mtime)


def rollback_to(stage_id: str, paths: dict[str, str], config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Rollback state to the snapshot just before the given stage.

    Returns the restored state dict, or None if no suitable snapshot exists.
    """
    snapshot_path = get_snapshot_before(stage_id, paths, config)
    if not snapshot_path:
        return None

    data = load_json(str(snapshot_path))
    if not data:
        return None

    data["status"] = "running"
    data["blocking_condition"] = ""
    data["current_stage"] = stage_id
    return data


def rollback_and_save(stage_id: str, paths: dict[str, str], config: dict[str, Any] | None = None) -> bool:
    """Rollback state and write to state.json. Returns True on success."""
    restored = rollback_to(stage_id, paths, config)
    if not restored:
        return False

    state_file = paths.get("state_file", "state.json")
    save_json(state_file, restored)
    return True
