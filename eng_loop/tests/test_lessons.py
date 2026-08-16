from __future__ import annotations

"""Tests for lessons management: load, save, distill, confirm, promote."""

import json
import tempfile
from pathlib import Path

from eng_loop.tools.lessons import (
    confirm_lesson,
    distill_lesson,
    get_confirmed_lessons,
    load_lessons,
    merge_lessons,
    promote_to_pending,
    save_lessons,
)


class TestLoadLessons:
    def test_load_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = load_lessons(tmp)
        assert result == {"shared": {}, "local": {}, "pending": {}}

    def test_load_nonexistent_directory(self):
        result = load_lessons("/nonexistent/path")
        assert result == {"shared": {}, "local": {}, "pending": {}}

    def test_load_local_lessons(self):
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "lessons.json"
            local_path.write_text('{"L-001": {"stage": "init"}}', encoding="utf-8")
            result = load_lessons(tmp)
        assert "L-001" in result["local"]

    def test_load_shared_lessons(self):
        with tempfile.TemporaryDirectory() as tmp:
            shared_path = Path(tmp) / "lessons-shared.json"
            shared_path.write_text('{"L-002": {"stage": "verify"}}', encoding="utf-8")
            result = load_lessons(tmp)
        assert "L-002" in result["shared"]

    def test_load_pending_lessons(self):
        with tempfile.TemporaryDirectory() as tmp:
            pending_path = Path(tmp) / "lessons-pending.json"
            pending_path.write_text('{"L-003": {"stage": "deploy"}}', encoding="utf-8")
            result = load_lessons(tmp)
        assert "L-003" in result["pending"]


class TestMergeLessons:
    def test_merge_local_and_shared(self):
        lessons = {
            "local": {"L-001": {"stage": "init"}},
            "shared": {"L-002": {"stage": "verify"}},
        }
        merged = merge_lessons(lessons)
        assert "L-001" in merged
        assert "L-002" in merged

    def test_shared_overrides_local(self):
        lessons = {
            "local": {"L-001": {"stage": "init", "status": "candidate"}},
            "shared": {"L-001": {"stage": "init", "status": "confirmed"}},
        }
        merged = merge_lessons(lessons)
        assert merged["L-001"]["status"] == "confirmed"


class TestDistillLesson:
    def test_distill_creates_lesson(self):
        lesson = distill_lesson(
            failure_stage="impl.code",
            failure_description="Tests failed",
            root_cause="Missing import",
            fix="Add import statement",
        )
        assert lesson["stage"] == "impl.code"
        assert lesson["failure"] == "Tests failed"
        assert lesson["root_cause"] == "Missing import"
        assert lesson["fix"] == "Add import statement"
        assert lesson["occurrences"] == 1
        assert lesson["status"] == "candidate"
        assert lesson["id"].startswith("L-")

    def test_distill_deterministic_id(self):
        l1 = distill_lesson("impl.code", "fail", "cause", "fix")
        l2 = distill_lesson("impl.code", "different desc", "cause", "fix")
        assert l1["id"] == l2["id"]

    def test_distill_different_cause_different_id(self):
        l1 = distill_lesson("impl.code", "fail", "cause1", "fix")
        l2 = distill_lesson("impl.code", "fail", "cause2", "fix")
        assert l1["id"] != l2["id"]


class TestConfirmLesson:
    def test_confirm_reaches_threshold(self):
        lessons = {"L-001": {"stage": "init", "occurrences": 1, "status": "candidate"}}
        result = confirm_lesson(lessons, "L-001", threshold=2)
        assert result["L-001"]["status"] == "confirmed"
        assert result["L-001"]["occurrences"] == 2

    def test_confirm_below_threshold(self):
        lessons = {"L-001": {"stage": "init", "occurrences": 1, "status": "candidate"}}
        result = confirm_lesson(lessons, "L-001", threshold=5)
        assert result["L-001"]["status"] == "candidate"
        assert result["L-001"]["occurrences"] == 2

    def test_confirm_unknown_lesson(self):
        lessons = {"L-001": {"stage": "init"}}
        result = confirm_lesson(lessons, "L-002", threshold=2)
        assert "L-002" not in result


class TestSaveLessons:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            lessons = {"L-001": {"stage": "init", "status": "candidate"}}
            path = save_lessons(tmp, lessons)
            loaded = json.loads(Path(path).read_text(encoding="utf-8"))
        assert loaded["L-001"]["stage"] == "init"

    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            art_dir = Path(tmp) / "deep" / "artifacts"
            lessons = {"L-001": {}}
            save_lessons(str(art_dir), lessons)
            assert art_dir.exists()


class TestGetConfirmedLessons:
    def test_filters_confirmed(self):
        lessons_data = {
            "local": {
                "L-001": {"status": "confirmed"},
                "L-002": {"status": "candidate"},
            }
        }
        confirmed = get_confirmed_lessons(lessons_data)
        assert len(confirmed) == 1
        assert confirmed[0]["status"] == "confirmed"

    def test_empty_when_none_confirmed(self):
        lessons_data = {"local": {"L-001": {"status": "candidate"}}}
        confirmed = get_confirmed_lessons(lessons_data)
        assert len(confirmed) == 0


class TestPromoteToPending:
    def test_promotes_confirmed(self):
        lessons = {
            "L-001": {"status": "confirmed"},
            "L-002": {"status": "candidate"},
        }
        promoted = promote_to_pending(lessons)
        assert "L-001" in promoted
        assert "L-002" not in promoted

    def test_empty_when_none_confirmed(self):
        lessons = {"L-001": {"status": "candidate"}}
        promoted = promote_to_pending(lessons)
        assert len(promoted) == 0
