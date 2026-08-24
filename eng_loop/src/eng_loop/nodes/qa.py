from __future__ import annotations

import json
import logging
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import QaOutput, get_schema
from eng_loop.tools.essence_gate import essence_gate
from eng_loop.tools.evidence_gate import validate_stage_output
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
    @essence_gate(stage_id)
    def node_fn(state: dict[str, Any]) -> dict[str, Any]:
        from eng_loop.tools.agent_runner import AgentResult, run_agent
        from eng_loop.tools.agent_tools import get_tools_for_stage
        from eng_loop.tools.stage_gate import run_stage_gate

        stages = dict(state.get("stages", {}))
        config = state.get("config", {})
        paths = state.get("paths", {})
        qa_policy = config.get("qa_policy", {})

        if stages.get(stage_id, {}).get("done", False):
            return {}

        max_attempts = config.get("constraints", {}).get(
            f"max_{stage_id.replace('.', '_').replace('-', '_')}_attempts", 2
        )

        if stages[stage_id].get("attempts", 0) >= max_attempts:
            stages[stage_id]["done"] = True
            stages[stage_id]["status"] = "blocked"
            return {
                "stages": {stage_id: stages[stage_id]},
                "status": "blocked",
                "blocking_condition": f"{stage_id} non-convergence",
            }

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
                # No self-retry in fan-out: sibling workers schedule qa-join in
                # the next superstep anyway; a self-goto would race the join.
                return {
                    "stages": {stage_id: stages[stage_id]},
                    "errors": [f"{stage_id} agent error: {agent_result.error}"],
                }
            # Exhausted — mark BLOCKED, not FAIL
            stages[stage_id]["done"] = True
            stages[stage_id]["status"] = "blocked"
            stages[stage_id]["verdict"] = "BLOCKED"
            return {
                "stages": {stage_id: stages[stage_id]},
                "status": "blocked",
                "blocking_condition": f"{stage_id} agent error",
            }

        is_valid, error_msg = validate_stage_output(stage_id, result, str(result))
        if not is_valid:
            log_stage_fail(stage_id, f"evidence gate: {error_msg}")
            stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
            if stages[stage_id]["attempts"] < max_attempts:
                # No self-retry in fan-out — see agent-error path above.
                return {
                    "stages": {stage_id: stages[stage_id]},
                    "errors": [f"{stage_id} evidence: {error_msg}"],
                }

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
                # No self-retry in fan-out — see agent-error path above.
                return {
                    "stages": {stage_id: stages[stage_id]},
                    "errors": [f"{stage_id} BLOCKED: {blocked_reason}"],
                }
            # Exhausted retries — mark done as blocked
            stages[stage_id]["done"] = True
            return {
                "stages": {stage_id: stages[stage_id]},
                "status": "blocked",
                "blocking_condition": f"{stage_id} BLOCKED: {blocked_reason}",
            }

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
                stages["impl.code"]["done"] = False
                return {
                    "stages": {stage_id: stages[stage_id], "impl.code": stages["impl.code"]},
                    "errors": [f"{stage_id} FAIL: {critical}"],
                }
            elif action == "repair":
                # Inline repair — re-attempt with repair context
                if stages[stage_id]["attempts"] < max_attempts:
                    # No self-retry in fan-out — the join applies the failure policy.
                    return {
                        "stages": {stage_id: stages[stage_id]},
                        "errors": [f"{stage_id} repair needed: {critical}"],
                    }
            elif action == "continue":
                # Warning only — proceed
                log_stage_done(stage_id, f"WARNING (proceeding): {critical}")
                stages[stage_id]["done"] = True
                stages[stage_id]["verdict"] = "PASS"
                handoff_update = build_handoff_update(stage_id, result, state.get("decisions", []), state)
                return {
                    "stages": {stage_id: stages[stage_id]},
                    **handoff_update,
                }

            # Default: rollback
            stages["impl.code"]["done"] = False
            return {
                "stages": {stage_id: stages[stage_id], "impl.code": stages["impl.code"]},
                "errors": [f"{stage_id} FAIL: {critical}"],
            }

        # PASS
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        stages[stage_id]["done"] = True
        stages[stage_id]["output"] = json.dumps(result, default=str)
        stages[stage_id]["verdict"] = "PASS"
        log_stage_done(stage_id, f"PASS (tools: {agent_result.tool_calls_made})")

        handoff_update = build_handoff_update(stage_id, result, state.get("decisions", []), state)
        return {
            "stages": {stage_id: stages[stage_id]},
            **handoff_update,
        }

    return node_fn


def get_qa_nodes() -> list[tuple[str, str]]:
    result = []
    for sid in QA_STAGES:
        node_name = sid.replace(".", "-").replace("_", "-")
        result.append((node_name, sid))
    return result
