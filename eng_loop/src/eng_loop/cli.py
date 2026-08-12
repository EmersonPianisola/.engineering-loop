from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from eng_loop.config import load_config, resolve_paths, ensure_directories
from eng_loop.state import make_initial_state, load_state_template, STAGE_ORDER
from eng_loop.graph import compile_graph
from eng_loop.tools.file_ops import save_json as save_json_file
from eng_loop.tools.progress import log_iteration
from eng_loop.model import create_model_from_config, DEFAULT_BASE_URL, DEFAULT_MODEL


def main():
    parser = argparse.ArgumentParser(description="Engineering Loop Orchestrator (LangGraph)")
    parser.add_argument("--work-item", "-w", type=str, default="", help="Work item description")
    parser.add_argument("--framework-root", "-f", type=str, default=".", help="Framework root directory")
    parser.add_argument("--loop-root", "-l", type=str, default=".", help="Loop root directory (submodule)")
    parser.add_argument("--project-root", "-p", type=str, default=".", help="Project root directory")
    parser.add_argument("--state-file", "-s", type=str, default=None, help="State file path (for resume)")
    parser.add_argument("--model-base-url", type=str, default=None, help="Model base URL (overrides config)")
    parser.add_argument("--model-name", type=str, default=None, help="Model name (overrides config)")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and exit")
    parser.add_argument("--check-model", action="store_true", help="Check model connectivity and exit")
    parser.add_argument("--dynamic-graph", action="store_true", help="Use dynamic graph construction (v11)")
    parser.add_argument("--parallel-qa", action="store_true", help="Run QA stages in parallel (requires --dynamic-graph)")
    parser.add_argument("--build-topology", action="store_true", help="Build dynamic graph topology and output as markdown (for LLM orchestrator)")
    parser.add_argument("--opencode-agent", action="store_true", help="Use opencode CLI as agent backend (Python controls graph, opencode executes with native tools)")
    parser.add_argument("--check-compliance", action="store_true", help="Validate stage transition against topology (for LLM orchestrator)")
    parser.add_argument("--requested-stage", type=str, default="", help="Stage ID to validate (required with --check-compliance)")
    args = parser.parse_args()

    framework_root = Path(args.framework_root).resolve()
    loop_root = Path(args.loop_root).resolve()
    project_root = Path(args.project_root).resolve()

    config = load_config(framework_root, loop_root)
    paths = resolve_paths(config, framework_root, loop_root, project_root)
    ensure_directories(paths)

    # Set agent backend env var for hybrid mode
    if args.opencode_agent:
        os.environ["ENG_AGENT_BACKEND"] = "opencode"
    elif config.get("agent", {}).get("backend", "langchain") == "opencode":
        os.environ["ENG_AGENT_BACKEND"] = "opencode"

    # Apply CLI overrides
    if args.model_base_url:
        config.setdefault("model", {})["base_url"] = args.model_base_url
    if args.model_name:
        config.setdefault("model", {})["model"] = args.model_name

    if args.check_model:
        _check_model(config)
        return

    if args.dry_run:
        print(json.dumps({"config": config, "paths": paths}, indent=2, default=str))
        return

    if args.build_topology:
        _build_topology(args.work_item, config, paths)
        return

    if args.check_compliance:
        _check_compliance(args, paths)
        return

    # Validate model connectivity before starting
    if not _check_model(config, quiet=True):
        print("\n[warn] Model connectivity check failed.")
        print(f"       Check that {config.get('model', {}).get('base_url', DEFAULT_BASE_URL)} is running.")
        print("       Use --check-model for details.")
        response = input("Continue anyway? [y/N]: ")
        if response.lower() != "y":
            sys.exit(1)

    state = make_initial_state(config, paths)
    state["work_item"] = args.work_item

    if args.state_file and Path(args.state_file).exists():
        saved = load_state_template(args.state_file)
        state.update(saved)

    # Determine graph mode
    dynamic_graph = args.dynamic_graph or config.get("dynamic_graph", {}).get("enabled", False)
    parallel_qa = args.parallel_qa or config.get("dynamic_graph", {}).get("parallel_qa", False)

    if dynamic_graph:
        if parallel_qa:
            print("Mode: Dynamic graph + parallel QA")
        else:
            print("Mode: Dynamic graph")
        if args.opencode_agent:
            print("Agent backend: opencode (hybrid mode)")

        from eng_loop.graph_builder import GraphBuilder
        graph_builder = GraphBuilder(parallel_qa=parallel_qa)
        compiled, topology = graph_builder.compile(state, config)
        graph = compiled

        state["graph_topology"] = topology.to_dict()
        state["active_nodes"] = topology.active_nodes

        print(f"Graph: {topology.nodes_included}/{topology.total_available} nodes active")
        print(f"Active: {', '.join(topology.active_nodes)}")
    else:
        print("Mode: Static graph (legacy)")
        graph = compile_graph(config=config)

    thread_config = {"configurable": {"thread_id": "eng-loop-run"}}

    model_info = config.get("model", {})
    print(f"Starting Engineering Loop...")
    print(f"Work item: {args.work_item}")
    print(f"Model: {model_info.get('model', DEFAULT_MODEL)} @ {model_info.get('base_url', DEFAULT_BASE_URL)}")
    print(f"Complexity: will be auto-sized")
    print()

    try:
        prev_stage = ""
        for event in graph.stream(state, config=thread_config, stream_mode="values"):
            status = event.get("status", "running")
            current = event.get("current_stage", "")
            iteration = event.get("iteration", 0)

            if current and current != prev_stage:
                log_iteration(iteration, current)
                _print_progress_bar(event)
                _save_state(event, paths)
                prev_stage = current

            if status not in ("running",):
                log_iteration(iteration, current or "complete")

        final_state = event
        _print_result(final_state)
        _save_state(final_state, paths, verbose=True)
    except KeyboardInterrupt:
        state["status"] = "halted"
        state["blocking_condition"] = "user interrupted"
        _save_state(state, paths, verbose=True)
        print("\nLoop halted by user.")
        sys.exit(130)
    except Exception as e:
        state["status"] = "halted"
        state["blocking_condition"] = str(e)
        _save_state(state, paths, verbose=True)
        print(f"\nLoop halted: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def _build_topology(work_item: str, config: dict[str, Any], paths: dict[str, str]) -> None:
    """Build dynamic graph topology and output as markdown for LLM orchestrator."""
    from eng_loop.tools.autosizing import classify_complexity, classify_work_type, detect_ui_project
    from eng_loop.graph_builder import GraphBuilder

    # Classify from work item
    complexity = classify_complexity(work_item, config)
    work_type = classify_work_type(work_item)
    ui_project = detect_ui_project(paths)

    # Build state for graph builder
    state = make_initial_state(config, paths)
    state["work_item"] = work_item
    state["complexity"] = complexity
    state["work_type"] = work_type
    state["ui_project"] = ui_project

    parallel_qa = config.get("dynamic_graph", {}).get("parallel_qa", False)
    builder = GraphBuilder(parallel_qa=parallel_qa)
    _, topology = builder.build(state)

    # Generate markdown output
    md = _topology_to_markdown(topology, work_item, complexity, work_type, ui_project, config)

    # Save to file
    topology_file = paths.get("artifact_root", "artifacts") + "/graph-topology.md"
    from eng_loop.tools.file_ops import write_file
    write_file(topology_file, md)

    # Save JSON too
    topology_json = paths.get("artifact_root", "artifacts") + "/graph-topology.json"
    save_json_file(topology_json, topology.to_dict())

    print(md)
    print(f"\nTopology saved to: {topology_file}")
    print(f"JSON saved to: {topology_json}")


def _topology_to_markdown(
    topology: "GraphTopology",
    work_item: str,
    complexity: str,
    work_type: str,
    ui_project: bool,
    config: dict[str, Any],
) -> str:
    """Convert graph topology to markdown instructions for LLM orchestrator."""
    from eng_loop.state import STAGE_ORDER, STAGE_MIN_COMPLEXITY, get_active_stages
    from eng_loop.tools.autosizing import OPERATIONAL_EXCLUDED_STAGES

    lines = []
    lines.append("# DYNAMIC GRAPH TOPOLOGY — GENERATED EXECUTION PLAN")
    lines.append("")
    lines.append("> **This graph was built by the framework based on your work item.**")
    lines.append("> **You MUST follow this execution plan. Do not skip stages, do not change order.**")
    lines.append("> **Routing is deterministic — follow the edges as defined.**")
    lines.append("> **Before each stage, run `eng-loop --check-compliance --requested-stage <stage>` to validate.**")
    lines.append("")
    lines.append("## Context")
    lines.append(f"- **Work Item:** {work_item}")
    lines.append(f"- **Complexity:** {complexity}")
    lines.append(f"- **Work Type:** {work_type}")
    lines.append(f"- **UI Project:** {ui_project}")
    lines.append(f"- **Active Nodes:** {topology.nodes_included}/{topology.total_available}")
    lines.append("")

    # Work type explanation
    work_type_descriptions = {
        "feature": "New functionality — full loop (design, architecture, implementation, verification, QA, deploy)",
        "bugfix": "Fix existing behavior — skips design stages, keeps implementation + verification",
        "operational": "Run existing code (tests, deploys) — skips implementation, design, architecture",
    }
    lines.append(f"**Work Type: {work_type}** — {work_type_descriptions.get(work_type, '')}")
    lines.append("")

    # Active stages
    lines.append("## ACTIVE STAGES (execute in this order)")
    lines.append("")
    lines.append("| # | Stage ID | Phase | Description |")
    lines.append("|---|----------|-------|-------------|")

    phase_labels = {
        "init": "INIT", "design": "DESIGN", "arch": "ARCH",
        "impl": "IMPL", "verify": "VERIFY", "qa": "QA",
        "deploy": "DEPLOY", "doc": "DOC", "post": "POST",
    }

    for i, node_id in enumerate(topology.active_nodes, 1):
        min_c = STAGE_MIN_COMPLEXITY.get(node_id, "small")
        phase = ""
        for phase_id, label in phase_labels.items():
            if node_id.startswith(phase_id):
                phase = label
                break
        lines.append(f"| {i} | `{node_id}` | {phase} | min: {min_c} |")

    lines.append("")

    # Routing rules
    lines.append("## ROUTING RULES (deterministic)")
    lines.append("")
    lines.append("After each stage completes, determine the next stage:")
    lines.append("")

    # Build routing from edges
    edges_by_source: dict[str, list[dict]] = {}
    for edge in topology.edges:
        edges_by_source.setdefault(edge["from"], []).append(edge)

    # Key routing decisions
    lines.append("### Post-Init-Refine")
    lines.append(f"- IF complexity >= `medium` → `arch.requirements`")
    lines.append(f"- ELSE → `impl.design`")
    lines.append("")

    lines.append("### Post-Verify (PASS)")
    if ui_project:
        lines.append(f"- → `e2e.execute` (UI project)")
    else:
        lines.append(f"- IF complexity >= `medium` → `qa.security`")
    lines.append(f"- IF complexity == `small` → `deploy.prepare`")
    lines.append("")

    lines.append("### Post-E2E (PASS)")
    lines.append(f"- IF complexity >= `medium` → `qa.security`")
    lines.append(f"- ELSE → `deploy.prepare`")
    lines.append("")

    lines.append("### QA Chain")
    lines.append(f"- `qa.security` PASS → `qa.api-contract` (if medium+) or `deploy.prepare`")
    lines.append(f"- `qa.api-contract` PASS → `qa.performance` (if complex) or `deploy.prepare`")
    lines.append(f"- `qa.performance` PASS → `deploy.prepare`")
    lines.append(f"- Any QA FAIL → `impl.code` (RESET)")
    lines.append("")

    lines.append("### Post-Deploy (PASS)")
    if ui_project:
        lines.append(f"- → `smoke.test` (UI project)")
    lines.append(f"- IF complexity >= `medium` → `doc.decisions`")
    lines.append(f"- ELSE → `post`")
    lines.append("")

    lines.append("### FAIL ROUTING (any stage with verdict)")
    lines.append(f"- `verify` FAIL → `impl.code` (RESET)")
    lines.append(f"- `e2e.execute` FAIL → `impl.code` (RESET)")
    lines.append(f"- `qa.*` FAIL → `impl.code` (RESET)")
    lines.append(f"- `deploy.prepare` FAIL → `impl.code` (RESET)")
    lines.append(f"- `smoke.test` FAIL → `impl.code` (RESET)")
    lines.append("")

    # Parallel groups
    if topology.parallel_groups:
        lines.append("## PARALLEL GROUPS")
        lines.append("")
        for group_name, members in topology.parallel_groups.items():
            lines.append(f"### {group_name}")
            for m in members:
                lines.append(f"- `{m}`")
            lines.append("")

    # Constraints
    constraints = config.get("constraints", {})
    lines.append("## CONSTRAINTS")
    lines.append("")
    lines.append("| Stage | Max Attempts |")
    lines.append("|-------|-------------|")
    for stage_id in topology.active_nodes:
        key = f"max_{stage_id.replace('.', '_').replace('-', '_')}_attempts"
        max_att = constraints.get(key, 2)
        lines.append(f"| `{stage_id}` | {max_att} |")

    lines.append("")

    # Deactivated stages
    all_stages = get_active_stages(complexity, ui_project, "feature")
    deactivated = [s for s in STAGE_ORDER if s not in topology.active_nodes]
    if deactivated:
        lines.append("## DEACTIVATED STAGES (auto-sizing)")
        lines.append("")
        for s in deactivated:
            min_c = STAGE_MIN_COMPLEXITY.get(s, "small")
            reason = ""
            if s in OPERATIONAL_EXCLUDED_STAGES and work_type == "operational":
                reason = "excluded for operational work"
            elif s in ("design.user-research", "design.personas", "design.info-arch",
                       "design.interaction", "design.design-system", "design.visual-design") and work_type == "bugfix":
                reason = "excluded for bugfix work"
            elif min_c != "small":
                reason = f"min_complexity={min_c}, current={complexity}"
            elif s in ("e2e.execute", "smoke.test") and not ui_project:
                reason = "requires UI project"
            lines.append(f"- `{s}` — {reason}")
        lines.append("")

    # Stage checklist
    lines.append("## STAGE CHECKLIST")
    lines.append("")
    lines.append("Mark each stage as `[x]` when `done: true` in state.json.")
    lines.append("NEVER mark a stage without passing the compliance gate first.")
    lines.append("")
    for i, node_id in enumerate(topology.active_nodes, 1):
        lines.append(f"- [ ] {i}. `{node_id}`")
    lines.append("")

    # Stage scope
    stage_scope = {
        "init": "ALLOWED: read project files, explore structure. FORBIDDEN: write code, modify config.",
        "init.ideate": "ALLOWED: read project files. FORBIDDEN: write code, modify config.",
        "init.refine": "ALLOWED: read project files. FORBIDDEN: write code, modify config.",
        "impl.design": "ALLOWED: read code, write blueprint artifacts. FORBIDDEN: modify source code.",
        "impl.code": "ALLOWED: read/write code, run tests, edit config, git operations.",
        "doc.update": "ALLOWED: read/write documentation files. FORBIDDEN: modify source code.",
        "verify": "ALLOWED: read code, run tests, read artifacts. FORBIDDEN: modify source code.",
        "e2e.execute": "ALLOWED: read/write e2e/ files, run tests. FORBIDDEN: modify src/, edit playwright.config.js env, kill processes.",
        "deploy.prepare": "ALLOWED: run build/lint commands, read files. FORBIDDEN: modify source code.",
        "smoke.test": "ALLOWED: read/write e2e/ files, run tests against production build.",
        "post": "ALLOWED: read/write artifacts, git operations. FORBIDDEN: modify source code.",
    }
    lines.append("## STAGE SCOPE")
    lines.append("")
    for node_id in topology.active_nodes:
        scope = stage_scope.get(node_id, "Standard stage scope.")
        lines.append(f"- **`{node_id}`**: {scope}")
    lines.append("")

    lines.append("---")
    lines.append("*Generated by Engineering Loop v11.1 GraphBuilder*")

    return "\n".join(lines)


def _print_progress_bar(state: dict) -> None:
    stages = state.get("stages", {})
    complexity = state.get("complexity", "unset")
    active = [s for s in STAGE_ORDER if _is_active(s, complexity, state.get("ui_project", False))]
    total = len(active)
    done = sum(1 for s in active if stages.get(s, {}).get("done", False))
    current = state.get("current_stage", "").replace("-", ".", 99)

    bar_len = 30
    filled = int(bar_len * done / max(total, 1))
    bar = "#" * filled + "-" * (bar_len - filled)

    color = {"done": "\033[32m", "blocked": "\033[31m", "halted": "\033[31m"}.get(state.get("status", ""), "\033[36m")
    reset = "\033[0m"
    dim = "\033[2m"

    sys.stdout.write(f"\r{color}[{bar}] {done}/{total} stages  {current}{reset}")
    sys.stdout.flush()


def _is_active(stage_id: str, complexity: str, ui_project: bool) -> bool:
    from eng_loop.state import STAGE_MIN_COMPLEXITY, COMPLEXITY_ORDER
    if complexity == "unset":
        return True
    min_c = STAGE_MIN_COMPLEXITY.get(stage_id)
    if min_c and COMPLEXITY_ORDER.get(complexity, 0) < COMPLEXITY_ORDER.get(min_c, 0):
        return False
    if stage_id in ("e2e.execute", "smoke.test") and not ui_project:
        return False
    return True


def _check_model(config: dict[str, Any], quiet: bool = False) -> bool:
    try:
        model = create_model_from_config(config)
        if not quiet:
            base_url = config.get("model", {}).get("base_url", DEFAULT_BASE_URL)
            model_name = config.get("model", {}).get("model", DEFAULT_MODEL)
            print(f"Checking model: {model_name} @ {base_url}")
        model.invoke("Respond with OK")
        if not quiet:
            print("Model connectivity: OK")
        return True
    except Exception as e:
        if not quiet:
            print(f"Model connectivity failed: {e}")
        return False


def _print_result(state: dict) -> None:
    status = state.get("status", "unknown")
    blocking = state.get("blocking_condition", "")
    decisions = state.get("decisions", [])
    iteration = state.get("iteration", 0)

    print(f"\n{'='*60}")
    print(f"Engineering Loop Complete")
    print(f"{'='*60}")
    print(f"Status: {status}")
    if blocking:
        print(f"Blocking: {blocking}")
    print(f"Iterations: {iteration}")
    print(f"Decisions: {len(decisions)}")
    for d in decisions:
        print(f"  - {d}")
    print(f"{'='*60}")


def _save_state(state: dict, paths: dict, verbose: bool = False) -> None:
    saveable = {
        "iteration": state.get("iteration", 0),
        "status": state.get("status", "running"),
        "blocking_condition": state.get("blocking_condition", ""),
        "complexity": state.get("complexity", "unset"),
        "work_type": state.get("work_type", "feature"),
        "work_item": state.get("work_item", ""),
        "ideation": state.get("ideation"),
        "ui_project": state.get("ui_project", False),
        "stages": state.get("stages", {}),
        "decisions": state.get("decisions", []),
    }
    state_file = paths.get("state_file", "state.json")
    save_json_file(state_file, saveable)
    if verbose:
        print()
        print(f"State saved to: {state_file}")


def _check_compliance(args: argparse.Namespace, paths: dict[str, str]) -> None:
    """Validate stage transition against topology."""
    from eng_loop.tools.topology_compliance import check_compliance_from_files

    state_file = args.state_file or paths.get("state_file", "state.json")

    if not args.requested_stage:
        print("ERROR: --requested-stage is required with --check-compliance")
        sys.exit(1)

    if not Path(state_file).exists():
        print(f"ERROR: State file not found: {state_file}")
        sys.exit(1)

    result = check_compliance_from_files(state_file, args.requested_stage)
    print(result.to_json())

    if not result.ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
