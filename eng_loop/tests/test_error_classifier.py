from __future__ import annotations

from eng_loop.tools.error_classifier import classify_error


class TestClassifyError:
    def test_transient_timeout(self) -> None:
        state = {"current_stage": "impl.code", "stages": {}}
        result = classify_error("Connection timed out after 30s", state)
        assert result.category == "transient"
        assert result.suggested_strategy == "retry"
        assert result.is_retryable is True

    def test_transient_rate_limit(self) -> None:
        state = {"current_stage": "impl.code", "stages": {}}
        result = classify_error("429 Too Many Requests - rate limit exceeded", state)
        assert result.category == "transient"
        assert result.suggested_strategy == "retry"

    def test_infrastructure_llm_error(self) -> None:
        state = {"current_stage": "impl.code", "stages": {}}
        result = classify_error("OpenAI API error: 503 Service Unavailable", state)
        assert result.category == "infrastructure"
        assert result.suggested_strategy == "retry"

    def test_infrastructure_disk_full(self) -> None:
        state = {"current_stage": "impl.code", "stages": {}}
        result = classify_error("No space left on device: disk full", state)
        assert result.category == "infrastructure"
        assert result.suggested_strategy == "abort"
        assert result.is_retryable is False

    def test_schema_json_error(self) -> None:
        state = {"current_stage": "impl.code", "stages": {}}
        result = classify_error("JSON parse error: unexpected token at position 42", state)
        assert result.category == "schema"
        assert result.suggested_strategy == "retry"

    def test_schema_pydantic_error(self) -> None:
        state = {"current_stage": "impl.code", "stages": {}}
        result = classify_error("Pydantic validation error: field 'x' required", state)
        assert result.category == "schema"

    def test_contract_violation(self) -> None:
        state = {"current_stage": "impl.code", "stages": {}}
        result = classify_error("Contract violation: type mismatch in API response", state)
        assert result.category == "contract"
        assert result.suggested_strategy == "rollback"

    def test_logic_non_convergence(self) -> None:
        state = {"current_stage": "impl.code", "stages": {}}
        result = classify_error("impl.code non-convergence after 3 attempts", state)
        assert result.category == "logic"
        assert result.suggested_strategy == "rollback"

    def test_logic_stall(self) -> None:
        state = {"current_stage": "impl.code", "stages": {}}
        result = classify_error("Agent stalled: no progress after 10 iterations", state)
        assert result.category == "logic"

    def test_logic_test_failure(self) -> None:
        state = {"current_stage": "verify", "stages": {}}
        result = classify_error("Test failure: assertion error in test_login", state)
        assert result.category == "logic"
        assert result.suggested_strategy == "rollback"

    def test_context_overflow(self) -> None:
        state = {"current_stage": "impl.code", "stages": {}}
        result = classify_error("Context window exceeded: token limit reached", state)
        assert result.category == "context_overflow"
        assert result.suggested_strategy == "retry"

    def test_agent_error(self) -> None:
        state = {"current_stage": "impl.code", "stages": {}}
        result = classify_error("impl.code agent error: exceeded max iterations", state)
        assert result.category == "logic"
        assert result.suggested_strategy == "rollback"

    def test_blocked_infrastructure(self) -> None:
        state = {"current_stage": "qa.static", "stages": {}}
        result = classify_error("qa.static BLOCKED: infrastructure failure", state)
        assert result.category == "infrastructure"

    def test_unknown_error_fallback(self) -> None:
        state = {"current_stage": "impl.code", "stages": {}}
        result = classify_error("Some completely unknown error", state)
        assert result.category in ("logic", "infrastructure", "transient", "schema", "contract", "context_overflow")
        assert result.is_retryable is True

    def test_severity_critical_for_impl_code_infrastructure(self) -> None:
        state = {"current_stage": "impl.code", "stages": {}}
        result = classify_error("OpenAI API error: 503", state)
        assert result.severity == "critical"

    def test_severity_critical_for_verify_infrastructure(self) -> None:
        state = {"current_stage": "verify", "stages": {}}
        result = classify_error("OpenAI API error: 503", state)
        assert result.severity == "critical"

    def test_severity_medium_for_qa(self) -> None:
        state = {"current_stage": "qa.static", "stages": {}}
        result = classify_error("Test failure: assertion error", state)
        assert result.severity == "medium"

    def test_case_insensitive_matching(self) -> None:
        state = {"current_stage": "impl.code", "stages": {}}
        result = classify_error("TIMEOUT: Connection Timed Out", state)
        assert result.category == "transient"

    def test_empty_blocking_condition(self) -> None:
        state = {"current_stage": "impl.code", "stages": {}}
        result = classify_error("", state)
        assert result.category in ("logic", "infrastructure", "transient", "schema", "contract", "context_overflow")
