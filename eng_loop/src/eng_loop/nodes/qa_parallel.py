from __future__ import annotations

import logging
from typing import Any

from langgraph.types import Command, Send

from eng_loop.state import rollback_to_stage

logger = logging.getLogger(__name__)

# All QA stages with their metadata
QA_STAGE_DEFINITIONS = [
    {"id": "qa.static", "node": "qa-static", "min_complexity": "small", "qa_type": "deterministic"},
    {"id": "qa.unit", "node": "qa-unit", "min_complexity": "small", "qa_type": "deterministic"},
    {"id": "qa.integration", "node": "qa-integration", "min_complexity": "medium", "qa_type": "deterministic"},
    {"id": "qa.security", "node": "qa-security", "min_complexity": "medium", "qa_type": "deterministic"},
    {"id": "qa.api-contract", "node": "qa-api-contract", "min_complexity": "medium", "qa_type": "deterministic"},
    {"id": "qa.performance", "node": "qa-performance", "min_complexity": "complex", "qa_type": "deterministic"},
    {"id": "qa.human.flow", "node": "qa-human-flow", "min_complexity": "medium", "qa_type": "heuristic"},
    {"id": "qa.human.ux", "node": "qa-human-ux", "min_complexity": "medium", "qa_type": "heuristic"},
]

# Parallel groups — stages that can run concurrently
PARALLEL_GROUPS = {
    "qa-post-e2e": ["qa-security", "qa-performance"],
    "qa-human": ["qa-human-flow", "qa-human-ux"],
}

COMPLEXITY_ORDER = {"small": 0, "medium": 1, "large": 2, "complex": 3}


def _get_active_qa_nodes(state: dict[str, Any]) -> list[str]:
    complexity = state.get("complexity", "small")
    ui_project = state.get("ui_project", False)
    active = []
    for qa_def in QA_STAGE_DEFINITIONS:
        min_c = qa_def["min_complexity"]
        if COMPLEXITY_ORDER.get(complexity, 0) < COMPLEXITY_ORDER.get(min_c, 0):
            continue
        # qa.human.ux requires UI project
        if qa_def["id"] == "qa.human.ux" and not ui_project:
            continue
        active.append(qa_def["node"])
    return active


def qa_dispatcher_node(state: dict[str, Any]) -> Command[str]:
    """Deterministic Fan-Out node.

    Evaluates complexity and dispatches active QA nodes in parallel
    using LangGraph Send API.
    """
    qa_nodes = _get_active_qa_nodes(state)

    if not qa_nodes:
        logger.info("qa_dispatcher: no QA nodes active, routing to deploy-prepare")
        return Command(
            goto="deploy-prepare",
            update={"current_stage": "deploy-prepare", "iteration": state.get("iteration", 0) + 1},
        )

    logger.info(
        "qa_dispatcher: fanning out to %d QA nodes: %s",
        len(qa_nodes),
        qa_nodes,
    )

    # Use Command.goto with list[Send] for parallel fan-out
    # Convert state to plain dict for Send arg compatibility
    plain_state = dict(state)
    return Command(
        goto=[Send(node, plain_state) for node in qa_nodes],
        update={"current_stage": qa_nodes[0], "iteration": state.get("iteration", 0) + 1},
    )


def qa_join_node(state: dict[str, Any]) -> Command[str]:
    """Deterministic Fan-In node.

    Aggregates results from all parallel QA nodes. Applies failure policy:
    - FAIL + critical → rollback to impl.code
    - FAIL + high/medium → repair (re-attempt)
    - FAIL + low/info → continue with warning
    - BLOCKED → retry (never rollback)
    - Heuristic friction above threshold → FAIL
    """
    import json

    stages = dict(state.get("stages", {}))
    qa_nodes = _get_active_qa_nodes(state)
    config = state.get("config", {})
    qa_policy = config.get("qa_policy", {})
    human_policy = qa_policy.get("human", {})
    max_friction = human_policy.get("max_friction_score", 4)
    min_confidence = human_policy.get("min_confidence", 0.70)

    if not qa_nodes:
        return Command(
            goto="deploy-prepare",
            update={
                "current_stage": "deploy-prepare",
                "iteration": state.get("iteration", 0) + 1,
            },
        )

    all_passed = True
    any_blocked = False
    any_critical_fail = False
    all_fix_tasks: list[dict[str, Any]] = []

    for qa_node in qa_nodes:
        # Convert node name to stage ID: qa-security → qa.security, qa-api-contract → qa.api-contract
        # Only replace the first hyphen (after "qa") with a dot
        qa_stage_id = qa_node.replace("-", ".", 1)
        qa_stage = stages.get(qa_stage_id, {})

        # Check verdict from stage metadata first
        verdict = qa_stage.get("verdict", "")
        status = qa_stage.get("status", "")

        if not verdict:
            output_str = qa_stage.get("output", "")
            if output_str:
                try:
                    output_data = json.loads(output_str) if isinstance(output_str, str) else output_str
                    verdict = output_data.get("verdict", "")
                except (json.JSONDecodeError, TypeError):
                    pass
        if not verdict:
            verdict = "PASS" if qa_stage.get("done", False) else "FAIL"

        # BLOCKED: infrastructure issue, don't rollback code
        if status == "blocked" or verdict == "BLOCKED":
            any_blocked = True
            continue

        # Heuristic stages: check friction score
        if qa_stage_id in ("qa.human.flow", "qa.human.ux"):
            output_str = qa_stage.get("output", "{}")
            try:
                output_data = json.loads(output_str) if isinstance(output_str, str) else output_str
            except (json.JSONDecodeError, TypeError):
                output_data = {}

            friction = output_data.get("friction_score", -1)
            confidence = output_data.get("confidence", 0)

            if confidence < min_confidence:
                any_blocked = True
                continue

            if friction > max_friction:
                verdict = "FAIL"
                all_passed = False
                any_critical_fail = True
                all_fix_tasks.append({
                    "source": qa_stage_id,
                    "gap": f"Friction score {friction} exceeds threshold {max_friction}",
                    "evidence": json.dumps(output_data, default=str),
                    "severity": "critical",
                    "suggested_fix": "",
                })

        if verdict == "FAIL":
            all_passed = False
            output_str = qa_stage.get("output", "{}")
            try:
                output_data = json.loads(output_str) if isinstance(output_str, str) else output_str
            except (json.JSONDecodeError, TypeError):
                output_data = {}

            severity = output_data.get("severity", "critical")
            if severity in ("critical", "high"):
                any_critical_fail = True

            gaps = output_data.get("findings", []) + output_data.get("critical_findings", [])
            for gap in gaps:
                all_fix_tasks.append({
                    "source": qa_stage_id,
                    "gap": gap,
                    "evidence": output_data.get("evidence", ""),
                    "severity": severity,
                    "suggested_fix": "",
                })

    # BLOCKED takes priority — halt, don't rollback
    if any_blocked:
        logger.warning("qa_join: one or more QA stages BLOCKED, halting pipeline")
        return Command(
            update={
                "stages": stages,
                "status": "blocked",
                "blocking_condition": "QA stage BLOCKED (infrastructure)",
                "current_stage": "__end__",
                "iteration": state.get("iteration", 0) + 1,
            },
            goto="__end__",
        )

    if not all_passed:
        fix_iteration = state.get("fix_iteration", 0) + 1

        max_fix_iterations = state.get("config", {}).get("constraints", {}).get("max_fix_iterations", 3)
        if fix_iteration > max_fix_iterations:
            logger.error(
                "qa_join: fix iteration limit reached (%d), blocking pipeline",
                max_fix_iterations,
            )
            return Command(
                update={
                    "stages": stages,
                    "status": "blocked",
                    "blocking_condition": f"QA fix iteration limit reached ({max_fix_iterations})",
                    "errors": [f"QA fix iteration limit: {max_fix_iterations}"],
                    "iteration": state.get("iteration", 0) + 1,
                },
                goto="__end__",
            )

        # Critical failure → rollback; low severity → continue with warnings
        if any_critical_fail:
            reset_stages = rollback_to_stage(
                current_stages=stages,
                target_stage="qa-performance",
                reset_from="impl.code",
            )

            logger.warning(
                "qa_join: %d critical QA issues, rolling back to impl.code (fix_iteration=%d)",
                len(all_fix_tasks),
                fix_iteration,
            )

            return Command(
                update={
                    "stages": reset_stages,
                    "current_stage": "impl-code",
                    "rollback_target": "impl.code",
                    "fix_tasks": all_fix_tasks or [{
                        "source": "qa.join",
                        "gap": "QA failure detected",
                        "evidence": "",
                        "severity": "critical",
                        "suggested_fix": "",
                    }],
                    "fix_iteration": fix_iteration,
                    "errors": [f"QA join: {len(all_fix_tasks)} issues from parallel QA"],
                    "iteration": state.get("iteration", 0) + 1,
                },
                goto="impl-code",
            )

    logger.info("qa_join: all QA stages passed, routing to deploy-prepare")

    return Command(
        update={
            "stages": stages,
            "current_stage": "deploy-prepare",
            "iteration": state.get("iteration", 0) + 1,
        },
        goto="deploy-prepare",
    )
