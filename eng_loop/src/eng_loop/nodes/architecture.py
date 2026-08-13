from __future__ import annotations

import time
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import ArchOutput
from eng_loop.tools.node_helpers import build_node_prompt, build_handoff_update
from eng_loop.tools.progress import (
    log_model_invoke, log_model_done, log_stage_done, log_stage_fail, log_artifact,
)
from langgraph.types import Command

from eng_loop.templates import load_skill, load_stage_procedure, get_stage_file, get_skill_name
from eng_loop.tools.next_active import resolve_next


ARCH_STAGES = {
    "arch.requirements": "requirements-refiner",
    "arch.solution": "solution-designer",
    "arch.review": "architecture-reviewer",
}

ARCH_NEXT_MAP = {
    "arch.requirements": "arch-solution",
    "arch.solution": "_arch_post_solution",
    "arch.review": "impl-design",
}


def arch_node(stage_id: str):
    def node_fn(state: dict[str, Any]) -> Command[str]:
        from eng_loop.tools.agent_runner import run_agent, AgentResult
        from eng_loop.tools.agent_tools import get_tools_for_stage

        stages = dict(state.get("stages", {}))
        config = state.get("config", {})
        paths = state.get("paths", {})

        if stages.get(stage_id, {}).get("done", False):
            next_node = _resolve_next(stage_id, state)
            return Command(goto=next_node, update={"current_stage": next_node, "iteration": state.get("iteration", 0) + 1})

        max_attempts = config.get("constraints", {}).get(
            f"max_{stage_id.replace('.', '_').replace('-', '_')}_attempts", 2
        )

        if stages[stage_id].get("attempts", 0) >= max_attempts:
            stages[stage_id]["done"] = True
            next_node = _resolve_next(stage_id, state)
            return Command(
                update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} non-convergence"},
                goto=next_node,
            )

        context = _build_arch_context(stage_id, state)

        prompt = build_node_prompt(
            stage_id, state, paths, config,
            role_description=f"Architecture agent",
            extra_sections=context if context else "",
            instructions=(
                "Use your tools to explore the codebase for architectural context:\n"
                "1. **graphify_query** for high-level architecture understanding\n"
                "2. **graphify_explain** for specific entities\n"
                "3. **graphify_path** to trace connections between components\n"
                "4. Then use read, glob, grep for file-level details\n\n"
                "Execute the architecture task.\n"
                "Return a JSON object with these fields: architecture_output, complete, decisions, critical_findings."
            ),
        )
        model = create_model_from_config(config, stage_id)

        tools = get_tools_for_stage(stage_id, paths, config, state)
        max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 20)

        agent_result: AgentResult = run_agent(
            model=model,
            tools=tools,
            prompt=prompt,
            stage_id=stage_id,
            output_schema=ArchOutput,
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
            next_node = _resolve_next(stage_id, state)
            return Command(
                update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} agent error"},
                goto=next_node,
            )

        critical_findings = result.get("critical_findings", [])
        if critical_findings and stage_id == "arch.review":
            stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
            log_stage_fail(stage_id, f"critical findings: {critical_findings}")
            return Command(
                update={
                    "stages": stages,
                    "current_stage": "arch-requirements",
                    "iteration": state.get("iteration", 0) + 1,
                },
                goto="arch-requirements",
            )

        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        stages[stage_id]["done"] = True
        stages[stage_id]["output"] = str(result)

        artifact_root = paths.get("artifact_root", "")
        arch_output = result.get("architecture_output", "")
        if arch_output:
            from eng_loop.tools.file_ops import write_file
            safe_name = stage_id.replace(".", "-").replace("_", "-")
            artifact_path = f"{artifact_root}/architectures/{safe_name}.md"
            write_file(artifact_path, arch_output)
            log_artifact(stage_id, artifact_path)

        new_decisions = list(state.get("decisions", []))
        for d in result.get("decisions", []):
            from eng_loop.tools.decisions import record_decision
            record_decision({"decisions": new_decisions}, d)

        next_node = _resolve_next(stage_id, state)
        log_stage_done(stage_id, f"output: {len(arch_output)} chars, tools: {agent_result.tool_calls_made}")

        handoff_update = build_handoff_update(stage_id, result, new_decisions, state)

        return Command(
            update={
                "stages": stages,
                "decisions": new_decisions,
                "stage_artifacts": {**state.get("stage_artifacts", {}), stage_id: arch_output},
                **handoff_update,
                "current_stage": next_node,
                "iteration": state.get("iteration", 0) + 1,
            },
            goto=next_node,
        )

    return node_fn


def _build_arch_context(stage_id: str, state: dict[str, Any]) -> str:
    artifacts = state.get("stage_artifacts", {})
    parts = []
    if stage_id in ("arch.solution", "arch.review"):
        req = artifacts.get("arch.requirements", "")
        if req:
            parts.append(f"## Requirements\n{req}")
    if stage_id == "arch.review":
        sol = artifacts.get("arch.solution", "")
        if sol:
            parts.append(f"## Solution\n{sol}")
    return "\n".join(parts) if parts else "No prior architecture artifacts."


def _resolve_next(stage_id: str, state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if stage_id == "arch.solution":
        if complexity == "complex":
            return resolve_next("arch-review", state)
        return resolve_next("impl-design", state)
    if stage_id == "arch.review":
        return resolve_next("impl-design", state)
    intended = ARCH_NEXT_MAP.get(stage_id, "impl-design")
    if intended.startswith("_"):
        intended = "impl-design"
    return resolve_next(intended, state)


def get_arch_nodes() -> list[tuple[str, str]]:
    result = []
    for sid in ARCH_STAGES:
        node_name = sid.replace(".", "-").replace("_", "-")
        result.append((node_name, sid))
    return result
