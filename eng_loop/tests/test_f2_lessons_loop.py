"""F2.1 — Close the lessons loop (C2).

Before 2.1, recovery lessons got random ids (no accumulation), confirm_lesson
had no callers, and prompt consumption filtered only `confirmed` (always
empty). Now: deterministic ids + upsert, confirmation on recovery success,
and a curated ## LESSONS section (confirmed + top-N stage candidates) in
stage prompts.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from eng_loop.schemas import Lesson, RecoveryPlan
from eng_loop.tools.lessons import get_lessons_for_stage, lesson_id_for, load_lessons, save_lessons
from eng_loop.tools.recovery_logger import RecoveryLogger


def make_lesson(pattern: str, confirmed: bool = False) -> Lesson:
    return Lesson(
        lesson_id="lesson_test",
        category="logic",
        pattern=pattern,
        fix_strategy=f"fix for {pattern}",
        context="ctx",
        confirmed=confirmed,
    )


class TestDeterministicIds:
    def test_same_stage_pattern_same_id(self) -> None:
        assert lesson_id_for("impl.code", "boom") == lesson_id_for("impl.code", "boom")
        assert lesson_id_for("impl.code", "boom") != lesson_id_for("verify", "boom")
        assert lesson_id_for("impl.code", "boom") != lesson_id_for("impl.code", "other")

    def test_upsert_accumulates_occurrences(self, tmp_path: Path) -> None:
        logger = RecoveryLogger(str(tmp_path / "recovery.jsonl"))
        lesson = make_lesson("stale cache")
        logger.log_lessons([lesson], str(tmp_path), stage_id="impl.code")
        logger.log_lessons([lesson], str(tmp_path), stage_id="impl.code")

        local = load_lessons(str(tmp_path))["local"]
        lid = lesson_id_for("impl.code", "stale cache")
        assert len(local) == 1  # upserted, not duplicated
        assert local[lid]["occurrences"] == 2
        assert local[lid]["stage"] == "impl.code"
        assert local[lid]["status"] == "candidate"


class TestGetLessonsForStage:
    def _seed(self, tmp_path: Path) -> None:
        local = {
            lesson_id_for("impl.code", "stale cache"): {
                "id": lesson_id_for("impl.code", "stale cache"),
                "stage": "impl.code",
                "failure": "stale cache",
                "root_cause": "ctx",
                "fix": "clear the cache",
                "category": "logic",
                "occurrences": 3,
                "status": "confirmed",
            },
            lesson_id_for("verify", "verify-only issue"): {
                "id": lesson_id_for("verify", "verify-only issue"),
                "stage": "verify",
                "failure": "verify-only issue",
                "root_cause": "ctx",
                "fix": "fix verify",
                "category": "logic",
                "occurrences": 2,
                "status": "candidate",
            },
            lesson_id_for("impl.code", "impl-only issue"): {
                "id": lesson_id_for("impl.code", "impl-only issue"),
                "stage": "impl.code",
                "failure": "impl-only issue",
                "root_cause": "ctx",
                "fix": "fix impl",
                "category": "logic",
                "occurrences": 1,
                "status": "candidate",
            },
        }
        save_lessons(str(tmp_path), local, "lessons.json")

    def test_confirmed_global_candidates_stage_scoped(self, tmp_path: Path) -> None:
        self._seed(tmp_path)
        data = load_lessons(str(tmp_path))

        impl = get_lessons_for_stage("impl.code", data)
        failures = {l["failure"] for l in impl}
        assert "stale cache" in failures  # confirmed — global
        assert "impl-only issue" in failures  # same-stage candidate
        assert "verify-only issue" not in failures  # other stage

        verify = get_lessons_for_stage("verify", data)
        vfailures = {l["failure"] for l in verify}
        assert "stale cache" in vfailures  # confirmed — global
        assert "verify-only issue" in vfailures
        assert "impl-only issue" not in vfailures


class TestPromptLessonsSection:
    def test_impl_code_prompt_contains_confirmed_lesson(self, tmp_path: Path) -> None:
        from eng_loop.tools.prompt_builder import PromptBuilder

        TestGetLessonsForStage._seed(self, tmp_path)
        state = {"work_item": {"title": "t"}, "stage_artifacts": {}}
        paths = {"artifact_root": str(tmp_path), "project_root": str(tmp_path)}
        prompt = PromptBuilder(state, paths, {}).build("impl.code", role_description="r", instructions="i")
        assert "## LESSONS" in prompt
        assert "stale cache" in prompt
        assert "impl-only issue" in prompt
        assert "verify-only issue" not in prompt

    def test_verify_prompt_contains_stage_candidate(self, tmp_path: Path) -> None:
        from eng_loop.tools.prompt_builder import PromptBuilder

        TestGetLessonsForStage._seed(self, tmp_path)
        state = {"work_item": {"title": "t"}, "stage_artifacts": {}}
        paths = {"artifact_root": str(tmp_path), "project_root": str(tmp_path)}
        prompt = PromptBuilder(state, paths, {}).build("verify", role_description="r", instructions="i")
        assert "## LESSONS" in prompt
        assert "verify-only issue" in prompt
        assert "impl-only issue" not in prompt

    def test_no_lessons_no_section(self, tmp_path: Path) -> None:
        from eng_loop.tools.prompt_builder import PromptBuilder

        state = {"work_item": {"title": "t"}, "stage_artifacts": {}}
        paths = {"artifact_root": str(tmp_path), "project_root": str(tmp_path)}
        prompt = PromptBuilder(state, paths, {}).build("impl.code", role_description="r", instructions="i")
        assert "## LESSONS" not in prompt


class TestRecoveryLoopConfirmsOnSuccess:
    def test_fail_then_success_confirms_plan_lesson(self, tmp_path: Path) -> None:
        from eng_loop.cli import _recovery_loop

        plan = RecoveryPlan(
            root_cause="stale cache",
            error_category="logic",
            fix_actions=["clear cache"],
            stages_to_rollback=[],
            lessons=[make_lesson("stale cache")],
            confidence=0.7,
        )

        first = {
            "status": "blocked",
            "blocking_condition": "test failed: assertion error",
            "current_stage": "impl.code",
            "stages": {},
            "recovery_history": [],
        }
        outcomes = iter(
            [
                {
                    "status": "blocked",
                    "blocking_condition": "test failed: assertion error",
                    "current_stage": "impl.code",
                },
                {"status": "done", "blocking_condition": ""},
            ]
        )

        with (
            patch("eng_loop.cli._invoke_graph", side_effect=lambda *a, **k: next(outcomes)),
            patch("eng_loop.tools.recovery_agent.analyze_and_propose", return_value=plan),
        ):
            _recovery_loop(
                first,
                graph=object(),
                thread_config={},
                interrupt_nodes=[],
                paths={"artifact_root": str(tmp_path)},
                config={"recovery": {"max_attempts": 2}},
                exec_state=None,
                normalizer=None,
                hud=None,
                tui_controller=True,
                active_nodes_for_progress=[],
                event_bus=None,
            )

        local = load_lessons(str(tmp_path))["local"]
        lid = lesson_id_for("impl.code", "stale cache")
        assert lid in local
        assert local[lid]["occurrences"] >= 2  # failure + success
        assert local[lid]["status"] == "confirmed"

    def test_promote_to_pending_returns_only_confirmed(self) -> None:
        from eng_loop.tools.lessons import promote_to_pending

        local = {
            "L-1": {"id": "L-1", "status": "confirmed", "occurrences": 3},
            "L-2": {"id": "L-2", "status": "candidate", "occurrences": 1},
        }
        assert promote_to_pending(local) == ["L-1"]
