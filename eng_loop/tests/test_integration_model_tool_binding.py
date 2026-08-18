from __future__ import annotations

"""Integration tests: model creation + tool binding + agent loop.

Validates the full chain:
  config → model → tools → model.bind_tools() → agent loop → structured output
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import Tool
from pydantic import BaseModel

from eng_loop.model import (
    create_code_model,
    create_model_from_config,
    create_reasoning_model,
)
from eng_loop.tools.agent_runner import (
    _execute_tool,
    _extract_best_effort_from_messages,
    _extract_from_text,
)
from eng_loop.tools.agent_tools import STAGE_TOOLS, get_tools_for_stage
from eng_loop.tools.edit_tool import create_edit_tool
from eng_loop.tools.glob_tool import create_glob_tool
from eng_loop.tools.read_tool import create_read_tool
from eng_loop.tools.write_tool import create_write_tool


class MockChatModel:
    """Minimal ChatOpenAI-compatible model for testing tool binding."""

    def __init__(self, responses: list[AIMessage] | None = None):
        self.responses = responses or []
        self.response_index = 0
        self.model_name = "mock-model"
        self.temperature = 0.0

    def bind_tools(self, tools: list[Tool]):
        return MockBoundModel(self.responses, self.response_index, tools)


class MockBoundModel:
    """Mock model that returns pre-configured responses for tool binding tests."""

    def __init__(self, responses: list[AIMessage], response_index: int, tools: list[Tool]):
        self.responses = responses
        self.response_index = response_index
        self.tools = tools

    def stream(self, messages: list):
        if self.response_index < len(self.responses):
            msg = self.responses[self.response_index]
            self.response_index += 1
            yield MagicMock(content=msg.content, tool_calls=msg.tool_calls, usage_metadata={})
        else:
            yield MagicMock(
                content='{"complete": true}',
                tool_calls=[],
                usage_metadata={},
            )

    def invoke(self, messages: list):
        if self.response_index < len(self.responses):
            msg = self.responses[self.response_index]
            self.response_index += 1
            return msg
        return AIMessage(content='{"complete": true}')


class TestModelToolBinding:
    """Verify model.bind_tools() integrates correctly with tool instances."""

    def test_model_binds_read_tool(self):
        """A model can bind a read tool and receive tool calls."""
        tool = create_read_tool()
        tools = [tool]

        tool_call_msg = AIMessage(
            content="",
            tool_calls=[{"name": "read", "args": {"file_path": "test.txt"}, "id": "tc1"}],
        )
        final_msg = AIMessage(content='{"complete": true}')

        mock_model = MockChatModel(responses=[tool_call_msg, final_msg])
        bound = mock_model.bind_tools(tools)

        assert len(bound.tools) == 1
        assert bound.tools[0].name == "read"

    def test_model_binds_multiple_tools(self):
        """A model can bind multiple tools."""
        tools = [create_read_tool(), create_write_tool(), create_edit_tool()]
        mock_model = MockChatModel()
        bound = mock_model.bind_tools(tools)

        names = {t.name for t in bound.tools}
        assert names == {"read", "write", "edit"}

    def test_model_binds_all_impl_code_tools(self):
        """All tools for impl.code stage can be bound."""
        tools = get_tools_for_stage("impl.code", {"project_root": "."})
        assert len(tools) == 6

        mock_model = MockChatModel()
        bound = mock_model.bind_tools(tools)
        names = {t.name for t in bound.tools}
        assert names == {"read", "write", "edit", "bash", "glob", "grep"}

    def test_model_binds_readonly_tools(self):
        """Read-only stages get correct tool subset."""
        tools = get_tools_for_stage("init", {"project_root": "."})
        names = {t.name for t in tools}
        assert "read" in names
        assert "glob" in names
        assert "write" not in names
        assert "edit" not in names
        assert "bash" not in names

    def test_tool_description_in_binding(self):
        """Bound tools retain their descriptions for LLM context."""
        tool = create_read_tool()
        mock_model = MockChatModel()
        bound = mock_model.bind_tools([tool])

        assert len(bound.tools[0].description) > 10

    def test_tool_binding_preserves_function(self):
        """Bound tools retain their callable function."""
        tool = create_read_tool()
        mock_model = MockChatModel()
        bound = mock_model.bind_tools([tool])

        assert callable(bound.tools[0].func)


class TestModelConfigIntegration:
    """Verify model creation respects config and stage overrides."""

    def test_model_from_config_with_overrides(self):
        """Per-stage model overrides are applied correctly."""
        config = {
            "model": {"base_url": "http://localhost:8000", "model": "default-model"},
            "model_overrides": {
                "impl.code": {"model": "code-specialist", "temperature": 0.1},
                "init": {"model": "reasoning-model", "temperature": 0.3},
            },
        }

        code_model = create_model_from_config(config, stage_id="impl.code")
        assert code_model.model_name == "code-specialist"
        assert code_model.temperature == 0.1

        init_model = create_model_from_config(config, stage_id="init")
        assert init_model.model_name == "reasoning-model"
        assert init_model.temperature == 0.3

        default_model = create_model_from_config(config, stage_id="verify")
        assert default_model.model_name == "default-model"

    def test_code_model_high_max_tokens(self):
        """Code model gets elevated max_tokens for large code generation."""
        model = create_code_model({})
        assert model.max_tokens == 200000
        assert model.temperature == 0.0

    def test_reasoning_model_temperature(self):
        """Reasoning model gets elevated temperature for creative tasks."""
        model = create_reasoning_model({})
        assert model.temperature == 0.3


class TestAgentLoopIntegration:
    """Full agent loop: model → tool call → execution → result extraction."""

    def test_agent_loop_single_tool_call(self):
        """Agent executes one tool call then returns structured output."""
        with tempfile.TemporaryDirectory() as tmp:
            test_file = Path(tmp) / "hello.txt"
            test_file.write_text("Hello, World!", encoding="utf-8")

            tools = [create_read_tool()]

            tool_call_msg = AIMessage(
                content="",
                tool_calls=[{"name": "read", "args": {"file_path": str(test_file)}, "id": "tc1"}],
            )
            final_msg = AIMessage(content='{"complete": true, "summary": "done"}')

            mock_model = MockChatModel(responses=[tool_call_msg, final_msg])
            bound = mock_model.bind_tools(tools)

            messages = [HumanMessage(content="Read the file")]

            # Simulate agent loop iteration 1: tool call
            chunks = list(bound.stream(messages))
            ai_msg = AIMessage(content=chunks[0].content, tool_calls=chunks[0].tool_calls)

            assert len(ai_msg.tool_calls) == 1
            tool_name = ai_msg.tool_calls[0]["name"]
            tool_args = ai_msg.tool_calls[0]["args"]

            # Execute tool
            tool_result = _execute_tool(tools, tool_name, tool_args)
            assert "Hello, World!" in tool_result

            # Add tool result to conversation
            messages.append(ai_msg)
            messages.append(ToolMessage(content=tool_result, tool_call_id="tc1"))

            # Simulate agent loop iteration 2: final answer
            chunks2 = list(bound.stream(messages))
            final_content = chunks2[0].content
            assert "complete" in final_content

    def test_agent_loop_multi_tool_calls(self):
        """Agent executes multiple sequential tool calls."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.txt").write_text("content A", encoding="utf-8")
            (Path(tmp) / "b.txt").write_text("content B", encoding="utf-8")

            tools = [create_read_tool(), create_glob_tool()]

            # Step 1: glob to find files
            glob_msg = AIMessage(
                content="",
                tool_calls=[{"name": "glob", "args": {"pattern": "*.txt", "path": tmp}, "id": "tc1"}],
            )
            # Step 2: read first file
            read_msg = AIMessage(
                content="",
                tool_calls=[{"name": "read", "args": {"file_path": str(Path(tmp) / "a.txt")}, "id": "tc2"}],
            )
            # Step 3: final answer
            final_msg = AIMessage(content='{"complete": true, "files_read": 1}')

            mock_model = MockChatModel(responses=[glob_msg, read_msg, final_msg])
            bound = mock_model.bind_tools(tools)

            messages = [HumanMessage(content="Find and read text files")]

            # Iteration 1: glob
            chunks = list(bound.stream(messages))
            ai_msg = AIMessage(content=chunks[0].content, tool_calls=chunks[0].tool_calls)
            tool_result = _execute_tool(tools, "glob", {"pattern": "*.txt", "path": tmp})
            assert "a.txt" in tool_result
            messages.append(ai_msg)
            messages.append(ToolMessage(content=tool_result, tool_call_id="tc1"))

            # Iteration 2: read
            chunks = list(bound.stream(messages))
            ai_msg = AIMessage(content=chunks[0].content, tool_calls=chunks[0].tool_calls)
            tool_result = _execute_tool(tools, "read", {"file_path": str(Path(tmp) / "a.txt")})
            assert "content A" in tool_result
            messages.append(ai_msg)
            messages.append(ToolMessage(content=tool_result, tool_call_id="tc2"))

            # Iteration 3: final answer
            chunks = list(bound.stream(messages))
            result = json.loads(chunks[0].content)
            assert result["complete"] is True

    def test_agent_loop_write_then_read_verify(self):
        """Agent writes a file then reads it back to verify."""
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                tools = [create_write_tool(), create_read_tool()]

                write_msg = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "write",
                            "args": {"file_path": "output.txt", "content": "Generated content"},
                            "id": "tc1",
                        }
                    ],
                )
                read_msg = AIMessage(
                    content="",
                    tool_calls=[{"name": "read", "args": {"file_path": "output.txt"}, "id": "tc2"}],
                )
                final_msg = AIMessage(content='{"complete": true, "verified": true}')

                mock_model = MockChatModel(responses=[write_msg, read_msg, final_msg])
                bound = mock_model.bind_tools(tools)

                messages = [HumanMessage(content="Write and verify a file")]

                # Write
                chunks = list(bound.stream(messages))
                ai_msg = AIMessage(content=chunks[0].content, tool_calls=chunks[0].tool_calls)
                tool_result = _execute_tool(tools, "write", {"file_path": "output.txt", "content": "Generated content"})
                assert "Wrote" in tool_result
                assert Path(tmp, "output.txt").exists()
                messages.append(ai_msg)
                messages.append(ToolMessage(content=tool_result, tool_call_id="tc1"))

                # Read back
                chunks = list(bound.stream(messages))
                ai_msg = AIMessage(content=chunks[0].content, tool_calls=chunks[0].tool_calls)
                tool_result = _execute_tool(tools, "read", {"file_path": "output.txt"})
                assert "Generated content" in tool_result
                messages.append(ai_msg)
                messages.append(ToolMessage(content=tool_result, tool_call_id="tc2"))

                # Final
                chunks = list(bound.stream(messages))
                result = json.loads(chunks[0].content)
                assert result["verified"] is True
            finally:
                os.chdir(old_cwd)

    def test_agent_loop_tool_error_handling(self):
        """Agent handles tool errors gracefully and continues."""
        tools = [create_read_tool()]

        # Request to read nonexistent file
        tool_call_msg = AIMessage(
            content="",
            tool_calls=[{"name": "read", "args": {"file_path": "/nonexistent.txt"}, "id": "tc1"}],
        )
        final_msg = AIMessage(content='{"complete": true, "error_handled": true}')

        mock_model = MockChatModel(responses=[tool_call_msg, final_msg])
        bound = mock_model.bind_tools(tools)

        messages = [HumanMessage(content="Read a file")]

        chunks = list(bound.stream(messages))
        ai_msg = AIMessage(content=chunks[0].content, tool_calls=chunks[0].tool_calls)
        tool_result = _execute_tool(tools, "read", {"file_path": "/nonexistent.txt"})

        assert "Error" in tool_result
        assert "not found" in tool_result

        messages.append(ai_msg)
        messages.append(ToolMessage(content=tool_result, tool_call_id="tc1"))

        chunks = list(bound.stream(messages))
        result = json.loads(chunks[0].content)
        assert result["error_handled"] is True

    def test_structured_output_extraction_with_schema(self):
        """Agent output can be validated against a Pydantic schema."""

        class VerifyOutput(BaseModel):
            verdict: str
            gaps: list[str]
            tests_passed: bool

        messages = [
            AIMessage(
                content=json.dumps(
                    {
                        "verdict": "PASS",
                        "gaps": [],
                        "tests_passed": True,
                    }
                )
            )
        ]

        data = _extract_best_effort_from_messages(messages, VerifyOutput, "verify")
        assert data["verdict"] == "PASS"
        assert data["tests_passed"] is True

    def test_structured_output_extraction_fallback(self):
        """When schema validation fails, JSON extraction still works."""
        messages = [AIMessage(content='{"complete": true, "extra_field": "unexpected"}')]

        class StrictSchema(BaseModel):
            complete: bool

        data = _extract_best_effort_from_messages(messages, StrictSchema, "test")
        assert data["complete"] is True

    def test_json_extraction_from_markdown_code_block(self):
        """JSON embedded in markdown code blocks is extracted correctly."""
        text = 'Here is the result:\n\n```json\n{"complete": true, "summary": "done"}\n```'
        data = _extract_from_text(text, None)
        assert data["complete"] is True
        assert data["summary"] == "done"

    def test_json_extraction_brace_matching(self):
        """JSON can be extracted using brace matching from prose."""
        text = 'The analysis is complete. Here are the findings: {"complete": true, "findings": []}'
        data = _extract_from_text(text, None)
        assert data["complete"] is True


class TestToolRegistryIntegration:
    """Verify tool registry maps stages to correct tools."""

    def test_all_stages_have_tools(self):
        """Every stage in STAGE_TOOLS has at least read tool."""
        from eng_loop.state import STAGE_ORDER

        for stage_id in STAGE_ORDER:
            assert stage_id in STAGE_TOOLS, f"Missing tools for {stage_id}"
            tools = STAGE_TOOLS[stage_id]
            assert "read" in tools, f"{stage_id} missing read tool"

    def test_impl_code_full_toolkit(self):
        """impl.code has all 6 core tools."""
        assert STAGE_TOOLS["impl.code"] == ["read", "write", "edit", "bash", "glob", "grep"]

    def test_verify_has_bash_for_test_execution(self):
        """verify stage has bash tool for running tests."""
        assert "bash" in STAGE_TOOLS["verify"]

    def test_deploy_has_bash(self):
        """deploy stage has bash for deployment commands."""
        assert "bash" in STAGE_TOOLS["deploy.prepare"]

    def test_init_readonly(self):
        """init stage is read-only (no write/edit/bash)."""
        tools = STAGE_TOOLS["init"]
        assert "write" not in tools
        assert "edit" not in tools
        assert "bash" not in tools

    def test_qa_security_and_performance_have_bash(self):
        """qa.security and qa.performance have bash for running analysis."""
        assert "bash" in STAGE_TOOLS["qa.security"]
        assert "bash" in STAGE_TOOLS["qa.performance"]
        # qa.api-contract is read-only (no bash needed for contract checks)
        assert "bash" not in STAGE_TOOLS["qa.api-contract"]

    def test_get_tools_returns_instantiated_tools(self):
        """get_tools_for_stage returns actual Tool instances."""
        tools = get_tools_for_stage("impl.code", {"project_root": "."})
        for tool in tools:
            assert isinstance(tool, Tool)
            assert callable(tool.func)
            assert len(tool.description) > 5
