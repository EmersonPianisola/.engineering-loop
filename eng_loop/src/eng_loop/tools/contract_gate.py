from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langgraph.types import Command

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContractRule:
    source: str
    target: str
    validator: Callable[[dict[str, Any], dict[str, Any]], tuple[bool, str]]
    on_fail: str = "retry_source"
    description: str = ""


def blueprint_has_tasks(
    source_output: dict[str, Any],
    state: dict[str, Any],
) -> tuple[bool, str]:
    """impl.design → impl.code: Blueprint must contain actionable tasks."""
    tasks = source_output.get("tasks", [])
    if not tasks or len(tasks) == 0:
        return False, "Blueprint has no tasks — impl.code has nothing to implement"

    blueprint = source_output.get("blueprint", "")
    if len(blueprint) < 50:
        return False, f"Blueprint too short ({len(blueprint)} chars) — insufficient guidance for implementation"

    return True, "ok"


def code_exists_for_verify(
    source_output: dict[str, Any],
    state: dict[str, Any],
) -> tuple[bool, str]:
    """impl.code → doc-update: Implementation must have produced artifacts."""
    files = source_output.get("files_created", [])
    if not files:
        return False, "No files created — nothing to verify"

    tests_passed = source_output.get("tests_passed", False)
    if not tests_passed:
        return False, "Tests not passing — cannot verify broken implementation"

    summary = source_output.get("implementation_summary", "")
    if len(summary) < 20:
        return False, "Implementation summary too short — possible incomplete execution"

    return True, "ok"


def implementation_artifacts_exist(
    source_output: dict[str, Any],
    state: dict[str, Any],
) -> tuple[bool, str]:
    """doc-update → verify: impl.code must have produced artifacts (checked via state)."""
    impl_code_output = state.get("stage_artifacts", {}).get("impl.code", "")
    if not impl_code_output:
        stages = state.get("stages", {})
        impl_code_stage = stages.get("impl.code", {})
        if not impl_code_stage.get("done", False):
            return False, "impl.code not completed — nothing to verify"
        impl_code_output = impl_code_stage.get("output", "")

    if not impl_code_output or len(impl_code_output) < 20:
        return False, "No implementation artifacts found — cannot verify"

    return True, "ok"


def architecture_exists_for_review(
    source_output: dict[str, Any],
    state: dict[str, Any],
) -> tuple[bool, str]:
    """arch.solution → arch.review: Both requirements and solution must exist."""
    has_requirements = bool(state.get("stage_artifacts", {}).get("arch.requirements", ""))
    has_solution = bool(source_output.get("architecture_output", ""))

    if not has_requirements:
        return False, "Requirements artifact missing — cannot review architecture without baseline"
    if not has_solution:
        return False, "Solution output empty — nothing to review"

    return True, "ok"


def verify_has_substantive_output(
    source_output: dict[str, Any],
    state: dict[str, Any],
) -> tuple[bool, str]:
    """verify → downstream: Verdict must be explicit with evidence."""
    verdict = source_output.get("verdict", "")
    if verdict not in ("PASS", "FAIL"):
        return False, f"Invalid verdict: {verdict!r} — must be PASS or FAIL"

    if verdict == "PASS":
        evidence = source_output.get("per_ac_evidence", [])
        if not evidence:
            return False, "Verdict is PASS but no per-AC evidence provided"

    return True, "ok"


CONTRACT_RULES: list[ContractRule] = [
    ContractRule(
        source="impl-design",
        target="impl-code",
        validator=blueprint_has_tasks,
        on_fail="retry_source",
        description="Blueprint must have tasks before implementation",
    ),
    ContractRule(
        source="impl-code",
        target="doc-update",
        validator=code_exists_for_verify,
        on_fail="retry_source",
        description="Code must exist before doc update",
    ),
    ContractRule(
        source="doc-update",
        target="verify",
        validator=implementation_artifacts_exist,
        on_fail="retry_source",
        description="Implementation artifacts must exist before verification",
    ),
    ContractRule(
        source="arch-solution",
        target="arch-review",
        validator=architecture_exists_for_review,
        on_fail="block",
        description="Architecture review requires both requirements and solution",
    ),
    ContractRule(
        source="verify",
        target="qa-security",
        validator=verify_has_substantive_output,
        on_fail="retry_source",
        description="Verifier must produce substantive verdict",
    ),
    ContractRule(
        source="verify",
        target="e2e-execute",
        validator=verify_has_substantive_output,
        on_fail="retry_source",
        description="Verifier must produce substantive verdict",
    ),
    ContractRule(
        source="verify",
        target="deploy-prepare",
        validator=verify_has_substantive_output,
        on_fail="retry_source",
        description="Verifier must produce substantive verdict",
    ),
]


def _ensure_dict(value: Any) -> dict[str, Any]:
    """Ensure the value is a dict. Handles:
    - Already a dict → return as-is
    - JSON string → parse with json.loads
    - Python dict repr like {'key': 'value'} → parse with ast.literal_eval
    - Plain string → extract verdict/gaps if present, else wrap in {'output': value}
    """
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}

    # Try JSON first
    try:
        import json

        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Try Python dict repr: {'key': 'value', 'list': [...]}
    stripped = value.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            import ast

            parsed = ast.literal_eval(value)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, SyntaxError, MemoryError):
            pass

    # Fallback: extract verdict/gaps from plain string
    if "FAIL" in value:
        return {"verdict": "FAIL", "output": value}
    if "PASS" in value:
        return {"verdict": "PASS", "output": value}
    return {"output": value}


def check_contract(
    source_node: str,
    target_node: str,
    source_output: dict[str, Any],
    state: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Validate all contract rules for the given source→target edge.

    Returns:
        (action, update_dict) where action is one of:
        - "proceed": all contracts passed, continue to target
        - "retry_source": contract failed, route back to source node
        - "block": contract failed critically, halt pipeline
        - "warn_proceed": minor issue, log and continue
    """
    # Defensive: ensure source_output is a dict
    source_output = _ensure_dict(source_output)

    # Safety: check if source node has exhausted attempts — don't retry infinitely
    stages = state.get("stages", {})
    source_stage_key = source_node.replace("-", ".")
    source_stage = stages.get(source_stage_key, {})
    source_max_attempts = (
        state.get("config", {})
        .get("constraints", {})
        .get(f"max_{source_stage_key.replace('.', '_').replace('-', '_')}_attempts", 2)
    )

    for rule in CONTRACT_RULES:
        if rule.source != source_node or rule.target != target_node:
            continue

        valid, msg = rule.validator(source_output, state)
        if valid:
            continue

        logger.warning(
            "Contract violation [%s→%s]: %s (rule: %s)",
            rule.source,
            rule.target,
            msg,
            rule.description,
        )

        if rule.on_fail == "retry_source":
            # Check if source has exhausted attempts — block instead of infinite retry
            if source_stage.get("attempts", 0) >= source_max_attempts:
                logger.error(
                    "Contract violation [%s→%s]: source exhausted %d attempts, blocking pipeline",
                    rule.source,
                    rule.target,
                    source_max_attempts,
                )
                return "block", {
                    "status": "blocked",
                    "blocking_condition": f"Contract violation {rule.source}→{rule.target} after {source_max_attempts} attempts: {msg}",
                    "errors": [f"Contract violation (max attempts): {msg}"],
                }
            return "retry_source", {
                "errors": [f"Contract {rule.source}→{rule.target}: {msg}"],
                "current_stage": rule.source,
            }
        elif rule.on_fail == "block":
            return "block", {
                "status": "blocked",
                "blocking_condition": f"Contract violation {rule.source}→{rule.target}: {msg}",
                "errors": [f"Contract violation: {msg}"],
            }
        elif rule.on_fail == "warn_proceed":
            logger.warning("Contract warning (proceeding): %s", msg)
            return "proceed", {
                "errors": [f"Contract warning {rule.source}→{rule.target}: {msg}"],
            }

    return "proceed", {}


def contract_gate_middleware(
    source_node: str,
    handler_result: Command[str],
    source_output: dict[str, Any],
    state: dict[str, Any],
) -> Command[str]:
    """Intercept a node's Command result and validate the handoff contract.

    If the contract passes, returns the original Command unchanged.
    If it fails, overrides the Command with retry/block routing.
    """
    target_node = handler_result.goto
    if target_node == "__end__":
        return handler_result

    # Skip validation if node is in "already done" pass-through mode.
    # When a node sees done=True, it returns a minimal Command without
    # stage output in the update. The contract gate should not re-validate
    # output that was already validated on the first successful run.
    stages_in_cmd = handler_result.update.get("stages", {}) if handler_result.update else {}
    stage_key = source_node.replace("-", ".")
    if not source_output and stage_key not in stages_in_cmd and source_node not in stages_in_cmd:
        source_stage = state.get("stages", {}).get(stage_key, {})
        if source_stage.get("done", False) and source_stage.get("output"):
            return handler_result

    action, update = check_contract(source_node, target_node, source_output, state)

    if action == "proceed":
        merged_update = {**handler_result.update, **update} if update else handler_result.update
        return Command(update=merged_update, goto=handler_result.goto)

    if action == "retry_source":
        merged_update = dict(handler_result.update) if handler_result.update else {}
        merged_update.update(update)
        merged_update["iteration"] = state.get("iteration", 0) + 1
        # Reset done flag so the node re-executes instead of short-circuiting
        if "stages" not in merged_update:
            merged_update["stages"] = {}
        stage_id = source_node.replace("-", ".")
        if stage_id in merged_update["stages"]:
            merged_update["stages"][stage_id]["done"] = False
        return Command(update=merged_update, goto=source_node)

    if action == "block":
        # Node already exhausted attempts — pass through its __end__ Command
        # to avoid conflicting state updates (status, blocking_condition)
        if handler_result.update and handler_result.update.get("status") == "blocked":
            return Command(goto="__end__", update=handler_result.update)
        merged_update = dict(handler_result.update) if handler_result.update else {}
        merged_update.update(update)
        return Command(update=merged_update, goto="__end__")

    return handler_result


def with_contract_gate(source_node: str):
    """Decorator that wraps a node handler with contract validation."""
    import functools
    from collections.abc import Callable as C

    def decorator(handler: C[[dict[str, Any]], Command[str]]) -> C[[dict[str, Any]], Any]:
        @functools.wraps(handler)
        def wrapper(state: dict[str, Any]) -> Any:
            result = handler(state)

            # Pass through list[Send] returns (e.g., qa-dispatcher fan-out)
            if isinstance(result, list):
                return result

            cmd: Command[str] = result

            # Extract stage output from the Command's stages update.
            # The stage key can be either node name ("impl-design") or stage ID ("impl.design").
            stage_output = {}
            stages_data = cmd.update.get("stages", {}) if cmd.update else {}

            # Try node name first (e.g., "impl-design")
            if source_node in stages_data:
                stage_output = stages_data[source_node].get("output", {})
            else:
                # Try stage ID format (e.g., "impl.design")
                stage_key = source_node.replace("-", ".")
                if stage_key in stages_data:
                    stage_output = stages_data[stage_key].get("output", {})

            # Fallback: check previous state's stage_artifacts
            if not stage_output:
                stage_artifacts = state.get("stage_artifacts", {})
                stage_key = source_node.replace("-", ".")
                artifact = stage_artifacts.get(stage_key, "")
                if artifact:
                    stage_output = {"output": artifact}

            return contract_gate_middleware(source_node, cmd, stage_output, state)

        return wrapper

    return decorator
