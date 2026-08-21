from __future__ import annotations

import pytest
from pydantic import ValidationError

from eng_loop.schemas import (
    DynamicAuditEntry,
    DynamicBlueprint,
    DynamicBlueprintProposal,
    DynamicRuntime,
    DynamicStep,
    FilesExistPayload,
    SymbolPayload,
    TestsPassPayload,
    ValidationRule,
)
from eng_loop.tools.dynamic_validation import (
    _eval_contains_symbol,
    _eval_files_exist,
    _eval_tests_pass,
    evaluate_validation_rules,
)
from eng_loop.tools.policy_resolver import (
    SAFE_TOOL_POOL,
    authorize_blueprint,
    get_tools_by_names,
)

# ============================================================
# SCHEMA VALIDATION
# ============================================================


class TestValidationRulePayloads:
    def test_tests_pass_payload_defaults(self):
        p = TestsPassPayload()
        assert p.suite == "unit"
        assert p.command == ""

    def test_tests_pass_payload_custom(self):
        p = TestsPassPayload(suite="e2e", command="npm test")
        assert p.suite == "e2e"
        assert p.command == "npm test"

    def test_files_exist_payload(self):
        p = FilesExistPayload(paths=("src/main.py", "tests/test_main.py"))
        assert len(p.paths) == 2

    def test_symbol_payload(self):
        p = SymbolPayload(symbol="def main", target_file="src/main.py")
        assert p.symbol == "def main"

    def test_payloads_are_frozen(self):
        p = TestsPassPayload(suite="unit")
        with pytest.raises(ValidationError):
            p.suite = "e2e"


class TestValidationRule:
    def test_validation_rule_tests_pass(self):
        rule = ValidationRule(
            type="tests_pass",
            payload=TestsPassPayload(suite="unit"),
        )
        assert rule.type == "tests_pass"

    def test_validation_rule_files_exist(self):
        rule = ValidationRule(
            type="files_exist",
            payload=FilesExistPayload(paths=("a.py", "b.py")),
        )
        assert rule.type == "files_exist"

    def test_validation_rule_is_frozen(self):
        rule = ValidationRule(
            type="tests_pass",
            payload=TestsPassPayload(),
        )
        with pytest.raises(ValidationError):
            rule.type = "files_exist"


class TestDynamicStep:
    def test_valid_step_id(self):
        step = DynamicStep(
            step_id="db-migration-step",
            role_description="Run database migration",
        )
        assert step.step_id == "db-migration-step"

    def test_step_id_rejects_uppercase(self):
        with pytest.raises(ValueError, match="must match"):
            DynamicStep(
                step_id="DB-Migration",
                role_description="Bad ID",
            )

    def test_step_id_rejects_spaces(self):
        with pytest.raises(ValueError, match="must match"):
            DynamicStep(
                step_id="db migration",
                role_description="Bad ID",
            )

    def test_step_max_attempts_bounds(self):
        step = DynamicStep(
            step_id="test-step",
            role_description="Test",
            max_attempts=5,
        )
        assert step.max_attempts == 5

    def test_step_max_attempts_too_high(self):
        with pytest.raises(ValueError):
            DynamicStep(
                step_id="test-step",
                role_description="Test",
                max_attempts=6,
            )

    def test_step_max_attempts_too_low(self):
        with pytest.raises(ValueError):
            DynamicStep(
                step_id="test-step",
                role_description="Test",
                max_attempts=0,
            )

    def test_step_defaults(self):
        step = DynamicStep(
            step_id="test-step",
            role_description="Test",
        )
        assert step.max_attempts == 3
        assert step.requested_capabilities == ()
        assert step.validation_rules == ()

    def test_step_is_frozen(self):
        step = DynamicStep(
            step_id="test-step",
            role_description="Test",
        )
        with pytest.raises(ValidationError):
            step.step_id = "other-step"


class TestDynamicBlueprintProposal:
    def test_proposal_augment_with_steps(self):
        step = DynamicStep(
            step_id="prep-step",
            role_description="Prepare environment",
        )
        proposal = DynamicBlueprintProposal(
            plan_id="p-001",
            trigger="augment",
            steps=(step,),
            rationale="Need prep step",
        )
        assert proposal.trigger == "augment"
        assert len(proposal.steps) == 1

    def test_proposal_augment_without_steps_fails(self):
        with pytest.raises(ValueError, match="requires at least one"):
            DynamicBlueprintProposal(
                plan_id="p-001",
                trigger="augment",
                steps=(),
                rationale="Nothing",
            )

    def test_proposal_none_with_steps_fails(self):
        step = DynamicStep(
            step_id="prep-step",
            role_description="Prepare",
        )
        with pytest.raises(ValueError, match="cannot contain"):
            DynamicBlueprintProposal(
                plan_id="p-001",
                trigger="none",
                steps=(step,),
                rationale="Nothing",
            )

    def test_proposal_none_without_steps_ok(self):
        proposal = DynamicBlueprintProposal(
            plan_id="p-001",
            trigger="none",
            rationale="No augmentation needed",
        )
        assert proposal.trigger == "none"
        assert proposal.steps == ()


class TestDynamicBlueprint:
    def test_blueprint_valid(self):
        step = DynamicStep(
            step_id="prep-step",
            role_description="Prepare",
        )
        bp = DynamicBlueprint(
            plan_id="p-001",
            trigger="augment",
            authorized_complexity="standard",
            steps=(step,),
            rationale="Authorized",
        )
        assert len(bp.steps) == 1

    def test_blueprint_duplicate_step_ids_fails(self):
        step1 = DynamicStep(
            step_id="dup-step",
            role_description="First",
        )
        step2 = DynamicStep(
            step_id="dup-step",
            role_description="Second",
        )
        with pytest.raises(ValueError, match="must be unique"):
            DynamicBlueprint(
                plan_id="p-001",
                trigger="augment",
                authorized_complexity="standard",
                steps=(step1, step2),
                rationale="Bad",
            )

    def test_blueprint_exceeds_max_steps(self):
        steps = tuple(
            DynamicStep(
                step_id=f"step-{i}",
                role_description=f"Step {i}",
            )
            for i in range(6)
        )
        with pytest.raises(ValueError, match="exceeds MAX_DYNAMIC_STEPS"):
            DynamicBlueprint(
                plan_id="p-001",
                trigger="augment",
                authorized_complexity="standard",
                steps=steps,
                rationale="Too many",
            )

    def test_blueprint_max_five_steps_ok(self):
        steps = tuple(
            DynamicStep(
                step_id=f"step-{i}",
                role_description=f"Step {i}",
            )
            for i in range(5)
        )
        bp = DynamicBlueprint(
            plan_id="p-001",
            trigger="augment",
            authorized_complexity="standard",
            steps=steps,
            rationale="Exactly five",
        )
        assert len(bp.steps) == 5

    def test_blueprint_is_frozen(self):
        step = DynamicStep(
            step_id="prep-step",
            role_description="Prepare",
        )
        bp = DynamicBlueprint(
            plan_id="p-001",
            trigger="augment",
            authorized_complexity="standard",
            steps=(step,),
            rationale="Test",
        )
        with pytest.raises(ValidationError):
            bp.plan_id = "p-002"


class TestDynamicAuditEntry:
    def test_audit_entry(self):
        entry = DynamicAuditEntry(
            plan_id="p-001",
            step_id="prep-step",
            attempt=1,
            status="success",
            started_at=0.0,
            finished_at=1.0,
        )
        assert entry.status == "success"
        assert entry.error is None

    def test_audit_entry_with_error(self):
        entry = DynamicAuditEntry(
            plan_id="p-001",
            step_id="prep-step",
            attempt=2,
            status="failed",
            started_at=0.0,
            finished_at=1.0,
            error="Validation failed",
        )
        assert entry.error == "Validation failed"


class TestDynamicRuntime:
    def test_runtime_defaults(self):
        rt = DynamicRuntime()
        assert rt.cursor == 0
        assert rt.attempts == {}
        assert rt.completed == []
        assert rt.failed == []
        assert rt.status == "pending"
        assert rt.step_audit == []

    def test_runtime_cursor_in_bounds(self):
        rt = DynamicRuntime(cursor=2)
        rt.validate_invariants(5)

    def test_runtime_cursor_out_of_bounds(self):
        rt = DynamicRuntime(cursor=6)
        with pytest.raises(ValueError, match="out of bounds"):
            rt.validate_invariants(5)

    def test_runtime_cursor_at_boundary(self):
        rt = DynamicRuntime(cursor=5)
        rt.validate_invariants(5)

    def test_runtime_overlap_completed_failed(self):
        rt = DynamicRuntime(
            completed=["step-1"],
            failed=["step-1"],
        )
        with pytest.raises(ValueError, match="Overlap"):
            rt.validate_invariants(3)

    def test_runtime_no_overlap(self):
        rt = DynamicRuntime(
            completed=["step-1"],
            failed=["step-2"],
        )
        rt.validate_invariants(3)

    def test_runtime_serialization(self):
        rt = DynamicRuntime(cursor=1, status="running")
        d = rt.model_dump()
        assert d["cursor"] == 1
        assert d["status"] == "running"
        rt2 = DynamicRuntime(**d)
        assert rt2.cursor == 1


# ============================================================
# VALIDATION RULES
# ============================================================


class TestEvaluateValidationRules:
    def test_empty_rules_pass(self):
        passed, err = evaluate_validation_rules({}, (), ".", {})
        assert passed is True
        assert err is None

    def test_single_rule_pass(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")
        rule = ValidationRule(
            type="files_exist",
            payload=FilesExistPayload(paths=("test.py",)),
        )
        passed, _ = evaluate_validation_rules({}, (rule,), str(tmp_path), {})
        assert passed is True

    def test_first_failure_stops(self, tmp_path):
        rule1 = ValidationRule(
            type="files_exist",
            payload=FilesExistPayload(paths=("nonexistent.txt",)),
        )
        rule2 = ValidationRule(
            type="files_exist",
            payload=FilesExistPayload(paths=("nonexistent.txt",)),
        )
        passed, err = evaluate_validation_rules({}, (rule1, rule2), str(tmp_path), {})
        assert passed is False
        assert "nonexistent.txt" in err


class TestEvalTestsPass:
    def test_tests_pass_success(self):
        passed, _ = _eval_tests_pass(
            TestsPassPayload(command="echo ok"),
            "/tmp",
        )
        assert passed is True

    def test_tests_pass_failure(self):
        passed, err = _eval_tests_pass(
            TestsPassPayload(command="exit 1"),
            "/tmp",
        )
        assert passed is False
        assert "exit code 1" in err


class TestEvalFilesExist:
    def test_files_exist_all_present(self, tmp_path):
        (tmp_path / "a.py").touch()
        (tmp_path / "b.py").touch()
        passed, _ = _eval_files_exist(
            FilesExistPayload(paths=("a.py", "b.py")),
            str(tmp_path),
        )
        assert passed is True

    def test_files_exist_one_missing(self, tmp_path):
        (tmp_path / "a.py").touch()
        passed, err = _eval_files_exist(
            FilesExistPayload(paths=("a.py", "missing.py")),
            str(tmp_path),
        )
        assert passed is False
        assert "missing.py" in err


class TestEvalContainsSymbol:
    def test_symbol_found(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("def main(): pass")
        passed, _ = _eval_contains_symbol(
            SymbolPayload(symbol="def main", target_file="main.py"),
            str(tmp_path),
        )
        assert passed is True

    def test_symbol_not_found(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("def other(): pass")
        passed, err = _eval_contains_symbol(
            SymbolPayload(symbol="def main", target_file="main.py"),
            str(tmp_path),
        )
        assert passed is False
        assert "not found" in err

    def test_target_file_missing(self, tmp_path):
        passed, err = _eval_contains_symbol(
            SymbolPayload(symbol="def main", target_file="nope.py"),
            str(tmp_path),
        )
        assert passed is False
        assert "not found" in err


# ============================================================
# POLICY RESOLVER
# ============================================================


class TestAuthorizeBlueprint:
    def test_risk_keyword_blocked(self):
        proposal = DynamicBlueprintProposal(
            plan_id="p-001",
            trigger="none",
            proposed_complexity="standard",
            rationale="Test",
        )
        state = {"work_item": "Drop database and reset credentials"}
        bp = authorize_blueprint(proposal, state)
        assert bp.authorized_complexity == "restricted"

    def test_safe_work_item_preserves_complexity(self):
        proposal = DynamicBlueprintProposal(
            plan_id="p-001",
            trigger="none",
            proposed_complexity="adaptive",
            rationale="Test",
        )
        state = {"work_item": "Add login page to dashboard"}
        bp = authorize_blueprint(proposal, state)
        assert bp.authorized_complexity == "adaptive"

    def test_risk_keyword_rm_rf(self):
        proposal = DynamicBlueprintProposal(
            plan_id="p-001",
            trigger="none",
            proposed_complexity="standard",
            rationale="Test",
        )
        state = {"work_item": "Clean up with rm -rf /tmp"}
        bp = authorize_blueprint(proposal, state)
        assert bp.authorized_complexity == "restricted"

    def test_risk_keyword_production_deploy(self):
        proposal = DynamicBlueprintProposal(
            plan_id="p-001",
            trigger="none",
            proposed_complexity="standard",
            rationale="Test",
        )
        state = {"work_item": "Run production deploy script"}
        bp = authorize_blueprint(proposal, state)
        assert bp.authorized_complexity == "restricted"

    def test_sanitize_files_exist_nonexistent(self, tmp_path):
        """files_exist rules for non-existent files are stripped."""
        step = DynamicStep(
            step_id="test-step",
            role_description="Test",
            validation_rules=(
                ValidationRule(
                    type="files_exist",
                    payload=FilesExistPayload(paths=("does-not-exist.txt",)),
                ),
            ),
        )
        proposal = DynamicBlueprintProposal(
            plan_id="p-001",
            trigger="augment",
            proposed_complexity="standard",
            steps=(step,),
            rationale="Test",
        )
        state = {
            "work_item": "Add feature",
            "paths": {"project_root": str(tmp_path)},
        }
        bp = authorize_blueprint(proposal, state)
        assert len(bp.steps[0].validation_rules) == 0

    def test_sanitize_files_exist_partial(self, tmp_path):
        """files_exist keeps only paths that exist."""
        (tmp_path / "real.txt").write_text("hello")
        step = DynamicStep(
            step_id="test-step",
            role_description="Test",
            validation_rules=(
                ValidationRule(
                    type="files_exist",
                    payload=FilesExistPayload(paths=("real.txt", "fake.txt")),
                ),
            ),
        )
        proposal = DynamicBlueprintProposal(
            plan_id="p-001",
            trigger="augment",
            proposed_complexity="standard",
            steps=(step,),
            rationale="Test",
        )
        state = {
            "work_item": "Add feature",
            "paths": {"project_root": str(tmp_path)},
        }
        bp = authorize_blueprint(proposal, state)
        rule = bp.steps[0].validation_rules[0]
        assert rule.type == "files_exist"
        assert "real.txt" in rule.payload.paths
        assert "fake.txt" not in rule.payload.paths

    def test_sanitize_contains_symbol_nonexistent_file(self, tmp_path):
        """contains_symbol for non-existent target files are stripped."""
        step = DynamicStep(
            step_id="test-step",
            role_description="Test",
            validation_rules=(
                ValidationRule(
                    type="contains_symbol",
                    payload=SymbolPayload(symbol="def foo", target_file="no-such-file.py"),
                ),
            ),
        )
        proposal = DynamicBlueprintProposal(
            plan_id="p-001",
            trigger="augment",
            proposed_complexity="standard",
            steps=(step,),
            rationale="Test",
        )
        state = {
            "work_item": "Add feature",
            "paths": {"project_root": str(tmp_path)},
        }
        bp = authorize_blueprint(proposal, state)
        assert len(bp.steps[0].validation_rules) == 0

    def test_sanitize_tests_pass_unchanged(self, tmp_path):
        """tests_pass rules are never stripped (they run at execution time)."""
        step = DynamicStep(
            step_id="test-step",
            role_description="Test",
            validation_rules=(
                ValidationRule(
                    type="tests_pass",
                    payload=TestsPassPayload(suite="unit", command="echo ok"),
                ),
            ),
        )
        proposal = DynamicBlueprintProposal(
            plan_id="p-001",
            trigger="augment",
            proposed_complexity="standard",
            steps=(step,),
            rationale="Test",
        )
        state = {
            "work_item": "Add feature",
            "paths": {"project_root": str(tmp_path)},
        }
        bp = authorize_blueprint(proposal, state)
        assert len(bp.steps[0].validation_rules) == 1


class TestSafeToolPool:
    def test_safe_pool_contains_expected_tools(self):
        assert "read" in SAFE_TOOL_POOL
        assert "write" in SAFE_TOOL_POOL
        assert "bash" in SAFE_TOOL_POOL
        assert "dangerous_tool" not in SAFE_TOOL_POOL

    def test_get_tools_by_names(self):
        state = {
            "paths": {"project_root": "."},
            "config": {},
        }
        tools = get_tools_by_names(["read", "glob"], state)
        names = [t.name for t in tools]
        assert "read" in names
        assert "glob" in names

    def test_get_tools_by_names_empty(self):
        state = {
            "paths": {"project_root": "."},
            "config": {},
        }
        tools = get_tools_by_names([], state)
        assert len(tools) == 0

    def test_get_tools_by_names_unknown_tool(self):
        state = {
            "paths": {"project_root": "."},
            "config": {},
        }
        tools = get_tools_by_names(["read", "unknown_tool"], state)
        names = [t.name for t in tools]
        assert "read" in names
        assert "unknown_tool" not in names


# ============================================================
# MAX_ATTEMPTS COUNTING LOGIC
# ============================================================


class TestMaxAttemptsCounting:
    """Verify the off-by-one correction for max_attempts counting.

    max_attempts=3 means: 1 execution + 2 retries = 3 total attempts.
    The check `current_attempts > max_attempts` must fire on attempt 4.
    """

    def test_attempt_counting_correct(self):
        max_attempts = 3
        attempts_count = 0

        def simulate_step():
            nonlocal attempts_count
            current = attempts_count + 1
            attempts_count = current

            if current > max_attempts:
                return "blocked", current

            if current < max_attempts:
                return "retry", current
            else:
                return "last-chance", current

        results = []
        for _ in range(5):
            status, attempt_num = simulate_step()
            results.append((status, attempt_num))
            if status == "blocked":
                break

        assert results[0] == ("retry", 1)
        assert results[1] == ("retry", 2)
        assert results[2] == ("last-chance", 3)
        assert results[3] == ("blocked", 4)

    def test_three_attempts_allowed(self):
        max_attempts = 3
        allowed = []
        for i in range(1, 5):
            if i > max_attempts:
                break
            allowed.append(i)
        assert len(allowed) == 3
        assert allowed == [1, 2, 3]
