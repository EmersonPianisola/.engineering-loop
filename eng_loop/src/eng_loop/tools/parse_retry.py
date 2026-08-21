"""Retry mechanism for LLM response parsing with correction prompts."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from eng_loop.tools.json_parse import extract_json

logger = logging.getLogger(__name__)

MAX_PARSE_RETRIES = 2  # Maximum number of retry attempts after initial parse failure


def create_correction_prompt(
    original_content: str,
    error_message: str,
    output_schema: type[BaseModel] | None = None,
    attempt: int = 1,
) -> str:
    """Create a correction prompt to help the LLM fix its malformed output.

    Args:
        original_content: The original malformed response
        error_message: The error message from the parser
        output_schema: Expected schema (if any)
        attempt: Current retry attempt number

    Returns:
        A prompt asking the LLM to reformulate its response as valid JSON
    """
    schema_hint = ""
    if output_schema:
        schema_fields = list(output_schema.model_fields.keys()) if hasattr(output_schema, "model_fields") else []
        if schema_fields:
            schema_hint = f"\n\nExpected fields: {', '.join(schema_fields)}"

    return (
        f"[SYSTEM: JSON CORRECTION NEEDED - Attempt {attempt}/{MAX_PARSE_RETRIES}]\n\n"
        f"Your previous response could not be parsed as valid JSON.\n\n"
        f"Error: {error_message}\n\n"
        f"Your previous output was:\n```\n"
        f"{original_content[:500]}\n```\n\n"
        f"Please reformulate your response as valid JSON. "
        f"Enclose it in a markdown code block with 'json' language tag."
        f"{schema_hint}\n\n"
        f"Return ONLY the JSON object, no additional text."
    )


def retry_with_correction(
    model: ChatOpenAI,
    original_content: str,
    error_message: str,
    output_schema: type[BaseModel] | None = None,
    stage_id: str = "unknown",
) -> dict[str, Any] | None:
    """Attempt to fix a parsing error by asking the LLM to reformulate.

    Args:
        model: The LLM model to use for correction
        original_content: The original malformed response
        error_message: The error message from the parser
        output_schema: Expected schema (if any)
        stage_id: Stage identifier for logging

    Returns:
        Parsed dict if successful, None if all retries exhausted
    """
    for attempt in range(1, MAX_PARSE_RETRIES + 1):
        logger.info(
            "[PARSE RETRY] Attempt %d/%d for stage %s",
            attempt,
            MAX_PARSE_RETRIES,
            stage_id,
        )

        correction_prompt = create_correction_prompt(
            original_content,
            error_message,
            output_schema,
            attempt,
        )

        try:
            # Create a minimal conversation for correction
            messages = [
                SystemMessage(content="You are a helpful assistant that outputs valid JSON."),
                HumanMessage(content=correction_prompt),
            ]

            response = model.invoke(messages)
            corrected_content = response.content if isinstance(response.content, str) else str(response.content)

            # Try to parse the corrected content
            logger.debug("[PARSE RETRY] Corrected content preview: %s", corrected_content[:200])
            result = extract_json(corrected_content)

            logger.info("[PARSE RETRY] Success on attempt %d for stage %s", attempt, stage_id)
            return result

        except ValueError as e:
            logger.warning(
                "[PARSE RETRY] Attempt %d failed for stage %s: %s",
                attempt,
                stage_id,
                str(e)[:100],
            )
            error_message = str(e)  # Update error for next attempt

    logger.error("[PARSE RETRY] All %d attempts exhausted for stage %s", MAX_PARSE_RETRIES, stage_id)
    return None


def validate_against_schema(
    data: dict[str, Any],
    output_schema: type[BaseModel] | None,
    stage_id: str = "unknown",
) -> tuple[bool, str]:
    """Validate parsed data against the expected schema.

    Args:
        data: The parsed data to validate
        output_schema: Expected Pydantic schema
        stage_id: Stage identifier for logging

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not output_schema:
        return True, ""

    try:
        # Try to create a model instance from the data
        model_instance = output_schema.model_validate(data)
        logger.debug("[SCHEMA VALIDATION] Passed for stage %s", stage_id)
        return True, ""

    except Exception as e:
        error_msg = f"Schema validation failed for stage {stage_id}: {str(e)[:200]}"
        logger.warning("[SCHEMA VALIDATION] %s", error_msg)
        return False, error_msg
