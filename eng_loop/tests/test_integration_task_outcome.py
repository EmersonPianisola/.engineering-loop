from __future__ import annotations

"""Integration tests for compute_task_outcome().

Validates that the final status computation correctly reflects
the actual execution outcome, not just stage completion counts.
"""

from eng_loop.state import compute_task_outcome, make_stage


class TestComputeTaskOutcomeDone:
    def test_all_stages_done_no_retries(self):
        """Clean execution — all stages done, single attempt each."""
        stages = {
            "init": make_stage(),
            "impl.code": make_stage(),
            "post": make_stage(),
        }
        stages["init"]["done"] = True
        stages["init"]["attempts"] = 1
        stages["impl.code"]["done"] = True
        stages["impl.code"]["attempts"] = 1
        stages["post"]["done"] = True
        stages["post"]["attempts"] = 1

        assert compute_task_outcome(stages, "done") == "done"

    def test_post_done_with_clean_output(self):
        """Post stage succeeded with clean output."""
        stages = {
            "init": make_stage(),
            "post": make_stage(),
        }
        stages["init"]["done"] = True
        stages["init"]["attempts"] = 1
        stages["post"]["done"] = True
        stages["post"]["attempts"] = 1
        stages["post"]["output"] = "{'summary': 'all good', 'final_status': 'done'}"

        assert compute_task_outcome(stages, "done") == "done"


class TestComputeTaskOutcomeFailed:
    def test_post_agent_error(self):
        """Post stage agent error — task is failed."""
        stages = {
            "init": make_stage(),
            "post": make_stage(),
        }
        stages["init"]["done"] = True
        stages["init"]["attempts"] = 1
        stages["post"]["done"] = True
        stages["post"]["attempts"] = 1
        stages["post"]["output"] = "{'summary': 'tool execution failures', 'final_status': 'failed'}"

        assert compute_task_outcome(stages, "failed") == "failed"

    def test_post_failed_status(self):
        """Post final_status is 'failed' — task is failed."""
        stages = {
            "init": make_stage(),
            "post": make_stage(),
        }
        stages["init"]["done"] = True
        stages["post"]["done"] = True
        stages["post"]["output"] = "some output"

        assert compute_task_outcome(stages, "failed") == "failed"

    def test_post_output_contains_failed(self):
        """Post output contains 'failed' — task is failed."""
        stages = {
            "init": make_stage(),
            "post": make_stage(),
        }
        stages["init"]["done"] = True
        stages["post"]["done"] = True
        stages["post"]["output"] = "{'final_status': 'failed', 'summary': 'artifact missing'}"

        assert compute_task_outcome(stages, "done") == "failed"

    def test_post_failed_case_insensitive(self):
        """'failed' detection is case-insensitive."""
        stages = {
            "post": make_stage(),
        }
        stages["post"]["done"] = True
        stages["post"]["output"] = "{'final_status': 'FAILED'}"

        assert compute_task_outcome(stages, "done") == "failed"


class TestComputeTaskOutcomePartial:
    def test_active_stage_attempted_not_done(self):
        """Stage was attempted but not completed — partial."""
        stages = {
            "init": make_stage(),
            "impl.code": make_stage(),
            "post": make_stage(),
        }
        stages["init"]["done"] = True
        stages["init"]["attempts"] = 1
        stages["impl.code"]["done"] = False
        stages["impl.code"]["attempts"] = 2
        stages["post"]["done"] = True
        stages["post"]["attempts"] = 1

        assert compute_task_outcome(stages, "done") == "partial"

    def test_multiple_failed_stages(self):
        """Multiple stages failed — still partial."""
        stages = {
            "init": make_stage(),
            "impl.code": make_stage(),
            "verify": make_stage(),
            "post": make_stage(),
        }
        stages["init"]["done"] = True
        stages["init"]["attempts"] = 1
        stages["impl.code"]["done"] = False
        stages["impl.code"]["attempts"] = 3
        stages["verify"]["done"] = False
        stages["verify"]["attempts"] = 1
        stages["post"]["done"] = True
        stages["post"]["attempts"] = 1

        assert compute_task_outcome(stages, "done") == "partial"


class TestComputeTaskOutcomeDoneWithWarnings:
    def test_retried_stages(self):
        """All stages done but some retried — warnings."""
        stages = {
            "init": make_stage(),
            "impl.code": make_stage(),
            "post": make_stage(),
        }
        stages["init"]["done"] = True
        stages["init"]["attempts"] = 1
        stages["impl.code"]["done"] = True
        stages["impl.code"]["attempts"] = 2
        stages["post"]["done"] = True
        stages["post"]["attempts"] = 1

        assert compute_task_outcome(stages, "done") == "done_with_warnings"

    def test_multiple_retried_stages(self):
        """Multiple retried stages — still warnings."""
        stages = {
            "init": make_stage(),
            "impl.code": make_stage(),
            "verify": make_stage(),
            "post": make_stage(),
        }
        stages["init"]["done"] = True
        stages["init"]["attempts"] = 2
        stages["impl.code"]["done"] = True
        stages["impl.code"]["attempts"] = 3
        stages["verify"]["done"] = True
        stages["verify"]["attempts"] = 2
        stages["post"]["done"] = True
        stages["post"]["attempts"] = 1

        assert compute_task_outcome(stages, "done") == "done_with_warnings"


class TestComputeTaskOutcomePriority:
    def test_failed_takes_precedence_over_partial(self):
        """Failed post overrides partial stages."""
        stages = {
            "init": make_stage(),
            "impl.code": make_stage(),
            "post": make_stage(),
        }
        stages["init"]["done"] = True
        stages["impl.code"]["done"] = False
        stages["impl.code"]["attempts"] = 2
        stages["post"]["done"] = True
        stages["post"]["output"] = "{'final_status': 'failed'}"

        assert compute_task_outcome(stages, "failed") == "failed"

    def test_partial_takes_precedence_over_warnings(self):
        """Partial stages override warning status."""
        stages = {
            "init": make_stage(),
            "impl.code": make_stage(),
            "verify": make_stage(),
            "post": make_stage(),
        }
        stages["init"]["done"] = True
        stages["init"]["attempts"] = 2
        stages["impl.code"]["done"] = False
        stages["impl.code"]["attempts"] = 3
        stages["verify"]["done"] = True
        stages["verify"]["attempts"] = 2
        stages["post"]["done"] = True
        stages["post"]["attempts"] = 1

        assert compute_task_outcome(stages, "done") == "partial"

    def test_empty_stages_done(self):
        """Empty stages dict with done post — done."""
        stages = {}
        assert compute_task_outcome(stages, "done") == "done"

    def test_empty_stages_failed_post(self):
        """Empty stages dict with failed post — failed."""
        stages = {}
        assert compute_task_outcome(stages, "failed") == "failed"
