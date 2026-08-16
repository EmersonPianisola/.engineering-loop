from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from rich.panel import Panel

from eng_loop.config import ensure_directories, load_config, resolve_paths
from eng_loop.graph import compile_graph
from eng_loop.graph_builder import GraphTopology
from eng_loop.model import DEFAULT_BASE_URL, DEFAULT_MODEL, create_model_from_config
from eng_loop.state import STAGE_ORDER, load_state_template, make_initial_state
from eng_loop.tools.file_ops import save_json as save_json_file
from eng_loop.tools.progress import log_iteration, tracker, ui


def main():
    parser = argparse.ArgumentParser(description="Engineering Loop Orchestrator (LangGraph)")

    # ── Main loop flags ──────────────────────────────────────────
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
    parser.add_argument(
        "--parallel-qa", action="store_true", help="Run QA stages in parallel (requires --dynamic-graph)"
    )
    parser.add_argument(
        "--build-topology",
        action="store_true",
        help="Build dynamic graph topology and output as markdown (for LLM orchestrator)",
    )
    parser.add_argument(
        "--opencode-agent",
        action="store_true",
        help="Use opencode CLI as agent backend (Python controls graph, opencode executes with native tools)",
    )
    parser.add_argument(
        "--check-compliance",
        action="store_true",
        help="Validate stage transition against topology (for LLM orchestrator)",
    )
    parser.add_argument(
        "--requested-stage", type=str, default="", help="Stage ID to validate (required with --check-compliance)"
    )

    # ── Interactive / breakpoint flags ───────────────────────────
    parser.add_argument(
        "--pause-at",
        type=str,
        nargs="+",
        default=[],
        help="Stage IDs to pause execution before (e.g. impl.code verify)",
    )
    parser.add_argument("--interactive", action="store_true", help="Enable full-screen TUI dashboard (experimental)")
    parser.add_argument("--tui", action="store_true", help="Enable interactive Textual TUI (MAGE HUD v2.0)")

    # ── Surgical subcommands ─────────────────────────────────────
    subparsers = parser.add_subparsers(dest="command", help="Surgical commands")

    # rollback
    p_rollback = subparsers.add_parser("rollback", help="Time-travel: restore state to before a stage")
    p_rollback.add_argument("stage_id", type=str, help="Stage ID to rollback to")
    p_rollback.add_argument("--framework-root", "-f", type=str, default=".")
    p_rollback.add_argument("--loop-root", "-l", type=str, default=".")
    p_rollback.add_argument("--project-root", "-p", type=str, default=".")

    # run-node
    p_runnode = subparsers.add_parser("run-node", help="Execute a single node in isolation (single-step replay)")
    p_runnode.add_argument("stage_id", type=str, help="Stage ID to execute")
    p_runnode.add_argument("--from-state", type=str, default=None, help="State file to load (default: state.json)")
    p_runnode.add_argument("--framework-root", "-f", type=str, default=".")
    p_runnode.add_argument("--loop-root", "-l", type=str, default=".")
    p_runnode.add_argument("--project-root", "-p", type=str, default=".")

    # clear-state
    p_clear = subparsers.add_parser("clear-state", help="Reset a stage's attempts and done status")
    p_clear.add_argument("stage_id", type=str, help="Stage ID to clear")
    p_clear.add_argument("--reset-attempts", action="store_true", help="Reset attempt counter to 0")
    p_clear.add_argument("--framework-root", "-f", type=str, default=".")
    p_clear.add_argument("--loop-root", "-l", type=str, default=".")
    p_clear.add_argument("--project-root", "-p", type=str, default=".")

    # skip-node
    p_skip = subparsers.add_parser("skip-node", help="Force-mark a stage as done")
    p_skip.add_argument("stage_id", type=str, help="Stage ID to skip")
    p_skip.add_argument("--framework-root", "-f", type=str, default=".")
    p_skip.add_argument("--loop-root", "-l", type=str, default=".")
    p_skip.add_argument("--project-root", "-p", type=str, default=".")

    # history
    p_history = subparsers.add_parser("history", help="List state snapshots")
    p_history.add_argument("--framework-root", "-f", type=str, default=".")
    p_history.add_argument("--loop-root", "-l", type=str, default=".")
    p_history.add_argument("--project-root", "-p", type=str, default=".")

    args = parser.parse_args()

    # ── Resolve paths (shared across all modes) ──────────────────
    framework_root = Path(getattr(args, "framework_root", ".")).resolve()
    loop_root = Path(getattr(args, "loop_root", ".")).resolve()
    project_root = Path(getattr(args, "project_root", ".")).resolve()

    config = load_config(framework_root, loop_root)
    paths = resolve_paths(config, framework_root, loop_root, project_root)
    ensure_directories(paths)

    # ── Surgical commands (exit immediately) ─────────────────────
    if args.command == "rollback":
        _cmd_rollback(args.stage_id, paths, config)
        return

    if args.command == "run-node":
        _cmd_run_node(args.stage_id, args.from_state, paths, config, framework_root)
        return

    if args.command == "clear-state":
        _cmd_clear_state(args.stage_id, args.reset_attempts, paths, config)
        return

    if args.command == "skip-node":
        _cmd_skip_node(args.stage_id, paths, config)
        return

    if args.command == "history":
        _cmd_history(paths, config)
        return

    # ── Apply CLI overrides ──────────────────────────────────────
    if hasattr(args, "opencode_agent"):
        if args.opencode_agent or config.get("agent", {}).get("backend", "langchain") == "opencode":
            os.environ["ENG_AGENT_BACKEND"] = "opencode"

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

    # ── Validate model connectivity ──────────────────────────────
    if not _check_model(config, quiet=True):
        ui.console.print()
        ui.console.print(
            Panel(
                f"[yellow]Model connectivity check failed.[/yellow]\n"
                f"Check that [bold]{config.get('model', {}).get('base_url', DEFAULT_BASE_URL)}[/bold] is running.\n"
                f"Use [dim]--check-model[/dim] for details.",
                title="[bold yellow]Warning[/bold yellow]",
                border_style="yellow",
            )
        )
        response = input("Continue anyway? [y/N]: ")
        if response.lower() != "y":
            sys.exit(1)

    # ── Build state ──────────────────────────────────────────────
    state = make_initial_state(config, paths)
    state["work_item"] = args.work_item

    if args.state_file and Path(args.state_file).exists():
        saved = load_state_template(args.state_file)
        state.update(saved)

    # ── Pre-classify work item (before graph build) ─────────────
    # The graph must know complexity/work_type/ui_project to filter
    # the correct active nodes. If resuming from a saved state, these
    # values are already set; otherwise classify now.
    if not args.work_item:
        args.work_item = state.get("work_item", "")

    if state.get("complexity", "unset") == "unset":
        from eng_loop.tools.autosizing import (
            classify_complexity,
            classify_work_type,
            detect_ui_project,
        )

        state["complexity"] = classify_complexity(args.work_item, config)
        state["work_type"] = classify_work_type(args.work_item)
        state["ui_project"] = detect_ui_project(paths)

    # ── Determine graph mode ─────────────────────────────────────
    dynamic_graph = args.dynamic_graph or config.get("dynamic_graph", {}).get("enabled", False)
    parallel_qa = args.parallel_qa or config.get("dynamic_graph", {}).get("parallel_qa", False)
    hud_mode = args.interactive or args.tui

    # Convert pause-at stage IDs to node names (dots → hyphens)
    interrupt_nodes = []
    if args.pause_at:
        interrupt_nodes = [s.replace(".", "-").replace("_", "-") for s in args.pause_at]

    if dynamic_graph:
        if not hud_mode:
            ui.console.print("[bold cyan]Mode:[/bold cyan] Dynamic graph" + (" + parallel QA" if parallel_qa else ""))
            if args.opencode_agent:
                ui.console.print("[bold cyan]Agent backend:[/bold cyan] opencode (hybrid mode)")

        from eng_loop.graph_builder import GraphBuilder

        graph_builder = GraphBuilder(parallel_qa=parallel_qa)

        # ── Pre-build: Architect proposes topology ──
        authorized_topology = None
        use_proposal = False

        try:
            from eng_loop.nodes.dynamic_architect import propose_topology
            from eng_loop.tools.policy_resolver import TopologyValidationError
            from eng_loop.tools.policy_resolver import authorize_topology as auth_topology

            proposal = propose_topology(
                work_item=args.work_item,
                codebase_facts=state.get("codebase_facts", {}),
                config=config,
                state=state,
                paths=paths,
            )

            if proposal:
                authorized_topology = auth_topology(proposal, state)
                use_proposal = True
                if not hud_mode:
                    ui.console.print(
                        f"[bold green]Architect:[/bold green] topology proposed "
                        f"({len(authorized_topology.authorized_stages)} stages)"
                    )
                    if authorized_topology.policy_notes:
                        ui.console.print(
                            f"[dim]  Policy notes: {authorized_topology.policy_notes}[/dim]"
                        )

                # Store proposal in state for runtime reference
                state["topology_proposal"] = proposal.model_dump()

        except TopologyValidationError as e:
            if not hud_mode:
                ui.console.print(
                    f"[bold yellow]Architect rejected:[/bold yellow] [{e.layer}] {e.message}"
                )
        except Exception as e:
            if not hud_mode:
                ui.console.print(
                    f"[bold yellow]Architect error:[/bold yellow] {e} — falling back to deterministic"
                )

        if not use_proposal:
            if not hud_mode:
                ui.console.print("[dim]Architect: falling back to deterministic graph builder[/dim]")

        # ── Compile graph (proposal or deterministic) ──
        compiled, topology = graph_builder.compile(
            state,
            config,
            interrupt_before=interrupt_nodes or None,
            authorized_topology=authorized_topology if use_proposal else None,
        )
        graph = compiled

        state["graph_topology"] = topology.to_dict()
        state["active_nodes"] = topology.active_nodes

        if not hud_mode:
            ui.render_topology(
                work_item=args.work_item,
                active_nodes=topology.active_nodes,
                complexity=state.get("complexity", "unset"),
                total_available=topology.total_available,
                work_type=state.get("work_type", "feature"),
                ui_project=state.get("ui_project", False),
            )
    else:
        if not hud_mode:
            ui.console.print("[dim]Mode: Static graph (legacy)[/dim]")
        graph = compile_graph(config=config)

    thread_config = {"configurable": {"thread_id": "eng-loop-run"}}

    # HUD initialization for --interactive mode
    hud = None
    tui_controller = None
    exec_state = None
    normalizer = None
    use_tui = args.tui

    if args.interactive or use_tui:
        from eng_loop.tools.event_normalizer import EventNormalizer
        from eng_loop.tools.execution_state import ExecutionState

        active_stages = state.get("active_nodes", [])

        quest_id = f"Q_{uuid.uuid4().hex[:6]}"

        max_att_map = {}
        constraints = config.get("constraints", {})
        for node in active_stages:
            key = f"max_{node.replace('.', '_').replace('-', '_')}_attempts"
            max_att_map[node] = constraints.get(key, 2)

        exec_state = ExecutionState(
            quest_id=quest_id,
            title=args.work_item,
            all_node_names=active_stages,
            max_attempts_map=max_att_map,
        )
        normalizer = EventNormalizer(exec_state, active_stages, max_att_map)

        if use_tui:
            # Textual TUI (MAGE HUD v2.0)
            try:
                from eng_loop.tools.hud_tui import TextualHUDController

                tui_controller = TextualHUDController(exec_state, normalizer, args.work_item)
                ui.set_normalizer(normalizer)
            except ImportError:
                ui.console.print("[yellow]Warning: Textual not installed, falling back to Rich HUD.[/yellow]")
                use_tui = False
        else:
            # Rich-based HUD (legacy)
            from eng_loop.tools.hud import HUDRenderer

            hud = HUDRenderer(ui.console, execution_state=exec_state, normalizer=normalizer)
            ui.set_hud(hud)
            ui.set_normalizer(normalizer)
            hud.start(
                work_item=args.work_item,
                active_stages=active_stages,
                config=config,
                initial_state=state,
            )
        # Silence all Python logging output to prevent stdout/stderr leakage
        # that would corrupt the HUD terminal rendering.
        import logging as _logging

        _logging.getLogger().addHandler(_logging.NullHandler())
        _logging.getLogger().setLevel(_logging.CRITICAL)

    model_info = config.get("model", {})
    if not tui_controller:
        ui.console.print()
        ui.console.print(
            Panel(
                f"[bold]Work item:[/bold] {args.work_item}\n"
                f"[bold]Model:[/bold] {model_info.get('model', DEFAULT_MODEL)} @ {model_info.get('base_url', DEFAULT_BASE_URL)}\n"
                f"[bold]Complexity:[/bold] auto-sized",
                title="[bold blue]Engineering Loop v11[/bold blue]",
                border_style="blue",
            )
        )

        if interrupt_nodes:
            ui.console.print(f"[bold yellow]Breakpoints set at:[/bold yellow] {', '.join(interrupt_nodes)}")

    # ── Execute graph with interrupt support ─────────────────────
    try:
        tracker.start_loop()
        prev_stage = ""

        for event in _stream_with_interrupts(
            graph,
            state,
            thread_config,
            interrupt_nodes,
            paths,
            config,
            exec_state=exec_state,
            normalizer=normalizer,
        ):
            status = event.get("status", "running")
            current = event.get("current_stage", "")
            iteration = event.get("iteration", 0)

            if current and current != prev_stage:
                log_iteration(iteration, current)
                if not hud and not tui_controller:
                    _print_progress_bar(event)
                _save_state(event, paths)
                _save_snapshot(event, paths, current, config)

                # Store payload for Node Inspector
                if normalizer and current:
                    stage_data = event.get("stages", {}).get(current, {})
                    output = stage_data.get("output", "")
                    if output:
                        normalizer.store_output_result(current, str(output)[:8000])

                prev_stage = current

            if hud:
                hud.update(event)

            if status not in ("running",):
                log_iteration(iteration, current or "complete")

        final_state = event
        if normalizer:
            status = final_state.get("status", "unknown")
            if status == "done":
                normalizer.quest_completed()
            elif status == "blocked":
                normalizer.quest_failed(final_state.get("blocking_condition", ""))
        if not tui_controller:
            _print_result(final_state)
        _save_state(final_state, paths, verbose=True)

    except KeyboardInterrupt:
        state["status"] = "halted"
        state["blocking_condition"] = "user interrupted"
        _save_state(state, paths, verbose=True)
        if normalizer:
            normalizer.quest_cancelled("user interrupted")
        if hud:
            hud.log("SYS", "User interrupted")
        ui.console.print()
        ui.console.print(Panel("[bold yellow]Loop halted by user.[/bold yellow]", border_style="yellow"))
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        state["status"] = "halted"
        state["blocking_condition"] = str(e)
        _save_state(state, paths, verbose=True)
        if normalizer:
            normalizer.quest_failed(str(e))
        if hud:
            hud.log("ERROR", str(e))
        ui.console.print()
        ui.console.print(Panel(f"[bold red]Loop halted:[/bold red] {e}", border_style="red"))
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        if hud:
            hud.stop()
            ui.set_hud(None)


def _stream_with_interrupts(
    graph: Any,
    state: dict[str, Any],
    thread_config: dict[str, Any],
    interrupt_nodes: list[str],
    paths: dict[str, Any],
    config: dict[str, Any],
    exec_state: Any = None,
    normalizer: Any = None,
) -> Any:
    """Stream graph events, handling breakpoint interrupts.

    Yields events from graph.stream(). When an interrupt occurs at a
    breakpoint node, shows the interactive menu and resumes or aborts.

    When exec_state is provided, checks for pause/resume and step mode.
    """
    from langgraph.types import Command

    from eng_loop.tools.interactive import edit_state_in_editor

    def do_stream(initial_input):
        yield from graph.stream(initial_input, config=thread_config, stream_mode="values")

    # First stream (or resume stream)
    stream_input = state
    while True:
        # Check for pause before executing next batch
        if exec_state and exec_state.is_paused:
            # Wait for resume — poll with sleep
            import time as _time

            while exec_state.is_paused:
                _time.sleep(0.1)

        events_from_stream = list(do_stream(stream_input))
        for event in events_from_stream:
            # Check for interventions on the current node
            current_stage = event.get("current_stage", "")
            if current_stage and exec_state and exec_state.has_intervention(current_stage):
                intervention = exec_state.get_intervention(current_stage)
                if intervention:
                    ui.console.print(f"\n  [bold yellow]Intervention injected for {current_stage}[/bold yellow]")

            yield event

        # Step mode: pause after each batch
        if exec_state and exec_state.step_mode:
            exec_state.pause_after_step()

        # Check if stream stopped due to interrupt
        # LangGraph with interrupt_before stops the stream when it hits a paused node.
        # We detect this by checking if the current state indicates an interrupt.
        try:
            current_state = graph.get_state(thread_config)
            if current_state.next:
                # There are more nodes to execute — we were interrupted
                interrupted_node = current_state.next[0]
                stage_id = interrupted_node.replace("-", ".")

                if ui.is_hud_active():
                    # TUI mode: skip breakpoint menu (input() would hang), auto-resume
                    stream_input = Command(resume=True)
                    continue

                ui.console.print()
                action = ui.show_breakpoint_menu(interrupted_node, current_state.values)

                if action == "abort":
                    ui.console.print()
                    ui.console.print(
                        Panel("[bold yellow]Loop aborted at breakpoint.[/bold yellow]", border_style="yellow")
                    )
                    return

                if action == "edit":
                    edited = edit_state_in_editor(current_state.values, stage_id)
                    _save_state(edited, paths)
                    _save_snapshot(edited, paths, stage_id, config)

                # Resume
                stream_input = Command(resume=True)
                continue
            else:
                # No more nodes — normal completion
                break
        except Exception:
            # If get_state fails (no checkpointer), just break
            break


# ───────────────────────────────────────────────────────────────────
# Surgical Command Implementations
# ───────────────────────────────────────────────────────────────────


def _cmd_rollback(stage_id: str, paths: dict[str, str], config: dict[str, Any]) -> None:
    """eng-loop rollback <stage_id>"""
    from eng_loop.tools.state_history import rollback_and_save

    if rollback_and_save(stage_id, paths, config):
        state_file = paths.get("state_file", "state.json")
        ui.console.print(
            Panel(
                f"[bold green]State restored[/bold green]\n"
                f"Rolled back to state before [bold]{stage_id}[/bold]\n"
                f"Saved to: [dim]{state_file}[/dim]",
                title="[bold blue]Rollback Complete[/bold blue]",
                border_style="blue",
            )
        )
    else:
        ui.console.print(
            Panel(
                f"[bold red]No snapshot found before {stage_id}[/bold red]\n"
                f"Run [dim]eng-loop history[/dim] to list available snapshots.",
                title="[bold red]Rollback Failed[/bold red]",
                border_style="red",
            )
        )
        sys.exit(1)


def _cmd_run_node(
    stage_id: str, from_state: str | None, paths: dict[str, str], config: dict[str, Any], framework_root: Path
) -> None:
    """eng-loop run-node <stage_id> --from-state <file>"""
    from eng_loop.node_registry import build_registry

    state_file = from_state or paths.get("state_file", "state.json")
    if not Path(state_file).exists():
        ui.console.print(f"[bold red]State file not found:[/bold red] {state_file}")
        sys.exit(1)

    state = load_state_template(state_file)
    state.setdefault("config", config)
    state.setdefault("paths", paths)

    registry = build_registry()
    spec = registry.get(stage_id)
    if not spec:
        ui.console.print(f"[bold red]Unknown stage:[/bold red] {stage_id}")
        sys.exit(1)

    ui.console.print(f"[bold cyan]Running node:[/bold cyan] {stage_id} [dim](isolated)[/dim]")

    try:
        result = spec.handler(state)
        from langgraph.types import Command

        if isinstance(result, Command):
            update = result.update or {}
            state.update(update)
            goto = getattr(result, "goto", None)
            ui.console.print(
                Panel(
                    f"[bold green]Node executed: {stage_id}[/bold green]\n"
                    f"[bold]Routed to:[/bold] {goto or '(none)'}\n"
                    f"[bold]Status:[/bold] {state.get('status', 'unknown')}",
                    title="[bold blue]Single-Step Complete[/bold blue]",
                    border_style="blue",
                )
            )
        else:
            ui.console.print(f"[bold green]Node {stage_id} completed.[/bold green]")
    except Exception as e:
        ui.console.print(Panel(f"[bold red]Node failed:[/bold red] {e}", border_style="red"))
        import traceback

        traceback.print_exc()
        sys.exit(1)

    _save_state(state, paths, verbose=True)


def _cmd_clear_state(stage_id: str, reset_attempts: bool, paths: dict[str, str], config: dict[str, Any]) -> None:
    """eng-loop clear-state <stage_id> --reset-attempts"""
    state_file = paths.get("state_file", "state.json")
    if not Path(state_file).exists():
        ui.console.print(f"[bold red]State file not found:[/bold red] {state_file}")
        sys.exit(1)

    state = load_state_template(state_file)
    stages = state.setdefault("stages", {})
    stage_data = stages.setdefault(stage_id, {})

    if reset_attempts:
        stage_data["attempts"] = 0

    stage_data["done"] = False
    stage_data["essence_checked"] = False

    state["status"] = "running"
    state["blocking_condition"] = ""

    save_json_file(state_file, _make_saveable(state))

    ui.console.print(
        Panel(
            f"[bold green]State cleared for: {stage_id}[/bold green]\n"
            f"  done = false\n"
            f"  attempts = {stage_data['attempts']}\n"
            f"  essence_checked = false\n"
            f"  status = running",
            title="[bold blue]State Cleared[/bold blue]",
            border_style="blue",
        )
    )


def _cmd_skip_node(stage_id: str, paths: dict[str, str], config: dict[str, Any]) -> None:
    """eng-loop skip-node <stage_id>"""
    state_file = paths.get("state_file", "state.json")
    if not Path(state_file).exists():
        ui.console.print(f"[bold red]State file not found:[/bold red] {state_file}")
        sys.exit(1)

    state = load_state_template(state_file)
    stages = state.setdefault("stages", {})
    stage_data = stages.setdefault(stage_id, {})
    stage_data["done"] = True

    save_json_file(state_file, _make_saveable(state))

    ui.console.print(
        Panel(
            f"[bold yellow]Stage skipped: {stage_id}[/bold yellow]\nMarked as done: true",
            title="[bold yellow]Node Skipped[/bold yellow]",
            border_style="yellow",
        )
    )


def _cmd_history(paths: dict[str, str], config: dict[str, Any]) -> None:
    """eng-loop history"""
    from rich.table import Table

    from eng_loop.tools.state_history import list_snapshots

    snapshots = list_snapshots(paths, config)
    if not snapshots:
        ui.console.print("[dim]No snapshots found. Run the loop first.[/dim]")
        return

    table = Table(title="State Snapshots", border_style="blue")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Stage", style="bold cyan")
    table.add_column("Timestamp", style="dim")
    table.add_column("Size", justify="right", style="dim")
    table.add_column("Path", style="dim", no_wrap=True)

    for i, snap in enumerate(snapshots, 1):
        size_str = _format_size(snap["size"])
        table.add_row(str(i), snap["stage_id"], snap["timestamp"], size_str, snap["path"])

    ui.console.print(table)


def _format_size(nbytes: int) -> str:
    if nbytes < 1024:
        return f"{nbytes}B"
    elif nbytes < 1024 * 1024:
        return f"{nbytes / 1024:.1f}KB"
    return f"{nbytes / (1024 * 1024):.1f}MB"


def _make_saveable(state: dict[str, Any]) -> dict[str, Any]:
    """Build a clean state dict for saving to JSON."""
    return {
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
        "stage_artifacts": state.get("stage_artifacts", {}),
        "lessons": state.get("lessons", []),
        "errors": state.get("errors", []),
        "handoffs": state.get("handoffs", {}),
        "context_tiers": state.get("context_tiers", {}),
        "tags": state.get("tags", []),
        "active_nodes": state.get("active_nodes", []),
        "graph_topology": state.get("graph_topology", {}),
        "parallel_groups": state.get("parallel_groups", {}),
        "timing": tracker.to_json(),
        "current_stage": state.get("current_stage", ""),
        "fix_tasks": state.get("fix_tasks", []),
        "fix_iteration": state.get("fix_iteration", 0),
        "rollback_target": state.get("rollback_target", ""),
        "explorer_evidence": state.get("explorer_evidence", []),
        "codebase_facts": state.get("codebase_facts", {}),
        "topology_proposal": state.get("topology_proposal"),
        "dynamic_plan": state.get("dynamic_plan"),
        "dynamic_runtime": state.get("dynamic_runtime", {}),
    }


# ───────────────────────────────────────────────────────────────────
# Existing helper functions (preserved)
# ───────────────────────────────────────────────────────────────────


def _build_topology(work_item: str, config: dict[str, Any], paths: dict[str, str]) -> None:
    """Build dynamic graph topology and output as markdown for LLM orchestrator."""
    from eng_loop.graph_builder import GraphBuilder
    from eng_loop.tools.autosizing import classify_complexity, classify_work_type, detect_ui_project

    complexity = classify_complexity(work_item, config)
    work_type = classify_work_type(work_item)
    ui_project = detect_ui_project(paths)

    state = make_initial_state(config, paths)
    state["work_item"] = work_item
    state["complexity"] = complexity
    state["work_type"] = work_type
    state["ui_project"] = ui_project

    parallel_qa = config.get("dynamic_graph", {}).get("parallel_qa", False)
    builder = GraphBuilder(parallel_qa=parallel_qa)
    _, topology = builder.build(state)

    md = _topology_to_markdown(topology, work_item, complexity, work_type, ui_project, config)

    topology_file = paths.get("artifact_root", "artifacts") + "/graph-topology.md"
    from eng_loop.tools.file_ops import write_file

    write_file(topology_file, md)

    topology_json = paths.get("artifact_root", "artifacts") + "/graph-topology.json"
    save_json_file(topology_json, topology.to_dict())

    print(md)
    ui.console.print()
    ui.console.print(f"  [dim]Topology saved to: {topology_file}[/dim]")
    ui.console.print(f"  [dim]JSON saved to: {topology_json}[/dim]")


def _topology_to_markdown(
    topology: GraphTopology,
    work_item: str,
    complexity: str,
    work_type: str,
    ui_project: bool,
    config: dict[str, Any],
) -> str:
    """Convert graph topology to markdown instructions for LLM orchestrator."""
    from eng_loop.state import STAGE_MIN_COMPLEXITY, STAGE_ORDER, get_active_stages
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

    work_type_descriptions = {
        "feature": "New functionality — full loop (design, architecture, implementation, verification, QA, deploy)",
        "bugfix": "Fix existing behavior — skips design stages, keeps implementation + verification",
        "operational": "Run existing code (tests, deploys) — skips implementation, design, architecture",
        "documentation": "Write/generate documents — init → impl.code → post (no design/verify/deploy)",
    }
    lines.append(f"**Work Type: {work_type}** — {work_type_descriptions.get(work_type, '')}")
    lines.append("")

    lines.append("## ACTIVE STAGES (execute in this order)")
    lines.append("")
    lines.append("| # | Stage ID | Phase | Description |")
    lines.append("|---|----------|-------|-------------|")

    phase_labels = {
        "init": "INIT",
        "design": "DESIGN",
        "arch": "ARCH",
        "impl": "IMPL",
        "verify": "VERIFY",
        "qa": "QA",
        "deploy": "DEPLOY",
        "doc": "DOC",
        "post": "POST",
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
    lines.append("## ROUTING RULES (deterministic)")
    lines.append("")
    lines.append("After each stage completes, determine the next stage:")
    lines.append("")

    lines.append("### Post-Init-Refine")
    lines.append("- IF complexity >= `medium` → `arch.requirements`")
    lines.append("- ELSE → `impl.design`")
    lines.append("")

    lines.append("### Post-Verify (PASS)")
    if ui_project:
        lines.append("- → `e2e.execute` (UI project)")
    else:
        lines.append("- IF complexity >= `medium` → `qa.security`")
    lines.append("- IF complexity == `small` → `deploy.prepare`")
    lines.append("")

    lines.append("### Post-E2E (PASS)")
    lines.append("- IF complexity >= `medium` → `qa.security`")
    lines.append("- ELSE → `deploy.prepare`")
    lines.append("")

    lines.append("### QA Chain")
    lines.append("- `qa.security` PASS → `qa.api-contract` (if medium+) or `deploy.prepare`")
    lines.append("- `qa.api-contract` PASS → `qa.performance` (if complex) or `deploy.prepare`")
    lines.append("- `qa.performance` PASS → `deploy.prepare`")
    lines.append("- Any QA FAIL → `impl.code` (RESET)")
    lines.append("")

    lines.append("### Post-Deploy (PASS)")
    if ui_project:
        lines.append("- → `smoke.test` (UI project)")
    lines.append("- IF complexity >= `medium` → `doc.decisions`")
    lines.append("- ELSE → `post`")
    lines.append("")

    lines.append("### FAIL ROUTING (any stage with verdict)")
    lines.append("- `verify` FAIL → `impl.code` (RESET)")
    lines.append("- `e2e.execute` FAIL → `impl.code` (RESET)")
    lines.append("- `qa.*` FAIL → `impl.code` (RESET)")
    lines.append("- `deploy.prepare` FAIL → `impl.code` (RESET)")
    lines.append("- `smoke.test` FAIL → `impl.code` (RESET)")
    lines.append("")

    if topology.parallel_groups:
        lines.append("## PARALLEL GROUPS")
        lines.append("")
        for group_name, members in topology.parallel_groups.items():
            lines.append(f"### {group_name}")
            for m in members:
                lines.append(f"- `{m}`")
            lines.append("")

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

    get_active_stages(complexity, ui_project, "feature")
    deactivated = [s for s in STAGE_ORDER if s not in topology.active_nodes]
    if deactivated:
        lines.append("## DEACTIVATED STAGES (auto-sizing)")
        lines.append("")
        from eng_loop.tools.autosizing import DOCUMENTATION_EXCLUDED_STAGES

        for s in deactivated:
            min_c = STAGE_MIN_COMPLEXITY.get(s, "small")
            reason = ""
            if s in DOCUMENTATION_EXCLUDED_STAGES and work_type == "documentation":
                reason = "excluded for documentation work"
            elif s in OPERATIONAL_EXCLUDED_STAGES and work_type == "operational":
                reason = "excluded for operational work"
            elif (
                s
                in (
                    "design.user-research",
                    "design.personas",
                    "design.info-arch",
                    "design.interaction",
                    "design.design-system",
                    "design.visual-design",
                )
                and work_type == "bugfix"
            ):
                reason = "excluded for bugfix work"
            elif min_c != "small":
                reason = f"min_complexity={min_c}, current={complexity}"
            elif s in ("e2e.execute", "smoke.test") and not ui_project:
                reason = "requires UI project"
            lines.append(f"- `{s}` — {reason}")
        lines.append("")

    lines.append("## STAGE CHECKLIST")
    lines.append("")
    lines.append("Mark each stage as `[x]` when `done: true` in state.json.")
    lines.append("NEVER mark a stage without passing the compliance gate first.")
    lines.append("")
    for i, node_id in enumerate(topology.active_nodes, 1):
        lines.append(f"- [ ] {i}. `{node_id}`")
    lines.append("")

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
    lines.append("*Generated by Engineering Loop v11.2 GraphBuilder*")

    return "\n".join(lines)


def _print_progress_bar(state: dict) -> None:
    stages = state.get("stages", {})
    complexity = state.get("complexity", "unset")
    active = [s for s in STAGE_ORDER if _is_active(s, complexity, state.get("ui_project", False))]
    done_set = {s for s in active if stages.get(s, {}).get("done", False)}
    current = state.get("current_stage", "").replace("-", ".", 99)
    status = state.get("status", "running")

    ui.render_progress_bar(active, done_set, current, status)


def _is_active(stage_id: str, complexity: str, ui_project: bool) -> bool:
    from eng_loop.state import COMPLEXITY_ORDER, STAGE_MIN_COMPLEXITY

    if complexity == "unset":
        return True
    min_c = STAGE_MIN_COMPLEXITY.get(stage_id)
    if min_c and COMPLEXITY_ORDER.get(complexity, 0) < COMPLEXITY_ORDER.get(min_c, 0):
        return False
    return not (stage_id in ("e2e.execute", "smoke.test") and not ui_project)


def _check_model(config: dict[str, Any], quiet: bool = False) -> bool:
    try:
        model = create_model_from_config(config)
        if not quiet:
            base_url = config.get("model", {}).get("base_url", DEFAULT_BASE_URL)
            model_name = config.get("model", {}).get("model", DEFAULT_MODEL)
            ui.console.print(f"[yellow]Checking model:[/yellow] {model_name} @ {base_url}")
        model.invoke("Respond with OK")
        if not quiet:
            ui.console.print("[bold green]Model connectivity: OK[/bold green]")
        return True
    except Exception as e:
        if not quiet:
            ui.console.print(f"[bold red]Model connectivity failed:[/bold red] {e}")
        return False


def _print_result(state: dict) -> None:
    status = state.get("status", "unknown")
    blocking = state.get("blocking_condition", "")
    decisions = state.get("decisions", [])
    iteration = state.get("iteration", 0)
    stages = state.get("stages", {})

    ui.render_result(status, blocking, iteration, decisions, stages)


def _save_state(state: dict, paths: dict, verbose: bool = False) -> None:
    saveable = _make_saveable(state)
    state_file = paths.get("state_file", "state.json")
    save_json_file(state_file, saveable)
    if verbose:
        ui.console.print()
        ui.console.print(f"  [dim]State saved to: {state_file}[/dim]")


def _save_snapshot(state: dict, paths: dict, stage_id: str, config: dict[str, Any] | None = None) -> None:
    """Save a state snapshot after a stage completes."""
    from eng_loop.tools.state_history import save_snapshot as _save_snap

    _save_snap(state, paths, stage_id, config)


def _check_compliance(args: argparse.Namespace, paths: dict[str, str]) -> None:
    """Validate stage transition against topology."""
    from eng_loop.tools.topology_compliance import check_compliance_from_files

    state_file = args.state_file or paths.get("state_file", "state.json")

    if not args.requested_stage:
        ui.console.print("[bold red]ERROR:[/bold red] --requested-stage is required with --check-compliance")
        sys.exit(1)

    if not Path(state_file).exists():
        ui.console.print(f"[bold red]ERROR:[/bold red] State file not found: {state_file}")
        sys.exit(1)

    result = check_compliance_from_files(state_file, args.requested_stage)
    ui.console.print(result.to_json())

    if not result.ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
