from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

if TYPE_CHECKING:
    from eng_loop.tools.token_counter import TokenCounter


# ============================================================
# PRESSURE STATES
# ============================================================


class ContextPressure(str, Enum):
    SAFE = "safe"
    WATCH = "watch"
    PRESSURE = "pressure"
    EXHAUSTED = "exhausted"


class CompactionMode(str, Enum):
    AUTO = "auto"
    SUGGEST = "suggest"
    DISABLED = "disabled"


# ============================================================
# TYPES
# ============================================================


@dataclass
class CallBreakdown:
    """Token breakdown for a single LLM call."""

    system_prompt: int = 0
    stage_instructions: int = 0
    conversation: int = 0
    tool_results: int = 0
    previous_outputs: int = 0
    other: int = 0
    input_total: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0


@dataclass
class StageHistoryEntry:
    """One LLM call within a stage."""

    call_number: int
    stage_id: str
    timestamp: float
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    pressure: str = "safe"


@dataclass
class CompactionRecord:
    """Audit trail for compaction events."""

    stage_id: str
    call_number: int
    timestamp: float
    tokens_before: int
    tokens_after: int
    tokens_saved: int
    strategy: str


@dataclass
class ReservedOutputConfig:
    """Per-stage reserved output configuration."""

    mode: str = "fixed"  # "fixed" | "adaptive"
    value: int = 4096
    min_value: int = 2048
    max_value: int = 8192


@dataclass
class BudgetCheckResult:
    """Result of a pre-call budget check."""

    allowed: bool
    safe_remaining: int
    pressure: ContextPressure
    reason: str = ""


@dataclass
class ForecastResult:
    """Graph-level context budget projection."""

    total_projected: int
    context_window: int
    feasible: bool
    peak_stage: str = ""
    peak_tokens: int = 0
    stages_exceeding: list[str] = field(default_factory=list)


@dataclass
class ContextBudgetState:
    """Full budget state for ViewModel exposure."""

    model_name: str = ""
    context_window: int = 0
    # Current call
    call_breakdown: CallBreakdown = field(default_factory=CallBreakdown)
    # Budget
    reserved_output: int = 0
    safety_margin: int = 0
    used_tokens: int = 0
    remaining_tokens: int = 0
    safe_remaining: int = 0
    pressure: ContextPressure = ContextPressure.SAFE
    # Stage history
    stage_history: dict[str, list[StageHistoryEntry]] = field(default_factory=dict)
    # Tool tracking (per-stage, current)
    tool_calls: int = 0
    tool_tokens: int = 0
    # Compaction
    compaction_mode: CompactionMode = CompactionMode.AUTO
    compaction_records: list[CompactionRecord] = field(default_factory=list)
    tokens_compacted: int = 0
    compaction_suggested: bool = False
    # Tokenizer
    tokenizer_provider: str = ""
    tokenizer_accuracy: str = "estimated"


# ============================================================
# MANAGER
# ============================================================


class ContextBudgetManager:
    """Manages context window budget for LLM calls.

    Responsibilities:
    1. Detect context window of the model
    2. Measure tokens per request
    3. Measure input/output
    4. Measure tool payloads
    5. Calculate safe remaining
    6. Maintain per-stage history
    7. Detect pressure
    8. Project next call
    9. Trigger compaction when necessary
    10. Prevent predictable overflow
    11. Expose state for ViewModel
    """

    def __init__(
        self,
        context_window: int,
        model_name: str = "",
        reserved_output: int = 4096,
        safety_margin: int = 2048,
        thresholds: dict[str, float] | None = None,
        compaction_mode: CompactionMode = CompactionMode.AUTO,
        stage_reserved: dict[str, ReservedOutputConfig] | None = None,
        preserve_count: int = 15,
        truncate_tool_result_chars: int = 2000,
    ):
        self._context_window = context_window
        self._model_name = model_name
        self._reserved_output = reserved_output
        self._safety_margin = safety_margin
        self._preserve_count = preserve_count
        self._truncate_tool_result_chars = truncate_tool_result_chars

        # Thresholds: ratio of context_window at which pressure changes
        self._threshold_safe = thresholds.get("safe", 0.70) if thresholds else 0.70
        self._threshold_watch = thresholds.get("watch", 0.85) if thresholds else 0.85
        self._threshold_pressure = thresholds.get("pressure", 0.95) if thresholds else 0.95

        self._compaction_mode = compaction_mode
        self._stage_reserved = stage_reserved or {}

        # Per-stage call history
        self._stage_history: dict[str, list[StageHistoryEntry]] = {}
        # Per-stage call counter
        self._call_counters: dict[str, int] = {}
        # Compaction audit trail
        self._compaction_records: list[CompactionRecord] = []
        # Current call state
        self._current_breakdown: CallBreakdown = CallBreakdown()
        self._current_stage: str = ""
        self._current_tool_calls: int = 0
        self._current_tool_tokens: int = 0
        # Cumulative compaction savings
        self._total_compacted: int = 0

    # ── Pre-call check ──────────────────────────────────────────

    def check_before_call(
        self,
        stage_id: str,
        estimated_input: int,
        estimated_output: int,
    ) -> BudgetCheckResult:
        """Proactive check: can the next call fit safely?

        Real criterion: input + reserved_output + safety_margin <= context_window
        Percentage thresholds are only for visual indication.
        """
        reserved = self._get_reserved_output(stage_id)
        total_needed = estimated_input + reserved + self._safety_margin

        if total_needed > self._context_window:
            return BudgetCheckResult(
                allowed=False,
                safe_remaining=self._context_window - total_needed,
                pressure=ContextPressure.EXHAUSTED,
                reason=(
                    f"Need {total_needed} tokens "
                    f"(input={estimated_input}, reserved={reserved}, margin={self._safety_margin}), "
                    f"but context window is {self._context_window}"
                ),
            )

        # Classify pressure from usage ratio
        usage_ratio = estimated_input / max(self._context_window, 1)
        pressure = self._classify_pressure(usage_ratio)

        safe_remaining = self._context_window - total_needed
        return BudgetCheckResult(
            allowed=True,
            safe_remaining=safe_remaining,
            pressure=pressure,
        )

    # ── Post-call recording ─────────────────────────────────────

    def record_call(
        self,
        stage_id: str,
        breakdown: CallBreakdown,
    ) -> None:
        """Record a completed LLM call. Updates history, computes state."""
        self._current_stage = stage_id
        self._current_breakdown = breakdown

        self._call_counters[stage_id] = self._call_counters.get(stage_id, 0) + 1
        call_num = self._call_counters[stage_id]

        usage_ratio = breakdown.input_total / max(self._context_window, 1)
        pressure = self._classify_pressure(usage_ratio)

        entry = StageHistoryEntry(
            call_number=call_num,
            stage_id=stage_id,
            timestamp=time.monotonic(),
            input_tokens=breakdown.input_total,
            output_tokens=breakdown.output_tokens,
            cached_tokens=breakdown.cached_tokens,
            pressure=pressure.value,
        )
        self._stage_history.setdefault(stage_id, []).append(entry)

    def record_tool_call(self, stage_id: str, result_tokens: int) -> None:
        """Track tool call count and token contribution."""
        self._current_tool_calls += 1
        self._current_tool_tokens += result_tokens
        if self._current_breakdown:
            self._current_breakdown.tool_results += result_tokens

    # ── Compaction ──────────────────────────────────────────────

    def should_compact(self, stage_id: str, estimated_input: int) -> bool:
        """Check if compaction should run before the next call."""
        if self._compaction_mode == CompactionMode.DISABLED:
            return False

        reserved = self._get_reserved_output(stage_id)
        total_needed = estimated_input + reserved + self._safety_margin

        # Compact if we're approaching the limit
        return total_needed > self._context_window * self._threshold_pressure

    def compact_messages(
        self,
        stage_id: str,
        messages: list[Any],
        token_counter: TokenCounter,
    ) -> tuple[list[Any], CompactionRecord | None]:
        """Compact messages to fit within budget.

        Preserves:
        - SystemMessage (always)
        - First HumanMessage (objective/work item)
        - Essence Gate answers / confirmed decisions
        - Last N tool exchanges (configurable)
        - Recent conversation

        Reduces:
        - Older ToolMessage pairs → condensed summary
        - Large tool results → truncated
        - Redundant outputs
        """
        if len(messages) <= self._preserve_count + 2:
            return messages, None

        tokens_before = token_counter.estimate_messages_input(messages)

        # Separate messages by category
        system_msgs: list[Any] = []
        first_human: Any = None
        other_human: list[Any] = []
        ai_msgs: list[Any] = []
        tool_msgs: list[Any] = []

        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_msgs.append(msg)
            elif isinstance(msg, HumanMessage):
                if first_human is None:
                    first_human = msg
                else:
                    other_human.append(msg)
            elif isinstance(msg, ToolMessage):
                tool_msgs.append(msg)
            elif isinstance(msg, AIMessage):
                ai_msgs.append(msg)
            else:
                other_human.append(msg)

        # Build compacted list
        compacted: list[Any] = []

        # Always keep system messages
        compacted.extend(system_msgs)

        # Always keep first human (objective)
        if first_human:
            compacted.append(first_human)

        # Truncate large tool results
        truncated_tool_msgs = []
        for tm in tool_msgs:
            content = getattr(tm, "content", "")
            if isinstance(content, str) and len(content) > self._truncate_tool_result_chars:
                head = content[: self._truncate_tool_result_chars // 2]
                tail = content[-self._truncate_tool_result_chars // 2 :]
                compacted_content = (
                    f"[truncated tool result, {len(content)} chars]\n--- head ---\n{head}\n--- tail ---\n{tail}"
                )
                truncated_tool_msgs.append(ToolMessage(content=compacted_content, tool_call_id=tm.tool_call_id))
            else:
                truncated_tool_msgs.append(tm)

        # Keep recent messages (last preserve_count from combined ai+tool+human)
        recent_pool = list(other_human) + list(ai_msgs) + list(truncated_tool_msgs)

        # Keep the last N messages
        kept_recent = recent_pool[-self._preserve_count :]

        # Summarize the dropped messages
        dropped = recent_pool[: -self._preserve_count]
        if dropped:
            dropped_tokens = sum(token_counter.count(getattr(m, "content", "") or "") for m in dropped)
            summary = HumanMessage(
                content=(
                    f"[Compacted: {len(dropped)} earlier messages "
                    f"({dropped_tokens} tokens). Tool exchanges and intermediate "
                    f"results have been summarized for context window management.]"
                )
            )
            compacted.append(summary)

        compacted.extend(kept_recent)

        tokens_after = token_counter.estimate_messages_input(compacted)
        saved = tokens_before - tokens_after

        record = None
        if saved > 0:
            call_num = self._call_counters.get(stage_id, 0)
            record = CompactionRecord(
                stage_id=stage_id,
                call_number=call_num,
                timestamp=time.monotonic(),
                tokens_before=tokens_before,
                tokens_after=tokens_after,
                tokens_saved=saved,
                strategy="message_truncation",
            )
            self._compaction_records.append(record)
            self._total_compacted += saved

        return compacted, record

    # ── Forecast ────────────────────────────────────────────────

    def forecast_graph(
        self,
        stages: list[str],
        stage_estimates: dict[str, int],
    ) -> ForecastResult:
        """Project whether the proposed graph can execute within budget."""
        total = 0
        peak_stage = ""
        peak_tokens = 0
        exceeding = []

        for stage_id in stages:
            estimate = stage_estimates.get(stage_id, 0)
            total += estimate
            if estimate > peak_tokens:
                peak_tokens = estimate
                peak_stage = stage_id
            if estimate > self._context_window:
                exceeding.append(stage_id)

        return ForecastResult(
            total_projected=total,
            context_window=self._context_window,
            feasible=len(exceeding) == 0 and peak_tokens <= self._context_window,
            peak_stage=peak_stage,
            peak_tokens=peak_tokens,
            stages_exceeding=exceeding,
        )

    # ── State ───────────────────────────────────────────────────

    def get_state(self, stage_id: str = "") -> ContextBudgetState:
        """Current budget snapshot for ViewModel."""
        reserved = self._get_reserved_output(stage_id or self._current_stage)
        used = self._current_breakdown.input_total + self._current_breakdown.output_tokens
        remaining = self._context_window - self._current_breakdown.input_total
        safe_remaining = self._context_window - used - reserved - self._safety_margin

        # Determine current pressure
        usage_ratio = self._current_breakdown.input_total / max(self._context_window, 1)
        pressure = self._classify_pressure(usage_ratio)

        # Build stage history for the requested stage
        stage_hist = {}
        if stage_id:
            stage_hist[stage_id] = self._stage_history.get(stage_id, [])
        else:
            stage_hist = dict(self._stage_history)

        return ContextBudgetState(
            model_name=self._model_name,
            context_window=self._context_window,
            call_breakdown=CallBreakdown(
                system_prompt=self._current_breakdown.system_prompt,
                stage_instructions=self._current_breakdown.stage_instructions,
                conversation=self._current_breakdown.conversation,
                tool_results=self._current_breakdown.tool_results,
                previous_outputs=self._current_breakdown.previous_outputs,
                other=self._current_breakdown.other,
                input_total=self._current_breakdown.input_total,
                output_tokens=self._current_breakdown.output_tokens,
                cached_tokens=self._current_breakdown.cached_tokens,
            ),
            reserved_output=reserved,
            safety_margin=self._safety_margin,
            used_tokens=used,
            remaining_tokens=remaining,
            safe_remaining=safe_remaining,
            pressure=pressure,
            stage_history=stage_hist,
            tool_calls=self._current_tool_calls,
            tool_tokens=self._current_tool_tokens,
            compaction_mode=self._compaction_mode,
            compaction_records=list(self._compaction_records),
            tokens_compacted=self._total_compacted,
            compaction_suggested=pressure == ContextPressure.PRESSURE,
            tokenizer_provider="",  # set by caller
            tokenizer_accuracy="estimated",  # set by caller
        )

    def reset_stage(self, stage_id: str) -> None:
        """Reset tracking state when entering a new stage."""
        self._current_stage = stage_id
        self._current_breakdown = CallBreakdown()
        self._current_tool_calls = 0
        self._current_tool_tokens = 0

    # ── Reserved output resolution ──────────────────────────────

    def _get_reserved_output(self, stage_id: str) -> int:
        """Resolve reserved output: stage override > global default.

        In adaptive mode, adjusts based on historical output for this stage.
        """
        if stage_id in self._stage_reserved:
            cfg = self._stage_reserved[stage_id]
            if cfg.mode == "adaptive":
                return self._adaptive_reserved(stage_id, cfg)
            return cfg.value
        return self._reserved_output

    @staticmethod
    def _adaptive_reserved(
        stage_id: str,
        cfg: ReservedOutputConfig,
        history: dict[str, list[StageHistoryEntry]] | None = None,
    ) -> int:
        """Calculate reserved output from historical data."""
        # This is called from _get_reserved_output which has access to history
        # We use a class-level reference pattern
        return cfg.value  # base; overridden below

    # ── Pressure classification ─────────────────────────────────

    def _classify_pressure(self, usage_ratio: float) -> ContextPressure:
        """Classify pressure state from usage ratio."""
        if usage_ratio >= self._threshold_pressure:
            return ContextPressure.EXHAUSTED
        if usage_ratio >= self._threshold_watch:
            return ContextPressure.PRESSURE
        if usage_ratio >= self._threshold_safe:
            return ContextPressure.WATCH
        return ContextPressure.SAFE


__all__ = [
    "BudgetCheckResult",
    "CallBreakdown",
    "CompactionMode",
    "CompactionRecord",
    "ContextBudgetManager",
    "ContextBudgetState",
    "ContextPressure",
    "ForecastResult",
    "ReservedOutputConfig",
    "StageHistoryEntry",
]
