from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any


def format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    total_secs = int(seconds)
    hours = total_secs // 3600
    minutes = (total_secs % 3600) // 60
    secs = total_secs % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class TimingTracker:
    """Central timing tracker for the engineering loop.

    Records loop start time, per-stage durations per attempt, and provides
    formatted HH:MM:SS output for console and persistence.
    """

    def __init__(self) -> None:
        self.loop_start_mono: float = 0.0
        self.loop_start_iso: str = ""
        self._stage_durations: dict[str, list[float]] = {}

    def start_loop(self) -> None:
        self.loop_start_mono = time.monotonic()
        self.loop_start_iso = datetime.now(timezone.utc).isoformat()

    def record_stage(self, stage_id: str, duration: float) -> None:
        self._stage_durations.setdefault(stage_id, []).append(duration)

    def get_stage_durations(self, stage_id: str) -> list[float]:
        return self._stage_durations.get(stage_id, [])

    def get_stage_total(self, stage_id: str) -> float:
        return sum(self._stage_durations.get(stage_id, []))

    def get_stage_total_formatted(self, stage_id: str) -> str:
        return format_time(self.get_stage_total(stage_id))

    def get_stage_attempts(self, stage_id: str) -> int:
        return len(self._stage_durations.get(stage_id, []))

    def get_loop_elapsed(self) -> float:
        if self.loop_start_mono == 0.0:
            return 0.0
        return time.monotonic() - self.loop_start_mono

    def get_loop_elapsed_formatted(self) -> str:
        return format_time(self.get_loop_elapsed())

    def get_stage_ids(self) -> list[str]:
        return list(self._stage_durations.keys())

    def get_summary(self) -> list[dict[str, Any]]:
        rows = []
        for stage_id in self._stage_durations:
            durations = self._stage_durations[stage_id]
            rows.append(
                {
                    "stage_id": stage_id,
                    "durations": durations,
                    "total_seconds": sum(durations),
                    "total": format_time(sum(durations)),
                    "attempts": len(durations),
                }
            )
        return rows

    def get_total_seconds(self) -> float:
        return sum(sum(durs) for durs in self._stage_durations.values())

    def to_json(self) -> dict[str, Any]:
        stages_json = {}
        for stage_id, durations in self._stage_durations.items():
            total_secs = sum(durations)
            stages_json[stage_id] = {
                "durations": [round(d, 2) for d in durations],
                "total": format_time(total_secs),
                "total_seconds": round(total_secs, 2),
                "attempts": len(durations),
            }
        return {
            "loop_start": self.loop_start_iso,
            "loop_elapsed": self.get_loop_elapsed_formatted(),
            "loop_elapsed_seconds": round(self.get_loop_elapsed(), 2),
            "stages": stages_json,
        }
