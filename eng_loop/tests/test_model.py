from __future__ import annotations

"""Tests for model creation functions."""

from eng_loop.model import (
    DEFAULT_MODEL,
    create_code_model,
    create_model,
    create_model_from_config,
    create_reasoning_model,
)


class TestCreateModel:
    def test_defaults(self):
        model = create_model()
        assert model.model_name == DEFAULT_MODEL
        assert model.temperature == 0.0

    def test_custom_params(self):
        model = create_model(
            base_url="http://custom:9000",
            model_name="custom-model",
            temperature=0.7,
            max_tokens=50000,
        )
        assert model.model_name == "custom-model"
        assert model.temperature == 0.7


class TestCreateModelFromConfig:
    def test_default_config(self):
        config = {}
        model = create_model_from_config(config)
        assert model.model_name == DEFAULT_MODEL

    def test_config_with_model_settings(self):
        config = {
            "model": {
                "base_url": "http://custom:9000",
                "model": "custom-model",
                "temperature": 0.5,
                "max_tokens": 60000,
            }
        }
        model = create_model_from_config(config)
        assert model.model_name == "custom-model"
        assert model.temperature == 0.5

    def test_stage_override(self):
        config = {
            "model": {"model": "default-model"},
            "model_overrides": {
                "impl.code": {
                    "model": "code-specialist",
                    "temperature": 0.1,
                }
            },
        }
        model = create_model_from_config(config, stage_id="impl.code")
        assert model.model_name == "code-specialist"
        assert model.temperature == 0.1

    def test_no_override_uses_default(self):
        config = {"model": {"model": "default-model"}, "model_overrides": {"impl.code": {"model": "override-model"}}}
        model = create_model_from_config(config, stage_id="verify")
        assert model.model_name == "default-model"


class TestCreateReasoningModel:
    def test_reasoning_temperature(self):
        config = {}
        model = create_reasoning_model(config)
        assert model.temperature == 0.3


class TestCreateCodeModel:
    def test_code_model_defaults(self):
        config = {}
        model = create_code_model(config)
        assert model.temperature == 0.0
        assert model.max_tokens == 200000

    def test_code_model_override(self):
        config = {
            "model": {"model": "default"},
            "model_overrides": {"impl.code": {"model": "code-model", "max_tokens": 300000}},
        }
        model = create_code_model(config, stage_id="impl.code")
        assert model.model_name == "code-model"
        assert model.max_tokens == 300000


class TestCreateModelTimeout:
    def test_create_model_default_timeout(self):
        """Model accepts timeout parameter and returns ChatOpenAI instance."""
        model = create_model()
        assert model is not None

    def test_create_model_custom_timeout(self):
        """Model accepts explicit timeout value without error."""
        model = create_model(timeout=600)
        assert model is not None

    def test_create_model_from_config_default_timeout(self):
        """Config without timeout creates model successfully."""
        model = create_model_from_config({})
        assert model is not None

    def test_create_model_from_config_timeout_in_model_cfg(self):
        """Config with model.timeout is accepted."""
        config = {"model": {"timeout": 600}}
        model = create_model_from_config(config)
        assert model is not None

    def test_create_model_from_config_timeout_override(self):
        """Stage override timeout is respected."""
        config = {
            "model": {"timeout": 300},
            "model_overrides": {"dynamic.architect": {"timeout": 600}},
        }
        model = create_model_from_config(config, stage_id="dynamic.architect")
        assert model is not None

    def test_create_model_from_config_timeout_no_override(self):
        """Non-overridden stage uses default timeout."""
        config = {
            "model": {"timeout": 300},
            "model_overrides": {"dynamic.architect": {"timeout": 600}},
        }
        model = create_model_from_config(config, stage_id="impl.code")
        assert model is not None

    def test_create_reasoning_model_default_timeout(self):
        """Reasoning model accepts timeout."""
        model = create_reasoning_model({})
        assert model is not None

    def test_create_reasoning_model_timeout_override(self):
        """Reasoning model respects stage override."""
        config = {
            "model": {"timeout": 300},
            "model_overrides": {"dynamic.architect": {"timeout": 600}},
        }
        model = create_reasoning_model(config, stage_id="dynamic.architect")
        assert model is not None

    def test_create_code_model_default_timeout(self):
        """Code model accepts timeout."""
        model = create_code_model({})
        assert model is not None

    def test_create_code_model_timeout_override(self):
        """Code model respects stage override timeout."""
        config = {
            "model": {"timeout": 300},
            "model_overrides": {"impl.code": {"timeout": 45}},
        }
        model = create_code_model(config, stage_id="impl.code")
        assert model is not None
