from __future__ import annotations

from eng_loop.tools.agent_lifecycle import (
    AgentLifecycleManager,
    AgentState,
    DistilledState,
)


class TestAgentLifecycleBasics:
    def test_register_agent(self):
        mgr = AgentLifecycleManager({})
        agent_id = mgr.register_agent("impl.code")
        assert agent_id.startswith("impl.code-agent-")
        agent = mgr.get_current_agent("impl.code")
        assert agent is not None
        assert agent.state == AgentState.FRESH

    def test_record_iteration_continue(self):
        mgr = AgentLifecycleManager({"hardware": {"agent_context_limit": 100000}})
        mgr.register_agent("impl.code")
        action, stats = mgr.record_iteration("impl.code", 100, 50, "read", False)
        assert action == "continue"
        assert stats.input_tokens == 100
        assert stats.output_tokens == 50

    def test_record_iteration_distill_and_spawn(self):
        mgr = AgentLifecycleManager({"hardware": {"agent_context_limit": 1000, "max_parallel_agents": 3}})
        mgr.register_agent("impl.code")
        # Exhaust budget
        for _ in range(5):
            action, _ = mgr.record_iteration("impl.code", 300, 200, "read", False)
        assert action == "distill_and_spawn"

    def test_spawn_next_agent(self):
        mgr = AgentLifecycleManager({"hardware": {"agent_context_limit": 1000, "max_parallel_agents": 3}})
        mgr.register_agent("impl.code")
        distilled = DistilledState(
            stage_id="impl.code",
            predecessor_agent_id="impl.code-agent-0",
            work_completed=["Wrote fib.py"],
        )
        agent_id, agent = mgr.spawn_next_agent("impl.code", distilled)
        assert agent.state == AgentState.SPINNING_UP
        assert len(mgr._distilled["impl.code"]) == 1

    def test_complete_agent(self):
        mgr = AgentLifecycleManager({})
        mgr.register_agent("impl.code")
        stats = mgr.complete_agent("impl.code")
        assert stats.state == AgentState.COMPLETE
        assert stats.finished_at is not None


class TestParallelOrchestration:
    def test_parallel_limit_enforced(self):
        mgr = AgentLifecycleManager({"hardware": {"agent_context_limit": 100000, "max_parallel_agents": 2}})
        # Register + transition to RUNNING
        mgr.register_agent("stage-a")
        mgr._active_agents["stage-a"][-1].state = AgentState.RUNNING
        mgr.register_agent("stage-b")
        mgr._active_agents["stage-b"][-1].state = AgentState.RUNNING
        assert mgr.get_parallel_slots_available() == 0

        # Register a third (still 0 slots)
        mgr.register_agent("stage-c")
        mgr._active_agents["stage-c"][-1].state = AgentState.RUNNING
        assert mgr.get_parallel_slots_available() == 0

    def test_distillation_counted(self):
        mgr = AgentLifecycleManager({"hardware": {"agent_context_limit": 1000, "max_parallel_agents": 5}})
        mgr.register_agent("impl.code")
        distilled = DistilledState(
            stage_id="impl.code",
            predecessor_agent_id="impl.code-agent-0",
        )
        mgr.spawn_next_agent("impl.code", distilled)
        assert mgr._total_distillations == 1


class TestDistilledStateExtraction:
    def test_extract_work_completed(self):
        from langchain_core.messages import ToolMessage

        messages = [
            ToolMessage(content="Wrote src/fib.py (42 lines, 890 bytes)", tool_call_id="1"),
            ToolMessage(content="Edited src/main.py", tool_call_id="2"),
            ToolMessage(content="exit_code=0\nTests passed", tool_call_id="3"),
        ]
        completed = AgentLifecycleManager._extract_work_completed(messages)
        assert len(completed) == 3

    def test_extract_files_touched(self):
        # Test with empty messages — extraction should not crash
        files = AgentLifecycleManager._extract_files_touched([])
        assert files == []

    def test_extract_errors(self):
        from langchain_core.messages import ToolMessage

        messages = [
            ToolMessage(content="Error: file not found", tool_call_id="1"),
            ToolMessage(content="exit_code=1\nFailed", tool_call_id="2"),
        ]
        errors = AgentLifecycleManager._extract_errors(messages)
        assert len(errors) == 2

    def test_build_distilled_state(self):
        from langchain_core.messages import ToolMessage

        mgr = AgentLifecycleManager({"hardware": {"agent_context_limit": 1000}})
        mgr.register_agent("impl.code")
        messages = [
            ToolMessage(content="Wrote src/fib.py", tool_call_id="1"),
            ToolMessage(content="Error: timeout", tool_call_id="2"),
        ]
        distilled = mgr.build_distilled_state("impl.code", messages)
        assert distilled.stage_id == "impl.code"
        assert len(distilled.work_completed) >= 1
        assert len(distilled.errors_encountered) >= 1


class TestLifecycleConfig:
    def test_default_config(self):
        mgr = AgentLifecycleManager({})
        assert mgr.config.agent_context_limit == 66666
        assert mgr.config.max_parallel_agents == 3
        assert mgr.config.max_iterations_per_agent == 25

    def test_custom_config(self):
        mgr = AgentLifecycleManager(
            {
                "hardware": {
                    "agent_context_limit": 50000,
                    "max_parallel_agents": 5,
                },
                "agent": {"max_agent_iterations": 50},
            }
        )
        assert mgr.config.agent_context_limit == 50000
        assert mgr.config.max_parallel_agents == 5
        assert mgr.config.max_iterations_per_agent == 50


class TestObservability:
    def test_stage_summary(self):
        mgr = AgentLifecycleManager({"hardware": {"agent_context_limit": 100000}})
        mgr.register_agent("impl.code")
        mgr.record_iteration("impl.code", 100, 50, "write", True)
        summary = mgr.get_stage_summary("impl.code")
        assert summary["total_agents"] == 1
        assert summary["total_tool_calls"] == 1
        assert summary["productive_calls"] == 1

    def test_global_summary(self):
        mgr = AgentLifecycleManager({"hardware": {"max_parallel_agents": 3}})
        mgr.register_agent("stage-a")
        mgr._active_agents["stage-a"][-1].state = AgentState.RUNNING
        mgr.register_agent("stage-b")
        mgr._active_agents["stage-b"][-1].state = AgentState.RUNNING
        global_summary = mgr.get_global_summary()
        assert global_summary["stages_tracked"] == 2
        assert global_summary["active_agents"] == 2
