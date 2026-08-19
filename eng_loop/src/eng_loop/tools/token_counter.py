from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TokenAccuracy(str, Enum):
    EXACT = "exact"
    COMPATIBLE = "compatible"
    ESTIMATED = "estimated"


@dataclass
class TokenCounterInfo:
    provider: str
    model: str
    accuracy: TokenAccuracy


@dataclass
class MessageBreakdown:
    system_prompt: int = 0
    stage_instructions: int = 0
    conversation: int = 0
    tool_results: int = 0
    ai_output: int = 0
    other: int = 0

    @property
    def total(self) -> int:
        return (
            self.system_prompt
            + self.stage_instructions
            + self.conversation
            + self.tool_results
            + self.ai_output
            + self.other
        )


# Model family → tiktoken encoding name mapping
_MODEL_ENCODING_MAP: dict[str, str] = {
    # OpenAI models
    "gpt-4o": "cl100k_base",
    "gpt-4o-mini": "cl100k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-4": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
    # Claude models use a different tokenizer but cl100k_base is close enough for estimation
    "claude": "cl100k_base",
    # Default fallback for OpenAI-compatible endpoints
    "default": "cl100k_base",
}


@dataclass
class _TiktokenCounter:
    encoding: Any
    info: TokenCounterInfo

    def count(self, text: str) -> int:
        return len(self.encoding.encode(text))


@dataclass
class _FallbackCounter:
    info: TokenCounterInfo

    def count(self, text: str) -> int:
        return max(1, len(text) // 4) if text else 0


class TokenCounter:
    """Resolves the best available tokenizer for a model endpoint.

    Priority chain:
    1. tiktoken (OpenAI-compatible endpoints)
    2. Model-native tokenizer if accessible
    3. Fallback: 4 chars/token estimate
    """

    def __init__(self, model_name: str, base_url: str | None = None):
        self._model_name = model_name
        self._counter, self._info = self._resolve(model_name, base_url)

    @property
    def info(self) -> TokenCounterInfo:
        return self._info

    def count(self, text: str) -> int:
        return self._counter.count(text)

    def count_messages(self, messages: list[Any]) -> MessageBreakdown:
        """Count tokens per message type for breakdown analysis."""
        breakdown = MessageBreakdown()

        for msg in messages:
            content = self._extract_content(msg)
            if not content:
                continue

            tokens = self._counter.count(content)

            if self._is_system_message(msg):
                breakdown.system_prompt += tokens
            elif self._is_tool_message(msg):
                breakdown.tool_results += tokens
            elif self._is_ai_message(msg):
                breakdown.ai_output += tokens
            elif self._is_human_message(msg):
                # First human message often contains stage instructions
                if "##" in content and ("instruction" in content.lower() or "procedure" in content.lower()):
                    breakdown.stage_instructions += tokens
                else:
                    breakdown.conversation += tokens
            else:
                breakdown.other += tokens

        return breakdown

    def estimate_messages_input(self, messages: list[Any]) -> int:
        """Quick estimate of total input tokens for a message list."""
        total = 0
        for msg in messages:
            content = self._extract_content(msg)
            if content:
                total += self._counter.count(content)
        return total

    # ── Resolution ──────────────────────────────────────────────

    @staticmethod
    def _resolve(
        model_name: str,
        base_url: str | None,
    ) -> tuple[Any, TokenCounterInfo]:
        counter, info = TokenCounter._try_tiktoken(model_name)
        if counter is not None:
            return counter, info
        return TokenCounter._fallback(model_name)

    @staticmethod
    def _try_tiktoken(model_name: str) -> tuple[Any, TokenCounterInfo] | tuple[None, None]:
        try:
            import tiktoken
        except ImportError:
            logger.debug("tiktoken not installed; falling back to char estimator")
            return None, None

        encoding_name = TokenCounter._lookup_encoding(model_name)
        try:
            encoding = tiktoken.get_encoding(encoding_name)
            info = TokenCounterInfo(
                provider="tiktoken",
                model=model_name,
                accuracy=TokenAccuracy.EXACT
                if encoding_name in _MODEL_ENCODING_MAP.values()
                else TokenAccuracy.COMPATIBLE,
            )
            return _TiktokenCounter(encoding=encoding, info=info), info
        except Exception as e:
            logger.debug("tiktoken encoding failed (%s), falling back", e)
            return None, None

    @staticmethod
    def _fallback(model_name: str) -> tuple[Any, TokenCounterInfo]:
        info = TokenCounterInfo(
            provider="fallback",
            model=model_name,
            accuracy=TokenAccuracy.ESTIMATED,
        )
        return _FallbackCounter(info=info), info

    @staticmethod
    def _lookup_encoding(model_name: str) -> str:
        lower = model_name.lower()
        for key, enc in _MODEL_ENCODING_MAP.items():
            if key in lower:
                return enc
        return _MODEL_ENCODING_MAP["default"]

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _extract_content(msg: Any) -> str:
        content = getattr(msg, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(item.get("text", ""))
            return " ".join(parts)
        return str(content) if content else ""

    @staticmethod
    def _is_system_message(msg: Any) -> bool:
        from langchain_core.messages import SystemMessage

        return isinstance(msg, SystemMessage)

    @staticmethod
    def _is_tool_message(msg: Any) -> bool:
        from langchain_core.messages import ToolMessage

        return isinstance(msg, ToolMessage)

    @staticmethod
    def _is_ai_message(msg: Any) -> bool:
        from langchain_core.messages import AIMessage

        return isinstance(msg, AIMessage)

    @staticmethod
    def _is_human_message(msg: Any) -> bool:
        from langchain_core.messages import HumanMessage

        return isinstance(msg, HumanMessage)


__all__ = [
    "MessageBreakdown",
    "TokenAccuracy",
    "TokenCounter",
    "TokenCounterInfo",
]
