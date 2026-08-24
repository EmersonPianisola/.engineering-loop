"""F4.3 — Small accumulated fixes.

Unit tests for the plan items that get a specific test (1, 3, 5) plus
regression coverage for the other 4.3 fixes:
  - stall_detector: same_tool_repeat with varying args is soft (scaffolding);
    safe-inspection matching is whole-token (no "catfish"→"cat")
  - agent_runner template builder: no PydanticUndefined leak for required fields
  - CommandHistoryBuffer: offset/limit in the normalized key (pagination ≠ repeat)
  - dynamic_validation: malformed payloads fail; default test command detected
  - _inject_compact_skill: capture extends through internal ## sections to ## PROCEDURE
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from eng_loop.schemas import FilesExistPayload, SymbolPayload, ValidationRule
from eng_loop.tools.agent_runner import (
    CommandHistoryBuffer,
    _build_agent_prompt,
    _inject_compact_skill,
)
from eng_loop.tools.dynamic_validation import _default_test_command, evaluate_validation_rules
from eng_loop.tools.stall_detector import StallDetector, _is_safe_inspection

# ── 4.3.1 — stall detector ───────────────────────────────────────────


class TestSameToolRepeatSeverity:
    def test_varying_args_is_soft(self):
        detector = StallDetector(same_tool_threshold=5, window_size=10)
        for i in range(5):
            detector.record("write", {"file_path": f"scaffold/{i}.py", "content": "x"})
        report = detector.check()
        assert report is not None
        assert report.stall_type == "same_tool_repeat"
        # Different args across the run = legitimate scaffolding, not a true stall
        assert report.severity == "soft"

    def test_identical_args_is_hard(self):
        # exact_threshold above the window (10) so exact_repeat cannot fire;
        # the window truncation is what keeps the identical run out of reach.
        detector = StallDetector(exact_threshold=11, same_tool_threshold=10, window_size=10)
        for _ in range(12):
            detector.record("bash", {"command": "npm test"})
        report = detector.check()
        assert report is not None
        assert report.stall_type == "same_tool_repeat"
        assert report.severity == "hard"


class TestSafeInspectionTokenMatching:
    def test_catfish_does_not_match_cat(self):
        assert _is_safe_inspection("bash", {"command": "catfish file.txt"}) is False

    def test_lsblk_does_not_match_ls(self):
        assert _is_safe_inspection("bash", {"command": "lsblk"}) is False

    def test_multi_token_safe_with_extra_args(self):
        assert _is_safe_inspection("bash", {"command": "git status --short"}) is True

    def test_plain_cat_still_safe(self):
        assert _is_safe_inspection("bash", {"command": "cat x.txt"}) is True


# ── 4.3.2 — template builder sentinel ────────────────────────────────


class TestTemplateBuilderDefaults:
    def test_required_fields_no_undefined_leak(self):
        class Out(BaseModel):
            verdict: str
            complete: bool
            count: int
            items: list[str]

        prompt = _build_agent_prompt("work item", [], output_schema=Out)
        assert "Undefined" not in prompt
        assert '"verdict": ""' in prompt
        assert '"complete": true' in prompt
        assert '"count": 0' in prompt
        assert '"items": []' in prompt

    def test_real_defaults_render(self):
        class Out(BaseModel):
            verdict: str = "PASS"
            notes: str | None = None

        prompt = _build_agent_prompt("work item", [], output_schema=Out)
        assert "Undefined" not in prompt
        assert '"verdict": PASS' in prompt
        assert '"notes": null' in prompt


# ── 4.3.5 — command history normalization ────────────────────────────


class TestCommandHistoryPagination:
    def test_same_file_different_offsets_different_keys(self):
        k1 = CommandHistoryBuffer.normalize("read", {"filePath": "a.py", "offset": 1, "limit": 100})
        k2 = CommandHistoryBuffer.normalize("read", {"filePath": "a.py", "offset": 101, "limit": 100})
        assert k1 != k2

    def test_same_page_same_key(self):
        k1 = CommandHistoryBuffer.normalize("read", {"filePath": "a.py", "offset": 1, "limit": 100})
        k2 = CommandHistoryBuffer.normalize("read", {"filePath": "a.py", "offset": 1, "limit": 100})
        assert k1 == k2


# ── 4.3.6 — compact skill anchoring ──────────────────────────────────


class TestInjectCompactSkillAnchoring:
    def test_capture_extends_through_internal_sections(self):
        bullets = "\n".join(f"- rule {i}" for i in range(60))
        prompt = f"## SKILL\nIntro.\n\n## Rules\n{bullets}\n\n## PROCEDURE\n1. do thing\n"
        out = _inject_compact_skill(prompt, max_skill_lines=50)
        assert out.count("## PROCEDURE") == 1
        # The whole skill (up to ## PROCEDURE) is inside the compaction budget.
        # With the old first-"\n\n##" anchoring only the intro was captured, so
        # all 60 bullets would survive verbatim in the output.
        assert out.count("- rule") < 60
        assert "1. do thing" in out

    def test_no_procedure_section_still_compacted(self):
        prompt = "## SKILL\nIntro.\n\nSome body text.\n"
        out = _inject_compact_skill(prompt, max_skill_lines=50)
        assert out.count("## SKILL") == 1
        assert "Some body text." in out


# ── 4.3.7 — dynamic validation ───────────────────────────────────────


class TestDynamicValidationMalformed:
    def test_files_exist_without_paths_fails(self, tmp_path: Path) -> None:
        rule = ValidationRule(type="files_exist", payload=FilesExistPayload(paths=()))
        ok, err = evaluate_validation_rules({}, (rule,), str(tmp_path), {})
        assert ok is False
        assert "malformed rule payload" in (err or "")

    def test_contains_symbol_with_empty_symbol_fails(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1", encoding="utf-8")
        rule = ValidationRule(type="contains_symbol", payload=SymbolPayload(symbol="", target_file="a.py"))
        ok, err = evaluate_validation_rules({}, (rule,), str(tmp_path), {})
        assert ok is False
        assert "malformed rule payload" in (err or "")

    def test_default_command_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        assert _default_test_command(tmp_path, "unit") == "pytest --tb=short -q"
        assert _default_test_command(tmp_path, "integration") == "pytest --tb=short -q -m integration"

    def test_default_command_package_json(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        assert _default_test_command(tmp_path, "unit") == "npm test"
        # python project wins when both markers exist
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        assert _default_test_command(tmp_path, "unit") == "pytest --tb=short -q"
