from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class NodeSpec:
    """Declarative specification for a graph node/stage."""
    id: str
    node_name: str
    handler: Callable[[dict[str, Any]], Any]
    phase: str
    min_complexity: str = "small"
    requires_ui: bool = False
    requires_tags: list[str] = field(default_factory=list)
    excluded_for_work_types: list[str] = field(default_factory=list)
    parallel_group: str | None = None
    depends_on: list[str] = field(default_factory=list)
    model_override: dict[str, Any] | None = None
    description: str = ""


COMPLEXITY_ORDER = {"small": 0, "medium": 1, "large": 2, "complex": 3}


def complexity_meets(complexity: str, min_complexity: str) -> bool:
    """Check if a complexity level meets the minimum requirement."""
    return COMPLEXITY_ORDER.get(complexity, 0) >= COMPLEXITY_ORDER.get(min_complexity, 0)


class NodeRegistry:
    """Central registry of all available stage nodes."""

    def __init__(self):
        self._specs: dict[str, NodeSpec] = {}

    def register(self, spec: NodeSpec) -> None:
        self._specs[spec.id] = spec

    def get(self, stage_id: str) -> NodeSpec | None:
        return self._specs.get(stage_id)

    def all_specs(self) -> list[NodeSpec]:
        return list(self._specs.values())

    def filter(
        self,
        complexity: str = "small",
        ui_project: bool = False,
        tags: list[str] | None = None,
        work_type: str = "feature",
    ) -> list[NodeSpec]:
        """Return only the nodes that should be active for the given context."""
        tags = tags or []
        result = []
        for spec in self._specs.values():
            if not complexity_meets(complexity, spec.min_complexity):
                continue
            if spec.requires_ui and not ui_project:
                continue
            if work_type in spec.excluded_for_work_types:
                continue
            for tag in spec.requires_tags:
                if tag not in tags:
                    break
            else:
                result.append(spec)
        return result

    def get_by_phase(self, phase: str) -> list[NodeSpec]:
        return [s for s in self._specs.values() if s.phase == phase]

    def get_parallel_groups(self) -> dict[str, list[NodeSpec]]:
        groups: dict[str, list[NodeSpec]] = {}
        for spec in self._specs.values():
            if spec.parallel_group:
                groups.setdefault(spec.parallel_group, []).append(spec)
        return groups

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, stage_id: str) -> bool:
        return stage_id in self._specs


def _make_node_name(stage_id: str) -> str:
    return stage_id.replace(".", "-").replace("_", "-")


def build_registry() -> NodeRegistry:
    """Build the full node registry by importing handlers from existing node modules."""
    from eng_loop.nodes.init import (
        init_node, init_ideate_node, init_bdd_node, init_refine_node,
    )
    from eng_loop.nodes.design import DESIGN_STAGES, design_node, get_design_nodes
    from eng_loop.nodes.architecture import ARCH_STAGES, arch_node, get_arch_nodes
    from eng_loop.nodes.implementation import impl_design_node, impl_code_node, doc_update_node
    from eng_loop.nodes.verification import verify_node, e2e_execute_node
    from eng_loop.nodes.qa import QA_STAGES, qa_node, get_qa_nodes
    from eng_loop.nodes.deploy import deploy_prepare_node, smoke_test_node
    from eng_loop.nodes.documentation import doc_decisions_node, doc_project_node
    from eng_loop.nodes.post import post_node

    registry = NodeRegistry()

    # --- INIT phase ---
    registry.register(NodeSpec(
        id="init", node_name="init", handler=init_node,
        phase="init", description="Validate work item, classify complexity, prepare loop",
    ))
    registry.register(NodeSpec(
        id="init.ideate", node_name="init-ideate", handler=init_ideate_node,
        phase="init", description="BMAD ideation with Party Mode",
    ))
    registry.register(NodeSpec(
        id="init.bdd", node_name="init-bdd", handler=init_bdd_node,
        phase="init", min_complexity="large",
        description="BDD journey mapping with Gherkin scenarios",
    ))
    registry.register(NodeSpec(
        id="init.refine", node_name="init-refine", handler=init_refine_node,
        phase="init", description="Refine work item into engineering spec",
    ))

    # --- DESIGN phase (all require large+) ---
    for stage_id in DESIGN_STAGES:
        node_name = _make_node_name(stage_id)
        registry.register(NodeSpec(
            id=stage_id, node_name=node_name, handler=design_node(stage_id),
            phase="design", min_complexity="large",
            description=f"Design stage: {stage_id}",
        ))

    # --- ARCHITECTURE phase ---
    arch_complexity = {
        "arch.requirements": "medium",
        "arch.solution": "medium",
        "arch.review": "complex",
    }
    for stage_id in ARCH_STAGES:
        node_name = _make_node_name(stage_id)
        registry.register(NodeSpec(
            id=stage_id, node_name=node_name, handler=arch_node(stage_id),
            phase="arch", min_complexity=arch_complexity.get(stage_id, "medium"),
            description=f"Architecture stage: {stage_id}",
        ))

    # --- IMPLEMENTATION phase ---
    registry.register(NodeSpec(
        id="impl.design", node_name="impl-design", handler=impl_design_node,
        phase="impl", description="Implementation blueprint creation",
    ))
    registry.register(NodeSpec(
        id="impl.code", node_name="impl-code", handler=impl_code_node,
        phase="impl", description="TDD code implementation",
    ))
    registry.register(NodeSpec(
        id="doc.update", node_name="doc-update", handler=doc_update_node,
        phase="impl", description="Update existing project documentation",
    ))

    # --- VERIFICATION phase ---
    registry.register(NodeSpec(
        id="verify", node_name="verify", handler=verify_node,
        phase="verify", description="Independent verification with discrimination sensor",
    ))
    registry.register(NodeSpec(
        id="e2e.execute", node_name="e2e-execute", handler=e2e_execute_node,
        phase="verify", requires_ui=True,
        description="E2E Playwright testing with 4-layer assertions",
    ))

    # --- QA phase (parallel capable) ---
    qa_complexity = {
        "qa.security": "medium",
        "qa.api-contract": "medium",
        "qa.performance": "complex",
    }
    for stage_id in QA_STAGES:
        node_name = _make_node_name(stage_id)
        registry.register(NodeSpec(
            id=stage_id, node_name=node_name, handler=qa_node(stage_id),
            phase="qa", min_complexity=qa_complexity.get(stage_id, "medium"),
            parallel_group="qa",
            description=f"QA stage: {stage_id}",
        ))

    # --- DEPLOY phase ---
    registry.register(NodeSpec(
        id="deploy.prepare", node_name="deploy-prepare", handler=deploy_prepare_node,
        phase="deploy", description="Build, lint, typecheck, env config, migration",
    ))
    registry.register(NodeSpec(
        id="smoke.test", node_name="smoke-test", handler=smoke_test_node,
        phase="deploy", requires_ui=True,
        description="Full user journey against production build",
    ))

    # --- DOCUMENTATION phase ---
    registry.register(NodeSpec(
        id="doc.decisions", node_name="doc-decisions", handler=doc_decisions_node,
        phase="doc", min_complexity="medium",
        description="Consolidate AD-NNN decisions into MADR format",
    ))
    registry.register(NodeSpec(
        id="doc.project", node_name="doc-project", handler=doc_project_node,
        phase="doc", min_complexity="medium",
        description="Generate project documentation (arc42 + C4)",
    ))

    # --- POST phase ---
    registry.register(NodeSpec(
        id="post", node_name="post", handler=post_node,
        phase="post", description="Finalize, lessons consolidation, commit",
    ))

    return registry
