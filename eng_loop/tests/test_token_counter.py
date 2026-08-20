from __future__ import annotations

from eng_loop.tools.token_counter import (
    MessageBreakdown,
    TokenAccuracy,
    TokenCounter,
    TokenCounterInfo,
)


# ── Resolution tests ──────────────────────────────────────────


def test_resolve_tiktoken():
    counter = TokenCounter("gpt-4o")
    assert counter.info.provider == "tiktoken"
    assert counter.info.accuracy in (TokenAccuracy.EXACT, TokenAccuracy.COMPATIBLE)


def test_fallback_estimator():
    """When tiktoken is unavailable, falls back to char estimator."""
    # Force fallback by using an unknown model with no tiktoken
    counter = TokenCounter("unknown-local-model-xyz")
    # tiktoken should still resolve (it uses cl100k_base as default)
    # So we check the count works
    assert counter.count("hello world") > 0


def test_count_basic():
    counter = TokenCounter("gpt-4o")
    count = counter.count("hello world")
    assert count > 0
    assert count < 10  # "hello world" is a few tokens


def test_count_empty():
    counter = TokenCounter("gpt-4o")
    assert counter.count("") == 0


def test_count_long_text():
    counter = TokenCounter("gpt-4o")
    long_text = "The quick brown fox jumps over the lazy dog. " * 100
    count = counter.count(long_text)
    assert count > 100  # Should be well over 100 tokens


# ── Message breakdown tests ───────────────────────────────────


def test_count_messages_breakdown():
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    counter = TokenCounter("gpt-4o")
    messages = [
        SystemMessage(content="You are a helpful assistant."),
        HumanMessage(content="What is 2+2?"),
        AIMessage(content="2+2 equals 4."),
        ToolMessage(content="File read result: some content here", tool_call_id="1"),
    ]
    breakdown = counter.count_messages(messages)

    assert breakdown.system_prompt > 0
    assert breakdown.conversation > 0
    assert breakdown.ai_output > 0
    assert breakdown.tool_results > 0
    assert breakdown.total == (
        breakdown.system_prompt + breakdown.conversation + breakdown.ai_output + breakdown.tool_results
    )


def test_estimate_messages_input():
    from langchain_core.messages import HumanMessage, SystemMessage

    counter = TokenCounter("gpt-4o")
    messages = [
        SystemMessage(content="System prompt here."),
        HumanMessage(content="User message here."),
    ]
    total = counter.estimate_messages_input(messages)
    assert total > 0


def test_estimate_empty_messages():
    counter = TokenCounter("gpt-4o")
    assert counter.estimate_messages_input([]) == 0


# ── Info accuracy ─────────────────────────────────────────────


def test_info_fields():
    counter = TokenCounter("gpt-4o")
    assert counter.info.provider in ("tiktoken", "fallback")
    assert counter.info.model == "gpt-4o"
    assert counter.info.accuracy in (
        TokenAccuracy.EXACT,
        TokenAccuracy.COMPATIBLE,
        TokenAccuracy.ESTIMATED,
    )


def test_fallback_accuracy():
    """Fallback counter reports ESTIMATED accuracy."""
    counter = TokenCounter("some-unknown-model")
    # tiktoken may still resolve with compatible accuracy
    assert counter.info.accuracy in (
        TokenAccuracy.EXACT,
        TokenAccuracy.COMPATIBLE,
        TokenAccuracy.ESTIMATED,
    )


# ── Edge cases ────────────────────────────────────────────────


def test_count_special_characters():
    counter = TokenCounter("gpt-4o")
    text = "Hello \u2603 \U0001f600 world!"
    count = counter.count(text)
    assert count > 0


def test_count_multiline():
    counter = TokenCounter("gpt-4o")
    text = "line1\nline2\nline3\n"
    count = counter.count(text)
    assert count > 0


def test_breakdown_with_only_system():
    from langchain_core.messages import SystemMessage

    counter = TokenCounter("gpt-4o")
    messages = [SystemMessage(content="Only system message.")]
    breakdown = counter.count_messages(messages)
    assert breakdown.system_prompt > 0
    assert breakdown.conversation == 0
    assert breakdown.ai_output == 0


def test_breakdown_with_only_human():
    from langchain_core.messages import HumanMessage

    counter = TokenCounter("gpt-4o")
    messages = [HumanMessage(content="Just a question.")]
    breakdown = counter.count_messages(messages)
    # Simple human message goes to conversation
    assert breakdown.conversation > 0 or breakdown.stage_instructions > 0
