from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

if TYPE_CHECKING:
    from collections.abc import Callable


logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    FRESH = "fresh"
    RUNNING = "running"
    SPINNING_UP = "spinning_up"  # new agent being bootstrapped
    DISTILLING = "distilling"   # current agent producing handoff
    COMPLETE = "complete"
    EXHAUSTED = "exhausted"      # hit token or iteration limit


class ExhaustReason(str, Enum):
    NONE = "none"
    TOKEN_BUDGET = "token_budget"
    ITERATION_LIMIT = "iteration_limit"
    STALL_DETECTED = "stall_detected"
    MANUAL = "manual"


@dataclass
class AgentStats:
    """Immutable snapshot of an agent's execution metrics."""

    agent_id: str
    stage_id: str
    started_at: float
    finished_at: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    productive_calls: int = 0  # write, edit, bash
    read_calls: int = 0
    iterations: int = 0
    state: AgentState = AgentState.FRESH
    error: str | None = None
    distillation_cost: int = 0  # tokens spent on distillation


@dataclass
class DistilledState:
    """Lossless handoff from one agent to the next.

    This replaces the old compaction approach. Instead of discarding
    context, we distill it into structured form and pass it to a fresh agent.
    """

    stage_id: str
    predecessor_agent_id: str
    work_completed: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    errors_encountered: list[str] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)
    remaining_work: list[str] = field(default_factory=list)
    tool_call_summary: str = ""
    total_tokens_consumed: int = 0
    predecessor_stats: AgentStats | None = None


@dataclass
class LifecycleConfig:
    """Configuration for agent lifecycle management.

    Sourced from config.yaml under `hardware` and `agent` keys.
    """

    # Per-agent context budget (tokens)
    agent_context_limit: int = 66666
    # Spawn threshold — when to trigger distill + spawn
    spawn_threshold_pct: float = 0.85
    # Maximum parallel agents (from config)
    max_parallel_agents: int = 3
    # Maximum iterations before forced distill
    max_iterations_per_agent: int = 25
    # Whether distillation is enabled
    distillation_enabled: bool = True
    # Distillation model (can be cheaper model for summarization)
    distillation_model: str | None = None


class AgentLifecycleManager:
    """Manages the lifecycle of agents within a stage.

    Responsibilities:
    1. Track token consumption per agent
    2. Detect exhaustion (token budget or iterations)
    3. Orchestrate distill → spawn transitions
    4. Enforce max_parallel_agents globally
    5. Provide observability via stats

    Design principle: agents start fresh. When an agent's budget is
    exhausted, we distill its state and spawn a new agent with full budget.
    No compaction of running context — that was the old, lossy approach.
    """

    def __init__(self, config: dict[str, Any]):
        hardware = config.get("hardware", {})
        agent_cfg = config.get("agent", {})

        self._cfg = LifecycleConfig(
            agent_context_limit=hardware.get("agent_context_limit", 66666),
            spawn_threshold_pct=0.85,
            max_parallel_agents=hardware.get("max_parallel_agents", 3),
            max_iterations_per_agent=agent_cfg.get("max_agent_iterations", 25),
            distillation_enabled=True,
        )

        # Per-stage agent tracking
        self._active_agents: dict[str, list[AgentStats]] = {}
        self._distilled: dict[str, list[DistilledState]] = {}
        self._total_distillations = 0
        self._global_spawn_semaphore = self._cfg.max_parallel_agents

    @property
    def config(self) -> LifecycleConfig:
        return self._cfg

    # ── Budget tracking ──────────────────────────────────────────

    def register_agent(self, stage_id: str) -> str:
        """Register a new agent for a stage. Returns agent_id."""
        agent_id = f"{stage_id}-agent-{len(self._active_agents.get(stage_id, []))}"
        self._active_agents.setdefault(stage_id, []).append(
            AgentStats(
                agent_id=agent_id,
                stage_id=stage_id,
                started_at=time.monotonic(),
                state=AgentState.FRESH,
            )
        )
        return agent_id

    def record_iteration(
        self,
        stage_id: str,
        input_tokens: int,
        output_tokens: int,
        tool_call_name: str = "",
        is_productive: bool = False,
    ) -> tuple[str, AgentStats]:
        """Record an iteration for the current agent.

        Returns (action, stats) where action is one of:
        - "continue" — agent has budget, keep running
        - "distill_and_spawn" — agent exhausted, distill and start new one
        - "abort" — hard limit hit, cannot continue
        """
        agents = self._active_agents.get(stage_id, [])
        if not agents:
            return "abort", AgentStats(
                agent_id="unknown",
                stage_id=stage_id,
                started_at=0,
                state=AgentState.EXHAUSTED,
                error="No agent registered for stage",
            )

        agent = agents[-1]  # current agent
        if agent.state in (AgentState.COMPLETE, AgentState.EXHAUSTED):
            return "abort", agent

        agent.input_tokens += input_tokens
        agent.output_tokens += output_tokens
        agent.iterations += 1

        if tool_call_name:
            agent.tool_calls += 1
            if is_productive:
                agent.productive_calls += 1
            else:
                agent.read_calls += 1

        # Check budget
        total_tokens = agent.input_tokens + agent.output_tokens
        budget_remaining = self._cfg.agent_context_limit - total_tokens
        budget_pct = total_tokens / max(self._cfg.agent_context_limit, 1)

        if budget_pct >= self._cfg.spawn_threshold_pct:
            agent.state = AgentState.DISTILLING
            return "distill_and_spawn", agent

        if agent.iterations >= self._cfg.max_iterations_per_agent:
            agent.state = AgentState.EXHAUSTED
            agent.error = f"iteration limit {self._cfg.max_iterations_per_agent} reached"
            return "distill_and_spawn", agent

        return "continue", agent

    def spawn_next_agent(self, stage_id: str, distilled: DistilledState) -> tuple[str, AgentStats]:
        """Spawn a new agent after distillation.

        Returns (agent_id, new_agent_stats).
        """
        if not self._can_spawn():
            logger.warning("Cannot spawn: max_parallel_agents=%d reached", self._cfg.max_parallel_agents)
            return "", AgentStats(
                agent_id="blocked",
                stage_id=stage_id,
                started_at=time.monotonic(),
                state=AgentState.EXHAUSTED,
                error="parallel agent limit reached",
            )

        self._distilled.setdefault(stage_id, []).append(distilled)
        self._total_distillations += 1

        agent_id = self.register_agent(stage_id)
        agent = self._active_agents[stage_id][-1]
        agent.state = AgentState.SPINNING_UP
        return agent_id, agent

    def complete_agent(self, stage_id: str) -> AgentStats | None:
        """Mark the current agent as complete. Returns its stats."""
        agents = self._active_agents.get(stage_id, [])
        if not agents:
            return None
        agent = agents[-1]
        agent.state = AgentState.COMPLETE
        agent.finished_at = time.monotonic()
        return agent

    def get_current_agent(self, stage_id: str) -> AgentStats | None:
        """Get the current (most recent) agent for a stage."""
        agents = self._active_agents.get(stage_id, [])
        if not agents:
            return None
        return agents[-1]

    # ── Parallel orchestration ───────────────────────────────────

    def _can_spawn(self) -> bool:
        """Check if we can spawn a new agent given parallel limits."""
        total_active = sum(
            1 for agents in self._active_agents.values()
            for a in agents
            if a.state in (AgentState.RUNNING, AgentState.SPINNING_UP)
        )
        return total_active < self._cfg.max_parallel_agents

    def get_parallel_slots_available(self) -> int:
        total_active = sum(
            1 for agents in self._active_agents.values()
            for a in agents
            if a.state in (AgentState.RUNNING, AgentState.SPINNING_UP)
        )
        return max(0, self._cfg.max_parallel_agents - total_active)

    # ── Distillation ─────────────────────────────────────────────

    def build_distilled_state(
        self,
        stage_id: str,
        messages: list[Any],
        tool_results: dict[str, str] | None = None,
    ) -> DistilledState:
        """Build a DistilledState from the current agent's context.

        This is lossless — it preserves all actionable information
        without truncating content. The next agent receives this as
        structured context, not as a summary.
        """
        agent = self.get_current_agent(stage_id)
        if not agent:
            return DistilledState(
                stage_id=stage_id,
                predecessor_agent_id="none",
            )

        # Extract actionable data from message history
        work_completed = self._extract_work_completed(messages)
        files_modified = self._extract_files_touched(messages, tool_results)
        errors = self._extract_errors(messages)
        findings = self._extract_findings(messages)

        return DistilledState(
            stage_id=stage_id,
            predecessor_agent_id=agent.agent_id,
            work_completed=work_completed,
            files_modified=files_modified,
            errors_encountered=errors,
            key_findings=findings,
            total_tokens_consumed=agent.input_tokens + agent.output_tokens,
            predecessor_stats=agent,
        )

    @staticmethod
    def _extract_work_completed(messages: list[Any]) -> list[str]:
        """Extract completed work items from tool call history."""
        completed: list[str] = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                content = str(getattr(msg, "content", ""))
                if "Wrote" in content or "Edited" in content or "exit_code=0" in content:
                    # Extract the actionable part
                    line = content.split("\n")[0]
                    if line and line not in completed:
                        completed.append(line[:200])
        return completed[-20:]  # keep last 20

    @staticmethod
    def _extract_files_touched(
        messages: list[Any],
        tool_results: dict[str, str] | None = None,
    ) -> list[str]:
        """Extract file paths that were read or modified."""
        files: list[str] = []
        for msg in messages:
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                for tc in msg.tool_calls:
                    args = tc.get("args", {})
                    fp = args.get("filePath", args.get("file_path", ""))
                    if fp and fp not in files:
                        files.append(str(fp))
        return files[-30:]

    @staticmethod
    def _extract_errors(messages: list[Any]) -> list[str]:
        """Extract error messages from tool results."""
        errors: list[str] = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                content = str(getattr(msg, "content", ""))
                if any(kw in content for kw in ("Error:", "FAILED", "exit_code=1", "exit_code=2")):
                    line = content.split("\n")[0]
                    if line and line not in errors:
                        errors.append(line[:200])
        return errors[-10:]

    @staticmethod
    def _extract_findings(messages: list[Any]) -> list[str]:
        """Extract key findings/observations."""
        findings: list[str] = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                content = str(getattr(msg, "content", ""))
                if "[System Notice]" in content or "CRITICAL" in content:
                    findings.append(content[:200])
        return findings[-10:]

    # ── Observability ────────────────────────────────────────────

    def get_stage_summary(self, stage_id: str) -> dict[str, Any]:
        agents = self._active_agents.get(stage_id, [])
        distilled = self._distilled.get(stage_id, [])
        return {
            "total_agents": len(agents),
            "distillations": len(distilled),
            "total_tokens": sum(a.input_tokens + a.output_tokens for a in agents),
            "total_tool_calls": sum(a.tool_calls for a in agents),
            "productive_calls": sum(a.productive_calls for a in agents),
            "current_agent": agents[-1].agent_id if agents else None,
            "current_state": agents[-1].state.value if agents else None,
        }

    def get_global_summary(self) -> dict[str, Any]:
        total_active = sum(
            1 for agents in self._active_agents.values()
            for a in agents
            if a.state in (AgentState.RUNNING, AgentState.SPINNING_UP)
        )
        return {
            "total_distillations": self._total_distillations,
            "active_agents": total_active,
            "parallel_slots_available": self.get_parallel_slots_available(),
            "stages_tracked": len(self._active_agents),
        }
