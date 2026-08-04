from __future__ import annotations

import json
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_json(content: str) -> dict[str, Any]:
    """Extract JSON from LLM response content.
    
    Tries multiple strategies:
    1. Direct JSON parse
    2. Extract from markdown code block
    3. Extract from JSON-like substring
    4. Fallback to empty dict with warning
    
    Raises ValueError if content is empty or extraction fails completely.
    """
    if not content or not content.strip():
        logger.warning("extract_json: empty content")
        raise ValueError("Empty LLM response")
    
    text = content.strip()
    
    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Extract from markdown code block
    code_block = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except json.JSONDecodeError:
            pass
    
    # Strategy 3: Find JSON object by matching braces
    brace_start = text.find('{')
    if brace_start >= 0:
        depth = 0
        brace_end = brace_start
        for i in range(brace_start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    brace_end = i
                    break
        
        if depth == 0 and brace_end > brace_start:
            candidate = text[brace_start:brace_end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
    
    # All strategies failed
    logger.error("extract_json: all strategies failed for content of length %d", len(text))
    logger.error("extract_json: content preview: %s", text[:200])
    raise ValueError(f"Could not extract JSON from LLM response (length={len(text)})")
