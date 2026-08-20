from __future__ import annotations

import tempfile
from pathlib import Path

from eng_loop.schemas import Lesson, RecoveryEntry
from eng_loop.tools.recovery_logger import RecoveryLogger


class TestRecoveryLogger:
    def test_init_creates_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "sub" / "recovery.jsonl"
            logger = RecoveryLogger(str(log_path))
            assert logger.log_path.parent.exists()

    def test_log_attempt_appends_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "recovery.jsonl"
            logger = RecoveryLogger(str(log_path))

            entry = RecoveryEntry(
                timestamp=1000.0,
                attempt_number=1,
                stage_id="impl.code",
                error_message="test error",
                error_category="logic",
                root_cause="test root cause",
                fix_actions=["fix1"],
                lessons_generated=[],
                outcome="success",
                confidence=0.8,
                duration_ms=100.0,
            )
            logger.log_attempt(entry)

            assert log_path.exists()
            content = log_path.read_text().strip()
            assert '"outcome": "success"' in content
            assert '"stage_id": "impl.code"' in content

    def test_log_attempt_multiple_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "recovery.jsonl"
            logger = RecoveryLogger(str(log_path))

            for i in range(1, 4):
                entry = RecoveryEntry(
                    timestamp=float(i),
                    attempt_number=i,
                    stage_id="impl.code",
                    error_message="error",
                    error_category="logic",
                    root_cause="cause",
                    fix_actions=["fix"],
                    lessons_generated=[],
                    outcome="failed",
                    confidence=0.5,
                    duration_ms=100.0,
                )
                logger.log_attempt(entry)

            lines = log_path.read_text().strip().split("\n")
            assert len(lines) == 3

    def test_get_history_returns_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "recovery.jsonl"
            logger = RecoveryLogger(str(log_path))

            entry = RecoveryEntry(
                timestamp=1000.0,
                attempt_number=1,
                stage_id="impl.code",
                error_message="test error",
                error_category="logic",
                root_cause="cause",
                fix_actions=["fix"],
                lessons_generated=[],
                outcome="success",
                confidence=0.8,
                duration_ms=100.0,
            )
            logger.log_attempt(entry)

            history = logger.get_history()
            assert len(history) == 1
            assert history[0].stage_id == "impl.code"
            assert history[0].outcome == "success"

    def test_get_history_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "recovery.jsonl"
            logger = RecoveryLogger(str(log_path))
            history = logger.get_history()
            assert history == []

    def test_get_history_skips_malformed_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "recovery.jsonl"
            log_path.write_text("not json\n")
            logger = RecoveryLogger(str(log_path))
            history = logger.get_history()
            assert history == []

    def test_get_summary_no_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "recovery.jsonl"
            logger = RecoveryLogger(str(log_path))
            summary = logger.get_summary()
            assert summary["total_attempts"] == 0
            assert summary["successful"] == 0
            assert summary["failed"] == 0
            assert summary["exhausted"] == 0

    def test_get_summary_counts_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "recovery.jsonl"
            logger = RecoveryLogger(str(log_path))

            for outcome in ["success", "failed", "exhausted"]:
                entry = RecoveryEntry(
                    timestamp=1000.0,
                    attempt_number=1,
                    stage_id="impl.code",
                    error_message="error",
                    error_category="logic",
                    root_cause="cause",
                    fix_actions=["fix"],
                    lessons_generated=[],
                    outcome=outcome,
                    confidence=0.5,
                    duration_ms=100.0,
                )
                logger.log_attempt(entry)

            summary = logger.get_summary()
            assert summary["total_attempts"] == 3
            assert summary["successful"] == 1
            assert summary["failed"] == 1
            assert summary["exhausted"] == 1
            assert summary["categories"]["logic"] == 3
            assert summary["stages"]["impl.code"] == 3

    def test_get_previous_attempts_for_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "recovery.jsonl"
            logger = RecoveryLogger(str(log_path))

            for stage in ["impl.code", "verify", "impl.code"]:
                entry = RecoveryEntry(
                    timestamp=1000.0,
                    attempt_number=1,
                    stage_id=stage,
                    error_message="error",
                    error_category="logic",
                    root_cause="cause",
                    fix_actions=["fix"],
                    lessons_generated=[],
                    outcome="failed",
                    confidence=0.5,
                    duration_ms=100.0,
                )
                logger.log_attempt(entry)

            impl_attempts = logger.get_previous_attempts_for_stage("impl.code")
            assert len(impl_attempts) == 2
            verify_attempts = logger.get_previous_attempts_for_stage("verify")
            assert len(verify_attempts) == 1

    def test_reset_clears_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "recovery.jsonl"
            logger = RecoveryLogger(str(log_path))

            entry = RecoveryEntry(
                timestamp=1000.0,
                attempt_number=1,
                stage_id="impl.code",
                error_message="error",
                error_category="logic",
                root_cause="cause",
                fix_actions=["fix"],
                lessons_generated=[],
                outcome="failed",
                confidence=0.5,
                duration_ms=100.0,
            )
            logger.log_attempt(entry)
            logger.reset()

            assert not log_path.exists()

    def test_log_lessons_persists_to_lessons_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "recovery.jsonl"
            artifact_root = Path(tmp) / "artifacts"
            artifact_root.mkdir()
            logger = RecoveryLogger(str(log_path))

            lessons = [
                Lesson(
                    lesson_id="lesson_001",
                    category="logic",
                    pattern="non-convergence in impl.code",
                    fix_strategy="Use TDD approach",
                    context="Agent kept generating same code",
                    confirmed=True,
                )
            ]
            logger.log_lessons(lessons, str(artifact_root))

            lessons_path = artifact_root / "lessons.json"
            assert lessons_path.exists()
