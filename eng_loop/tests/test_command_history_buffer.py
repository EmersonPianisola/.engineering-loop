from __future__ import annotations

"""Tests for CommandHistoryBuffer — redundant inspection detection and steering."""

from eng_loop.tools.agent_runner import CommandHistoryBuffer


class TestCommandHistoryBuffer:
    def test_normalize_read(self):
        key = CommandHistoryBuffer.normalize("read", {"filePath": "/src/main.py"})
        assert key == "read:/src/main.py"

    def test_normalize_bash(self):
        key = CommandHistoryBuffer.normalize("bash", {"command": "ls -la"})
        assert key == "bash:ls -la"

    def test_normalize_glob(self):
        key = CommandHistoryBuffer.normalize("glob", {"pattern": "**/*.py"})
        assert key == "glob:**/*.py"

    def test_normalize_grep(self):
        key = CommandHistoryBuffer.normalize("grep", {"pattern": "foo", "path": "src"})
        assert key == "grep:foo|src"

    def test_normalize_grep_different_patterns(self):
        """Different grep patterns must produce different keys."""
        k1 = CommandHistoryBuffer.normalize("grep", {"pattern": "query-1", "path": "src"})
        k2 = CommandHistoryBuffer.normalize("grep", {"pattern": "query-2", "path": "src"})
        assert k1 != k2

    def test_normalize_grep_different_paths(self):
        """Same pattern, different paths must produce different keys."""
        k1 = CommandHistoryBuffer.normalize("grep", {"pattern": "foo", "path": "src"})
        k2 = CommandHistoryBuffer.normalize("grep", {"pattern": "foo", "path": "lib"})
        assert k1 != k2

    def test_normalize_case_insensitive(self):
        key1 = CommandHistoryBuffer.normalize("bash", {"command": "LS -LA"})
        key2 = CommandHistoryBuffer.normalize("bash", {"command": "ls -la"})
        assert key1 == key2

    def test_record_first_time(self):
        buf = CommandHistoryBuffer()
        count = buf.record("read", {"filePath": "/f.txt"})
        assert count == 0  # First execution, no repeat

    def test_record_second_time(self):
        buf = CommandHistoryBuffer()
        buf.record("read", {"filePath": "/f.txt"})
        count = buf.record("read", {"filePath": "/f.txt"})
        assert count == 1  # 1st repeat

    def test_record_third_time(self):
        buf = CommandHistoryBuffer()
        buf.record("read", {"filePath": "/f.txt"})
        buf.record("read", {"filePath": "/f.txt"})
        count = buf.record("read", {"filePath": "/f.txt"})
        assert count == 2  # 2nd repeat (threshold)

    def test_should_intercept_after_threshold(self):
        buf = CommandHistoryBuffer(repeat_threshold=2)
        buf.record("read", {"filePath": "/f.txt"})
        buf.record("read", {"filePath": "/f.txt"})
        assert buf.should_intercept("read", {"filePath": "/f.txt"})

    def test_should_not_intercept_below_threshold(self):
        buf = CommandHistoryBuffer(repeat_threshold=2, has_productive_tools=True)
        buf.record("read", {"filePath": "/f.txt"})
        assert not buf.should_intercept("read", {"filePath": "/f.txt"})

    def test_readonly_stage_allows_more_reads(self):
        """Read-only stages (init, design, arch) allow 5 reads of same file before intercepting."""
        buf = CommandHistoryBuffer(repeat_threshold=2, has_productive_tools=False)
        # 4 reads should NOT trigger intercept (threshold is 5 for read-only stages)
        for _ in range(4):
            buf.record("read", {"filePath": "/f.txt"})
        assert not buf.should_intercept("read", {"filePath": "/f.txt"})
        # 5th read should trigger
        buf.record("read", {"filePath": "/f.txt"})
        assert buf.should_intercept("read", {"filePath": "/f.txt"})

    def test_readonly_stage_still_intercepts_bash(self):
        """Read-only stages still intercept bash commands at normal threshold."""
        buf = CommandHistoryBuffer(repeat_threshold=2, has_productive_tools=False)
        buf.record("bash", {"command": "ls -la"})
        buf.record("bash", {"command": "ls -la"})
        assert buf.should_intercept("bash", {"command": "ls -la"})

    def test_should_not_intercept_non_safe_tool(self):
        buf = CommandHistoryBuffer()
        for _ in range(5):
            buf.record("write", {"filePath": "/f.txt"})
        assert not buf.should_intercept("write", {"filePath": "/f.txt"})

    def test_steering_message_contains_tool_name(self):
        buf = CommandHistoryBuffer()
        buf.record("bash", {"command": "ls -la"})
        buf.record("bash", {"command": "ls -la"})
        msg = buf.steering_message("bash", {"command": "ls -la"})
        assert "bash" in msg
        assert "ls -la" in msg

    def test_steering_message_contains_repeat_count(self):
        buf = CommandHistoryBuffer()
        buf.record("read", {"filePath": "/f.txt"})
        buf.record("read", {"filePath": "/f.txt"})
        msg = buf.steering_message("read", {"filePath": "/f.txt"})
        assert "2" in msg

    def test_reset_clears_history(self):
        buf = CommandHistoryBuffer(repeat_threshold=2)
        buf.record("read", {"filePath": "/f.txt"})
        buf.record("read", {"filePath": "/f.txt"})
        buf.reset()
        assert not buf.should_intercept("read", {"filePath": "/f.txt"})

    def test_different_files_not_intercepted(self):
        buf = CommandHistoryBuffer(repeat_threshold=2)
        buf.record("read", {"filePath": "/a.txt"})
        buf.record("read", {"filePath": "/a.txt"})
        assert not buf.should_intercept("read", {"filePath": "/b.txt"})

    def test_stats(self):
        buf = CommandHistoryBuffer()
        buf.record("read", {"filePath": "/a.txt"})
        buf.record("read", {"filePath": "/a.txt"})
        buf.record("read", {"filePath": "/b.txt"})
        stats = buf.get_stats()
        assert stats["total_unique"] == 2
        assert stats["repeats"] == 1

    def test_bash_command_intercept(self):
        buf = CommandHistoryBuffer(repeat_threshold=2)
        buf.record("bash", {"command": "ls -la"})
        buf.record("bash", {"command": "ls -la"})
        assert buf.should_intercept("bash", {"command": "ls -la"})

    def test_grep_pattern_intercept(self):
        buf = CommandHistoryBuffer(repeat_threshold=2)
        buf.record("grep", {"pattern": "foo", "path": "src"})
        buf.record("grep", {"pattern": "foo", "path": "src"})
        assert buf.should_intercept("grep", {"pattern": "foo", "path": "src"})

    def test_glob_pattern_intercept(self):
        buf = CommandHistoryBuffer(repeat_threshold=2)
        buf.record("glob", {"pattern": "**/*.py"})
        buf.record("glob", {"pattern": "**/*.py"})
        assert buf.should_intercept("glob", {"pattern": "**/*.py"})
