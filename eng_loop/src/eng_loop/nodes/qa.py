from __future__ import annotations

import time
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import QaOutput
from eng_loop.tools.evidence_gate import validate_stage_output
from eng_loop.tools.progress import (
    log_model_invoke, log_model_done, log_stage_done, log_stage_fail,
)
from langgraph.types import Command

from eng_loop.templates import load_stage_procedure, get_stage_file


QA_STAGES = {
    "qa.security": "OWASP WSTG",
    "qa.api-contract": "OpenAPI",
    "qa.performance": "performance best practices",
}


def qa_node(stage_id: str):
    def node_fn(state: dict[str, Any]) -> Command[str]:
        from eng_loop.tools.agent_runner import run_agent, AgentResult
        from eng_loop.tools.agent_tools import get_tools_for_stage

        stages = dict(state.get("stages", {}))
        config = state.get("config", {})
        paths = state.get("paths", {})

        if stages.get(stage_id, {}).get("done", False):
            next_node = _resolve_next_qa(stage_id, state)
            return Command(goto=next_node, update={"current_stage": next_node, "iteration": state.get("iteration", 0) + 1})

        max_attempts = config.get("constraints", {}).get(
            f"max_{stage_id.replace('.', '_').replace('-', '_')}_attempts", 2
        )

        if stages[stage_id].get("attempts", 0) >= max_attempts:
            stages[stage_id]["done"] = True
            next_node = _resolve_next_qa(stage_id, state)
            return Command(
                update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} non-convergence"},
                goto=next_node,
            )

        stage_file = get_stage_file(stage_id)
        stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)

        qa_type = QA_STAGES.get(stage_id, "review")

        prompt = f"""You are the {qa_type} QA agent for stage: {stage_id}.

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

## BLUEPRINT
{state.get('stage_artifacts', {}).get('impl.design', '')}

## DIFF
{state.get('stage_artifacts', {}).get('diff', '')}

## PROJECT ROOT
{paths.get('project_root', '.')}

Use your tools to examine the actual code:
- Read source files to inspect implementation
- Use grep to search for security patterns, API endpoints, performance anti-patterns
- Use bash to run security scanners, lint tools, or performance analysis tools
- Use glob to find relevant files

Execute the QA review.
Return a JSON object with these fields: verdict (PASS or FAIL), findings, critical_findings, complete.
"""
        model = create_model_from_config(config, stage_id)

        tools = get_tools_for_stage(stage_id, paths, config)
        max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 20)

        agent_result: AgentResult = run_agent(
            model=model,
            tools=tools,
            prompt=prompt,
            stage_id=stage_id,
            output_schema=QaOutput,
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
                        "errors": list(state.get("errors", [])) + [f"{stage_id} agent error: {agent_result.error}"],
                        "current_stage": stage_id,
                        "iteration": state.get("iteration", 0) + 1,
                    },
                    goto=stage_id.replace(".", "-").replace("_", "-"),
                )
            stages[stage_id]["done"] = True
            next_node = _resolve_next_qa(stage_id, state)
            return Command(
                update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} agent error"},
                goto=next_node,
            )

        # Evidence gate
        is_valid, error_msg = validate_stage_output(stage_id, result, str(result))
        if not is_valid:
            log_stage_fail(stage_id, f"evidence gate: {error_msg}")
            stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
            if stages[stage_id]["attempts"] < max_attempts:
                return Command(
                    update={
                        "stages": stages,
                        "errors": list(state.get("errors", [])) + [f"{stage_id} evidence: {error_msg}"],
                        "current_stage": stage_id,
                        "iteration": state.get("iteration", 0) + 1,
                    },
                    goto=stage_id.replace(".", "-").replace("_", "-"),
                )

        verdict = result.get("verdict", "PASS")
        critical = result.get("critical_findings", [])

        if verdict == "FAIL" or critical:
            stages["impl.code"]["done"] = False
            stages[stage_id]["done"] = False
            stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
            log_stage_fail(stage_id, f"FAIL: {critical}")
            return Command(
                update={
                    "stages": stages,
                    "current_stage": "impl-code",
                    "errors": list(state.get("errors", [])) + [f"{stage_id} FAIL: {critical}"],
                    "iteration": state.get("iteration", 0) + 1,
                },
                goto="impl-code",
            )

        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        stages[stage_id]["done"] = True
        stages[stage_id]["output"] = str(result)
        log_stage_done(stage_id, f"PASS (tools: {agent_result.tool_calls_made})")

        next_node = _resolve_next_qa(stage_id, state)
        return Command(
            update={
                "stages": stages,
                "current_stage": next_node,
                "iteration": state.get("iteration", 0) + 1,
            },
            goto=next_node,
        )

    return node_fn


def _resolve_next_qa(stage_id: str, state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if stage_id == "qa.security":
        if complexity in ("medium", "large", "complex"):
            return "qa-api-contract"
        return "deploy-prepare"
    if stage_id == "qa.api-contract":
        if complexity == "complex":
            return "qa-performance"
        return "deploy-prepare"
    return "deploy-prepare"


def get_qa_nodes() -> list[tuple[str, str]]:
    result = []
    for sid in QA_STAGES:
        node_name = sid.replace(".", "-").replace("_", "-")
        result.append((node_name, sid))
    return result
