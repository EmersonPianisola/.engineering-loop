"""F3.5 — Model/config.

- load_yaml accepts str | Path (the old annotation was a broken `str % Path`).
- max_retries / api_key / headers are read from the model config (and stage
  overrides), with the previous hardcoded values as defaults.
- create_reasoning_model applies stage overrides like the other factories.
"""

from __future__ import annotations


def test_load_yaml_accepts_str_and_path(tmp_path) -> None:
    from eng_loop.config import load_yaml

    p = tmp_path / "c.yaml"
    p.write_text("a: 1\n", encoding="utf-8")
    assert load_yaml(str(p)) == {"a": 1}
    assert load_yaml(p) == {"a": 1}


class TestModelConfigKeys:
    def test_api_key_max_retries_headers_from_model_cfg(self) -> None:
        from eng_loop.model import create_model_from_config

        config = {"model": {"api_key": "sk-test", "max_retries": 7, "headers": {"X-Test": "1"}}}
        m = create_model_from_config(config)
        assert m.openai_api_key.get_secret_value() == "sk-test"
        assert m.max_retries == 7
        assert m.model_kwargs.get("headers") == {"X-Test": "1"}

    def test_defaults_when_absent(self) -> None:
        from eng_loop.model import create_model_from_config

        m = create_model_from_config({})
        assert m.openai_api_key.get_secret_value() == "not-needed"
        assert m.max_retries == 2
        assert "headers" not in (m.model_kwargs or {})

    def test_reasoning_stage_override_applied(self) -> None:
        from eng_loop.model import create_reasoning_model

        config = {
            "model": {"model": "default-model"},
            "model_overrides": {"dynamic.architect": {"model": "arch-model", "max_retries": 5}},
        }
        m = create_reasoning_model(config, stage_id="dynamic.architect")
        assert m.model_name == "arch-model"
        assert m.max_retries == 5
        assert m.temperature == 0.3

    def test_reasoning_no_override_uses_model_cfg(self) -> None:
        from eng_loop.model import create_reasoning_model

        config = {"model": {"model": "cfg-model", "api_key": "cfg-key"}}
        m = create_reasoning_model(config, stage_id="impl.code")
        assert m.model_name == "cfg-model"
        assert m.openai_api_key.get_secret_value() == "cfg-key"

    def test_code_override_beats_model_cfg(self) -> None:
        from eng_loop.model import create_code_model

        config = {
            "model": {"model": "default-model", "api_key": "cfg-key"},
            "model_overrides": {"impl.code": {"model": "code-model", "api_key": "override-key"}},
        }
        m = create_code_model(config, stage_id="impl.code")
        assert m.model_name == "code-model"
        assert m.openai_api_key.get_secret_value() == "override-key"
