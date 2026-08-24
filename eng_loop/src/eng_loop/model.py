from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_MODEL = "qwable-v2"

# Keys resolved with the same precedence everywhere: stage override > model
# config > per-factory default.
MODEL_PARAM_KEYS = ("base_url", "model", "temperature", "max_tokens", "timeout", "max_retries", "api_key", "headers")


def _resolve_model_params(config: dict[str, Any], stage_id: str, defaults: dict[str, Any]) -> dict[str, Any]:
    """Resolve model params: stage override > model config > defaults."""
    model_cfg = config.get("model", {})
    stage_override = config.get("model_overrides", {}).get(stage_id, {})
    params: dict[str, Any] = {}
    for key in MODEL_PARAM_KEYS:
        if key in stage_override:
            params[key] = stage_override[key]
        elif key in model_cfg:
            params[key] = model_cfg[key]
        else:
            params[key] = defaults[key]
    return params


def _build_model(params: dict[str, Any], callbacks: list[Any] | None = None) -> ChatOpenAI:
    kwargs: dict[str, Any] = {
        "base_url": params["base_url"],
        "model": params["model"],
        "temperature": params["temperature"],
        "max_tokens": params["max_tokens"],
        "timeout": params["timeout"],
        "max_retries": params["max_retries"],
        "api_key": params["api_key"],
    }
    if params.get("headers"):
        # Not a first-class ChatOpenAI param in this langchain-openai version —
        # the OpenAI client receives it through model_kwargs.
        kwargs["model_kwargs"] = {"headers": params["headers"]}
    if callbacks:
        kwargs["callbacks"] = callbacks
    return ChatOpenAI(**kwargs)


def create_model(
    base_url: str | None = None,
    model_name: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 128000,
    timeout: int = 300,
    callbacks: list[Any] | None = None,
) -> ChatOpenAI:
    kwargs: dict[str, Any] = {
        "base_url": base_url or DEFAULT_BASE_URL,
        "model": model_name or DEFAULT_MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "api_key": "not-needed",
    }
    if callbacks:
        kwargs["callbacks"] = callbacks
    return ChatOpenAI(**kwargs)


def _config_defaults(**overrides: Any) -> dict[str, Any]:
    defaults = {
        "base_url": DEFAULT_BASE_URL,
        "model": DEFAULT_MODEL,
        "temperature": 0.0,
        "max_tokens": 128000,
        "timeout": 300,
        "max_retries": 2,
        "api_key": "not-needed",
        "headers": None,
    }
    defaults.update(overrides)
    return defaults


def create_model_from_config(
    config: dict[str, Any],
    stage_id: str = "",
    callbacks: list[Any] | None = None,
) -> ChatOpenAI:
    params = _resolve_model_params(config, stage_id, _config_defaults())
    return _build_model(params, callbacks)


def create_reasoning_model(
    config: dict[str, Any],
    stage_id: str = "",
    callbacks: list[Any] | None = None,
) -> ChatOpenAI:
    params = _resolve_model_params(config, stage_id, _config_defaults(temperature=0.3))
    return _build_model(params, callbacks)


def create_code_model(
    config: dict[str, Any],
    stage_id: str = "",
    callbacks: list[Any] | None = None,
) -> ChatOpenAI:
    params = _resolve_model_params(config, stage_id, _config_defaults(temperature=0.0, max_tokens=200000))
    return _build_model(params, callbacks)
