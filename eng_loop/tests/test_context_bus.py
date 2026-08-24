from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from eng_loop.context_bus import ContextBus, _normalize, synonyms_from_config

# PT ←→ EN map used to exercise the (now config-driven) synonym expansion.
# The bus default is an EMPTY map (4.3.9) — these tests pass it explicitly.
TEST_SYNONYMS = {
    "laranja": {"orange"},
    "orange": {"laranja"},
    "bolo": {"cake"},
    "cake": {"bolo"},
    "chocolate": {"chocolates"},
    "chocolates": {"chocolate"},
    "receita": {"recipe"},
    "recipe": {"receita"},
    "formato": {"format"},
    "format": {"formato"},
    "arquivo": {"file"},
    "file": {"arquivo"},
    "gluten": {"gluten"},
    "markdown": {"md"},
    "md": {"markdown"},
}

# ── Normalization ────────────────────────────────────────────────────


class TestNormalize:
    def test_basic_lowercase(self):
        assert _normalize("Hello World") == {"hello", "world"}

    def test_diacritics_stripped(self):
        assert _normalize("laranja sem glúten") == {"laranja", "sem", "gluten"}

    def test_empty(self):
        assert _normalize("") == set()

    def test_accents_portuguese(self):
        result = _normalize("café naïve résumé")
        assert "cafe" in result
        assert "naive" in result


# ── Core Operations ─────────────────────────────────────────────────


class TestCoreOperations:
    def test_init_empty(self):
        bus = ContextBus()
        assert bus.version == 0
        assert bus.entry_count == 0

    def test_append_increments_version(self):
        bus = ContextBus()
        v1 = bus.append("clarification", {"q": "tipo?", "a": "laranja"})
        assert v1 == 1
        assert bus.version == 1
        assert bus.entry_count == 1

    def test_multiple_appends(self):
        bus = ContextBus()
        bus.append("clarification", {"q": "q1"})
        bus.append("intent_refinement", {"before": "x", "after": "y"})
        assert bus.version == 2
        assert bus.entry_count == 2

    def test_unknown_entry_type_rejected(self):
        bus = ContextBus()
        with pytest.raises(ValueError, match="Unknown entry type"):
            bus.append("nonexistent_type", {"data": True})

    def test_max_entries_enforced(self):
        bus = ContextBus(max_entries=5)
        for i in range(10):
            bus.append("clarification", {"i": i})
        # After exceeding, oldest half is trimmed
        assert bus.entry_count <= 5

    def test_source_stage_recorded(self):
        bus = ContextBus()
        bus.append("clarification", {"q": "x"}, source_stage="init.refine")
        assert bus._entries[-1].source_stage == "init.refine"


# ── Semantic Resolution (is_resolved) ───────────────────────────────


class TestIsResolved:
    def test_exact_match(self):
        bus = ContextBus()
        bus.append("clarification", {"q": "tipo de bolo?", "a": "laranja"})
        assert bus.is_resolved("tipo de bolo") is True

    def test_answer_contains_finding(self):
        bus = ContextBus()
        bus.append("clarification", {"q": "formato?", "a": "Markdown .md"})
        assert bus.is_resolved("formato do arquivo") is True

    def test_cross_lingual_pt_en(self):
        """PT answer should resolve EN finding about same concept (with configured map)."""
        bus = ContextBus(synonyms=TEST_SYNONYMS)
        bus.append("clarification", {"q": "tipo?", "a": "bolo de laranja"})
        # EN rephrasing of the same concept
        assert bus.is_resolved("orange flavor cake type") is True

    def test_default_bus_has_no_synonym_expansion(self):
        """4.3.9 — synonyms are config-driven and empty by default."""
        bus = ContextBus()
        bus.append("clarification", {"q": "tipo?", "a": "bolo de laranja"})
        # Without a configured map there is no PT→EN expansion…
        assert bus.is_resolved("orange flavor cake type") is False
        # …but plain token overlap still resolves.
        assert bus.is_resolved("tipo de bolo") is True

    def test_synonyms_from_config(self):
        config = {"context_bus": {"synonyms": {"laranja": ["orange"], "orange": ["laranja"]}}}
        mapping = synonyms_from_config(config)
        assert mapping == {"laranja": {"orange"}, "orange": {"laranja"}}
        assert synonyms_from_config({}) == {}
        assert synonyms_from_config(None) == {}

    def test_diacritics_handled(self):
        bus = ContextBus()
        bus.append("clarification", {"q": "x", "a": "sem glúten"})
        assert bus.is_resolved("sem gluten") is True

    def test_unrelated_not_resolved(self):
        bus = ContextBus()
        bus.append("clarification", {"q": "x", "a": "chocolate"})
        assert bus.is_resolved("database migration strategy") is False

    def test_empty_finding_not_resolved(self):
        bus = ContextBus()
        bus.append("clarification", {"q": "x", "a": "something"})
        assert bus.is_resolved("") is False

    def test_empty_bus_not_resolved(self):
        bus = ContextBus()
        assert bus.is_resolved("anything at all") is False

    def test_keyword_overlap_cross_lingual(self):
        """Safety-net layer 3 catches partial overlap."""
        bus = ContextBus()
        bus.append("clarification", {"a": "receita bolo laranja sem gluten"})
        assert bus.is_resolved("receita de bolo de laranja") is True

    def test_threshold_tuning(self):
        """Stricter threshold should reject marginal matches."""
        bus = ContextBus()
        bus.append("clarification", {"a": "chocolate"})
        # Very strict threshold → no overlap with unrelated text
        assert bus.is_resolved("vanilla cake recipe", threshold=0.6) is False


# ── Snapshot / Restore ──────────────────────────────────────────────


class TestSnapshot:
    def test_roundtrip(self):
        bus = ContextBus()
        bus.append("clarification", {"q": "q1", "a": "a1"}, "init")
        bus.append("intent_refinement", {"before": "x", "after": "y"}, "refine")

        snap = bus.snapshot()
        restored = ContextBus.from_snapshot(snap)

        assert restored.version == bus.version
        assert restored.entry_count == bus.entry_count
        assert restored.is_resolved("q1") is True

    def test_empty_snapshot(self):
        bus = ContextBus()
        snap = bus.snapshot()
        restored = ContextBus.from_snapshot(snap)
        assert restored.version == 0
        assert restored.entry_count == 0


# ── Disk Flush & Load ───────────────────────────────────────────────


class TestDiskOperations:
    def test_flush_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = f"{td}/bus.jsonl"
            bus = ContextBus(flush_path=path)
            bus.append("clarification", {"q": "test"})
            bus.flush()
            assert Path(path).exists()
            lines = Path(path).read_text().strip().split("\n")
            assert len(lines) == 1
            obj = json.loads(lines[0])
            assert obj["t"] == "clarification"

    def test_load_from_disk(self):
        with tempfile.TemporaryDirectory() as td:
            path = f"{td}/bus.jsonl"
            # Write a known entry
            entry = {"v": 5, "t": "clarification", "c": {"q": "loaded"}, "s": "init", "ts": 0.0}
            Path(path).write_text(json.dumps(entry) + "\n")

            bus = ContextBus(flush_path=path, cross_session=True)
            assert bus.entry_count == 1
            assert bus.version == 5
            assert bus.is_resolved("loaded") is True

    def test_flush_clears_in_memory(self):
        with tempfile.TemporaryDirectory() as td:
            path = f"{td}/bus.jsonl"
            bus = ContextBus(flush_path=path)
            bus.append("clarification", {"q": "x"})
            assert bus.entry_count == 1
            bus.flush()
            assert bus.entry_count == 0

    def test_flush_failure_is_graceful(self):
        """OSError during flush should not crash (file blocks the parent dir on all OSes)."""
        with tempfile.TemporaryDirectory() as td:
            blocker = Path(td) / "blocker"
            blocker.write_text("file, not dir")
            bus = ContextBus(flush_path=f"{td}/blocker/bus.jsonl")
            bus.append("clarification", {"q": "x"})
            bus.flush()  # Should log warning, not raise
            assert bus.entry_count == 1

    def test_rotate_keeps_recent(self):
        with tempfile.TemporaryDirectory() as td:
            # Create 7 old files
            for i in range(7):
                Path(f"{td}/bus-old-{i}.jsonl").write_text("data")
            ContextBus.rotate(f"{td}/bus.jsonl", keep=3)
            remaining = list(Path(td).glob("bus-old-*.jsonl"))
            assert len(remaining) == 3


# ── Integration: Full Propagation Scenario ──────────────────────────


class TestFullPropagation:
    """Simulate the exact failing scenario from the user's log."""

    def test_bolo_receita_no_reasking(self):
        """Three clarifications answered → subsequent stages should NOT re-ask."""
        bus = ContextBus()

        # Round 1: user answers 3 questions
        bus.append("clarification", {"q": "tipo de bolo?", "a": "laranja"}, "init.refine")
        bus.append("clarification", {"q": "formato?", "a": "Markdown .md"}, "init.refine")
        bus.append("clarification", {"q": "restrição dietética?", "a": "sem glúten"}, "init.refine")

        # Now simulate essence gate re-checking in downstream stage
        assert bus.is_resolved("tipo de bolo") is True
        assert bus.is_resolved("formato do arquivo") is True
        assert bus.is_resolved("restrição dietética ou alergia") is True
        assert bus.is_resolved("qual tipo de bolo você quer") is True

    def test_intent_refinement_flows(self):
        """init.refine produces refined work item → impl.code sees it."""
        bus = ContextBus()
        bus.append(
            "intent_refinement",
            {"before": "crie receita bolo", "after": "crie receita de bolo de laranja sem glúten em MD"},
            "init.refine",
        )
        assert bus.is_resolved("receita bolo laranja") is True
