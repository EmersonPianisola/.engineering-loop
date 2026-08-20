from __future__ import annotations

import re
from typing import Any

from eng_loop.schemas import ErrorClassification

ERROR_PATTERNS: list[tuple[str, str, str, str]] = [
    # (regex, category, strategy, description)
    (
        r"(?i)(timeout|timed?\s*out|deadline|exceeded\s+time|connection\s*(refused|reset|closed))",
        "transient",
        "retry",
        "Transient network or timeout error — retry may succeed",
    ),
    (
        r"(?i)(rate\s*limit|429|too\s+many\s+requests|throttl)",
        "transient",
        "retry",
        "Rate limit hit — backoff and retry",
    ),
    (
        r"(?i)(llm\s*error|model\s*error|api\s*error|openai\s*error|chat\s*completion)",
        "infrastructure",
        "retry",
        "LLM API error — check model availability",
    ),
    (
        r"(?i)(disk\s*full|no\s+space|permission\s*denied|access\s*denied|eacces)",
        "infrastructure",
        "abort",
        "Infrastructure issue: disk space or permissions",
    ),
    (
        r"(?i)(context\s*(window|budget|overflow|exceeded|full)|token\s*(limit|exceeded|budget))",
        "context_overflow",
        "retry",
        "Context window exceeded — compaction needed",
    ),
    (
        r"(?i)(json.*invalid|malformed|parse.*error|unexpected.*token|pydantic|validation.*error|schema.*violation)",
        "schema",
        "retry",
        "Schema or JSON parsing error — retry with stricter output",
    ),
    (
        r"(?i)(contract\s*violation|type\s*mismatch|interface.*error|signature.*mismatch)",
        "contract",
        "rollback",
        "Contract violation — rollback and re-implement",
    ),
    (
        r"(?i)(non-?convergence|stalled|stall|loop.*detected|redundant|no.*progress)",
        "logic",
        "rollback",
        "Agent non-convergence or stall — needs different approach",
    ),
    (
        r"(?i)(agent\s*error|exceeded\s+max|iteration.*limit|max.*attempt)",
        "logic",
        "rollback",
        "Agent exceeded limits — fix tasks or constraints needed",
    ),
    (
        r"(?i)(test.*fail|assertion.*error|expect.*not.*match|verification.*fail)",
        "logic",
        "rollback",
        "Test or verification failure — implementation needs fix",
    ),
    (
        r"(?i)(blocked|block.*reason|infrastructure.*fail)",
        "infrastructure",
        "retry",
        "Stage blocked due to infrastructure issue",
    ),
]


def classify_error(blocking_condition: str, state: dict[str, Any]) -> ErrorClassification:
    """Classify an error based on the blocking condition and pipeline state.

    Uses pattern matching against known error signatures. Falls back to
    'logic' category with 'rollback' strategy for unknown errors.
    """
    error_text = blocking_condition or ""
    current_stage = state.get("current_stage", "")
    status = state.get("status", "")

    for pattern, category, strategy, description in ERROR_PATTERNS:
        if re.search(pattern, error_text):
            severity = _compute_severity(category, current_stage, state)
            is_retryable = strategy != "abort"
            return ErrorClassification(
                category=category,
                severity=severity,
                is_retryable=is_retryable,
                description=description,
                suggested_strategy=strategy,
            )

    # Fallback: analyze based on stage context
    fallback_category = _infer_category_from_stage(current_stage, state)
    fallback_strategy = "rollback" if fallback_category in ("logic", "contract") else "retry"
    severity = _compute_severity(fallback_category, current_stage, state)

    return ErrorClassification(
        category=fallback_category,
        severity=severity,
        is_retryable=fallback_strategy != "abort",
        description=f"Unclassified error in {current_stage}: {error_text[:200]}",
        suggested_strategy=fallback_strategy,
    )


def _compute_severity(category: str, stage_id: str, state: dict[str, Any]) -> str:
    """Compute error severity based on category and stage criticality."""
    critical_stages = {"impl.code", "verify", "e2e.execute", "deploy.prepare"}
    qa_stages = {"qa.static", "qa.unit", "qa.integration", "qa.security"}

    if stage_id in critical_stages:
        if category in ("infrastructure", "context_overflow"):
            return "critical"
        return "high"
    if stage_id in qa_stages:
        return "medium"
    if category in ("infrastructure", "context_overflow"):
        return "high"
    return "medium"


def _infer_category_from_stage(stage_id: str, state: dict[str, Any]) -> str:
    """Infer error category from the stage where the error occurred."""
    stage_data = state.get("stages", {}).get(stage_id, {})
    stage_status = stage_data.get("status", "")
    verdict = stage_data.get("verdict", "")

    if stage_status == "blocked":
        return "infrastructure"
    if verdict == "FAIL":
        return "logic"
    if stage_id.startswith("qa."):
        return "logic"
    if stage_id in ("verify", "e2e.execute"):
        return "logic"
    return "logic"
