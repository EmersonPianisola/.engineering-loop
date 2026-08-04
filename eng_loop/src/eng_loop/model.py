from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_MODEL = "qwable-v2"


def create_model(
    base_url: str | None = None,
    model_name: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 128000,
) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=base_url or DEFAULT_BASE_URL,
        model=model_name or DEFAULT_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key="not-needed",
    )


def create_model_from_config(config: dict[str, Any], stage_id: str = "") -> ChatOpenAI:
    model_cfg = config.get("model", {})
    overrides = config.get("model_overrides", {})
    stage_override = overrides.get(stage_id, {})

    base_url = stage_override.get("base_url", model_cfg.get("base_url", DEFAULT_BASE_URL))
    model_name = stage_override.get("model", model_cfg.get("model", DEFAULT_MODEL))
    temperature = stage_override.get("temperature", model_cfg.get("temperature", 0.0))
    max_tokens = stage_override.get("max_tokens", model_cfg.get("max_tokens", 128000))

    return ChatOpenAI(
        base_url=base_url,
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key="not-needed",
    )


def create_reasoning_model(config: dict[str, Any], stage_id: str = "") -> ChatOpenAI:
    model_cfg = config.get("model", {})
    return ChatOpenAI(
        base_url=model_cfg.get("base_url", DEFAULT_BASE_URL),
        model=model_cfg.get("model", DEFAULT_MODEL),
        temperature=0.3,
        max_tokens=model_cfg.get("max_tokens", 128000),
        api_key="not-needed",
    )


def create_code_model(config: dict[str, Any], stage_id: str = "") -> ChatOpenAI:
    model_cfg = config.get("model", {})
    overrides = config.get("model_overrides", {})
    stage_override = overrides.get(stage_id, {})

    return ChatOpenAI(
        base_url=stage_override.get("base_url", model_cfg.get("base_url", DEFAULT_BASE_URL)),
        model=stage_override.get("model", model_cfg.get("model", DEFAULT_MODEL)),
        temperature=0.0,
        max_tokens=stage_override.get("max_tokens", 200000),
        api_key="not-needed",
    )
