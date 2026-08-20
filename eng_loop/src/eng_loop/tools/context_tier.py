from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ============================================================
# CONTEXT TIERS — Hierarchical memory model (3 layers)
# ============================================================

# Global: shared across all stages (work_item, decisions, complexity, etc.)
GLOBAL_TIER_KEYS = {
    "work_item",
    "complexity",
    "work_type",
    "ui_project",
    "tags",
    "ideation",
    "decisions",
    "graph_topology",
    "active_nodes",
    "errors",
}

# Group: domain-scoped knowledge
GROUP_DOMAINS = {
    "init": {"init_summary", "ideation", "journey_map", "refined_work_item"},
    "design": {
        "design.user-research",
        "design.personas",
        "design.info-arch",
        "design.interaction",
        "design.design-system",
        "design.visual-design",
    },
    "arch": {"arch.requirements", "arch.solution", "arch.review"},
    "impl": {"impl.design", "impl.code", "diff"},
    "verify": {"verify"},
    "qa": {"qa.security", "qa.api-contract", "qa.performance"},
    "deploy": {"deploy.prepare"},
    "doc": {"doc.update", "doc.decisions", "doc.project"},
}

# Private: stage-specific working memory
PRIVATE_TIER_KEYS = {
    "current_stage",
    "iteration",
    "status",
    "blocking_condition",
}


# Stage-to-domain mapping for tier access control
STAGE_DOMAIN_MAP: dict[str, str] = {
    "init": "init",
    "init.ideate": "init",
    "init.bdd": "init",
    "init.refine": "init",
    "design.user-research": "design",
    "design.personas": "design",
    "design.info-arch": "design",
    "design.interaction": "design",
    "design.design-system": "design",
    "design.visual-design": "design",
    "arch.requirements": "arch",
    "arch.solution": "arch",
    "arch.review": "arch",
    "impl.design": "impl",
    "impl.code": "impl",
    "doc.update": "doc",
    "verify": "verify",
    "qa.static": "qa",
    "qa.unit": "qa",
    "qa.integration": "qa",
    "e2e.execute": "verify",
    "qa.security": "qa",
    "qa.api-contract": "qa",
    "qa.performance": "qa",
    "qa.human.flow": "qa",
    "qa.human.ux": "qa",
    "deploy.prepare": "deploy",
    "smoke.test": "deploy",
    "doc.decisions": "doc",
    "doc.project": "doc",
    "post": "post",
}


# Read dependencies: which domains each stage needs to read
STAGE_READ_DEPENDENCIES: dict[str, list[str]] = {
    "init": [],
    "init.ideate": ["init"],
    "init.bdd": ["init"],
    "init.refine": ["init"],
    "design.user-research": ["init"],
    "design.personas": ["init", "design"],
    "design.info-arch": ["init", "design"],
    "design.interaction": ["init", "design"],
    "design.design-system": ["init", "design"],
    "design.visual-design": ["init", "design"],
    "arch.requirements": ["init"],
    "arch.solution": ["init", "arch"],
    "arch.review": ["init", "arch"],
    "impl.design": ["init", "arch"],
    "impl.code": ["init", "arch", "impl"],
    "doc.update": ["init", "impl"],
    "verify": ["init", "impl"],
    "qa.static": ["init", "impl"],
    "qa.unit": ["init", "impl"],
    "qa.integration": ["init", "impl"],
    "e2e.execute": ["init", "impl"],
    "qa.security": ["init", "impl"],
    "qa.api-contract": ["init", "impl"],
    "qa.performance": ["init", "impl"],
    "qa.human.flow": ["init", "impl", "qa"],
    "qa.human.ux": ["init", "impl", "qa"],
    "deploy.prepare": ["init", "impl", "verify", "qa"],
    "smoke.test": ["init", "impl"],
    "doc.decisions": [],
    "doc.project": ["init", "impl"],
    "post": [],
}


@dataclass
class ContextTierConfig:
    """Configuration for context budget per tier."""

    global_max_tokens: int = 4000
    group_max_tokens: int = 8000
    private_max_tokens: int = 2000
    total_agent_context_limit: int = 66666


def get_stage_domain(stage_id: str) -> str:
    return STAGE_DOMAIN_MAP.get(stage_id, "post")


def get_read_dependencies(stage_id: str) -> list[str]:
    return STAGE_READ_DEPENDENCIES.get(stage_id, [])


def build_context_tiers(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build the 3-tier context structure from PipelineState.

    Returns:
        {
            "global": { key: value, ... },
            "group": { domain: { key: value, ... }, ... },
            "private": { key: value, ... },
        }
    """
    tiers: dict[str, dict[str, Any]] = {
        "global": {},
        "group": {},
        "private": {},
    }

    # Global tier: shared keys
    for key in GLOBAL_TIER_KEYS:
        if key in state:
            tiers["global"][key] = state[key]

    # Group tier: domain-scoped artifacts
    stage_artifacts = state.get("stage_artifacts", {})
    for domain, artifact_keys in GROUP_DOMAINS.items():
        domain_artifacts = {}
        for key in artifact_keys:
            if key in stage_artifacts:
                domain_artifacts[key] = stage_artifacts[key]
        if domain_artifacts:
            tiers["group"][domain] = domain_artifacts

    # Private tier: stage execution state
    for key in PRIVATE_TIER_KEYS:
        if key in state:
            tiers["private"][key] = state[key]

    return tiers


def get_accessible_context(
    stage_id: str,
    tiers: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Filter context tiers based on stage's read dependencies.

    Returns only the tiers/domains that this stage is allowed to access.
    """
    domain = get_stage_domain(stage_id)
    read_deps = get_read_dependencies(stage_id)

    accessible: dict[str, dict[str, Any]] = {
        "global": tiers.get("global", {}),
        "group": {},
        "private": tiers.get("private", {}),
    }

    group = tiers.get("group", {})
    for dep_domain in read_deps:
        if dep_domain in group:
            accessible["group"][dep_domain] = group[dep_domain]

    if domain in group:
        accessible["group"][domain] = group[domain]

    return accessible


def estimate_context_tokens(tiers: dict[str, dict[str, Any]]) -> int:
    """Estimate token count of context tiers (4 chars per token)."""
    total_chars = 0
    for tier_data in tiers.values():
        total_chars += len(str(tier_data))
    return total_chars // 4


def enforce_context_budget(
    tiers: dict[str, dict[str, Any]],
    config: ContextTierConfig,
) -> dict[str, dict[str, Any]]:
    """Truncate context tiers to stay within budget.

    Priority: global > group > private.
    """
    result = {
        "global": dict(tiers.get("global", {})),
        "group": {},
        "private": {},
    }

    remaining = config.total_agent_context_limit
    global_chars = len(str(result["global"]))
    global_tokens = global_chars // 4

    if global_tokens > config.global_max_tokens:
        # Truncate global tier to budget while preserving critical keys
        critical_keys = {"work_item", "complexity", "work_type"}
        truncated = {k: v for k, v in result["global"].items() if k in critical_keys}
        truncated["_truncated"] = True
        truncated["_original_size"] = global_tokens
        result["global"] = truncated
        remaining -= config.global_max_tokens
    else:
        remaining -= global_tokens

    group = tiers.get("group", {})
    group_budget = min(config.group_max_tokens, remaining)
    group_tokens_used = 0

    for domain, artifacts in group.items():
        if group_tokens_used >= group_budget:
            break
        artifact_chars = len(str(artifacts))
        artifact_tokens = artifact_chars // 4
        if group_tokens_used + artifact_tokens <= group_budget:
            result["group"][domain] = artifacts
            group_tokens_used += artifact_tokens
            remaining -= artifact_tokens

    private = tiers.get("private", {})
    if remaining > config.private_max_tokens:
        result["private"] = private

    return result
