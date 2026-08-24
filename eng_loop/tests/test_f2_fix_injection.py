"""F2.2 — H4: recovery fix guidance actually reaches the prompt.

handoffs["recovery_fix_prompt"] / handoffs["recovery_lessons"] were written
by the fix applier but had no consumer. PromptBuilder now renders them as a
## RECOVERY GUIDANCE section for the re-executed stage.
"""

from __future__ import annotations

from eng_loop.schemas import Lesson, RecoveryPlan
from eng_loop.tools.fix_applier import apply_recovery_plan
from eng_loop.tools.prompt_builder import PromptBuilder


def _plan_with_injection() -> RecoveryPlan:
    return RecoveryPlan(
        root_cause="stale cache",
        error_category="logic",
        fix_actions=["clear cache"],
        stages_to_rollback=[],
        lessons=[
            Lesson(
                lesson_id="l1",
                category="logic",
                pattern="stale cache",
                fix_strategy="clear the cache first",
                context="",
            )
        ],
        confidence=0.8,
        fix_prompt_injection="Always invalidate the build cache before retrying.",
    )


class TestFixInjection:
    def test_fix_prompt_and_lessons_reach_prompt(self, tmp_path) -> None:
        state = {"stages": {}, "current_stage": "impl.code", "handoffs": {}}
        fixed = apply_recovery_plan(state, _plan_with_injection())

        assert fixed["handoffs"]["recovery_fix_prompt"] == "Always invalidate the build cache before retrying."
        assert "clear the cache first" in fixed["handoffs"]["recovery_lessons"]

        paths = {"artifact_root": str(tmp_path), "project_root": str(tmp_path)}
        prompt = PromptBuilder(fixed, paths, {}).build("impl.code", role_description="r", instructions="i")
        assert "## RECOVERY GUIDANCE" in prompt
        assert "Always invalidate the build cache before retrying." in prompt
        assert "clear the cache first" in prompt

    def test_no_recovery_no_section(self, tmp_path) -> None:
        state = {"stages": {}, "handoffs": {}}
        paths = {"artifact_root": str(tmp_path), "project_root": str(tmp_path)}
        prompt = PromptBuilder(state, paths, {}).build("impl.code", role_description="r", instructions="i")
        assert "## RECOVERY GUIDANCE" not in prompt

    def test_empty_fix_prompt_only_lessons(self, tmp_path) -> None:
        plan = _plan_with_injection().model_copy(update={"fix_prompt_injection": ""})
        fixed = apply_recovery_plan({"stages": {}, "handoffs": {}}, plan)
        paths = {"artifact_root": str(tmp_path), "project_root": str(tmp_path)}
        prompt = PromptBuilder(fixed, paths, {}).build("impl.code", role_description="r", instructions="i")
        assert "## RECOVERY GUIDANCE" in prompt
        assert "clear the cache first" in prompt
