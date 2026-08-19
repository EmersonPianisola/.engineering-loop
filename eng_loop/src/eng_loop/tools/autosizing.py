from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from eng_loop.model import create_model_from_config
from eng_loop.state import STAGE_MIN_COMPLEXITY, STAGE_ORDER
from eng_loop.tools.agent_runner import AgentResult, run_agent
from eng_loop.tools.agent_tools import get_tools_for_stage
from eng_loop.tools.node_helpers import build_node_prompt

logger = logging.getLogger(__name__)


class ComplexityAssessment(BaseModel):
    """LLM-assessed complexity for a work item."""

    complexity: str = Field(description="Assessed complexity: small, medium, large, or complex")
    estimated_files: int = Field(description="Estimated number of files that will be touched or created")
    estimated_tasks: int = Field(description="Estimated number of distinct sub-tasks required")
    requires_architecture: bool = Field(description="Does this task require architectural design or solution planning?")
    requires_design: bool = Field(description="Does this task require UI/UX design work?")
    requires_qa: bool = Field(description="Does this task require QA beyond basic linting and unit tests?")
    requires_e2e: bool = Field(description="Does this task require end-to-end testing?")
    requires_deploy: bool = Field(description="Does this task involve deployment preparation?")
    rationale: str = Field(description="Explanation of why this complexity level was chosen")


def classify_complexity_llm(
    work_item: str,
    config: dict[str, Any],
    state: dict[str, Any] | None = None,
    paths: dict[str, Any] | None = None,
) -> str:
    """Use LLM to assess work item complexity with codebase context.

    Falls back to heuristic classification on any error.
    """
    state = state or {}
    paths = paths or {}
    ui_project = state.get("ui_project", False)
    work_type = state.get("work_type", "feature")
    codebase_facts = state.get("codebase_facts", {})

    # Build stage context for the LLM
    stage_context = _build_stage_context()

    instructions = (
        f"You are a Complexity Assessor. Your job is to accurately assess the\n"
        f"complexity of a work item to determine which pipeline stages are needed.\n\n"
        f"## WORK ITEM\n"
        f"{work_item}\n\n"
        f"## PROJECT CONTEXT\n"
        f"UI Project: {ui_project}\n"
        f"Work Type: {work_type}\n"
        f"Codebase Facts: {json.dumps(codebase_facts, default=str)}\n\n"
        f"## COMPLEXITY LEVELS\n"
        f"small — 1-3 files, single focused task, no new domains, no integrations\n"
        f"medium — 4-10 files, multiple related tasks, may involve integrations\n"
        f"large — 10+ files, cross-cutting changes, new domains, architecture needed\n"
        f"complex — ambiguous scope, multiple new domains, major integrations\n\n"
        f"## STAGE REQUIREMENTS BY COMPLEXITY\n"
        f"{stage_context}\n\n"
        f"## IMPORTANT GUIDELINES\n"
        f"1. 'Validation' of multiple user flows is NOT small — it touches many files.\n"
        f"2. Tasks mentioning 'all flows', 'production readiness', 'all stages' are medium+.\n"
        f"3. Firebase integration (auth, firestore, storage, functions) is an integration.\n"
        f"4. Multi-feature validation requires architecture and QA stages.\n"
        f"5. When in doubt, err on the side of higher complexity (more stages is safer).\n\n"
        f"## OUTPUT\n"
        f"Return a JSON object with the assessment fields."
    )

    prompt = build_node_prompt(
        "init.setup",
        state,
        paths,
        config,
        role_description="Complexity Assessor",
        instructions=instructions,
    )

    model = create_model_from_config(config, "init.setup")
    tools = get_tools_for_stage("init.setup", paths, config, state)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 15)

    try:
        agent_result: AgentResult = run_agent(
            model=model,
            tools=tools,
            prompt=prompt,
            stage_id="init.setup.complexity",
            output_schema=ComplexityAssessment,
            max_iterations=max_agent_iterations,
            config=config,
        )

        if agent_result.error:
            logger.warning(
                "LLM complexity classification error: %s, falling back to heuristics",
                agent_result.error,
            )
            return classify_complexity(work_item, config)

        assessment = ComplexityAssessment(**agent_result.data)
        complexity = assessment.complexity
        if complexity not in ("small", "medium", "large", "complex"):
            logger.warning(
                "LLM returned invalid complexity '%s', falling back to heuristics",
                complexity,
            )
            return classify_complexity(work_item, config)

        logger.info(
            "LLM complexity assessment: %s (files=%d, tasks=%d, rationale=%s)",
            complexity,
            assessment.estimated_files,
            assessment.estimated_tasks,
            assessment.rationale[:200],
        )

        # Store assessment for downstream use (essence gate can reference it)
        if state is not None:
            state.setdefault("complexity_assessment", {})
            state["complexity_assessment"].update(
                {
                    "complexity": complexity,
                    "estimated_files": assessment.estimated_files,
                    "estimated_tasks": assessment.estimated_tasks,
                    "requires_architecture": assessment.requires_architecture,
                    "requires_design": assessment.requires_design,
                    "requires_qa": assessment.requires_qa,
                    "requires_e2e": assessment.requires_e2e,
                    "requires_deploy": assessment.requires_deploy,
                    "rationale": assessment.rationale,
                }
            )

        return complexity

    except Exception as e:
        logger.warning("LLM complexity classification failed: %s, falling back to heuristics", e)
        return classify_complexity(work_item, config)


def _build_stage_context() -> str:
    """Build a context string describing which stages are active at each complexity."""
    lines = ["| Complexity | Active Stages |"]
    lines.append("|---|---|")

    for level in ["small", "medium", "large", "complex"]:
        active = []
        from eng_loop.state import COMPLEXITY_ORDER

        level_order = COMPLEXITY_ORDER.get(level, 0)
        for stage in STAGE_ORDER:
            min_c = STAGE_MIN_COMPLEXITY.get(stage)
            if min_c and COMPLEXITY_ORDER.get(min_c, 0) > level_order:
                continue
            active.append(stage)
        lines.append(f"| {level} | {', '.join(active[:8])}{'...' if len(active) > 8 else ''} |")

    return "\n".join(lines)


def classify_complexity(work_item: str, config: dict[str, Any]) -> str:
    heuristics = config.get("auto_sizing", {}).get("heuristics", {})
    small_h = heuristics.get("small", {})
    medium_h = heuristics.get("medium", {})

    estimated_files = _estimate_files(work_item)
    estimated_tasks = _estimate_tasks(work_item)
    has_new_domains = _has_new_domains(work_item)
    has_integrations = _has_integrations(work_item)
    has_ambiguity = _has_ambiguity(work_item)

    max_files_small = small_h.get("max_files", 3)
    max_tasks_small = small_h.get("max_tasks", 3)

    max_files_medium = medium_h.get("max_files", 10)
    max_tasks_medium = medium_h.get("max_tasks", 8)

    if has_ambiguity and has_new_domains and has_integrations:
        return "complex"

    if estimated_files > max_files_medium or estimated_tasks > max_tasks_medium or has_new_domains or has_integrations:
        return "large"

    if estimated_files > max_files_small or estimated_tasks > max_tasks_small or has_integrations:
        return "medium"

    return "small"


def _estimate_files(text: str) -> int:
    import re

    file_keywords = re.findall(r"\b(file|module|component|class|function|endpoint|route|page|screen)\b", text.lower())
    return max(len(file_keywords), 1)


def _estimate_tasks(text: str) -> int:
    import re

    task_indicators = re.findall(r"\b(should|must|need to|implement|create|build|add|update|fix)\b", text.lower())
    return max(len(task_indicators), 1)


def _has_new_domains(text: str) -> bool:
    domain_keywords = ["machine learning", "ai", "blockchain", "iot", "real-time", "streaming", "ml model", "neural"]
    text_lower = text.lower()
    return any(kw in text_lower for kw in domain_keywords)


def _has_integrations(text: str) -> bool:
    integration_keywords = [
        "api",
        "integration",
        "webhook",
        "third-party",
        "external service",
        "sdk",
        "oauth",
        "payment",
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in integration_keywords)


def _has_ambiguity(text: str) -> bool:
    ambiguity_keywords = ["maybe", "perhaps", "ideally", "somewhat", "roughly", "approximately", "might want"]
    text_lower = text.lower()
    return any(kw in text_lower for kw in ambiguity_keywords)


def deactivate_inactive_stages(stages: dict[str, Any], complexity: str, ui_project: bool) -> dict[str, Any]:
    from eng_loop.state import COMPLEXITY_ORDER, STAGE_MIN_COMPLEXITY, STAGE_ORDER

    result = dict(stages)
    for sid in STAGE_ORDER:
        min_c = STAGE_MIN_COMPLEXITY.get(sid)
        if min_c and COMPLEXITY_ORDER.get(complexity, 0) < COMPLEXITY_ORDER.get(min_c, 0):
            result[sid]["done"] = True
            result[sid]["attempts"] = 0
            result[sid]["essence_checked"] = False

        if sid in ("e2e.execute", "smoke.test") and not ui_project:
            result[sid]["done"] = True

    return result


def detect_ui_project(paths: dict[str, Any]) -> bool:
    import os

    project_root = paths.get("project_root", "")
    ui_indicators = ["package.json", "vite.config", "next.config", "nuxt.config", "angular.json", "tailwind.config"]
    for indicator in ui_indicators:
        for ext in [".js", ".ts", ".json", ".mjs"]:
            if os.path.exists(os.path.join(project_root, indicator + ext)):
                return True
            if os.path.exists(os.path.join(project_root, indicator)):
                return True
    return False


# ──────────────────────────────────────────────
# Work Type Classification
# ──────────────────────────────────────────────

WORK_TYPE_KEYWORDS: dict[str, list[str]] = {
    "documentation": [
        "write summary",
        "create summary",
        "generate summary",
        "write document",
        "create document",
        "generate report",
        "write docs",
        "create docs",
        "update docs",
        "update documentation",
        "escrever resumo",
        "criar resumo",
        "gerar relatorio",
        "project summary",
        "sumario do projeto",
        "sumário do projeto",
        "write a summary",
        "create a summary",
        "generate a summary",
        "write the",
        "create the",
        "generate the",
        "documentation",
        "documentação",
        "readme",
        "changelog",
        "write changelog",
        "report",
        "relatorio",
        "relatório",
        "artifact",
        "artifacts",
    ],
    "documentation_single": [
        "summary",
        "document",
        "docs",
        "report",
        "relatorio",
        "changelog",
        "readme",
        "artifact",
    ],
    "operational": [
        "run tests",
        "execute tests",
        "run test",
        "execute test",
        "rodar testes",
        "executar testes",
        "rodar test",
        "executar test",
        "run e2e",
        "execute e2e",
        "rodar e2e",
        "executar e2e",
        "run build",
        "execute build",
        "deploy",
        "deployar",
        "migrate",
        "seed",
        "rollback",
        "backup",
        "monitor",
        "check health",
        "verify deployment",
        "run lint",
        "run typecheck",
        "npm test",
        "pytest",
        "playwright test",
        "vitest",
        "jest",
        "garantir que esteja funcionando",
        "garantir funcionamento",
        "production readiness",
        "entregue ao cliente",
        "test suite",
        "full test",
        "all tests",
        "run the test",
    ],
    "operational_single": [
        "testes",
        "test",
        "e2e",
        "build",
        "deploy",
        "lint",
        "typecheck",
        "rodar",
        "executar",
        "firebase",
        "production",
        "staging",
        "suite",
    ],
    "bugfix": [
        "fix",
        "repair",
        "corrigir",
        "broken",
        "bug",
        "fix bug",
        "fix error",
        "fix test",
        "fix tests",
        "corrigir erro",
        "corrigir bug",
        "corrigir teste",
        "resolve issue",
        "patch",
        "hotfix",
    ],
    "bugfix_single": [
        "erro",
        "error",
        "falha",
        "fail",
        "failing",
    ],
    "validation": [
        "validate",
        "validation",
        "validar",
        "validação",
        "validade",
        "valide",
        "valide o",
        "validar o",
        "validar sistema",
        "validate system",
        "validate the",
        "production readiness",
        "prontidão para produção",
        "garantir que esteja funcionando",
        "garantir funcionamento",
        "check if working",
        "ensure it works",
        "ensure production",
        "verify system",
        "verificar sistema",
        "audit",
        "auditar",
        "health check",
        "readiness check",
        "all stages",
        "all flows",
        "todas etapas",
        "todos fluxos",
    ],
    "validation_single": [
        "valid",
        "check",
        "audit",
        "readiness",
        "garantir",
    ],
    "feature": [
        "implement",
        "create",
        "add feature",
        "build",
        "develop",
        "implementar",
        "criar",
        "adicionar",
        "desenvolver",
        "new feature",
        "nova funcionalidade",
        "novo recurso",
        "add support",
        "implement support",
    ],
}


def classify_work_type(work_item: str) -> str:
    """Classify work item as documentation, operational, bugfix, or feature.

    Documentation: write/generate documents, summaries, reports.
    Operational: run existing code (tests, builds, deploys).
    Bugfix: fix broken behavior.
    Feature: create new functionality (default).

    Uses two-tier matching:
    1. Multi-word phrases (high confidence, weight=2)
    2. Single words (lower confidence, weight=1)
    """
    text_lower = work_item.lower()

    # Tier 1: Multi-word phrase matches (weight=2)
    documentation_phrase = sum(2 for kw in WORK_TYPE_KEYWORDS["documentation"] if kw in text_lower)
    operational_phrase = sum(2 for kw in WORK_TYPE_KEYWORDS["operational"] if kw in text_lower)
    bugfix_phrase = sum(2 for kw in WORK_TYPE_KEYWORDS["bugfix"] if kw in text_lower)
    validation_phrase = sum(2 for kw in WORK_TYPE_KEYWORDS["validation"] if kw in text_lower)
    feature_phrase = sum(2 for kw in WORK_TYPE_KEYWORDS["feature"] if kw in text_lower)

    # Tier 2: Single-word matches (weight=1)
    documentation_single = sum(1 for kw in WORK_TYPE_KEYWORDS["documentation_single"] if kw in text_lower)
    operational_single = sum(1 for kw in WORK_TYPE_KEYWORDS["operational_single"] if kw in text_lower)
    bugfix_single = sum(1 for kw in WORK_TYPE_KEYWORDS["bugfix_single"] if kw in text_lower)
    validation_single = sum(1 for kw in WORK_TYPE_KEYWORDS["validation_single"] if kw in text_lower)

    documentation_score = documentation_phrase + documentation_single
    operational_score = operational_phrase + operational_single
    bugfix_score = bugfix_phrase + bugfix_single
    validation_score = validation_phrase + validation_single
    feature_score = feature_phrase

    # Documentation: needs phrase match (>=2) OR strong single-word signal (>=3)
    if documentation_phrase >= 2 or (
        documentation_single >= 3
        and documentation_score > operational_score
        and documentation_score > bugfix_score
        and documentation_score > validation_score
        and documentation_score > feature_score
    ):
        return "documentation"

    # Validation: needs phrase match (>=2) OR strong single-word signal (>=3)
    if validation_phrase >= 2 or (
        validation_single >= 3
        and validation_score > documentation_score
        and validation_score > operational_score
        and validation_score > bugfix_score
        and validation_score > feature_score
    ):
        return "validation"

    # Operational: needs phrase match (>=2) OR strong single-word signal (>=4)
    if operational_phrase >= 2 or (
        operational_single >= 4 and operational_score > bugfix_score and operational_score > feature_score
    ):
        return "operational"

    # Bugfix: needs phrase match or single-word signal
    if bugfix_phrase >= 2 or (bugfix_score >= 3 and bugfix_score > feature_score):
        return "bugfix"

    return "feature"


def is_operational_work(work_item: str) -> bool:
    return classify_work_type(work_item) == "operational"


# Stages to deactivate for operational work (no new code creation needed)
OPERATIONAL_EXCLUDED_STAGES: list[str] = [
    "impl.design",
    "impl.code",
    "doc.update",
    "verify",
    "arch.requirements",
    "arch.solution",
    "arch.review",
    "design.user-research",
    "design.personas",
    "design.info-arch",
    "design.interaction",
    "design.design-system",
    "design.visual-design",
    "doc.decisions",
    "doc.project",
]

# Stages to deactivate for documentation work (just init + impl.code + post)
DOCUMENTATION_EXCLUDED_STAGES: list[str] = [
    "impl.design",
    "doc.update",
    "verify",
    "deploy.prepare",
    "arch.requirements",
    "arch.solution",
    "arch.review",
    "design.user-research",
    "design.personas",
    "design.info-arch",
    "design.interaction",
    "design.design-system",
    "design.visual-design",
    "qa.security",
    "qa.api-contract",
    "qa.performance",
    "e2e.execute",
    "smoke.test",
    "doc.decisions",
    "doc.project",
]

# Stages to deactivate for validation work (no new code, skip creation stages)
# Validation tasks audit existing systems: init → verify → QA → deploy → post
VALIDATION_EXCLUDED_STAGES: list[str] = [
    "impl.design",
    "impl.code",
    "doc.update",
    "arch.requirements",
    "arch.solution",
    "arch.review",
    "design.user-research",
    "design.personas",
    "design.info-arch",
    "design.interaction",
    "design.design-system",
    "design.visual-design",
    "doc.decisions",
    "doc.project",
]


def deactivate_for_work_type(stages: dict[str, Any], work_type: str) -> dict[str, Any]:
    """Deactivate stages that don't apply for the given work type."""
    if work_type == "feature":
        return stages

    result = dict(stages)
    excluded = []

    if work_type == "documentation":
        excluded = DOCUMENTATION_EXCLUDED_STAGES
    elif work_type == "validation":
        excluded = VALIDATION_EXCLUDED_STAGES
    elif work_type == "operational":
        excluded = OPERATIONAL_EXCLUDED_STAGES
    elif work_type == "bugfix":
        # Bugfix: skip design stages, keep impl but skip heavy architecture
        excluded = [
            "design.user-research",
            "design.personas",
            "design.info-arch",
            "design.interaction",
            "design.design-system",
            "design.visual-design",
        ]

    for sid in excluded:
        if sid in result:
            result[sid]["done"] = True
            result[sid]["attempts"] = 0
            result[sid]["essence_checked"] = False

    return result
