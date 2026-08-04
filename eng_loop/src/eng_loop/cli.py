from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from eng_loop.config import load_config, resolve_paths, ensure_directories
from eng_loop.state import make_initial_state, load_state_template
from eng_loop.graph import compile_graph
from eng_loop.tools.file_ops import save_json as save_json_file
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
    args = parser.parse_args()

    framework_root = Path(args.framework_root).resolve()
    loop_root = Path(args.loop_root).resolve()
    project_root = Path(args.project_root).resolve()

    config = load_config(framework_root, loop_root)
    paths = resolve_paths(config, framework_root, loop_root, project_root)
    ensure_directories(paths)

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

    graph = compile_graph(config=config)

    thread_config = {"configurable": {"thread_id": "eng-loop-run"}}

    model_info = config.get("model", {})
    print(f"Starting Engineering Loop...")
    print(f"Work item: {args.work_item}")
    print(f"Model: {model_info.get('model', DEFAULT_MODEL)} @ {model_info.get('base_url', DEFAULT_BASE_URL)}")
    print(f"Complexity: will be auto-sized")
    print()

    try:
        for event in graph.stream(state, config=thread_config, stream_mode="values"):
            status = event.get("status", "running")
            current = event.get("current_stage", "")
            iteration = event.get("iteration", 0)
            if current or status != "running":
                print(f"[iter {iteration}] stage={current} status={status}")

        final_state = event
        _print_result(final_state)
        _save_state(final_state, paths)
    except KeyboardInterrupt:
        state["status"] = "halted"
        state["blocking_condition"] = "user interrupted"
        _save_state(state, paths)
        print("\nLoop halted by user.")
        sys.exit(130)
    except Exception as e:
        state["status"] = "halted"
        state["blocking_condition"] = str(e)
        _save_state(state, paths)
        print(f"\nLoop halted: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


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


def _save_state(state: dict, paths: dict) -> None:
    saveable = {
        "iteration": state.get("iteration", 0),
        "status": state.get("status", "running"),
        "blocking_condition": state.get("blocking_condition", ""),
        "complexity": state.get("complexity", "unset"),
        "work_item": state.get("work_item", ""),
        "ideation": state.get("ideation"),
        "ui_project": state.get("ui_project", False),
        "stages": state.get("stages", {}),
        "decisions": state.get("decisions", []),
    }
    state_file = paths.get("state_file", "state.json")
    save_json_file(state_file, saveable)
    print(f"\nState saved to: {state_file}")


if __name__ == "__main__":
    main()
