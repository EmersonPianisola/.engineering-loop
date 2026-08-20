from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any

from langgraph.types import Command

from eng_loop.model import create_model_from_config
from eng_loop.schemas import EssenceDecision, EssenceOutput, Severity
from eng_loop.state import get_work_item_text
from eng_loop.templates import load_skill
from eng_loop.tools.agent_runner import AgentResult, run_agent
from eng_loop.tools.agent_tools import get_essence_tools
from eng_loop.tools.tension_memory import TensionMemory

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# ── Tension Memory singleton ───────────────────────────────────────────
_tension_memory: TensionMemory | None = None


def get_tension_memory() -> TensionMemory:
    """Return global tension memory instance. Lazy-init if needed."""
    global _tension_memory
    if _tension_memory is None:
        _tension_memory = TensionMemory()
    return _tension_memory


def init_tension_memory(storage_path: str | None = None) -> TensionMemory:
    """Initialize tension memory with persistent storage path.

    Call once at CLI startup with the project-specific path (.eng/tension-memory.json).
    """
    global _tension_memory
    _tension_memory = TensionMemory(storage_path)
    return _tension_memory


# ── Severity policy ────────────────────────────────────────────────────
SEVERITY_ORDER: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
}


def should_clarify(finding_severity: str, threshold: str) -> bool:
    """Deterministic policy: should a finding trigger user clarification?

    Runtime decides based on finding severity vs configured threshold.
    The LLM never decides its own authority.
    """
    return SEVERITY_ORDER.get(finding_severity, 0) >= SEVERITY_ORDER.get(threshold, 1)


# ── Result types ───────────────────────────────────────────────────────
@dataclass
class EssenceResult:
    """Result from running the essence gate before a stage."""

    passed: bool = False
    blocked: bool = False
    waiting_for_input: bool = False
    decision: EssenceDecision = EssenceDecision.PASS
    tension: str = ""
    adjustments: list[str] = None
    clarifying_questions: list[dict[str, Any]] = None
    updated_state: dict[str, Any] | None = None

    def __post_init__(self):
        if self.adjustments is None:
            self.adjustments = []
        if self.clarifying_questions is None:
            self.clarifying_questions = []


# ── Decorator ──────────────────────────────────────────────────────────
def essence_gate(stage_id: str):
    """Decorator that runs the essence gate before a node handler.

    Usage:
        @essence_gate("impl.code")
        def impl_code_node(state: dict[str, Any]) -> Command[str]:
            ...

    The decorator extracts config and paths from state, runs the essence
    gate, and returns a blocked/waiting Command based on the policy decision.
    """

    def decorator(fn: Callable[[dict[str, Any]], Command[str]]) -> Callable[[dict[str, Any]], Command[str]]:
        @wraps(fn)
        def wrapper(state: dict[str, Any]) -> Command[str]:
            config = state.get("config", {})
            paths = state.get("paths", {})
            stages = dict(state.get("stages", {}))

            essence = run_essence_gate(stage_id, state, paths, config)

            if essence.blocked:
                return Command(
                    update={
                        "status": "blocked",
                        "blocking_condition": f"Essence Lens 4 tension in {stage_id}: {essence.tension}",
                        "stages": stages,
                        "essence_tension": essence.tension,
                    },
                    goto="__end__",
                )

            if essence.waiting_for_input:
                essence_state = build_essence_state(stage_id, essence, state, config)
                return Command(
                    update={
                        "status": "waiting_for_input",
                        "blocking_condition": "essence_clarification_needed",
                        "stages": stages,
                        "essence": essence_state,
                        "essence_clarifying_questions": essence.clarifying_questions,
                    },
                    goto="__end__",
                )

            if essence.updated_state and essence.updated_state.get("stages"):
                state["stages"] = essence.updated_state["stages"]

            return fn(state)

        return wrapper

    return decorator


# ── Core gate ──────────────────────────────────────────────────────────
def run_essence_gate(
    stage_id: str,
    state: dict[str, Any],
    paths: dict[str, Any],
    config: dict[str, Any],
) -> EssenceResult:
    """Run the Four Lenses essence validation before stage execution.

    Policy flow (deterministic):
      1. Lens 4 conflicts → BLOCKED (terminal)
      2. Significant findings (severity >= threshold) → CLARIFICATION_REQUIRED
      3. Adjustments available, severity < threshold → AUTO_ADJUST (retry)
      4. Auto-adjust exhausted → CLARIFICATION_REQUIRED
      5. Clean → PASS
      6. Fallback → AUTO_ADJUST (retry)

    The LLM detects findings. The policy engine decides.
    """
    essence_config = config.get("essence", {})
    if not essence_config.get("enabled", True):
        return EssenceResult(passed=True, decision=EssenceDecision.PASS)

    stages = dict(state.get("stages", {}))
    stage_state = stages.get(stage_id, {})
    if stage_state.get("essence_checked", False):
        return EssenceResult(passed=True, decision=EssenceDecision.PASS)

    skill_name = essence_config.get("skill", "essence")
    skill_root = paths.get("framework_skill_root", "")
    skill_content = load_skill(skill_root, skill_name)
    if not skill_content:
        logger.warning(
            "Essence skill '%s' not found, skipping gate for %s",
            skill_name,
            stage_id,
        )
        return EssenceResult(passed=True, decision=EssenceDecision.PASS)

    # Policy parameters
    threshold = essence_config.get("clarification_threshold", "medium")
    auto_adjust_max = essence_config.get("auto_adjust_max", 3)
    max_retries = config.get("max_essence_retries_per_stage", 5)
    max_clarification_attempts = essence_config.get("max_clarification_attempts", 3)

    # Operational state — clarification attempts are scoped per stage.
    # If the blocked_stage changed, reset the counter for the new stage.
    essence_state = state.get("essence", {})
    blocked_stage = essence_state.get("blocked_stage", "")
    if blocked_stage != stage_id:
        # New stage — reset clarification counter so each stage gets its own budget
        clarification_attempts = 0
        auto_adjust_attempts = 0
    else:
        clarification_attempts = essence_state.get("clarification_attempts", 0)
        auto_adjust_attempts = essence_state.get("auto_adjust_attempts", 0)

    # Check clarification attempt limit (per-stage)
    if clarification_attempts >= max_clarification_attempts:
        logger.warning(
            "Essence gate for %s: clarification attempts (%d) exceeded max (%d). BLOCKED.",
            stage_id,
            clarification_attempts,
            max_clarification_attempts,
        )
        return EssenceResult(
            blocked=True,
            decision=EssenceDecision.BLOCKED,
            tension=f"Clarification exhausted after {clarification_attempts} attempts",
        )

    stage_inputs = _gather_essence_inputs(stage_id, state, paths)

    prompt = _build_essence_prompt(skill_content, stage_id, stage_inputs, state, config)

    model = create_model_from_config(config, "essence")
    tools = get_essence_tools(paths)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 15)

    for attempt in range(max_retries):
        agent_result: AgentResult = run_agent(
            model=model,
            tools=tools,
            prompt=prompt,
            stage_id=f"essence:{stage_id}",
            output_schema=EssenceOutput,
            max_iterations=max_agent_iterations,
            config=config,
        )

        if agent_result.error:
            logger.warning(
                "Essence gate agent error for %s: %s",
                stage_id,
                agent_result.error,
            )
            return EssenceResult(passed=True, decision=EssenceDecision.PASS)

        result = agent_result.data

        # Debug: log LLM output for essence gate diagnosis
        logger.info(
            "Essence gate for %s: LLM returned clean=%s, lens1=%d, lens2=%d, lens3=%d, lens4=%d, adjustments=%d, questions=%d, summary=%s",
            stage_id,
            result.get("clean", False),
            len(result.get("lens_1_subjective_terms", [])),
            len(result.get("lens_2_hidden_assumptions", [])),
            len(result.get("lens_3_literal_traps", [])),
            len(result.get("lens_4_conflicts", [])),
            len(result.get("adjustments", [])),
            len(result.get("clarifying_questions", [])),
            result.get("summary", "")[:200],
        )
        for finding in result.get("lens_1_subjective_terms", []):
            d = finding.model_dump() if hasattr(finding, "model_dump") else finding
            logger.info("  Lens 1: term=%s severity=%s", d.get("term", ""), d.get("severity", ""))
        for finding in result.get("lens_2_hidden_assumptions", []):
            d = finding.model_dump() if hasattr(finding, "model_dump") else finding
            logger.info("  Lens 2: assumption=%s severity=%s", d.get("assumption", "")[:80], d.get("severity", ""))
        for finding in result.get("lens_3_literal_traps", []):
            d = finding.model_dump() if hasattr(finding, "model_dump") else finding
            logger.info("  Lens 3: phrasing=%s severity=%s", d.get("phrasing", ""), d.get("severity", ""))

        # ── Policy evaluation (deterministic) ──────────────────────
        lens_4 = result.get("lens_4_conflicts", [])
        is_clean = result.get("clean", False)
        adjustments = result.get("adjustments", [])
        clarifying_questions = result.get("clarifying_questions", [])

        # Collect all findings for severity evaluation
        all_findings = []
        for item in result.get("lens_1_subjective_terms", []):
            if isinstance(item, dict):
                all_findings.append(item)
            else:
                all_findings.append(item.model_dump())
        for item in result.get("lens_2_hidden_assumptions", []):
            if isinstance(item, dict):
                all_findings.append(item)
            else:
                all_findings.append(item.model_dump())
        for item in result.get("lens_3_literal_traps", []):
            if isinstance(item, dict):
                all_findings.append(item)
            else:
                all_findings.append(item.model_dump())

        # 1. Lens 4 → check if auto-adjustable (scope/complexity mismatch)
        if lens_4:
            tensions = []
            for conflict in lens_4:
                if isinstance(conflict, dict):
                    tensions.append(conflict.get("tension", str(conflict)))
                else:
                    tensions.append(str(conflict))
            tension_str = "; ".join(tensions)

            # Auto-adjust: if tension is about scope/complexity mismatch,
            # try to bump complexity up instead of blocking
            auto_adjusted = _try_auto_adjust_complexity(tensions, stage_id, state, config)
            if auto_adjusted:
                logger.info(
                    "Essence gate for %s: auto-adjusted complexity from '%s' to '%s'",
                    stage_id,
                    auto_adjusted["old_complexity"],
                    auto_adjusted["new_complexity"],
                )
                # Record successful auto-adjust for future learning
                get_tension_memory().record(
                    tension_str,
                    "auto_adjust",
                    complexity_before=auto_adjusted["old_complexity"],
                    complexity_after=auto_adjusted["new_complexity"],
                    stage_id=stage_id,
                    work_type=state.get("work_type", ""),
                )
                # Re-run essence check with updated complexity context
                continue

            # Learning-based resolution: check tension memory for past outcomes
            memory_resolution = get_tension_memory().get_resolution(tension_str)
            if memory_resolution == "auto_adjust":
                logger.info(
                    "Essence gate for %s: tension memory suggests auto_adjust (learned resolution)",
                    stage_id,
                )
                # Force complexity bump based on learned pattern
                forced_adjust = _try_auto_adjust_complexity_force(tensions, stage_id, state, config)
                if forced_adjust:
                    get_tension_memory().record(
                        tension_str,
                        "auto_adjust",
                        complexity_before=forced_adjust["old_complexity"],
                        complexity_after=forced_adjust["new_complexity"],
                        stage_id=stage_id,
                        work_type=state.get("work_type", ""),
                    )
                    continue

            # Not auto-adjustable — ask user for scope clarification.
            # Only block terminally if clarification attempts are exhausted.
            if clarification_attempts >= max_clarification_attempts:
                logger.warning(
                    "Essence gate for %s: Lens 4 scope tension, clarification exhausted (%d attempts). BLOCKED.",
                    stage_id,
                    clarification_attempts,
                )
                get_tension_memory().record(
                    tension_str,
                    "blocked",
                    complexity_before=state.get("complexity", ""),
                    stage_id=stage_id,
                    work_type=state.get("work_type", ""),
                )

                capture_decision = essence_config.get("capture_decisions", True)
                context_file = essence_config.get("context_file", "context.md")

                if capture_decision and context_file:
                    _capture_lens4_decision(stage_id, tensions, state, paths, context_file)

                return EssenceResult(
                    blocked=True,
                    decision=EssenceDecision.BLOCKED,
                    tension=tension_str,
                    updated_state={
                        "stages": stages,
                        "essence_blocked_stage": stage_id,
                        "essence_tension": tension_str,
                    },
                )

            # Generate scope-clarification questions from Lens 4 tensions
            scope_questions = _build_scope_clarification_questions(tensions, stage_id, all_findings)
            return EssenceResult(
                waiting_for_input=True,
                decision=EssenceDecision.CLARIFICATION_REQUIRED,
                clarifying_questions=scope_questions,
                updated_state={"stages": _mark_essence_checked_stages(stage_id, stages)},
                adjustments=[],
            )

        # 2. Significant findings (severity >= threshold) → CLARIFICATION
        significant_findings = [f for f in all_findings if should_clarify(_get_severity(f), threshold)]
        logger.info(
            "Essence gate for %s: total_findings=%d, significant(>=%s)=%d",
            stage_id,
            len(all_findings),
            threshold,
            len(significant_findings),
        )

        if significant_findings:
            # Build questions from significant findings (with deduplication)
            questions = _build_clarification_questions(
                significant_findings,
                clarifying_questions,
                resolved_findings=essence_state.get("resolved_findings", []),
                resolved_answers=(
                    state.get("work_item", {}).get("clarifications", {}).get("answers", {})
                    if isinstance(state.get("work_item"), dict)
                    else {}
                ),
            )

            # Mark stage as essence-checked so the gate doesn't re-run after
            # the user answers clarification. Re-running would generate the
            # same findings and create an infinite clarification loop.
            finding_ids = [f.get("finding_id", "") for f in significant_findings if f.get("finding_id")]

            if questions:
                return EssenceResult(
                    waiting_for_input=True,
                    decision=EssenceDecision.CLARIFICATION_REQUIRED,
                    clarifying_questions=questions,
                    updated_state={"stages": _mark_essence_checked_stages(stage_id, stages)},
                    adjustments=finding_ids,
                )
            # Significant findings but no questions — still block
            return EssenceResult(
                waiting_for_input=True,
                decision=EssenceDecision.CLARIFICATION_REQUIRED,
                clarifying_questions=[
                    {
                        "id": f"essence_q_{len(all_findings)}",
                        "finding_id": f.get("finding_id", ""),
                        "lens": f.get("lens", "lens_1"),
                        "finding_summary": _finding_summary(f),
                        "question": f"Please clarify: {_finding_summary(f)}",
                        "options": [],
                        "severity": _get_severity(f),
                    }
                    for f in significant_findings[:5]
                ],
                updated_state={"stages": _mark_essence_checked_stages(stage_id, stages)},
                adjustments=finding_ids,
            )

        # 3. Clean → PASS
        if is_clean and not adjustments:
            return _mark_essence_checked(stage_id, stages, state)

        # 4. Adjustments with severity < threshold → AUTO_ADJUST
        if adjustments:
            if auto_adjust_attempts < auto_adjust_max:
                stage_inputs = _apply_adjustments(stage_inputs, adjustments)
                prompt = _build_essence_prompt(
                    skill_content,
                    stage_id,
                    stage_inputs,
                    state,
                    config,
                )
                auto_adjust_attempts += 1
                logger.info(
                    "Essence gate for %s: applied %d adjustments, re-running (auto-adjust %d/%d)",
                    stage_id,
                    len(adjustments),
                    auto_adjust_attempts,
                    auto_adjust_max,
                )
                continue

            # Auto-adjust exhausted → CLARIFICATION
            logger.warning(
                "Essence gate for %s: auto-adjust exhausted (%d), escalating to clarification",
                stage_id,
                auto_adjust_max,
            )
            return EssenceResult(
                waiting_for_input=True,
                decision=EssenceDecision.CLARIFICATION_REQUIRED,
                clarifying_questions=[
                    {
                        "id": "essence_q_exhausted",
                        "finding_id": "",
                        "lens": "lens_1",
                        "finding_summary": ("Auto-adjust exhausted. Please clarify ambiguities."),
                        "question": (
                            "The system could not auto-resolve ambiguities. Please clarify any remaining uncertainties."
                        ),
                        "options": [],
                        "severity": "medium",
                    }
                ],
                updated_state={"stages": _mark_essence_checked_stages(stage_id, stages)},
            )

        # 5. Fallback — not clean, no adjustments, no significant findings
        #    → retry once
        logger.info(
            "Essence gate for %s: no clean result, re-running (attempt %d/%d)",
            stage_id,
            attempt + 1,
            max_retries,
        )

    # Max retries exhausted — proceed with warning
    logger.warning(
        "Essence gate for %s: exhausted %d retries, proceeding anyway",
        stage_id,
        max_retries,
    )
    return _mark_essence_checked(stage_id, stages, state, retries_exceeded=True)


# ── Policy helpers ─────────────────────────────────────────────────────
def _get_severity(finding: dict) -> str:
    """Extract severity from a finding dict, defaulting to 'low'."""
    sev = finding.get("severity", "low")
    if isinstance(sev, Severity):
        return sev.value
    return str(sev).lower()


def _finding_summary(finding: dict) -> str:
    """Generate a brief summary of a finding for user display."""
    if "term" in finding:
        return f"Subjective term '{finding['term']}' in context: {finding.get('context', '')}"
    if "assumption" in finding:
        return f"Hidden assumption: {finding['assumption']}"
    if "phrasing" in finding:
        return f"Literal trap: '{finding['phrasing']}' — {finding.get('ambiguity', '')}"
    return str(finding)[:200]


def _build_clarification_questions(
    significant_findings: list[dict],
    llm_questions: list,
    resolved_findings: list[str] | None = None,
    resolved_answers: dict[str, str] | None = None,
) -> list[dict]:
    """Build clarification questions from significant findings.

    Prefers LLM-generated questions that reference valid finding_ids.
    Falls back to auto-generated questions for uncovered findings.

    Deduplicates: if a finding_id is already resolved, or if the question
    is semantically equivalent to a previously answered question, it is
    eliminated before presentation (PRD §14).
    """
    if not significant_findings:
        return []

    resolved = set(resolved_findings or [])
    answers = resolved_answers or {}

    # Index LLM questions by finding_id
    llm_by_finding = {}
    for q in llm_questions:
        if isinstance(q, dict):
            fid = q.get("finding_id", "")
            if fid:
                llm_by_finding[fid] = q
        elif hasattr(q, "model_dump"):
            d = q.model_dump()
            fid = d.get("finding_id", "")
            if fid:
                llm_by_finding[fid] = d

    questions = []
    covered_findings = set()

    for finding in significant_findings:
        fid = finding.get("finding_id", "")

        # Dedup: skip if finding_id already resolved
        if fid and fid in resolved:
            covered_findings.add(fid)
            continue

        # Dedup: skip if finding is semantically covered by a resolved answer
        if _is_semantically_resolved(finding, answers):
            covered_findings.add(fid)
            continue

        # Use LLM question if available
        if fid and fid in llm_by_finding:
            q = llm_by_finding[fid]
            q_copy = dict(q)
            q_copy["severity"] = finding.get("severity", "low")
            questions.append(q_copy)
            covered_findings.add(fid)
            continue

        # Auto-generate for uncovered findings
        if fid:
            questions.append(
                {
                    "id": f"essence_q_auto_{len(questions)}",
                    "finding_id": fid,
                    "lens": finding.get("lens", "lens_1"),
                    "finding_summary": _finding_summary(finding),
                    "question": f"Please clarify: {_finding_summary(finding)}",
                    "options": finding.get("interpretations", []),
                    "severity": _get_severity(finding),
                }
            )
            covered_findings.add(fid)

    return questions[:5]  # max_questions_per_request


def _is_semantically_resolved(
    finding: dict,
    resolved_answers: dict[str, str],
) -> bool:
    """Check if a finding is semantically covered by a resolved answer.

    Uses simple string containment to detect semantic equivalence.
    Example: if Q1 asked 'recipe or receipt?' and answer was 'recipe',
    a subsequent finding 'hidden assumption: user wants cooking recipe'
    is resolved.
    """
    if not resolved_answers:
        return False

    # Extract key terms from the finding
    finding_text = ""
    if "term" in finding:
        finding_text = finding["term"].lower()
    elif "assumption" in finding:
        finding_text = finding["assumption"].lower()
    elif "phrasing" in finding:
        finding_text = finding["phrasing"].lower()
    elif "finding_summary" in finding:
        finding_text = finding["finding_summary"].lower()

    if not finding_text:
        return False

    # Check if any resolved answer's value matches or contains key terms
    for answer_value in resolved_answers.values():
        answer_lower = str(answer_value).lower()
        if not answer_lower:
            continue

        # Direct containment check
        if answer_lower in finding_text or finding_text in answer_lower:
            return True

        # Token overlap check (for multi-word matches)
        finding_words = set(finding_text.split())
        answer_words = set(answer_lower.split())
        if finding_words and answer_words:
            overlap = finding_words & answer_words
            # If 50%+ of significant words (>2 chars) overlap, consider resolved
            significant_finding = {w for w in finding_words if len(w) > 2}
            significant_answer = {w for w in answer_words if len(w) > 2}
            if significant_finding and significant_answer:
                common = significant_finding & significant_answer
                if len(common) / max(len(significant_finding), 1) >= 0.5:
                    return True

    return False


def build_essence_state(
    stage_id: str,
    essence: EssenceResult,
    state: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Build the essence operational state for persistence.

    Clarification attempts are scoped per stage — if the blocked stage
    changed, the counter resets so each stage gets its own budget.
    """
    old_essence = state.get("essence", {})
    blocked_stage = old_essence.get("blocked_stage", "")

    if blocked_stage != stage_id:
        # New stage — reset counters
        current_attempts = 0
        current_auto_adjust = 0
    else:
        current_attempts = old_essence.get("clarification_attempts", 0)
        current_auto_adjust = old_essence.get("auto_adjust_attempts", 0)

    return {
        "checked": False,
        "blocked_stage": stage_id,
        "decision": essence.decision.value,
        "clarification_attempts": current_attempts + 1,
        "auto_adjust_attempts": current_auto_adjust,
        "pending_questions": essence.clarifying_questions,
        "resolved_findings": old_essence.get("resolved_findings", []),
    }


# ── Existing helpers (preserved) ───────────────────────────────────────
def _gather_essence_inputs(
    stage_id: str,
    state: dict[str, Any],
    paths: dict[str, Any],
) -> str:
    """Gather stage-specific inputs for essence validation."""
    parts = []
    work_item_text = get_work_item_text(state)
    if work_item_text:
        parts.append(f"Work Item: {work_item_text}")

    # Include existing clarifications as context
    raw_work_item = state.get("work_item", {})
    if isinstance(raw_work_item, dict):
        clarifications = raw_work_item.get("clarifications", {})
        if clarifications and clarifications.get("answers"):
            answers = clarifications.get("answers", {})
            if answers:
                parts.append(
                    "Previous Clarifications (already resolved):\n"
                    + "\n".join(f"  - {k}: {v}" for k, v in answers.items())
                )

    # Include resolved findings as context
    essence_state = state.get("essence", {})
    resolved = essence_state.get("resolved_findings", [])
    if resolved:
        parts.append("Resolved Findings (do not re-ask):\n" + "\n".join(f"  - {f}" for f in resolved))

    stage_artifacts = state.get("stage_artifacts", {})
    if stage_artifacts:
        parts.append("Stage Artifacts:")
        for key, value in stage_artifacts.items():
            if value and isinstance(value, str) and len(value) > 1000:
                parts.append(f"  {key}: (exists, {len(value)} chars)")
            elif value:
                parts.append(f"  {key}: {value[:500]}")

    decisions = state.get("decisions", [])
    if decisions:
        parts.append(f"Decisions ({len(decisions)}):")
        for d in decisions[-10:]:
            parts.append(f"  - {d[:200]}")

    complexity = state.get("complexity", "unset")
    parts.append(f"Complexity: {complexity}")

    ui_project = state.get("ui_project", False)
    parts.append(f"UI Project: {ui_project}")

    return "\n\n".join(parts) if parts else "No inputs available."


def _build_essence_prompt(
    skill_content: str,
    stage_id: str,
    stage_inputs: str,
    state: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> str:
    """Build the essence validation prompt."""
    config = config or {}
    essence_config = config.get("essence", {})
    threshold = essence_config.get("clarification_threshold", "medium")
    max_questions = essence_config.get("max_questions_per_request", 5)

    return (
        f"{skill_content}\n\n"
        f"## STAGE TO VALIDATE\n"
        f"Stage ID: {stage_id}\n\n"
        f"## STAGE INPUTS\n"
        f"{stage_inputs}\n\n"
        f"## POLICY\n"
        f"Clarification threshold: {threshold} (findings at this severity or above require user clarification)\n"
        f"Max questions per request: {max_questions}\n\n"
        f"## INSTRUCTIONS\n"
        f"Apply the Four Lenses to these stage inputs for stage '{stage_id}'.\n"
        f"Are the inputs sufficient and unambiguous for the upcoming stage?\n\n"
        f"Severity classification (based on IMPACT of ambiguity on the solution, NOT finding type):\n"
        f"  HIGH   — Interpretation fundamentally changes the solution or architecture.\n"
        f"           Examples: 'login' = OAuth vs session vs SSO; 'database' = SQL vs NoSQL.\n"
        f"  MEDIUM — Meaningful decision exists, but a reasonable default is available.\n"
        f"           Examples: 'cache' = in-memory vs distributed; 'logging' level/format.\n"
        f"  LOW    — Decision doesn't significantly change the outcome.\n"
        f"           Examples: 'nice UI' aesthetic preference; 'clean code' stylistic.\n\n"
        f"For each finding, assign a finding_id like 'lens1_subject_cake', 'lens2_assump_no_allergies'.\n"
        f"For significant findings (severity >= {threshold}), generate clarifying_questions with:\n"
        f"  - id: 'essence_q_NNN'\n"
        f"  - finding_id: references the finding\n"
        f"  - lens: 'lens_1', 'lens_2', or 'lens_3'\n"
        f"  - question: what to ask the user\n"
        f"  - options: suggested answers if applicable\n"
        f"  - severity: mirrors the finding's severity\n\n"
        f"INVARIENTS:\n"
        f"  - Every clarifying question MUST reference an existing finding_id.\n"
        f"  - Every significant finding MUST have a corresponding question.\n\n"
        f"Return a JSON object with fields:\n"
        f"lens_1_subjective_terms, lens_2_hidden_assumptions, lens_3_literal_traps,\n"
        f"lens_4_conflicts, clean, adjustments, clarifying_questions, summary."
    )


def _try_auto_adjust_complexity(
    tensions: list[str],
    stage_id: str,
    state: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    """Detect scope/complexity mismatch in Lens 4 tensions and auto-adjust.

    If the tension indicates that the current complexity classification is too
    low for the scope of work (e.g., 'NOT a small task', 'scope is medium-to-large'),
    bumps the complexity up and re-activates the corresponding stages.

    Returns a dict with old/new complexity on success, None if not applicable.
    """
    from eng_loop.state import COMPLEXITY_ORDER
    from eng_loop.tools.autosizing import deactivate_inactive_stages

    current_complexity = state.get("complexity", "small")
    complexity_order = COMPLEXITY_ORDER.get(current_complexity, 0)

    # Check if we've already auto-adjusted (prevent infinite loop)
    auto_adjust_count = state.get("_complexity_auto_adjust_count", 0)
    if auto_adjust_count >= 2:
        logger.warning("Auto-adjust complexity already attempted %d times, stopping", auto_adjust_count)
        return None

    # Detect scope/complexity mismatch patterns
    scope_mismatch_keywords = [
        "not a small task",
        "not a medium task",
        "scope is medium",
        "scope is large",
        "scope is medium-to-large",
        "complexity conflicts",
        "classification conflicts",
        "is NOT a small",
        "is NOT a medium",
        "requires more stages",
        "broad validation",
        "all flows",
        "all user flows",
        "production readiness",
        # Learning-augmented patterns
        "unbounded",
        "significant time",
        "phased approach",
        "conflicts with",
        "comprehensive validation",
        "requires prioritization",
        "large-scope",
        "large scope",
        "multiple feature",
        "cross-cutting",
    ]

    tension_combined = " ".join(tensions).lower()
    is_scope_mismatch = any(kw in tension_combined for kw in scope_mismatch_keywords)

    if not is_scope_mismatch:
        return None

    # Determine new complexity level
    complexity_ladder = ["small", "medium", "large", "complex"]
    current_idx = complexity_ladder.index(current_complexity) if current_complexity in complexity_ladder else 0
    if current_idx >= len(complexity_ladder) - 1:
        return None  # Already at maximum

    new_complexity = complexity_ladder[current_idx + 1]
    logger.info(
        "Essence gate detected scope mismatch at stage %s: '%s' → '%s'",
        stage_id,
        current_complexity,
        new_complexity,
    )

    # Update state
    state["complexity"] = new_complexity
    state["_complexity_auto_adjust_count"] = auto_adjust_count + 1

    # Re-activate stages for new complexity
    stages = dict(state.get("stages", {}))
    stages = deactivate_inactive_stages(stages, new_complexity, state.get("ui_project", False))
    state["stages"] = stages

    return {
        "old_complexity": current_complexity,
        "new_complexity": new_complexity,
    }


def _try_auto_adjust_complexity_force(
    tensions: list[str],
    stage_id: str,
    state: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    """Force complexity bump based on learned tension memory resolution.

    Unlike _try_auto_adjust_complexity, this bypasses keyword matching and
    trusts the empirical evidence from past resolutions. Used only when
    tension memory returns a high-confidence 'auto_adjust' resolution.
    """
    from eng_loop.state import COMPLEXITY_ORDER
    from eng_loop.tools.autosizing import deactivate_inactive_stages

    current_complexity = state.get("complexity", "small")
    complexity_order = COMPLEXITY_ORDER.get(current_complexity, 0)

    # Prevent infinite loop
    auto_adjust_count = state.get("_complexity_auto_adjust_count", 0)
    if auto_adjust_count >= 2:
        logger.warning("Auto-adjust complexity already attempted %d times, stopping", auto_adjust_count)
        return None

    complexity_ladder = ["small", "medium", "large", "complex"]
    current_idx = complexity_ladder.index(current_complexity) if current_complexity in complexity_ladder else 0
    if current_idx >= len(complexity_ladder) - 1:
        return None  # Already at maximum

    new_complexity = complexity_ladder[current_idx + 1]
    logger.info(
        "Essence gate (learned) at stage %s: '%s' → '%s'",
        stage_id,
        current_complexity,
        new_complexity,
    )

    state["complexity"] = new_complexity
    state["_complexity_auto_adjust_count"] = auto_adjust_count + 1

    stages = dict(state.get("stages", {}))
    stages = deactivate_inactive_stages(stages, new_complexity, state.get("ui_project", False))
    state["stages"] = stages

    return {
        "old_complexity": current_complexity,
        "new_complexity": new_complexity,
    }


def _build_scope_clarification_questions(
    tensions: list[str],
    stage_id: str,
    all_findings: list[dict],
) -> list[dict]:
    """Build clarification questions from Lens 4 scope/complexity tensions.

    Instead of blocking, asks the user to narrow scope or confirm priorities.
    """
    questions = []

    tension_summary = "; ".join(tensions[:3])
    questions.append(
        {
            "id": "essence_q_lens4_scope",
            "finding_id": "lens4_scope_mismatch",
            "lens": "lens_4",
            "finding_summary": f"Scope-complexity tension: {tension_summary}",
            "question": (
                "The work item scope exceeds the current complexity classification. "
                "How would you like to proceed?\n"
                "  (a) Narrow scope: Focus on the most critical flows first\n"
                "  (b) Accept full scope: Proceed with all stages (will take longer)\n"
                "  (c) Redefine: Provide a more specific work item"
            ),
            "options": ["Narrow scope", "Accept full scope", "Redefine work item"],
            "severity": "high",
        }
    )

    tension_lower = " ".join(tensions).lower()
    if any(
        kw in tension_lower
        for kw in [
            "all flows",
            "all modules",
            "complete",
            "comprehensive",
            "all functionality",
            "broad validation",
            "all user flows",
            "unbounded",
            "phased approach",
            "cross-cutting",
        ]
    ):
        questions.append(
            {
                "id": "essence_q_lens4_priority",
                "finding_id": "lens4_priority",
                "lens": "lens_4",
                "finding_summary": "Work item references comprehensive coverage",
                "question": (
                    "Which areas should be prioritized if the full scope cannot be "
                    "completed in a single pass? List the top 2-3 critical flows."
                ),
                "options": [],
                "severity": "medium",
            }
        )

    return questions[:3]


def _apply_adjustments(stage_inputs: str, adjustments: list[str]) -> str:
    """Apply inline adjustments from Lens 1-3 findings."""
    adjusted = stage_inputs
    for adj in adjustments:
        adjusted += f"\n\n[Adjusted: {adj}]"
    return adjusted


def _mark_essence_checked_stages(
    stage_id: str,
    stages: dict[str, Any],
) -> dict[str, Any]:
    """Mark a stage as essence-checked. Returns updated stages dict."""
    if stage_id not in stages:
        stages[stage_id] = {}
    stages[stage_id]["essence_checked"] = True
    return stages


def _mark_essence_checked(
    stage_id: str,
    stages: dict[str, Any],
    state: dict[str, Any],
    retries_exceeded: bool = False,
) -> EssenceResult:
    """Mark a stage as essence-checked and return the result."""
    updated = _mark_essence_checked_stages(stage_id, stages)
    if retries_exceeded:
        updated[stage_id]["essence_retries_exceeded"] = True

    return EssenceResult(
        passed=True,
        decision=EssenceDecision.PASS,
        updated_state={"stages": updated},
    )


def _capture_lens4_decision(
    stage_id: str,
    tensions: list[str],
    state: dict[str, Any],
    paths: dict[str, Any],
    context_file: str,
) -> None:
    """Capture Lens 4 tension decisions in context.md."""
    from pathlib import Path

    loop_root = paths.get("loop_root", ".")
    context_path = Path(loop_root) / context_file

    existing = ""
    if context_path.exists():
        existing = context_path.read_text(encoding="utf-8")

    decision_entries = []
    for tension in tensions:
        entry = (
            f"### Lens 4 Tension — {stage_id}\n"
            f"- **Tension**: {tension}\n"
            f"- **Date**: {__import__('datetime').date.today().isoformat()}\n"
            f"- **Stage**: {stage_id}\n"
            f"- **Resolution**: _awaiting user resolution_"
        )
        decision_entries.append(entry)

    if existing:
        content = existing.rstrip() + "\n\n" + "## Decisions\n\n" + "\n\n".join(decision_entries)
    else:
        slug = get_work_item_text(state, "feature")[:40].replace(" ", "-").lower()
        content = f"# Context — {slug}\n\n" + "## Decisions\n\n" + "\n\n".join(decision_entries)

    context_path.write_text(content, encoding="utf-8")
    logger.info("Captured Lens 4 decision in %s for stage %s", context_path, stage_id)
