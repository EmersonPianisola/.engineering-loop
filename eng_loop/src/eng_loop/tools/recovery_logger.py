from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from eng_loop.schemas import Lesson, RecoveryEntry


class RecoveryLogger:
    """Structured JSONL logger for recovery attempts.

    Each line is a RecoveryEntry serialized to JSON.
    Lessons are also persisted to the existing lessons.json system.
    """

    def __init__(self, log_path: str) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_attempt(self, entry: RecoveryEntry) -> None:
        """Append a recovery attempt entry to the JSONL log."""
        line = json.dumps(entry.model_dump(), ensure_ascii=False, default=str)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def log_lessons(self, lessons: list[Lesson], artifact_root: str) -> None:
        """Persist lessons to the existing lessons.json system."""
        from eng_loop.tools.lessons import load_lessons, save_lessons

        art = Path(artifact_root)
        lessons_data = load_lessons(str(art))
        local = lessons_data.get("local", {})
        if not isinstance(local, dict):
            local = {}
            lessons_data["local"] = local

        for lesson in lessons:
            key = uuid.uuid4().hex[:8]
            lesson_id = f"REC-{key.upper()}"
            local[lesson_id] = {
                "id": lesson_id,
                "stage": "",
                "failure": lesson.pattern,
                "root_cause": lesson.context,
                "fix": lesson.fix_strategy,
                "category": lesson.category,
                "occurrences": 1,
                "status": "candidate",
                "confirmed": lesson.confirmed,
            }

        lessons_data["local"] = local
        save_lessons(str(art), local, "lessons.json")

    def get_history(self) -> list[RecoveryEntry]:
        """Read all recovery entries from the log."""
        if not self.log_path.exists():
            return []
        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        entries.append(RecoveryEntry(**data))
                    except Exception:
                        continue
        return entries

    def get_summary(self) -> dict[str, Any]:
        """Generate a summary of all recovery attempts."""
        entries = self.get_history()
        if not entries:
            return {
                "total_attempts": 0,
                "successful": 0,
                "failed": 0,
                "exhausted": 0,
                "categories": {},
                "stages": {},
            }

        categories: dict[str, int] = {}
        stages: dict[str, int] = {}
        successful = 0
        failed = 0
        exhausted = 0

        for entry in entries:
            categories[entry.error_category] = categories.get(entry.error_category, 0) + 1
            stages[entry.stage_id] = stages.get(entry.stage_id, 0) + 1
            if entry.outcome == "success":
                successful += 1
            elif entry.outcome == "exhausted":
                exhausted += 1
            else:
                failed += 1

        return {
            "total_attempts": len(entries),
            "successful": successful,
            "failed": failed,
            "exhausted": exhausted,
            "categories": categories,
            "stages": stages,
        }

    def get_previous_attempts_for_stage(self, stage_id: str) -> list[RecoveryEntry]:
        """Get previous recovery attempts for a specific stage."""
        return [e for e in self.get_history() if e.stage_id == stage_id]

    def reset(self) -> None:
        """Clear the recovery log."""
        if self.log_path.exists():
            self.log_path.unlink()
