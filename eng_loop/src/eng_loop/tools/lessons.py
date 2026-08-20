from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_lessons(artifact_root: str) -> dict[str, Any]:
    result = {"shared": {}, "local": {}, "pending": {}}
    art = Path(artifact_root)
    if not art.exists():
        return result

    shared_path = art / "lessons-shared.json"
    local_path = art / "lessons.json"
    pending_path = art / "lessons-pending.json"

    if shared_path.exists():
        with open(shared_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            result["shared"] = data if isinstance(data, dict) else {}
    if local_path.exists():
        with open(local_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            result["local"] = data if isinstance(data, dict) else {}
    if pending_path.exists():
        with open(pending_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            result["pending"] = data if isinstance(data, dict) else {}

    return result


def merge_lessons(lessons_data: dict[str, Any]) -> dict[str, Any]:
    local = lessons_data.get("local", {})
    shared = lessons_data.get("shared", {})
    # Defend against malformed lessons files that store lists instead of dicts
    if not isinstance(local, dict):
        local = {}
    if not isinstance(shared, dict):
        shared = {}
    merged = dict(local)
    merged.update(shared)
    return merged


def distill_lesson(failure_stage: str, failure_description: str, root_cause: str, fix: str) -> dict[str, Any]:
    import hashlib

    key = hashlib.md5(f"{failure_stage}:{root_cause}".encode(), usedforsecurity=False).hexdigest()[:8]
    return {
        "id": f"L-{key.upper()}",
        "stage": failure_stage,
        "failure": failure_description,
        "root_cause": root_cause,
        "fix": fix,
        "occurrences": 1,
        "status": "candidate",
    }


def confirm_lesson(lessons: dict[str, Any], lesson_id: str, threshold: int = 2) -> dict[str, Any]:
    if lesson_id in lessons:
        lessons[lesson_id]["occurrences"] = lessons[lesson_id].get("occurrences", 1) + 1
        if lessons[lesson_id]["occurrences"] >= threshold:
            lessons[lesson_id]["status"] = "confirmed"
    return lessons


def save_lessons(artifact_root: str, lessons: dict[str, Any], file_name: str = "lessons.json") -> str:
    art = Path(artifact_root)
    art.mkdir(parents=True, exist_ok=True)
    path = art / file_name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(lessons, f, indent=2, ensure_ascii=False)
    return str(path)


def get_confirmed_lessons(lessons_data: dict[str, Any]) -> list[dict[str, Any]]:
    merged = merge_lessons(lessons_data)
    return [l for l in merged.values() if isinstance(l, dict) and l.get("status") == "confirmed"]


def promote_to_pending(lessons: dict[str, Any] | list[Any]) -> list[str]:
    promoted = []
    if isinstance(lessons, list):
        return promoted
    for lid, ldata in lessons.items():
        if isinstance(ldata, dict) and ldata.get("status") == "confirmed":
            promoted.append(lid)
    return promoted
