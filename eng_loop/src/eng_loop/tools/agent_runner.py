from __future__ import annotations

import json
import time
from typing import Any, Type

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from eng_loop.tools.json_parse import extract_json
from eng_loop.tools.progress import (
    log_model_invoke, log_model_done, log_stage_done, log_stage_fail,
)


class AgentResult:
    """Result from an agent execution."""
    def __init__(
        self,
        data: dict[str, Any],
        conversation: list[Any] | None = None,
        tool_calls_made: int = 0,
        iterations: int = 0,
        elapsed: float = 0.0,
        error: str | None = None,
    ):
        self.data = data
        self.conversation = conversation or []
        self.tool_calls_made = tool_calls_made
        self.iterations = iterations
        self.elapsed = elapsed
        self.error = error


def run_agent(
    model: ChatOpenAI,
    tools: list[Tool],
    prompt: str,
    stage_id: str,
    output_schema: Type[BaseModel] | None = None,
    max_iterations: int = 25,
    system_message: str = "",
) -> AgentResult:
    """Run an agentic loop: LLM calls tools until work is complete, then extracts structured output.

    Flow:
    1. Bind tools to model
    2. Loop: invoke → check for tool_calls → execute tools → append results
    3. When no more tool calls: extract structured output via final invocation
    """
    log_model_invoke(stage_id)
    t0 = time.monotonic()

    # Build conversation
    messages: list[Any] = []
    if system_message:
        messages.append(SystemMessage(content=system_message))

    # The prompt instructs the agent to use tools and then produce a final answer
    agent_prompt = _build_agent_prompt(prompt, tools)
    messages.append(HumanMessage(content=agent_prompt))

    # Bind tools to model
    model_with_tools = model.bind_tools(tools)

    tool_calls_total = 0

    for iteration in range(1, max_iterations + 1):
        try:
            response = model_with_tools.invoke(messages)
        except Exception as e:
            elapsed = time.monotonic() - t0
            log_model_done(stage_id, elapsed)
            log_stage_fail(stage_id, f"LLM error on iteration {iteration}: {e}")
            return AgentResult(
                data={},
                iterations=iteration,
                elapsed=elapsed,
                error=f"LLM error: {e}",
            )

        if isinstance(response, AIMessage):
            if response.tool_calls:
                # Execute each tool call
                for tc in response.tool_calls:
                    tool_name = tc["name"]
                    tool_args = tc.get("args", {})
                    tool_result = _execute_tool(tools, tool_name, tool_args)

                    messages.append(response)
                    messages.append(ToolMessage(
                        content=tool_result,
                        tool_call_id=tc["id"],
                    ))
                    tool_calls_total += 1

                # Compact messages if conversation is getting too long
                if len(messages) > 80:
                    messages = _compact_messages(messages)
            else:
                # No more tool calls — agent has its final answer
                elapsed = time.monotonic() - t0
                log_model_done(stage_id, elapsed)

                # Extract structured output from the final answer
                data = _extract_structured_output(
                    model, response.content, stage_id,
                    output_schema, messages,
                )
                log_stage_done(stage_id, f"agent completed in {iteration} iterations, {tool_calls_total} tool calls")

                return AgentResult(
                    data=data,
                    conversation=list(messages),
                    tool_calls_made=tool_calls_total,
                    iterations=iteration,
                    elapsed=elapsed,
                )
        else:
            # Unexpected response type
            elapsed = time.monotonic() - t0
            log_model_done(stage_id, elapsed)
            log_stage_fail(stage_id, f"unexpected response type: {type(response)}")
            return AgentResult(
                data={},
                iterations=iteration,
                elapsed=elapsed,
                error=f"unexpected response type: {type(response)}",
            )

    # Exceeded max iterations
    elapsed = time.monotonic() - t0
    log_model_done(stage_id, elapsed)
    log_stage_fail(stage_id, f"exceeded max_iterations ({max_iterations})")

    # Try to extract whatever we have
    last_ai = _last_ai_message(messages)
    data = _extract_from_text(last_ai.content if last_ai else "", output_schema)

    return AgentResult(
        data=data,
        conversation=list(messages),
        tool_calls_made=tool_calls_total,
        iterations=max_iterations,
        elapsed=elapsed,
        error=f"exceeded max_iterations ({max_iterations})",
    )


def _build_agent_prompt(prompt: str, tools: list[Tool]) -> str:
    """Wrap the stage prompt with agent instructions."""
    tool_names = ", ".join(f"`{t.name}`" for t in tools)

    return (
        f"{prompt}\n\n"
        f"## AVAILABLE TOOLS\n"
        f"You have access to these tools: {tool_names}.\n\n"
        f"## EXECUTION INSTRUCTIONS\n"
        f"1. Use the available tools to perform the actual work described above.\n"
        f"2. Read files before modifying them. Write files to create new code.\n"
        f"3. Run tests with bash to verify your work.\n"
        f"4. When all work is complete, provide your final answer as a JSON object.\n"
        f"5. Your final answer (no more tool calls) will be parsed as the stage result.\n\n"
        f"IMPORTANT: Stop calling tools and provide your final answer when the work is done.\n"
        f"Do NOT continue calling tools after completing the task."
    )


def _execute_tool(tools: list[Tool], name: str, args: dict[str, Any]) -> str:
    """Execute a tool by name with given arguments."""
    tool_map = {t.name: t for t in tools}
    tool = tool_map.get(name)
    if not tool:
        return f"Error: tool '{name}' not found. Available: {list(tool_map.keys())}"

    try:
        if len(args) == 1:
            # Single argument — pass the value directly
            value = list(args.values())[0]
            result = tool.func(value)
        else:
            # Multiple arguments — call with kwargs
            result = tool.func(**args)
        # Truncate long outputs
        if isinstance(result, str) and len(result) > 10000:
            return result[:10000] + "\n... [output truncated, 10000 char limit]"
        return str(result)
    except Exception as e:
        return f"Error executing {name}: {e}"


def _extract_structured_output(
    model: ChatOpenAI,
    answer_content: str,
    stage_id: str,
    output_schema: Type[BaseModel] | None,
    conversation: list[Any],
) -> dict[str, Any]:
    """Extract structured output from the agent's final answer.

    Strategy:
    1. Try to parse JSON directly from the answer
    2. If schema provided, try model.with_structured_output() on conversation
    3. Fall back to best-effort JSON extraction
    """
    # Strategy 1: Direct JSON parse of answer
    data = extract_json(answer_content)
    if data and isinstance(data, dict) and data:
        return data

    # Strategy 2: Structured output from conversation
    if output_schema:
        try:
            structured_model = model.with_structured_output(output_schema)
            # Add a system prompt to guide the final extraction
            extraction_messages = [
                SystemMessage(content="Extract the stage result as a JSON object from the conversation above. Return only the JSON, nothing else."),
            ] + conversation
            response = structured_model.invoke(extraction_messages)
            if hasattr(response, "model_dump"):
                return response.model_dump()
            return dict(response)
        except Exception:
            pass

    # Strategy 3: Best effort from answer text
    return _extract_from_text(answer_content, output_schema)


def _extract_from_text(
    text: str,
    output_schema: Type[BaseModel] | None,
) -> dict[str, Any]:
    """Last-resort JSON extraction from text."""
    data = extract_json(text)
    if data and isinstance(data, dict):
        return data
    return {"raw_output": text[:5000], "complete": True}


def _last_ai_message(messages: list[Any]) -> AIMessage | None:
    """Find the last AI message that is not followed by tool messages."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            return msg
    # Fallback: any AI message
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return msg
    return None


def _compact_messages(messages: list[Any]) -> list[Any]:
    """Compact a long conversation by summarizing old tool exchanges."""
    if len(messages) <= 40:
        return messages

    # Keep system + first human + last 30 messages
    system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
    first_human = next((m for m in messages if isinstance(m, HumanMessage)), None)

    kept = list(system_msgs)
    if first_human:
        kept.append(first_human)

    # Add a summary of what was done
    tool_calls = sum(
        1 for m in messages
        if isinstance(m, ToolMessage)
    )

    summary = HumanMessage(
        content=f"[Conversation summary: {tool_calls} tool calls were made. "
                f"Earlier tool interactions have been compacted for context window management.]"
    )
    kept.append(summary)

    # Keep last 25 messages
    kept.extend(messages[-25:])

    return kept


__all__ = ["run_agent", "AgentResult"]
