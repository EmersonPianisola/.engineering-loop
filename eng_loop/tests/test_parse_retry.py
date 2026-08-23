"""Tests for parse_retry module."""

from __future__ import annotations

from unittest.mock import Mock, patch

from pydantic import BaseModel

from eng_loop.tools.parse_retry import (
    create_correction_prompt,
    retry_with_correction,
    validate_against_schema,
)


class SimpleSchema(BaseModel):
    name: str
    value: int


class TestCreateCorrectionPrompt:
    def test_basic_prompt(self):
        prompt = create_correction_prompt(
            original_content="invalid json",
            error_message="Unexpected token",
            attempt=1,
        )
        assert "JSON CORRECTION NEEDED" in prompt
        assert "Attempt 1/2" in prompt
        assert "invalid json" in prompt

    def test_prompt_with_schema(self):
        prompt = create_correction_prompt(
            original_content="invalid json",
            error_message="Unexpected token",
            output_schema=SimpleSchema,
            attempt=1,
        )
        assert "Expected fields: name, value" in prompt


class TestValidateAgainstSchema:
    def test_valid_data(self):
        data = {"name": "test", "value": 42}
        is_valid, error = validate_against_schema(data, SimpleSchema, "test_stage")
        assert is_valid is True
        assert error == ""

    def test_invalid_data_missing_field(self):
        data = {"name": "test"}
        is_valid, error = validate_against_schema(data, SimpleSchema, "test_stage")
        assert is_valid is False
        assert "value" in error

    def test_invalid_data_wrong_type(self):
        data = {"name": "test", "value": "not an int"}
        is_valid, error = validate_against_schema(data, SimpleSchema, "test_stage")
        assert is_valid is False

    def test_no_schema(self):
        data = {"anything": "goes"}
        is_valid, error = validate_against_schema(data, None, "test_stage")
        assert is_valid is True
        assert error == ""


class TestRetryWithCorrection:
    @patch("eng_loop.tools.parse_retry.extract_json")
    def test_successful_retry(self, mock_extract):
        # First call succeeds on retry
        mock_extract.return_value = {"name": "test", "value": 42}

        mock_model = Mock()
        mock_response = Mock()
        mock_response.content = '{"name": "test", "value": 42}'
        mock_model.invoke.return_value = mock_response

        result = retry_with_correction(
            model=mock_model,
            original_content="invalid",
            error_message="parse error",
            output_schema=None,
            stage_id="test",
        )

        assert result == {"name": "test", "value": 42}
        assert mock_model.invoke.call_count >= 1

    @patch("eng_loop.tools.parse_retry.extract_json")
    def test_exhausted_retries(self, mock_extract):
        # All retries fail
        mock_extract.side_effect = ValueError("parse error")

        mock_model = Mock()
        mock_response = Mock()
        mock_response.content = "still invalid"
        mock_model.invoke.return_value = mock_response

        result = retry_with_correction(
            model=mock_model,
            original_content="invalid",
            error_message="parse error",
            output_schema=None,
            stage_id="test",
        )

        assert result is None
        assert mock_model.invoke.call_count == 2  # MAX_PARSE_RETRIES
