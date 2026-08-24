from __future__ import annotations

import logging
import time
from typing import Any

from langgraph.types import Command

from eng_loop.state import get_work_item_text
from eng_loop.tools.autosizing import (
    classify_complexity,
    classify_work_type,
    deactivate_for_work_type,
    deactivate_inactive_stages,
    detect_ui_project,
)
from eng_loop.tools.graphify import run_graphify_init
from eng_loop.tools.progress import log_complexity

logger = logging.getLogger(__name__)


def init_setup_node(state: dict[str, Any]) -> Command[str]:
    """Deterministic setup node — runs ONCE per pipeline.

    Performs all non-LLM work: complexity classification, work type
    detection, UI project detection, graphify init, and stage
    deactivation.

    Results are cached in state['codebase_facts'] so retries of
    downstream LLM nodes never re-run this deterministic work.
    """
    config = state.get("config", {})
    paths = state.get("paths", {})
    stages = dict(state.get("stages", {}))
    t0 = time.monotonic()

    if state.get("codebase_facts"):
        logger.info("init_setup: codebase_facts already cached, skipping")
        return Command(
            update={"current_stage": "dynamic-architect"},
            goto="dynamic-architect",
        )

    work_item = get_work_item_text(state)

    complexity = state.get("complexity", "unset")
    if complexity == "unset":
        complexity = classify_complexity(work_item, config)

    work_type = state.get("work_type", "feature")
    if work_type == "feature" and not state.get("_work_type_set"):
        work_type = classify_work_type(work_item)

    ui_project = state.get("ui_project", False)
    if not ui_project:
        ui_project = detect_ui_project(paths)

    log_complexity(complexity, ui_project)

    project_root = paths.get("project_root", ".")
    graphify_result = run_graphify_init(config, complexity, project_root)

    graphify_state = {
        "built": graphify_result.get("graphify_built", False),
        "stats": graphify_result.get("graphify_stats"),
        "skipped": graphify_result.get("graphify_skipped", False),
        "error": graphify_result.get("graphify_error"),
    }

    stages = deactivate_inactive_stages(stages, complexity, ui_project)
    stages = deactivate_for_work_type(stages, work_type)

    codebase_facts = {
        "computed_at": time.time(),
        "complexity": complexity,
        "work_type": work_type,
        "ui_project": ui_project,
        "graphify": graphify_state,
    }

    elapsed = time.monotonic() - t0
    logger.info(
        "init_setup: complexity=%s, work_type=%s, ui=%s, graphify=%s (%.2fs)",
        complexity,
        work_type,
        ui_project,
        "built" if graphify_state["built"] else "skipped",
        elapsed,
    )

    return Command(
        update={
            "complexity": complexity,
            "work_type": work_type,
            "ui_project": ui_project,
            "stages": stages,
            "codebase_facts": codebase_facts,
            "graphify": graphify_state,
            "current_stage": "dynamic-architect",
        },
        goto="dynamic-architect",
    )
