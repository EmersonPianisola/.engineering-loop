from __future__ import annotations

import json
import logging
from typing import Any

from langgraph.types import Command

from eng_loop.model import create_model_from_config
from eng_loop.schemas import QaOutput, get_schema
from eng_loop.tools.evidence_gate import validate_stage_output
from eng_loop.tools.next_active import resolve_next
from eng_loop.tools.node_helpers import build_handoff_update, build_node_prompt
from eng_loop.tools.progress import (
    log_stage_done,
    log_stage_fail,
)

logger = logging.getLogger(__name__)

# All QA stages with their reference documentation
QA_STAGES = {
    "qa.security": "OWASP WSTG",
    "qa.api-contract": "OpenAPI",
    "qa.performance": "performance best practices",
    "qa.static": "ESLint, TypeScript, cyclomatic complexity",
    "qa.unit": "Vitest/Jest unit testing",
    "qa.integration": "OpenAPI + component integration",
    "qa.human.flow": "Persona-based heuristic simulation",
    "qa.human.ux": "WCAG 2.1 AA + cognitive walkthrough",
}

# Heuristic stages use friction_score instead of deterministic PASS/FAIL
HEURISTIC_STAGES = {"qa.human.flow", "qa.human.ux"}


def qa_node(stage_id: str, parallel_mode: bool = False):
    def node_fn(state: dict[str, Any]) -> Command[str]:
        from eng_loop.tools.agent_runner import AgentResult, run_agent
        from eng_loop.tools.agent_tools import get_tools_for_stage
        from eng_loop.tools.stage_gate import run_stage_gate

        stages = dict(state.get("stages", {}))
        config = state.get("config", {})
        paths = state.get("paths", {})
        qa_policy = config.get("qa_policy", {})

        if stages.get(stage_id, {}).get("done", False):
            if parallel_mode:
                return Command(
                    update={"stages": stages},
                    goto="qa-join",
                )
            next_node = _resolve_next_qa(stage_id, state)
            return Command(
                goto=next_node,
                update={"current_stage": next_node, "iteration": state.get("iteration", 0) + 1},
            )

        max_attempts = config.get("constraints", {}).get(
            f"max_{stage_id.replace('.', '_').replace('-', '_')}_attempts", 2
        )

        if stages[stage_id].get("attempts", 0) >= max_attempts:
            stages[stage_id]["done"] = True
            stages[stage_id]["status"] = "blocked"
            if parallel_mode:
                return Command(
                    update={
                        "stages": stages,
                        "status": "blocked",
                        "blocking_condition": f"{stage_id} non-convergence",
                    },
                    goto="qa-join",
                )
            next_node = _resolve_next_qa(stage_id, state)
            return Command(
                update={
                    "stages": stages,
                    "status": "blocked",
                    "blocking_condition": f"{stage_id} non-convergence",
                },
                goto=next_node,
            )

        is_heuristic = stage_id in HEURISTIC_STAGES
        qa_type_label = QA_STAGES.get(stage_id, "review")

        # Build instructions based on stage type
        if is_heuristic:
            human_policy = qa_policy.get("human", {})
            max_friction = human_policy.get("max_friction_score", 4)
            instructions = (
                f"You are a heuristic QA agent evaluating user experience.\n\n"
                f"Assume the persona described in your stage prompt.\n"
                f"Navigate through the system's flows and report friction points.\n\n"
                f"Return a JSON object with:\n"
                f"- verdict (PASS, FAIL, or BLOCKED)\n"
                f"- friction_score (0-10, 0=no friction, 10=unusable)\n"
                f"- confidence (0-1, your confidence in this assessment)\n"
                f"- confusion_points (list of confusing areas)\n"
                f"- jargon_found (list of technical terms exposed to users)\n"
                f"- recommendations (list of improvements)\n"
                f"- findings (list of {qa_type_label} findings)\n"
                f"- complete\n\n"
                f"Friction score > {max_friction} should result in FAIL verdict."
            )
        else:
            instructions = (
                f"Use your tools to examine the actual code.\n\n"
                f"Execute the {qa_type_label} QA review.\n\n"
                f"Return a JSON object with these fields:\n"
                f"- verdict (PASS, FAIL, or BLOCKED)\n"
                f"- findings (list of findings)\n"
                f"- critical_findings (list of critical issues)\n"
                f"- complete\n\n"
                f"BLOCKED means infrastructure prevented testing (not code defect).\n"
                f"FAIL means real defects were found.\n"
                f"PASS means no issues found."
            )

        prompt = build_node_prompt(
            stage_id,
            state,
            paths,
            config,
            role_description=f"{qa_type_label} QA agent",
            include_skill=False,
            instructions=instructions,
        )
        model = create_model_from_config(config, stage_id)

        tools = get_tools_for_stage(stage_id, paths, config, state)
        max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 20)

        # Use stage-specific schema if available, fallback to QaOutput
        output_schema = get_schema(stage_id) or QaOutput

        agent_result: AgentResult = run_agent(
            model=model,
            tools=tools,
            prompt=prompt,
            stage_id=stage_id,
            output_schema=output_schema,
            max_iterations=max_agent_iterations,
            config=config,
        )

        result = agent_result.data

        if agent_result.error:
            log_stage_fail(stage_id, agent_result.error)
            stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
            if stages[stage_id]["attempts"] < max_attempts:
                return Command(
                    update={
                        "stages": stages,
                        "errors": [f"{stage_id} agent error: {agent_result.error}"],
                        "current_stage": stage_id,
                        "iteration": state.get("iteration", 0) + 1,
                    },
                    goto=stage_id.replace(".", "-").replace("_", "-"),
                )
            # Exhausted — mark BLOCKED, not FAIL
            stages[stage_id]["done"] = True
            stages[stage_id]["status"] = "blocked"
            stages[stage_id]["verdict"] = "BLOCKED"
            if parallel_mode:
                return Command(
                    update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} agent error"},
                    goto="qa-join",
                )
            next_node = _resolve_next_qa(stage_id, state)
            return Command(
                update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} agent error"},
                goto=next_node,
            )

        is_valid, error_msg = validate_stage_output(stage_id, result, str(result))
        if not is_valid:
            log_stage_fail(stage_id, f"evidence gate: {error_msg}")
            stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
            if stages[stage_id]["attempts"] < max_attempts:
                return Command(
                    update={
                        "stages": stages,
                        "errors": [f"{stage_id} evidence: {error_msg}"],
                        "current_stage": stage_id,
                        "iteration": state.get("iteration", 0) + 1,
                    },
                    goto=stage_id.replace(".", "-").replace("_", "-"),
                )

        # Run stage gate for policy evaluation
        gate_result = run_stage_gate(stage_id, result, state)

        verdict = result.get("verdict", "PASS")
        critical = result.get("critical_findings", [])

        # Handle BLOCKED verdict — retry, never rollback
        if verdict == "BLOCKED":
            blocked_reason = result.get("blocked_reason", "Infrastructure prevented testing")
            stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
            stages[stage_id]["verdict"] = "BLOCKED"
            stages[stage_id]["status"] = "blocked"
            stages[stage_id]["output"] = json.dumps(result, default=str)
            log_stage_fail(stage_id, f"BLOCKED: {blocked_reason}")

            if stages[stage_id]["attempts"] < max_attempts:
                return Command(
                    update={
                        "stages": stages,
                        "errors": [f"{stage_id} BLOCKED: {blocked_reason}"],
                        "current_stage": stage_id,
                        "iteration": state.get("iteration", 0) + 1,
                    },
                    goto=stage_id.replace(".", "-").replace("_", "-"),
                )
            # Exhausted retries — mark done as blocked
            stages[stage_id]["done"] = True
            if parallel_mode:
                return Command(
                    update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} BLOCKED: {blocked_reason}"},
                    goto="qa-join",
                )
            next_node = _resolve_next_qa(stage_id, state)
            return Command(
                update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} BLOCKED: {blocked_reason}"},
                goto=next_node,
            )

        # Handle FAIL verdict — apply failure policy
        if verdict == "FAIL" or critical:
            stages[stage_id]["done"] = False
            stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
            stages[stage_id]["output"] = json.dumps(result, default=str)
            stages[stage_id]["verdict"] = "FAIL"
            log_stage_fail(stage_id, f"FAIL: {critical}")

            # Apply failure policy action
            action = gate_result.action
            if action == "rollback":
                if parallel_mode:
                    return Command(
                        update={
                            "stages": stages,
                            "iteration": state.get("iteration", 0) + 1,
                        },
                        goto="qa-join",
                    )
                stages["impl.code"]["done"] = False
                return Command(
                    update={
                        "stages": stages,
                        "current_stage": "impl-code",
                        "errors": [f"{stage_id} FAIL: {critical}"],
                        "iteration": state.get("iteration", 0) + 1,
                    },
                    goto="impl-code",
                )
            elif action == "repair":
                # Inline repair — re-attempt with repair context
                if stages[stage_id]["attempts"] < max_attempts:
                    return Command(
                        update={
                            "stages": stages,
                            "errors": [f"{stage_id} repair needed: {critical}"],
                            "current_stage": stage_id,
                            "iteration": state.get("iteration", 0) + 1,
                        },
                        goto=stage_id.replace(".", "-").replace("_", "-"),
                    )
            elif action == "continue":
                # Warning only — proceed
                log_stage_done(stage_id, f"WARNING (proceeding): {critical}")
                stages[stage_id]["done"] = True
                stages[stage_id]["verdict"] = "PASS"
                if parallel_mode:
                    return Command(
                        update={"stages": stages, "iteration": state.get("iteration", 0) + 1},
                        goto="qa-join",
                    )
                handoff_update = build_handoff_update(stage_id, result, state.get("decisions", []), state)
                next_node = _resolve_next_qa(stage_id, state)
                return Command(
                    update={
                        "stages": stages,
                        **handoff_update,
                        "current_stage": next_node,
                        "iteration": state.get("iteration", 0) + 1,
                    },
                    goto=next_node,
                )

            # Default: rollback for deterministic, join for parallel
            if parallel_mode:
                return Command(
                    update={
                        "stages": stages,
                        "iteration": state.get("iteration", 0) + 1,
                    },
                    goto="qa-join",
                )
            stages["impl.code"]["done"] = False
            return Command(
                update={
                    "stages": stages,
                    "current_stage": "impl-code",
                    "errors": [f"{stage_id} FAIL: {critical}"],
                    "iteration": state.get("iteration", 0) + 1,
                },
                goto="impl-code",
            )

        # PASS
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        stages[stage_id]["done"] = True
        stages[stage_id]["output"] = json.dumps(result, default=str)
        stages[stage_id]["verdict"] = "PASS"
        log_stage_done(stage_id, f"PASS (tools: {agent_result.tool_calls_made})")

        if parallel_mode:
            return Command(
                update={
                    "stages": stages,
                    "iteration": state.get("iteration", 0) + 1,
                },
                goto="qa-join",
            )

        handoff_update = build_handoff_update(stage_id, result, state.get("decisions", []), state)
        next_node = _resolve_next_qa(stage_id, state)
        return Command(
            update={
                "stages": stages,
                **handoff_update,
                "current_stage": next_node,
                "iteration": state.get("iteration", 0) + 1,
            },
            goto=next_node,
        )

    return node_fn


def _resolve_next_qa(stage_id: str, state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    ui_project = state.get("ui_project", False)

    # Base of pyramid: static → unit → integration
    if stage_id == "qa.static":
        return resolve_next("qa-unit", state)
    if stage_id == "qa.unit":
        if complexity in ("medium", "large", "complex"):
            return resolve_next("qa-integration", state)
        return resolve_next("e2e-execute", state)
    if stage_id == "qa.integration":
        return resolve_next("e2e-execute", state)

    # E2E → security/performance (parallel capable)
    if stage_id == "e2e.execute":
        if complexity in ("medium", "large", "complex"):
            return resolve_next("qa-security", state)
        return resolve_next("deploy-prepare", state)

    # Post-E2E QA stages
    if stage_id == "qa.security":
        if complexity == "complex":
            return resolve_next("qa-performance", state)
        # Check if human stages should run
        if complexity in ("medium", "large", "complex"):
            if ui_project:
                return resolve_next("qa-human-flow", state)
            return resolve_next("qa-human-flow", state)
        return resolve_next("deploy-prepare", state)

    if stage_id == "qa.api-contract":
        # DEPRECATED: alias for qa.integration
        if complexity == "complex":
            return resolve_next("qa-performance", state)
        return resolve_next("deploy-prepare", state)

    if stage_id == "qa.performance":
        if complexity in ("medium", "large", "complex"):
            if ui_project:
                return resolve_next("qa-human-flow", state)
            return resolve_next("qa-human-flow", state)
        return resolve_next("deploy-prepare", state)

    # Human stages
    if stage_id == "qa.human.flow":
        if ui_project:
            return resolve_next("qa-human-ux", state)
        return resolve_next("deploy-prepare", state)

    if stage_id == "qa.human.ux":
        return resolve_next("deploy-prepare", state)

    return resolve_next("deploy-prepare", state)


def get_qa_nodes() -> list[tuple[str, str]]:
    result = []
    for sid in QA_STAGES:
        node_name = sid.replace(".", "-").replace("_", "-")
        result.append((node_name, sid))
    return result
