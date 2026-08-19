from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any

from eng_loop.tools.execution_state import (
    AgentActionEvent,
    CommandHistoryEvent,
    ContextBudgetEvent,
    NodeCompletedEvent,
    NodeStartedEvent,
    NodeStatus,
    QuestCancelledEvent,
    QuestCompletedEvent,
    QuestFailedEvent,
    ResourceConsumedEvent,
    TokenStreamEvent,
    ToolCompletedEvent,
    ToolFailedEvent,
    ToolStartedEvent,
)

if TYPE_CHECKING:
    from eng_loop.tools.execution_state import ExecutionState


class EventNormalizer:
    """Translates LangGraph/runtime signals into domain events for ExecutionState.

    Maintains correlation between node entries and their execution IDs,
    tracks attempt numbers for retries, and generates unique execution IDs.
    """

    def __init__(
        self,
        execution_state: ExecutionState,
        all_node_names: list[str],
        max_attempts_map: dict[str, int] | None = None,
    ):
        self.execution_state = execution_state
        self.all_node_names = all_node_names
        self.max_attempts_map = max_attempts_map or {}
        self._executing: dict[str, str] = {}
        self._attempt_counter: dict[str, int] = {}

    def node_entered(self, stage_id: str) -> str:
        """Emit NodeStartedEvent when a node begins execution.

        Returns the execution ID for correlation.
        """
        execution_id = self._get_execution_id(stage_id)
        attempt = self._attempt_counter.get(stage_id, 0) + 1
        self._attempt_counter[stage_id] = attempt
        self._executing[stage_id] = execution_id

        self.execution_state.apply(
            NodeStartedEvent(
                node_name=stage_id,
                execution_id=execution_id,
                attempt_number=attempt,
                timestamp=time.monotonic(),
            )
        )
        return execution_id

    def node_completed(self, stage_id: str, status: NodeStatus) -> None:
        """Emit NodeCompletedEvent when a node finishes."""
        execution_id = self._get_current_execution_id(stage_id)
        if not execution_id:
            execution_id = self._get_execution_id(stage_id)

        self.execution_state.apply(
            NodeCompletedEvent(
                node_name=stage_id,
                execution_id=execution_id,
                status=status,
                timestamp=time.monotonic(),
            )
        )
        self._executing.pop(stage_id, None)

    def agent_action(
        self,
        stage_id: str,
        action_type: str,
        description: str,
    ) -> None:
        """Emit AgentActionEvent for agent behavior tracking."""
        execution_id = self._get_current_execution_id(stage_id)
        if not execution_id:
            return

        self.execution_state.apply(
            AgentActionEvent(
                node_name=stage_id,
                execution_id=execution_id,
                action_type=action_type,
                description=description,
                timestamp=time.monotonic(),
            )
        )

    def tool_started(
        self,
        stage_id: str,
        tool_name: str,
        args: dict[str, Any] | None = None,
    ) -> None:
        """Emit ToolStartedEvent."""
        execution_id = self._get_current_execution_id(stage_id)
        if not execution_id:
            return

        self.execution_state.apply(
            ToolStartedEvent(
                node_name=stage_id,
                execution_id=execution_id,
                tool_name=tool_name,
                args=args or {},
                timestamp=time.monotonic(),
            )
        )

    def tool_completed(
        self,
        stage_id: str,
        tool_name: str,
        result: str = "",
    ) -> None:
        """Emit ToolCompletedEvent."""
        execution_id = self._get_current_execution_id(stage_id)
        if not execution_id:
            return

        self.execution_state.apply(
            ToolCompletedEvent(
                node_name=stage_id,
                execution_id=execution_id,
                tool_name=tool_name,
                result=result,
                timestamp=time.monotonic(),
            )
        )

    def tool_failed(
        self,
        stage_id: str,
        tool_name: str,
        error: str = "",
    ) -> None:
        """Emit ToolFailedEvent."""
        execution_id = self._get_current_execution_id(stage_id)
        if not execution_id:
            return

        self.execution_state.apply(
            ToolFailedEvent(
                node_name=stage_id,
                execution_id=execution_id,
                tool_name=tool_name,
                error=error,
                timestamp=time.monotonic(),
            )
        )

    def tokens_consumed(
        self,
        stage_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
        gold: float = 0.0,
    ) -> None:
        """Emit ResourceConsumedEvent for token usage tracking."""
        execution_id = self._get_current_execution_id(stage_id)
        if not execution_id:
            return

        self.execution_state.apply(
            ResourceConsumedEvent(
                node_name=stage_id,
                execution_id=execution_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                gold=gold,
                timestamp=time.monotonic(),
            )
        )

    def token_streamed(
        self,
        stage_id: str,
        token: str,
        is_thought: bool = False,
    ) -> None:
        """Emit TokenStreamEvent for real-time HUD visibility."""
        execution_id = self._get_current_execution_id(stage_id)
        if not execution_id:
            return

        self.execution_state.apply(
            TokenStreamEvent(
                node_name=stage_id,
                execution_id=execution_id,
                token=token,
                is_thought=is_thought,
                timestamp=time.monotonic(),
            )
        )

    def quest_completed(self, reason: str = "") -> None:
        """Emit QuestCompletedEvent."""
        self.execution_state.apply(
            QuestCompletedEvent(
                reason=reason,
                timestamp=time.monotonic(),
            )
        )

    def quest_failed(self, reason: str = "") -> None:
        """Emit QuestFailedEvent."""
        self.execution_state.apply(
            QuestFailedEvent(
                reason=reason,
                timestamp=time.monotonic(),
            )
        )

    def quest_cancelled(self, reason: str = "") -> None:
        """Emit QuestCancelledEvent."""
        self.execution_state.apply(
            QuestCancelledEvent(
                reason=reason,
                timestamp=time.monotonic(),
            )
        )

    # ─── Payload Storage (Node Inspector X-Ray) ────────────────────

    def store_input_prompt(self, stage_id: str, prompt: str) -> None:
        """Store the input prompt for a stage (for Node Inspector)."""
        self.execution_state.store_payload(stage_id, input_prompt=prompt)

    def store_output_result(self, stage_id: str, result: str, data: dict[str, Any] | None = None) -> None:
        """Store the output result for a stage (for Node Inspector)."""
        self.execution_state.store_payload(stage_id, output_result=result, output_data=data)

    def command_history_update(
        self,
        stage_id: str,
        tool_name: str,
        target: str,
        count: int,
        is_intercepted: bool = False,
    ) -> None:
        """Emit CommandHistoryEvent for HUD command history panel."""
        execution_id = self._get_current_execution_id(stage_id)
        if not execution_id:
            return

        self.execution_state.apply(
            CommandHistoryEvent(
                node_name=stage_id,
                execution_id=execution_id,
                tool_name=tool_name,
                target=target,
                count=count,
                is_intercepted=is_intercepted,
                timestamp=time.monotonic(),
            )
        )

    # ─── CLI v2 Events ─────────────────────────────────────────────

    def planning_started(self, architect_node: str = "") -> None:
        """Emit PlanningStartedEvent."""
        from eng_loop.tools.execution_state import PlanningStartedEvent

        self.execution_state.apply(PlanningStartedEvent(architect_node=architect_node))

    def planning_completed(
        self,
        nodes: list[str],
        phases: dict[str, list[str]] | None = None,
        architect_node: str = "",
    ) -> None:
        """Emit PlanningCompletedEvent."""
        from eng_loop.tools.execution_state import PlanningCompletedEvent

        self.execution_state.apply(
            PlanningCompletedEvent(
                nodes=nodes,
                phases=phases or {},
                architect_node=architect_node,
            )
        )

    def gate_waiting(
        self,
        stage_id: str,
        questions: list[dict[str, Any]],
        reason: str = "",
    ) -> None:
        """Emit GateWaitingEvent."""
        from eng_loop.tools.execution_state import GateWaitingEvent

        self.execution_state.apply(
            GateWaitingEvent(
                node_name=stage_id,
                questions=questions,
                reason=reason,
            )
        )

    def gate_resolved(self, stage_id: str, clarifications_applied: int = 0) -> None:
        """Emit GateResolvedEvent."""
        from eng_loop.tools.execution_state import GateResolvedEvent

        self.execution_state.apply(
            GateResolvedEvent(
                node_name=stage_id,
                clarifications_applied=clarifications_applied,
            )
        )

    def checkpoint_saved(
        self,
        completed_nodes: list[str],
        active_node: str = "",
        state_version: int = 0,
    ) -> None:
        """Emit CheckpointEvent."""
        from eng_loop.tools.execution_state import CheckpointEvent

        self.execution_state.apply(
            CheckpointEvent(
                completed_nodes=completed_nodes,
                active_node=active_node,
                state_version=state_version,
            )
        )

    def diagnostic(
        self,
        severity: str,
        message: str,
        node_name: str = "",
    ) -> None:
        """Emit DiagnosticEvent."""
        from eng_loop.tools.execution_state import DiagnosticEvent

        self.execution_state.apply(
            DiagnosticEvent(
                severity=severity,
                message=message,
                node_name=node_name,
            )
        )

    def context_budget_record(
        self,
        stage_id: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        breakdown: dict[str, int] | None = None,
    ) -> None:
        """Record token usage in the context budget manager."""
        self.execution_state.apply(
            ContextBudgetEvent(
                stage_id=stage_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                breakdown=breakdown or {},
            )
        )

    # ─── Helpers ────────────────────────────────────────────────────

    def _get_execution_id(self, stage_id: str) -> str:
        """Generate a unique execution ID for a stage entry."""
        return f"{stage_id}-{uuid.uuid4().hex[:8]}"

    def _get_current_execution_id(self, stage_id: str) -> str | None:
        """Look up the active execution ID for a stage."""
        return self._executing.get(stage_id)


class HUDTelemetryCallback:
    """LangChain callback handler for HUD telemetry.

    Extracts token usage, tool calls, and other signals from
    LangChain/LangGraph callbacks and feeds them to the normalizer.
    """

    def __init__(self, normalizer: EventNormalizer):
        self.normalizer = normalizer
        self._current_node: str | None = None

    def _extract_node_name(self, tags: list[str]) -> str | None:
        """Extract node name from LangGraph tags."""
        for tag in tags:
            if tag.startswith("langgraph_node:"):
                return tag[len("langgraph_node:") :]
        return None

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: str,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Extract token usage from LLM response."""
        node_name = self._extract_node_name(tags or [])
        if not node_name:
            return

        try:
            llm_output = getattr(response, "llm_output", None) or {}
            token_usage = llm_output.get("token_usage", {})
            if token_usage:
                inp = token_usage.get("prompt_tokens", 0)
                out = token_usage.get("completion_tokens", 0)
                cached = token_usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                self.normalizer.tokens_consumed(node_name, inp, out, cached)
        except Exception:
            pass

    def on_tool_start(
        self,
        tool: Any,
        parsed_input: Any,
        *,
        run_id: str,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Record tool start."""
        node_name = self._extract_node_name(tags or [])
        if not node_name:
            return

        tool_name = getattr(tool, "name", str(tool))
        self.normalizer.tool_started(node_name, tool_name, parsed_input)

    def on_tool_end(
        self,
        response: Any,
        *,
        run_id: str,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Record tool completion."""
        node_name = self._extract_node_name(tags or [])
        if not node_name:
            return

        tool_name = kwargs.get("parent_run_id", "")
        self.normalizer.tool_completed(node_name, str(tool_name), str(response)[:500])

    def on_tool_error(
        self,
        error: Exception,
        *,
        run_id: str,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Record tool failure."""
        node_name = self._extract_node_name(tags or [])
        if not node_name:
            return

        self.normalizer.tool_failed(node_name, "unknown", str(error))

    def on_llm_new_token(
        self,
        token: str,
        *,
        chunk: Any = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Stream individual LLM tokens to HUD for real-time visibility."""
        node_name = self._extract_node_name(tags or [])
        if not node_name or not token:
            return

        self.normalizer.token_streamed(node_name, token)
