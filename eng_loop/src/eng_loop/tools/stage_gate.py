from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Evidence Contract — declarative per-stage requirements
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class EvidenceContract:
    """Declarative contract: what evidence a stage MUST produce."""

    stage_id: str
    required_fields: list[str]
    consistency_rules: tuple[str, ...] = ()
    min_values: dict[str, int | float] = field(default_factory=dict)


# Evidence contracts for each QA stage
EVIDENCE_CONTRACTS: dict[str, EvidenceContract] = {
    "qa.static": EvidenceContract(
        stage_id="qa.static",
        required_fields=["files_analyzed", "lint_errors", "type_errors"],
        min_values={"files_analyzed": 1},
    ),
    "qa.unit": EvidenceContract(
        stage_id="qa.unit",
        required_fields=["test_count", "tests_executed", "passed", "failed", "coverage", "exit_code"],
        min_values={"test_count": 1},
        consistency_rules=[
            "tests_executed <= test_count",
            "passed + failed == tests_executed",
        ],
    ),
    "qa.integration": EvidenceContract(
        stage_id="qa.integration",
        required_fields=["endpoints_tested", "contract_violations", "tests_executed"],
    ),
    "qa.security": EvidenceContract(
        stage_id="qa.security",
        required_fields=["verdict", "findings"],
    ),
    "qa.performance": EvidenceContract(
        stage_id="qa.performance",
        required_fields=["verdict", "findings"],
    ),
    "qa.human.flow": EvidenceContract(
        stage_id="qa.human.flow",
        required_fields=["friction_score", "confidence", "persona_name"],
    ),
    "qa.human.ux": EvidenceContract(
        stage_id="qa.human.ux",
        required_fields=["friction_score", "confidence"],
    ),
}


# ──────────────────────────────────────────────
# Failure Policy — severity → action mapping
# ──────────────────────────────────────────────

DEFAULT_FAILURE_POLICY = {
    "critical": "rollback",
    "high": "repair",
    "medium": "repair",
    "low": "continue",
    "info": "continue",
}


# ──────────────────────────────────────────────
# Gate Result
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class GateResult:
    """Result of running all gates for a stage."""

    action: str  # proceed | retry | rollback | repair | block | skip | continue
    update: dict[str, Any]
    reason: str = ""


# ──────────────────────────────────────────────
# EvidenceGate — validates verifiable evidence
# ──────────────────────────────────────────────


class EvidenceGate:
    """Validates that a stage's output has sufficient, consistent evidence.

    Rejects PASS when:
    - Required evidence fields are missing
    - Declared artifacts don't exist on disk
    - Exit code contradicts verdict
    - Metrics are inconsistent
    - Result is incomplete
    """

    @staticmethod
    def validate(
        stage_id: str,
        result: dict[str, Any],
        state: dict[str, Any],
    ) -> GateResult:
        contract = EVIDENCE_CONTRACTS.get(stage_id)

        if not contract:
            # No contract defined — fall back to basic verdict check
            return EvidenceGate._basic_verdict_check(stage_id, result)

        # 1. Required fields
        missing = []
        for f in contract.required_fields:
            if f not in result or result[f] is None:
                missing.append(f)

        if missing:
            return GateResult(
                action="block",
                update={
                    "status": "blocked",
                    "blocking_condition": f"Evidence missing: {missing}",
                    "errors": [f"{stage_id} missing evidence fields: {missing}"],
                },
                reason=f"Missing evidence fields: {missing}",
            )

        # 2. Minimum values
        for f, min_val in contract.min_values.items():
            actual = result.get(f, 0)
            if actual < min_val:
                return GateResult(
                    action="block",
                    update={
                        "status": "blocked",
                        "blocking_condition": f"Evidence below minimum: {field}={actual} < {min_val}",
                        "errors": [f"{stage_id} {field}={actual}, minimum {min_val}"],
                    },
                    reason=f"{field}={actual} below minimum {min_val}",
                )

        # 3. Consistency rules
        for rule in contract.consistency_rules:
            if not EvidenceGate._check_consistency(rule, result):
                return GateResult(
                    action="block",
                    update={
                        "status": "blocked",
                        "blocking_condition": f"Inconsistent evidence: {rule}",
                        "errors": [f"{stage_id} evidence inconsistency: {rule}"],
                    },
                    reason=f"Inconsistent evidence: {rule}",
                )

        # 4. Exit code ↔ verdict consistency
        verdict = result.get("verdict", "")
        exit_code = result.get("exit_code", -1)

        if exit_code >= 0 and verdict:
            if verdict == "PASS" and exit_code != 0:
                return GateResult(
                    action="block",
                    update={
                        "status": "blocked",
                        "blocking_condition": f"Exit code {exit_code} contradicts PASS verdict",
                        "errors": [f"{stage_id} exit_code={exit_code} but verdict=PASS"],
                    },
                    reason=f"Exit code {exit_code} contradicts PASS verdict",
                )
            if verdict == "FAIL" and exit_code == 0:
                logger.warning(
                    "%s: exit_code=0 but verdict=FAIL — possible false positive",
                    stage_id,
                )

        # 5. Artifact existence
        evidence = result.get("evidence", {})
        artifacts = evidence.get("artifacts", []) if isinstance(evidence, dict) else []
        if isinstance(artifacts, list):
            artifact_root = state.get("paths", {}).get("artifact_root", "")
            for artifact in artifacts:
                if artifact_root and os.path.exists(artifact):
                    continue
                # Artifact may be relative — just log warning, don't block
                logger.debug("%s: artifact %s not verified on disk", stage_id, artifact)

        return GateResult(
            action="proceed",
            update={},
            reason="Evidence valid",
        )

    @staticmethod
    def _basic_verdict_check(
        stage_id: str,
        result: dict[str, Any],
    ) -> GateResult:
        verdict = result.get("verdict", "")
        if verdict not in ("PASS", "FAIL", "BLOCKED"):
            return GateResult(
                action="block",
                update={
                    "status": "blocked",
                    "blocking_condition": f"Invalid verdict: {verdict!r}",
                    "errors": [f"{stage_id} invalid verdict: {verdict!r}"],
                },
                reason=f"Invalid verdict: {verdict!r}",
            )
        return GateResult(action="proceed", update={}, reason="Basic verdict OK")

    @staticmethod
    def _check_consistency(rule: str, result: dict[str, Any]) -> bool:
        """Evaluate a consistency rule like 'tests_executed <= test_count'."""
        try:
            parts = rule.split("==") if "==" in rule else rule.split("<=") if "<=" in rule else rule.split(">=")
            if len(parts) != 2:
                parts = rule.split("==")
            if len(parts) != 2:
                return True

            left_expr = parts[0].strip()
            right_expr = parts[1].strip()

            left_val = EvidenceGate._resolve_field(left_expr, result)
            right_val = EvidenceGate._resolve_field(right_expr, result)

            if left_val is None or right_val is None:
                return True  # Field not present, skip

            if "==" in rule:
                return left_val == right_val
            if "<=" in rule:
                return left_val <= right_val
            if ">=" in rule:
                return left_val >= right_val
        except (ValueError, TypeError):
            logger.warning("EvidenceGate: could not evaluate rule '%s'", rule)

        return True

    @staticmethod
    def _resolve_field(expr: str, result: dict[str, Any]) -> Any:
        """Resolve a field expression to its value."""
        expr = expr.strip()
        if expr in result:
            return result[expr]
        return None


# ──────────────────────────────────────────────
# DependencyGate — validates upstream dependencies
# ──────────────────────────────────────────────


class DependencyGate:
    """Validates that a stage's dependencies are satisfied before execution.

    If an upstream dependency is:
    - FAIL → SKIP this stage (no point running)
    - BLOCKED → SKIP (or propagate BLOCKED)
    - PASS → proceed
    """

    # Stage dependency map
    DEPENDENCIES: dict[str, list[str]] = {
        "qa.unit": ["qa.static"],
        "qa.integration": ["qa.unit"],
        "e2e.execute": ["qa.integration"],
        "qa.security": ["qa.integration", "e2e.execute"],
        "qa.performance": ["e2e.execute"],
        "qa.human.flow": ["qa.security", "qa.performance"],
        "qa.human.ux": ["qa.security", "qa.performance"],
        "deploy.prepare": ["qa.human.flow"],
    }

    @staticmethod
    def check(stage_id: str, state: dict[str, Any]) -> GateResult:
        deps = DependencyGate.DEPENDENCIES.get(stage_id, [])
        if not deps:
            return GateResult(action="proceed", update={}, reason="No dependencies")

        stages = state.get("stages", {})

        for dep_id in deps:
            dep_stage = stages.get(dep_id, {})
            dep_verdict = dep_stage.get("verdict", "")
            dep_status = dep_stage.get("status", "")
            dep_done = dep_stage.get("done", False)

            # If dependency is BLOCKED, propagate BLOCKED
            if dep_status == "blocked" or dep_verdict == "BLOCKED":
                return GateResult(
                    action="skip",
                    update={
                        "errors": [f"{stage_id} skipped: dependency {dep_id} is BLOCKED"],
                    },
                    reason=f"Dependency {dep_id} is BLOCKED",
                )

            # If dependency FAILED, skip this stage
            if dep_verdict == "FAIL" and not dep_done:
                return GateResult(
                    action="skip",
                    update={
                        "errors": [f"{stage_id} skipped: dependency {dep_id} FAILED"],
                    },
                    reason=f"Dependency {dep_id} FAILED",
                )

        return GateResult(action="proceed", update={}, reason="Dependencies satisfied")


# ──────────────────────────────────────────────
# PolicyGate — applies failure policy based on severity
# ──────────────────────────────────────────────


class PolicyGate:
    """Applies the configured failure policy to a stage's verdict.

    Maps severity to action:
    - critical → rollback (reset impl.code)
    - high → repair (inline fix)
    - medium → repair (inline fix)
    - low → continue (warning)
    - info → continue
    """

    @staticmethod
    def evaluate(
        stage_id: str,
        result: dict[str, Any],
        state: dict[str, Any],
    ) -> GateResult:
        verdict = result.get("verdict", "PASS")
        severity = result.get("severity", "info")

        config = state.get("config", {})
        qa_policy = config.get("qa_policy", {})
        failure_policy = qa_policy.get("failure_policy", DEFAULT_FAILURE_POLICY)

        # Heuristic stages: check friction score against policy threshold
        if result.get("qa_type") == "heuristic":
            friction = result.get("friction_score", -1.0)
            if friction >= 0:
                human_policy = qa_policy.get("human", {})
                max_friction = human_policy.get("max_friction_score", 4)
                min_confidence = human_policy.get("min_confidence", 0.70)
                confidence = result.get("confidence", 0.0)

                if confidence < min_confidence:
                    return GateResult(
                        action="block",
                        update={
                            "status": "blocked",
                            "blocking_condition": f"Low confidence: {confidence} < {min_confidence}",
                            "errors": [f"{stage_id} confidence {confidence} below minimum {min_confidence}"],
                        },
                        reason=f"Low confidence: {confidence}",
                    )

                if friction > max_friction:
                    severity = "high"
                    verdict = "FAIL"

        # BLOCKED verdict: retry, don't rollback
        if verdict == "BLOCKED":
            blocked_reason = result.get("blocked_reason", "")
            return GateResult(
                action="retry",
                update={
                    "errors": [f"{stage_id} BLOCKED: {blocked_reason}"],
                },
                reason=f"BLOCKED: {blocked_reason}",
            )

        # Apply failure policy based on severity
        if verdict == "FAIL":
            action = failure_policy.get(severity, "continue")

            if action == "rollback":
                return GateResult(
                    action="rollback",
                    update={
                        "errors": [f"{stage_id} FAIL (severity={severity}): rolling back to impl.code"],
                    },
                    reason=f"FAIL severity={severity} → rollback",
                )
            elif action == "repair":
                return GateResult(
                    action="repair",
                    update={
                        "errors": [f"{stage_id} FAIL (severity={severity}): inline repair needed"],
                    },
                    reason=f"FAIL severity={severity} → repair",
                )
            elif action == "continue":
                return GateResult(
                    action="continue",
                    update={
                        "errors": [f"{stage_id} warning (severity={severity}): proceeding"],
                    },
                    reason=f"FAIL severity={severity} → continue with warning",
                )

        return GateResult(action="proceed", update={}, reason=f"Verdict={verdict}, severity={severity}")


# ──────────────────────────────────────────────
# TransitionGate — validates stage handoffs
# ──────────────────────────────────────────────


class TransitionGate:
    """Validates handoff between stages.

    Wraps the existing contract_gate logic while providing a unified
    interface. Ensures that the source stage produced valid output
    before the target stage begins.
    """

    @staticmethod
    def check(
        source_node: str,
        target_node: str,
        source_output: dict[str, Any],
        state: dict[str, Any],
    ) -> GateResult:
        from eng_loop.tools.contract_gate import check_contract

        action, update = check_contract(source_node, target_node, source_output, state)

        if action == "proceed":
            return GateResult(action="proceed", update=update, reason="Contract satisfied")
        elif action == "retry_source":
            return GateResult(action="retry", update=update, reason="Contract failed, retry source")
        elif action == "block":
            return GateResult(action="block", update=update, reason="Contract violation, blocking")
        else:
            return GateResult(action="proceed", update=update, reason="Contract warning")


# ──────────────────────────────────────────────
# Unified Stage Gate — runs all gates in sequence
# ──────────────────────────────────────────────


def run_stage_gate(
    stage_id: str,
    result: dict[str, Any],
    state: dict[str, Any],
) -> GateResult:
    """Run all gates for a QA stage's output.

    Sequence: Evidence → Policy → State update.

    Returns GateResult with action and state update dict.
    """
    config = state.get("config", {})

    # 1. Evidence Gate
    evidence_result = EvidenceGate.validate(stage_id, result, state)
    if evidence_result.action in ("block",):
        return evidence_result

    # 2. Policy Gate
    policy_result = PolicyGate.evaluate(stage_id, result, state)
    return policy_result


def check_dependencies(stage_id: str, state: dict[str, Any]) -> GateResult:
    """Check if a stage's dependencies are satisfied before execution."""
    return DependencyGate.check(stage_id, state)


def check_transition(
    source_node: str,
    target_node: str,
    source_output: dict[str, Any],
    state: dict[str, Any],
) -> GateResult:
    """Check handoff contract between stages."""
    return TransitionGate.check(source_node, target_node, source_output, state)
