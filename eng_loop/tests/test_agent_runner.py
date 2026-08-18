from __future__ import annotations

import os
import tempfile
from pathlib import Path

"""Tests for agent runner: structured output extraction, message compaction, error handling."""


from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import Tool
from pydantic import BaseModel

from eng_loop.tools.agent_runner import (
    AgentResult,
    ToolResultCache,
    _build_agent_prompt,
    _compact_messages,
    _compact_skill,
    _execute_tool,
    _execute_tool_cached,
    _extract_best_effort_from_messages,
    _extract_from_text,
    _get_allowed_tools,
    _inject_compact_skill,
    _is_error_output,
    _last_ai_message,
    _summarize_error,
)
from eng_loop.tools.bash_tool import create_bash_tool
from eng_loop.tools.edit_tool import create_edit_tool
from eng_loop.tools.read_tool import create_read_tool
from eng_loop.tools.write_tool import create_write_tool

# ============================================================
# AGENT RESULT
# ============================================================


class TestAgentResult:
    def test_basic_creation(self):
        result = AgentResult(data={"key": "value"})
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_with_error(self):
        result = AgentResult(data={}, error="timeout")
        assert result.error == "timeout"

    def test_with_metadata(self):
        result = AgentResult(
            data={},
            tool_calls_made=10,
            iterations=5,
            elapsed=12.5,
        )
        assert result.tool_calls_made == 10
        assert result.iterations == 5
        assert result.elapsed == 12.5


# ============================================================
# BUILD AGENT PROMPT
# ============================================================


class TestBuildAgentPrompt:
    def test_includes_tools(self):
        tools = [Tool(name="read", description="r", func=lambda: "")]
        prompt = _build_agent_prompt("Do the task", tools, None)
        assert "`read`" in prompt

    def test_includes_instructions(self):
        tools = [Tool(name="read", description="r", func=lambda: "")]
        prompt = _build_agent_prompt("Do the task", tools, None)
        assert "## EXECUTION INSTRUCTIONS" in prompt

    def test_includes_json_template(self):
        class TestSchema(BaseModel):
            complete: bool
            summary: str

        tools = [Tool(name="read", description="r", func=lambda: "")]
        prompt = _build_agent_prompt("Do the task", tools, TestSchema)
        assert "## JSON OUTPUT TEMPLATE" in prompt
        assert '"complete"' in prompt


# ============================================================
# EXECUTE TOOL
# ============================================================


class TestExecuteTool:
    def test_execute_by_name(self):
        tools = [Tool(name="greet", description="d", func=lambda name: f"Hello {name}")]
        result = _execute_tool(tools, "greet", {"name": "World"})
        assert "Hello World" in result

    def test_execute_not_found(self):
        tools = []
        result = _execute_tool(tools, "unknown", {})
        assert "not found" in result

    def test_execute_truncates_long_output(self):
        tools = [Tool(name="long", description="d", func=lambda: "x" * 20000)]
        result = _execute_tool(tools, "long", {})
        assert "truncated" in result

    def test_execute_exception(self):
        tools = [Tool(name="fail", description="d", func=lambda: 1 / 0)]
        result = _execute_tool(tools, "fail", {})
        assert "Error" in result

    def test_execute_multi_arg_kwargs(self):
        """Multi-arg tools (write, edit) must work via kwargs dispatch."""
        tools = [Tool(name="write", description="d", func=lambda file_path, content: f"wrote {content} to {file_path}")]
        result = _execute_tool(tools, "write", {"file_path": "foo.txt", "content": "hello"})
        assert "wrote hello to foo.txt" in result

    def test_execute_three_arg_kwargs(self):
        """Three-arg tools (edit) must work via kwargs dispatch."""
        tools = [
            Tool(
                name="edit",
                description="d",
                func=lambda file_path, old_string, new_string: f"edited {old_string}->{new_string} in {file_path}",
            )
        ]
        result = _execute_tool(tools, "edit", {"file_path": "foo.py", "old_string": "bar", "new_string": "baz"})
        assert "edited bar->baz in foo.py" in result

    def test_execute_single_arg_uses_kwargs_not_positional(self):
        """Single-arg tools must receive args via kwargs, not positional dispatch.
        This ensures parameter names are respected — critical when the LLM provides
        args with specific key names that must match the tool function signature."""
        tools = [Tool(name="read", description="d", func=lambda file_path: f"read {file_path}")]
        result = _execute_tool(tools, "read", {"file_path": "foo.txt"})
        assert "read foo.txt" in result

    def test_execute_with_default_params(self):
        """Tools with default params should work when LLM omits optional args."""
        tools = [
            Tool(
                name="read",
                description="d",
                func=lambda file_path, offset=1, limit=500: f"read {file_path} at {offset}:{limit}",
            )
        ]
        # LLM provides only required arg
        result = _execute_tool(tools, "read", {"file_path": "foo.txt"})
        assert "read foo.txt at 1:500" in result
        # LLM provides all args
        result = _execute_tool(tools, "read", {"file_path": "foo.txt", "offset": 10, "limit": 5})
        assert "read foo.txt at 10:5" in result

    def test_execute_missing_required_arg_reports_error(self):
        """Missing required args should produce a clear error, not silent failure."""
        tools = [Tool(name="write", description="d", func=lambda file_path, content: "ok")]
        result = _execute_tool(tools, "write", {"file_path": "foo.txt"})
        assert "Error" in result
        assert "content" in result.lower() or "missing" in result.lower() or "required" in result.lower()

    def test_execute_wrong_arg_key_reports_error(self):
        """Wrong arg key names should produce a clear error, not silent wrong behavior."""
        tools = [Tool(name="read", description="d", func=lambda file_path: f"read {file_path}")]
        result = _execute_tool(tools, "read", {"path": "foo.txt"})
        assert "Error" in result

    def test_execute_no_args(self):
        """Tools with no required args should work with empty dict."""
        tools = [Tool(name="noop", description="d", func=lambda: "done")]
        result = _execute_tool(tools, "noop", {})
        assert "done" in result

    def test_execute_real_write_tool(self):
        """Verify real write tool works through _execute_tool with kwargs."""
        tool = create_write_tool()
        tools = [tool]
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                result = _execute_tool(tools, "write", {"file_path": "test.txt", "content": "hello world"})
            finally:
                os.chdir(old_cwd)
        assert "Wrote" in result
        assert "test.txt" in result

    def test_execute_real_edit_tool(self):
        """Verify real edit tool works through _execute_tool with kwargs."""
        tool = create_edit_tool()
        tools = [tool]
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                Path("test.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
                result = _execute_tool(
                    tools,
                    "edit",
                    {
                        "file_path": "test.py",
                        "old_string": "return 1",
                        "new_string": "return 42",
                    },
                )
            finally:
                os.chdir(old_cwd)
        assert "Edited" in result
        assert "test.py" in result

    def test_execute_real_read_tool(self):
        """Verify real read tool works through _execute_tool with kwargs."""
        tool = create_read_tool()
        tools = [tool]
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                Path("test.txt").write_text("line1\nline2\nline3", encoding="utf-8")
                result = _execute_tool(tools, "read", {"file_path": "test.txt"})
            finally:
                os.chdir(old_cwd)
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result

    def test_execute_real_bash_tool(self):
        """Verify real bash tool works through _execute_tool with kwargs."""
        tool = create_bash_tool(workdir=".")
        tools = [tool]
        result = _execute_tool(tools, "bash", {"command": "echo hello"})
        assert "exit_code=0" in result
        assert "hello" in result


# ============================================================
# EXECUTE TOOL CACHED
# ============================================================


class TestExecuteToolCached:
    def test_caches_result(self):
        call_count = [0]

        def counter():
            call_count[0] += 1
            return f"result {call_count[0]}"

        tools = [Tool(name="read", description="d", func=counter)]
        cache = ToolResultCache()
        r1 = _execute_tool_cached(tools, "read", {}, cache)
        r2 = _execute_tool_cached(tools, "read", {}, cache)
        assert r1 == r2
        assert call_count[0] == 1

    def test_invalidates_on_write(self):
        call_count = [0]

        def counter(file_path):
            call_count[0] += 1
            return f"result {call_count[0]} for {file_path}"

        def writer(file_path):
            return "ok"

        tools = [
            Tool(name="read", description="d", func=counter),
            Tool(name="write", description="d", func=writer),
        ]
        cache = ToolResultCache()
        _execute_tool_cached(tools, "read", {"file_path": "test.py"}, cache)
        _execute_tool_cached(tools, "write", {"file_path": "test.py"}, cache)
        _execute_tool_cached(tools, "read", {"file_path": "test.py"}, cache)
        assert call_count[0] == 2


# ============================================================
# COMPACT MESSAGES
# ============================================================


class TestCompactMessages:
    def test_no_compaction_under_limit(self):
        messages = [HumanMessage(content=f"msg{i}") for i in range(30)]
        compacted = _compact_messages(messages)
        assert len(compacted) == 30

    def test_compaction_over_limit(self):
        messages = [
            SystemMessage(content="system"),
            HumanMessage(content="first"),
        ] + [ToolMessage(content=f"tool{i}", tool_call_id=str(i)) for i in range(50)]
        compacted = _compact_messages(messages)
        assert len(compacted) < len(messages)
        assert any("summary" in m.content.lower() for m in compacted if isinstance(m, HumanMessage))


# ============================================================
# ERROR DETECTION
# ============================================================


class TestIsErrorOutput:
    def test_traceback(self):
        text = 'Traceback (most recent call last):\n  File "/app/main.py", line 10\n    x = 1/0\nError: something went wrong in the application code'
        assert _is_error_output(text) is True

    def test_test_failure(self):
        text = (
            "FAILED tests/test.py::test_something - AssertionError: expected value to match the pattern for validation"
        )
        assert _is_error_output(text) is True

    def test_short_text_not_error(self):
        assert _is_error_output("Hello world") is False

    def test_syntax_error(self):
        text = (
            "SyntaxError: invalid syntax in the Python source code that was provided to the interpreter for execution"
        )
        assert _is_error_output(text) is True


class TestSummarizeError:
    def test_json_error(self):
        text = '{"error": "Connection refused", "message": "ECONNREFUSED"}'
        summary = _summarize_error(text)
        assert "ERROR_SUMMARY" in summary

    def test_python_traceback(self):
        lines = []
        for i in range(20):
            lines.append(f'  File "/app/module{i}.py", line {i}, in func{i}\n    x = {i}/0')
        lines.append("ZeroDivisionError: division by zero")
        text = "Traceback (most recent call last):\n" + "\n".join(lines)
        summary = _summarize_error(text)
        assert len(summary) < len(text)


# ============================================================
# ALLOWED TOOLS
# ============================================================


class TestGetAllowedTools:
    def test_returns_all_tool_names(self):
        tools = [
            Tool(name="read", description="r", func=lambda: ""),
            Tool(name="write", description="w", func=lambda: ""),
        ]
        allowed = _get_allowed_tools("impl.code", tools)
        assert "read" in allowed
        assert "write" in allowed


# ============================================================
# LAST AI MESSAGE
# ============================================================


class TestLastAIMessage:
    def test_finds_clean_ai_message(self):
        messages = [
            AIMessage(content="call tool", tool_calls=[{"name": "read", "args": {}, "id": "1"}]),
            ToolMessage(content="result", tool_call_id="1"),
            AIMessage(content="Final answer: done"),
        ]
        last = _last_ai_message(messages)
        assert last is not None
        assert "Final answer" in last.content

    def test_fallback_to_any_ai_message(self):
        messages = [
            AIMessage(content="call tool", tool_calls=[{"name": "read", "args": {}, "id": "1"}]),
            ToolMessage(content="result", tool_call_id="1"),
        ]
        last = _last_ai_message(messages)
        assert last is not None
        assert "call tool" in last.content

    def test_no_ai_message(self):
        messages = [HumanMessage(content="hello")]
        last = _last_ai_message(messages)
        assert last is None


# ============================================================
# EXTRACT BEST EFFORT
# ============================================================


class TestExtractBestEffort:
    def test_from_clean_ai_message(self):
        messages = [
            AIMessage(content='{"complete": true, "summary": "done"}'),
        ]
        data = _extract_best_effort_from_messages(messages, None, "test")
        assert data.get("complete") is True

    def test_from_ai_with_tool_calls(self):
        messages = [
            AIMessage(
                content='{"complete": true, "summary": "done"}',
                tool_calls=[{"name": "read", "args": {}, "id": "1"}],
            ),
        ]
        data = _extract_best_effort_from_messages(messages, None, "test")
        assert data.get("complete") is True

    def test_fallback_raw_output(self):
        messages = [
            AIMessage(content="Just some text without JSON"),
        ]
        data = _extract_best_effort_from_messages(messages, None, "test")
        assert "raw_output" in data

    def test_no_messages(self):
        data = _extract_best_effort_from_messages([], None, "test")
        assert data == {}


# ============================================================
# EXTRACT FROM TEXT
# ============================================================


class TestExtractFromText:
    def test_valid_json(self):
        data = _extract_from_text('{"key": "value"}', None)
        assert data["key"] == "value"

    def test_markdown_json(self):
        data = _extract_from_text('```json\n{"key": "value"}\n```', None)
        assert data["key"] == "value"

    def test_no_json_fallback(self):
        data = _extract_from_text("Just plain text", None)
        assert "raw_output" in data
        assert "complete" in data


# ============================================================
# COMPACT SKILL
# ============================================================


class TestCompactSkill:
    def test_empty_input(self):
        assert _compact_skill("") == ""
        assert _compact_skill("   ") == ""
        assert _compact_skill("\n\n") == ""

    def test_short_skill_passthrough(self):
        short = "---\nname: test-skill\nversion: 1.0.0\n---\n\n# Test Skill\n\n## Rules\n- Never skip\n"
        result = _compact_skill(short, max_lines=50)
        assert "name: test-skill" in result
        assert "Never skip" in result

    def test_preserves_frontmatter_metadata(self):
        skill = (
            "---\n"
            "name: verifier\n"
            "version: 2.0.0\n"
            "type: skill\n"
            "description: Independent verification\n"
            "stage: verify\n"
            "---\n\n"
            "# Verifier Skill\n"
        )
        result = _compact_skill(skill, max_lines=50)
        assert "name: verifier" in result
        assert "version: 2.0.0" in result
        assert "type: skill" in result

    def test_preserves_section_headers(self):
        skill = (
            "## Purpose\nSome purpose text\n\n"
            "## Execution Protocol\nDo the thing\n\n"
            "## Rules\n- Rule one\n- Rule two\n\n"
            "## Anti-Patterns\n- Don't do this\n"
        )
        result = _compact_skill(skill, max_lines=50)
        assert "## Purpose" in result
        assert "## Execution Protocol" in result
        assert "## Rules" in result
        assert "## Anti-Patterns" in result

    def test_compacts_long_skill(self):
        lines = ["---\nname: long-skill\n---\n"]
        for i in range(100):
            lines.append(f"## Section {i}\n")
            lines.append(f"Some content for section {i}\n")
        skill = "".join(lines)
        result = _compact_skill(skill, max_lines=30)
        result_lines = result.split("\n")
        assert len(result_lines) <= 35  # 30 + compacted notice

    def test_skips_long_code_blocks(self):
        skill = (
            "## Protocol\n```\n" + "\n".join([f"line {i}" for i in range(20)]) + "\n```\n## Rules\n- Important rule\n"
        )
        result = _compact_skill(skill, max_lines=50)
        for i in range(20):
            assert f"line {i}" not in result

    def test_keeps_short_code_blocks(self):
        skill = "## Output\n```\nkey: value\nstatus: true\n```\n## Rules\n- Do this\n"
        result = _compact_skill(skill, max_lines=50)
        assert "key: value" in result

    def test_compacts_tables(self):
        skill = (
            "## Classification\n"
            "| Level | Criteria |\n"
            "|-------|----------|\n"
            + "".join([f"| Level {i} | Criteria {i} |\n" for i in range(15)])
            + "\n## Rules\n- Rule\n"
        )
        result = _compact_skill(skill, max_lines=50)
        assert "| Level | Criteria |" in result
        data_rows = [
            l
            for l in result.split("\n")
            if l.startswith("| Level") and "Criteria" not in l or ("Level" in l and "Criteria" not in l and "|" in l)
        ]
        assert len(data_rows) <= 2

    def test_adds_compaction_notice(self):
        lines = ["---\nname: big\n---\n"]
        for i in range(80):
            lines.append(f"## Section {i}\nContent {i}\n")
        skill = "".join(lines)
        result = _compact_skill(skill, max_lines=30)
        assert "compacted from" in result

    def test_preserves_bullet_points(self):
        skill = "## Rules\n- Never skip\n- Always verify\n- Bound to 3 rounds\n"
        result = _compact_skill(skill, max_lines=50)
        assert "Never skip" in result
        assert "Always verify" in result
        assert "Bound to 3 rounds" in result

    def test_preserves_numbered_lists(self):
        skill = "## Protocol\n1. First step\n2. Second step\n3. Third step\n"
        result = _compact_skill(skill, max_lines=50)
        assert "First step" in result
        assert "Second step" in result

    def test_filters_frontmatter_keys(self):
        skill = (
            "---\n"
            "name: test\n"
            "version: 1.0\n"
            "custom_key: should_be_filtered\n"
            "description: test skill\n"
            "---\n\n"
            "## Rules\n- Do this\n"
        )
        result = _compact_skill(skill, max_lines=50)
        assert "name: test" in result
        assert "custom_key" not in result
        assert "## Rules" in result


class TestInjectCompactSkill:
    def test_no_skill_section(self):
        prompt = "## WORK ITEM\nDo something\n\n## PROCEDURE\nSteps here\n"
        result = _inject_compact_skill(prompt)
        assert result == prompt

    def test_compacts_skill_in_prompt(self):
        skill_lines = ["## SKILL\n"]
        skill_lines.append("---\nname: test-skill\n---\n")
        for i in range(60):
            skill_lines.append(f"## Section {i}\nContent {i}\n")
        skill_block = "".join(skill_lines)
        prompt = f"## WORK ITEM\nDo something\n\n{skill_block}\n\n## PROCEDURE\nSteps\n"
        result = _inject_compact_skill(prompt, max_skill_lines=30)
        assert "## SKILL" in result
        assert "name: test-skill" in result
        skill_section = result.split("## SKILL\n")[1].split("\n\n## ")[0]
        assert len(skill_section.split("\n")) <= 40

    def test_preserves_other_sections(self):
        prompt = (
            "## WORK ITEM\nDo something\n\n"
            "## SKILL\n---\nname: test\n---\nLong skill content here with many lines.\n"
            + "\n".join([f"  - Item {i}" for i in range(100)])
            + "\n\n## PROCEDURE\nStep 1\nStep 2\n\n"
            "## DECISIONS\nDecision A\n"
        )
        result = _inject_compact_skill(prompt, max_skill_lines=20)
        assert "## WORK ITEM" in result
        assert "## SKILL" in result
        assert "## PROCEDURE" in result
        assert "Step 1" in result
        assert "## DECISIONS" in result
