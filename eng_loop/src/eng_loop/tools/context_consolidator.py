from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# CONTEXT CONSOLIDATOR — Dedup, compression, incremental diff
# ============================================================

SIMILARITY_THRESHOLD = 0.98  # Only dedup near-identical content (was 0.85, too aggressive)


def compute_text_hash(text: str) -> str:
    """Fast hash for content deduplication."""
    return hashlib.md5(text.encode("utf-8", errors="replace"), usedforsecurity=False).hexdigest()[:12]


def estimate_similarity(text_a: str, text_b: str) -> float:
    """Simple Jaccard-like similarity using word sets.

    Good enough for dedup detection without external dependencies.
    """
    if not text_a or not text_b:
        return 0.0

    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())

    if not words_a or not words_b:
        return 0.0

    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return intersection / union if union > 0 else 0.0


def deduplicate_stage_artifacts(
    stage_artifacts: dict[str, str],
    threshold: float = SIMILARITY_THRESHOLD,
) -> tuple[dict[str, str], list[str]]:
    """Remove duplicate artifacts by content similarity.

    Returns:
        (deduplicated_artifacts, list_of_removed_keys)
    """
    if len(stage_artifacts) <= 1:
        return stage_artifacts, []

    result = {}
    removed = []
    seen_hashes: dict[str, str] = {}

    for key, content in stage_artifacts.items():
        if not content.strip():
            continue

        content_hash = compute_text_hash(content)

        is_duplicate = False
        for existing_key, existing_hash in seen_hashes.items():
            if content_hash == existing_hash:
                removed.append(f"{key} (identical to {existing_key})")
                is_duplicate = True
                break

        if not is_duplicate:
            for existing_key in seen_hashes:
                existing_content = result.get(existing_key, "")
                if estimate_similarity(content, existing_content) >= threshold:
                    removed.append(f"{key} (similar to {existing_key})")
                    is_duplicate = True
                    break

        if not is_duplicate:
            result[key] = content
            seen_hashes[key] = content_hash

    return result, removed


def compress_handoff(handoff: str, max_tokens: int = 125) -> str:
    """Compress a handoff summary to stay within token budget.

    DEPRECATED: Hard truncation removed. Handoffs are now passed by reference
    (artifact paths) rather than inline content. The agent reads what it needs.
    """
    # Return full content — no truncation. Budget is managed by agent lifecycle, not content limits.
    return handoff


def compute_state_diff(
    old_state: dict[str, Any],
    new_state: dict[str, Any],
) -> dict[str, Any]:
    """Compute incremental diff between two state snapshots.

    Returns only the keys that changed, for efficient handoff.
    """
    diff = {}
    all_keys = set(list(old_state.keys()) + list(new_state.keys()))

    for key in all_keys:
        old_val = old_state.get(key)
        new_val = new_state.get(key)

        if old_val != new_val:
            diff[key] = new_val

    return diff


def build_handoff_summary(
    stage_id: str,
    stage_result: dict[str, Any],
    decisions: list[str],
    max_tokens: int = 125,
) -> str:
    """Build a compact handoff summary for the next stage.

    Contains: what was done, decisions, artifacts produced, alerts.
    """
    parts = []
    parts.append(f"Stage: {stage_id}")

    output = stage_result.get(
        "output",
        stage_result.get(
            "design_output", stage_result.get("architecture_output", stage_result.get("implementation_summary", ""))
        ),
    )
    if output:
        output_str = str(output)
        # No truncation — budget managed by agent lifecycle, not content limits
        parts.append(f"Output: {output_str}")

    if decisions:
        parts.append(f"Decisions: {len(decisions)} recorded")
        # Include all decisions — no arbitrary cap
        for d in decisions:
            parts.append(f"  - {d}")

    artifacts = stage_result.get("artifacts", stage_result.get("files_created", []))
    if artifacts:
        parts.append(f"Artifacts: {len(artifacts)} produced")

    errors = stage_result.get("gaps", stage_result.get("critical_findings", []))
    if errors:
        parts.append(f"Alerts: {len(errors)} issues found")
        # Include all alerts — no arbitrary cap
        for e in errors:
            parts.append(f"  ! {str(e)}")

    summary = "\n".join(parts)
    return compress_handoff(summary, max_tokens)


class ContextConsolidator:
    """Manages context lifecycle: dedup, compression, incremental updates.

    Use after each stage to maintain context health.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._artifact_history: dict[str, list[tuple[str, str]]] = {}

    def process_stage_output(
        self,
        stage_id: str,
        stage_artifacts: dict[str, str],
        stage_result: dict[str, Any],
        decisions: list[str],
    ) -> dict[str, Any]:
        """Process stage output: dedup artifacts, build handoff, track history.

        Returns state update dict with cleaned artifacts and handoff.
        """
        update: dict[str, Any] = {}

        deduped, removed = deduplicate_stage_artifacts(stage_artifacts)
        if removed:
            logger.info("Context dedup: removed %d artifacts: %s", len(removed), removed)
        update["stage_artifacts"] = deduped

        handoff = build_handoff_summary(stage_id, stage_result, decisions)
        existing_handoffs = stage_artifacts.get("__handoffs__", {})
        if isinstance(existing_handoffs, str):
            try:
                existing_handoffs = json.loads(existing_handoffs)
            except (json.JSONDecodeError, TypeError):
                existing_handoffs = {}
        existing_handoffs[stage_id] = handoff
        update["handoffs"] = existing_handoffs

        self._artifact_history.setdefault(stage_id, []).append((compute_text_hash(str(stage_result)), handoff))

        return update

    def should_consolidate(self, iteration: int, every: int = 5) -> bool:
        """Check if context consolidation is needed."""
        return iteration > 0 and iteration % every == 0

    def get_context_health(self, state: dict[str, Any]) -> dict[str, Any]:
        """Report context health metrics."""
        artifacts = state.get("stage_artifacts", {})
        handoffs = state.get("handoffs", {})
        decisions = state.get("decisions", [])

        total_chars = sum(len(v) for v in artifacts.values())
        total_tokens = total_chars // 4

        return {
            "artifact_count": len(artifacts),
            "handoff_count": len(handoffs),
            "decision_count": len(decisions),
            "estimated_tokens": total_tokens,
            "budget_remaining": max(0, 66666 - total_tokens),
            "budget_pct_used": min(100, (total_tokens / 66666) * 100),
        }
