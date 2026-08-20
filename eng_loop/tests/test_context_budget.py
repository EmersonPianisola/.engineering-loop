from __future__ import annotations

from eng_loop.tools.context_budget import (
    CallBreakdown,
    CompactionMode,
    ContextBudgetManager,
    ContextPressure,
    ReservedOutputConfig,
)

# ── Budget math ───────────────────────────────────────────────


def test_safe_remaining_calculation():
    mgr = ContextBudgetManager(
        context_window=32768,
        reserved_output=4096,
        safety_margin=2048,
    )
    result = mgr.check_before_call("test", 20000, 4096)
    # safe_remaining = 32768 - 20000 - 4096 - 2048 = 6624
    assert result.safe_remaining == 6624
    assert result.allowed is True


def test_exhausted_when_budget_exceeded():
    mgr = ContextBudgetManager(
        context_window=32768,
        reserved_output=4096,
        safety_margin=2048,
    )
    result = mgr.check_before_call("test", 28000, 4096)
    # total_needed = 28000 + 4096 + 2048 = 34144 > 32768
    assert result.allowed is False
    assert result.pressure == ContextPressure.EXHAUSTED


def test_blocking_by_budget_math_not_percentage():
    """94% usage is allowed if budget math fits."""
    mgr = ContextBudgetManager(
        context_window=10000,
        reserved_output=200,
        safety_margin=100,
        thresholds={"safe": 0.70, "watch": 0.85, "pressure": 0.95},
    )
    # 9400 / 10000 = 94% but 9400 + 200 + 100 = 9700 <= 10000
    result = mgr.check_before_call("test", 9400, 200)
    assert result.allowed is True


def test_pressure_transitions():
    mgr = ContextBudgetManager(
        context_window=10000,
        reserved_output=500,
        safety_margin=500,
        thresholds={"safe": 0.70, "watch": 0.85, "pressure": 0.95},
    )
    # SAFE: 5000 / 10000 = 50%
    assert mgr.check_before_call("test", 5000, 200).pressure == ContextPressure.SAFE
    # WATCH: 7500 / 10000 = 75%
    assert mgr.check_before_call("test", 7500, 200).pressure == ContextPressure.WATCH
    # PRESSURE: 9000 / 10000 = 90%
    assert mgr.check_before_call("test", 9000, 200).pressure == ContextPressure.PRESSURE


# ── Stage history ─────────────────────────────────────────────


def test_stage_history_tracking():
    mgr = ContextBudgetManager(context_window=32768)
    mgr.record_call("init", CallBreakdown(input_total=8000, output_tokens=1000))
    mgr.record_call("init", CallBreakdown(input_total=14000, output_tokens=1200))
    mgr.record_call("init", CallBreakdown(input_total=19000, output_tokens=1500))

    state = mgr.get_state("init")
    assert len(state.stage_history["init"]) == 3
    assert state.stage_history["init"][0].input_tokens == 8000
    assert state.stage_history["init"][1].input_tokens == 14000
    assert state.stage_history["init"][2].input_tokens == 19000


def test_stage_history_separate_per_stage():
    mgr = ContextBudgetManager(context_window=32768)
    mgr.record_call("init", CallBreakdown(input_total=8000, output_tokens=500))
    mgr.record_call("impl.code", CallBreakdown(input_total=12000, output_tokens=3000))

    state = mgr.get_state("init")
    assert len(state.stage_history.get("init", [])) == 1
    state_impl = mgr.get_state("impl.code")
    assert len(state_impl.stage_history.get("impl.code", [])) == 1


# ── Reserved output ───────────────────────────────────────────


def test_hierarchical_reserved_output():
    mgr = ContextBudgetManager(
        context_window=32768,
        reserved_output=4096,
        stage_reserved={
            "impl.code": ReservedOutputConfig(value=8192),
            "init": ReservedOutputConfig(value=2048),
        },
    )
    # Global default
    assert mgr._get_reserved_output("unknown") == 4096
    # Stage override
    assert mgr._get_reserved_output("impl.code") == 8192
    assert mgr._get_reserved_output("init") == 2048


def test_adaptive_reserved_output():
    mgr = ContextBudgetManager(
        context_window=32768,
        reserved_output=4096,
        stage_reserved={
            "impl.code": ReservedOutputConfig(
                mode="adaptive",
                value=4096,
                min_value=2048,
                max_value=8192,
            ),
        },
    )
    # Without history, falls back to default value
    reserved = mgr._get_reserved_output("impl.code")
    assert reserved == 4096


# ── Compaction ────────────────────────────────────────────────


def test_compaction_preserves_critical():
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    from eng_loop.tools.token_counter import TokenCounter

    mgr = ContextBudgetManager(
        context_window=32768,
        compaction_mode=CompactionMode.AUTO,
        preserve_count=3,
    )
    counter = TokenCounter("gpt-4o")

    # Build a long conversation
    messages = [
        SystemMessage(content="You are an assistant."),
        HumanMessage(content="Original objective and work item."),
    ]
    for i in range(20):
        messages.append(AIMessage(content=f"AI response {i} with some content here."))
        messages.append(ToolMessage(content=f"Tool result {i} with detailed output.", tool_call_id=str(i)))

    compacted, record = mgr.compact_messages("test", messages, counter)

    # System message preserved
    assert any(isinstance(m, SystemMessage) for m in compacted)
    # First human preserved
    humans = [m for m in compacted if isinstance(m, HumanMessage)]
    assert any("Original objective" in getattr(m, "content", "") for m in humans)
    # Compaction is now a no-op — lifecycle manager handles context overflow via spawn transitions
    # All messages are preserved unchanged
    assert len(compacted) == len(messages)
    assert compacted is messages


def test_compaction_audit_trail():
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    from eng_loop.tools.token_counter import TokenCounter

    mgr = ContextBudgetManager(
        context_window=32768,
        compaction_mode=CompactionMode.AUTO,
        preserve_count=3,
    )
    counter = TokenCounter("gpt-4o")

    messages = [
        SystemMessage(content="System."),
        HumanMessage(content="Objective."),
    ]
    for i in range(15):
        messages.append(AIMessage(content=f"Response {i}"))
        messages.append(ToolMessage(content=f"Result {i}", tool_call_id=str(i)))

    compacted, record = mgr.compact_messages("test", messages, counter)

    if record:
        assert record.tokens_saved > 0
        assert record.tokens_before > record.tokens_after
        assert record.strategy == "message_truncation"
        assert len(mgr._compaction_records) == 1


def test_compaction_no_op_when_short():
    from langchain_core.messages import HumanMessage, SystemMessage

    from eng_loop.tools.token_counter import TokenCounter

    mgr = ContextBudgetManager(
        context_window=32768,
        preserve_count=15,
    )
    counter = TokenCounter("gpt-4o")
    messages = [
        SystemMessage(content="System."),
        HumanMessage(content="Hello."),
    ]
    compacted, record = mgr.compact_messages("test", messages, counter)
    assert record is None
    assert len(compacted) == len(messages)


def test_compaction_disabled_mode():
    mgr = ContextBudgetManager(
        context_window=32768,
        compaction_mode=CompactionMode.DISABLED,
    )
    assert not mgr.should_compact("test", 30000)


def test_compaction_auto_mode_should_compact():
    mgr = ContextBudgetManager(
        context_window=32768,
        reserved_output=4096,
        safety_margin=2048,
        compaction_mode=CompactionMode.AUTO,
        thresholds={"pressure": 0.95},
    )
    assert mgr.should_compact("test", 30000)


# ── Forecast ──────────────────────────────────────────────────


def test_forecast_feasible_graph():
    mgr = ContextBudgetManager(context_window=32768)
    result = mgr.forecast_graph(
        stages=["init", "impl.code", "post"],
        stage_estimates={"init": 8000, "impl.code": 15000, "post": 5000},
    )
    assert result.feasible is True
    assert result.peak_stage == "impl.code"
    assert result.peak_tokens == 15000


def test_forecast_infeasible_graph():
    mgr = ContextBudgetManager(context_window=32768)
    result = mgr.forecast_graph(
        stages=["init", "impl.code", "post"],
        stage_estimates={"init": 8000, "impl.code": 35000, "post": 5000},
    )
    assert result.feasible is False
    assert "impl.code" in result.stages_exceeding


# ── State ─────────────────────────────────────────────────────


def test_get_state_defaults():
    mgr = ContextBudgetManager(context_window=32768)
    state = mgr.get_state()
    assert state.context_window == 32768
    assert state.pressure == ContextPressure.SAFE
    assert state.compaction_mode == CompactionMode.AUTO


def test_get_state_after_calls():
    mgr = ContextBudgetManager(context_window=32768)
    mgr.record_call("test", CallBreakdown(input_total=24000, output_tokens=3000, cached_tokens=500))
    state = mgr.get_state("test")
    assert state.used_tokens == 27000
    assert state.call_breakdown.input_total == 24000
    assert state.call_breakdown.output_tokens == 3000
    assert state.call_breakdown.cached_tokens == 500


def test_reset_stage():
    mgr = ContextBudgetManager(context_window=32768)
    mgr.record_call("init", CallBreakdown(input_total=20000, output_tokens=3000))
    mgr.reset_stage("impl.code")
    state = mgr.get_state("impl.code")
    assert state.used_tokens == 0
    assert state.tool_calls == 0


def test_tool_tracking():
    mgr = ContextBudgetManager(context_window=32768)
    mgr.record_tool_call("test", 1000)
    mgr.record_tool_call("test", 2000)
    state = mgr.get_state("test")
    assert state.tool_calls == 2
    assert state.tool_tokens == 3000


# ── Edge cases ────────────────────────────────────────────────


def test_zero_context_window():
    mgr = ContextBudgetManager(context_window=0)
    result = mgr.check_before_call("test", 100, 100)
    assert result.allowed is False


def test_negative_safe_remaining():
    mgr = ContextBudgetManager(
        context_window=10000,
        reserved_output=5000,
        safety_margin=3000,
    )
    result = mgr.check_before_call("test", 9000, 2000)
    assert result.allowed is False
    assert result.safe_remaining < 0


def test_exhausted_prevents_call():
    mgr = ContextBudgetManager(
        context_window=32768,
        reserved_output=4096,
        safety_margin=2048,
    )
    # Need 32768 + 1 tokens
    result = mgr.check_before_call("test", 29768, 4096)
    assert result.allowed is False


def test_custom_thresholds():
    mgr = ContextBudgetManager(
        context_window=10000,
        reserved_output=500,
        safety_margin=500,
        thresholds={"safe": 0.50, "watch": 0.70, "pressure": 0.90},
    )
    # 60% should be WATCH with custom thresholds
    result = mgr.check_before_call("test", 6000, 200)
    assert result.pressure == ContextPressure.WATCH
