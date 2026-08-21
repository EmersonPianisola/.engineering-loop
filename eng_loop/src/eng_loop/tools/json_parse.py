from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def extract_json(content: str) -> dict[str, Any]:
    """Extract JSON from LLM response content.

    Tries multiple strategies:
    1. Direct JSON parse
    2. Extract from markdown code block
    3. Extract from JSON-like substring (brace matching)
    4. Extract from array wrapper
    5. Fallback: construct dict from key-value patterns

    Raises ValueError if content is empty or extraction fails completely.
    """
    if not content or not content.strip():
        logger.debug("extract_json: empty content")
        raise ValueError("Empty LLM response")

    text = content.strip()
    logger.debug("[DEBUG] extract_json: attempting on content length=%d, preview=%r", len(text), text[:120])

    # Strategy 1: Direct parse
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            logger.debug("[DEBUG] extract_json: strategy 1 (direct) succeeded")
            return result
        # If it's a list, wrap it
        if isinstance(result, list):
            logger.debug("[DEBUG] extract_json: strategy 1 returned list, wrapping")
            return {"items": result}
    except json.JSONDecodeError as e:
        logger.debug("[DEBUG] extract_json: strategy 1 (direct) failed: %s", e)

    # Strategy 2: Extract from markdown code block
    code_block = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if code_block:
        inner = code_block.group(1).strip()
        logger.debug("[DEBUG] extract_json: strategy 2 (code block) found, inner length=%d", len(inner))
        try:
            result = json.loads(inner)
            if isinstance(result, dict):
                logger.debug("[DEBUG] extract_json: strategy 2 (code block) succeeded")
                return result
        except json.JSONDecodeError as e:
            logger.debug("[DEBUG] extract_json: strategy 2 (code block) parse failed: %s", e)

    # Strategy 3: Find JSON object by matching braces
    brace_result = _extract_brace_json(text)
    if brace_result:
        return brace_result

    # Strategy 4: Find JSON array
    array_result = _extract_array_json(text)
    if array_result:
        return array_result

    # Strategy 5: Extract key-value pairs from structured text
    kv_result = _extract_key_value_pairs(text)
    if kv_result:
        logger.debug("[DEBUG] extract_json: strategy 5 (key-value) succeeded with %d fields", len(kv_result))
        return kv_result

    # Strategy 6: REMOVED - Prose fallback silently masked parsing errors
    # Now raising proper errors to force retry or correction
    # Previous behavior: returned {"raw_output": text[:5000], "complete": True}
    # which allowed malformed data to flow through the pipeline

    # All strategies failed - log comprehensive error context
    logger.error("[ERROR] extract_json: ALL STRATEGIES FAILED for content length=%d", len(text))
    logger.error("[ERROR] extract_json: FULL CONTENT:\n%s", text[:1000])
    logger.error("[ERROR] extract_json: Strategies attempted:")
    logger.error("[ERROR]   - Strategy 1: Direct JSON parse - failed")
    logger.error("[ERROR]   - Strategy 2: Markdown code block - not found or invalid")
    logger.error("[ERROR]   - Strategy 3: Brace matching - no valid JSON object found")
    logger.error("[ERROR]   - Strategy 4: Array extraction - no valid JSON array found")
    logger.error("[ERROR]   - Strategy 5: Key-value pairs - insufficient fields")
    raise ValueError(f"Could not extract JSON from LLM response (length={len(text)}). Content preview: {text[:200]!r}")


def _extract_brace_json(text: str) -> dict[str, Any] | None:
    """Find a valid JSON object by matching braces."""
    # Find all opening braces
    for match in re.finditer(r"\{", text):
        start = match.start()
        depth = 0
        brace_end = start

        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    brace_end = i
                    break

        if depth == 0 and brace_end > start:
            candidate = text[start : brace_end + 1]
            try:
                result = json.loads(candidate)
                if isinstance(result, dict) and result:
                    logger.debug("[DEBUG] extract_json: strategy 3 (brace) succeeded at offset %d", start)
                    return result
            except json.JSONDecodeError:
                continue

    return None


def _extract_array_json(text: str) -> dict[str, Any] | None:
    """Find a valid JSON array and wrap it."""
    for match in re.finditer(r"\[", text):
        start = match.start()
        depth = 0
        bracket_end = start

        for i in range(start, len(text)):
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
                if depth == 0:
                    bracket_end = i
                    break

        if depth == 0 and bracket_end > start:
            candidate = text[start : bracket_end + 1]
            try:
                result = json.loads(candidate)
                if isinstance(result, list) and result:
                    logger.debug("[DEBUG] extract_json: strategy 4 (array) succeeded")
                    return {"items": result}
            except json.JSONDecodeError:
                continue

    return None


def _extract_key_value_pairs(text: str) -> dict[str, Any] | None:
    """Extract key-value pairs from structured text as fallback.

    Handles patterns like:
    - key: value
    - key = value
    - "key": "value"
    - - key: value
    - Portuguese text with accented characters
    """
    result = {}

    # Pattern 1: JSON-like key-value pairs (more robust for international text)
    for match in re.finditer(r'["\']?([\w\u00C0-\u024F]+)["\']?\s*[:=]\s*"?([^"\n]+?)"?(?:,|$)', text, re.MULTILINE):
        key = match.group(1).strip()
        value = match.group(2).strip().rstrip(",").strip('"')
        if key and value and len(key) < 50:
            # Try to parse value as JSON (for numbers, booleans, arrays)
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass
            result[key] = value

    # Pattern 2: Bullet points with colons (supports Unicode)
    for match in re.finditer(r'^\s*[-*]\s*["\']?([\w\u00C0-\u024F]+)["\']?\s*:\s*(.+)$', text, re.MULTILINE):
        key = match.group(1).strip()
        value = match.group(2).strip().rstrip(",").strip('"')
        if key and value and key not in result:
            result[key] = value

    # Pattern 3: Labeled lines (e.g., "Title: value", "Status: complete")
    for match in re.finditer(r"^([\w\u00C0-\u024F]+):\s+(.+)$", text, re.MULTILINE):
        key = match.group(1).strip()
        value = match.group(2).strip()
        # Only add if not already present and looks like a valid key
        if key and value and key not in result and len(key) < 30:
            result[key] = value

    return result if len(result) >= 2 else None
