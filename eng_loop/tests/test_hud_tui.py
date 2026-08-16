from __future__ import annotations

"""Tests for Textual HUD TUI components (MAGE HUD v2.0)."""


class TestNodePayload:
    def test_create_payload(self):
        from eng_loop.tools.execution_state import NodePayload

        payload = NodePayload("init")
        assert payload.node_name == "init"
        assert payload.input_prompt == ""
        assert payload.output_result == ""
        assert payload.output_data == {}

    def test_payload_storage(self):
        from eng_loop.tools.execution_state import NodePayload

        payload = NodePayload("impl.code")
        payload.input_prompt = "Write a function"
        payload.output_result = "Function written"
        payload.output_data = {"complete": True}
        assert payload.input_prompt == "Write a function"
        assert payload.output_result == "Function written"
        assert payload.output_data["complete"] is True


class TestExecutionStatePayload:
    def test_store_and_retrieve_payload(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init", "impl.code"])
        es.store_payload("init", input_prompt="Prompt here", output_result="Result here")
        payload = es.get_payload("init")
        assert payload is not None
        assert payload.input_prompt == "Prompt here"
        assert payload.output_result == "Result here"

    def test_store_output_only(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        es.store_payload("init", output_result="Output only")
        payload = es.get_payload("init")
        assert payload.input_prompt == ""
        assert payload.output_result == "Output only"

    def test_store_data_dict(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        es.store_payload("init", output_data={"key": "value"})
        payload = es.get_payload("init")
        assert payload.output_data == {"key": "value"}

    def test_get_nonexistent_payload(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        payload = es.get_payload("nonexistent")
        assert payload is None

    def test_payload_truncation(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        long_prompt = "x" * 10000
        es.store_payload("init", input_prompt=long_prompt)
        payload = es.get_payload("init")
        assert len(payload.input_prompt) == 8000

    def test_get_all_payloads(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init", "impl.code"])
        es.store_payload("init", input_prompt="P1")
        es.store_payload("impl.code", input_prompt="P2")
        all_payloads = es.get_all_payloads()
        assert len(all_payloads) == 2
        assert all_payloads["init"].input_prompt == "P1"
        assert all_payloads["impl.code"].input_prompt == "P2"


class TestExecutionStateControl:
    def test_initial_state_not_paused(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        assert not es.is_paused
        assert not es.step_mode

    def test_pause_and_resume(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        es.pause()
        assert es.is_paused
        es.resume()
        assert not es.is_paused

    def test_step_mode(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        es.step()
        assert not es.is_paused  # step() unpauses
        assert es.step_mode

    def test_pause_after_step(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        es.step()
        es.pause_after_step()
        assert es.is_paused
        assert es.step_mode

    def test_pause_after_step_ignored_when_not_step_mode(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        es.pause_after_step()
        assert not es.is_paused

    def test_snapshot_includes_pause_state(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        es.pause()
        snapshot = es.get_snapshot()
        assert snapshot.is_paused
        assert not snapshot.step_mode

    def test_snapshot_includes_step_mode(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        es.step()
        snapshot = es.get_snapshot()
        assert not snapshot.is_paused
        assert snapshot.step_mode


class TestExecutionStateIntervention:
    def test_add_and_get_intervention(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        es.add_intervention("init", "Fix the bug")
        assert es.has_intervention("init")
        text = es.get_intervention("init")
        assert text == "Fix the bug"
        assert not es.has_intervention("init")  # cleared after get

    def test_get_intervention_nonexistent(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        text = es.get_intervention("nonexistent")
        assert text is None

    def test_intervention_cleared_after_retrieval(self):
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        es.add_intervention("init", "Message 1")
        es.add_intervention("init", "Message 2")
        text = es.get_intervention("init")
        assert text == "Message 2"  # last one wins
        assert not es.has_intervention("init")


class TestEventNormalizerPayload:
    def test_store_input_prompt(self):
        from eng_loop.tools.event_normalizer import EventNormalizer
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        norm = EventNormalizer(es, ["init"])
        norm.store_input_prompt("init", "Test prompt")
        payload = es.get_payload("init")
        assert payload.input_prompt == "Test prompt"

    def test_store_output_result(self):
        from eng_loop.tools.event_normalizer import EventNormalizer
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        norm = EventNormalizer(es, ["init"])
        norm.store_output_result("init", "Test result", {"key": "val"})
        payload = es.get_payload("init")
        assert payload.output_result == "Test result"
        assert payload.output_data == {"key": "val"}

    def test_store_output_without_data(self):
        from eng_loop.tools.event_normalizer import EventNormalizer
        from eng_loop.tools.execution_state import ExecutionState

        es = ExecutionState("Q1", "Test", ["init"])
        norm = EventNormalizer(es, ["init"])
        norm.store_output_result("init", "Simple result")
        payload = es.get_payload("init")
        assert payload.output_result == "Simple result"
        assert payload.output_data == {}


class TestHUDTUIHelpers:
    def test_format_duration(self):
        from eng_loop.tools.hud_tui import _format_duration

        assert _format_duration(30) == "30s"
        assert _format_duration(0) == "0s"
        assert _format_duration(125) == "2m 5s"
        assert _format_duration(3661) == "1h 1m 1s"

    def test_draw_bar(self):
        from eng_loop.tools.hud_tui import _draw_bar

        bar = _draw_bar(10, 10, 10, "green")
        assert "10/10" in bar
        bar = _draw_bar(0, 10, 10, "red")
        assert "0/10" in bar

    def test_draw_casting_bar(self):
        from eng_loop.tools.hud_tui import _draw_casting_bar

        bar = _draw_casting_bar(5, 10, "blue")
        assert "\u2588" in bar  # filled block

    def test_wrap_text(self):
        from eng_loop.tools.hud_tui import _wrap_text

        lines = _wrap_text("a b c d e f g h i j", 10)
        assert len(lines) > 1

    def test_get_role(self):
        from eng_loop.tools.hud_tui import _get_role

        assert _get_role("init") == "MAGE"
        assert _get_role("impl.code") == "WARRIOR"
        assert _get_role("verify") == "INSPECTOR"

    def test_get_phase(self):
        from eng_loop.tools.hud_tui import _get_phase

        assert _get_phase("init") == "init"
        assert _get_phase("impl.code") == "impl"
        assert _get_phase("qa.security") == "qa"


class TestProgressStorePrompt:
    def test_store_stage_prompt_function_exists(self):
        from eng_loop.tools.progress import store_stage_prompt

        assert callable(store_stage_prompt)
