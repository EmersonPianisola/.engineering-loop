from __future__ import annotations

"""Tests for Essence Gate question deduplication (PRD §14)."""

from eng_loop.tools.essence_gate import (
    _build_clarification_questions,
    _is_semantically_resolved,
)


class TestSemanticResolution:
    def test_empty_answers_not_resolved(self):
        finding = {"term": "cake", "severity": "high"}
        assert _is_semantically_resolved(finding, {}) is False

    def test_direct_containment(self):
        """If answer 'recipe' is contained in finding, it's resolved."""
        finding = {"assumption": "User wants a cooking recipe"}
        answers = {"q1": "recipe"}
        assert _is_semantically_resolved(finding, answers) is True

    def test_reverse_containment(self):
        """If finding term is contained in answer, it's resolved."""
        finding = {"term": "recipe"}
        answers = {"q1": "I want a vanilla recipe for cake"}
        assert _is_semantically_resolved(finding, answers) is True

    def test_token_overlap(self):
        """50%+ word overlap indicates resolution."""
        finding = {"assumption": "User wants chocolate cake recipe"}
        answers = {"q1": "chocolate cake"}
        assert _is_semantically_resolved(finding, answers) is True

    def test_no_overlap(self):
        finding = {"term": "database"}
        answers = {"q1": "vanilla cake"}
        assert _is_semantically_resolved(finding, answers) is False

    def test_empty_finding_text(self):
        finding = {"severity": "high"}  # no term/assumption/phrasing
        answers = {"q1": "something"}
        assert _is_semantically_resolved(finding, answers) is False

    def test_case_insensitive(self):
        finding = {"term": "RECIPE"}
        answers = {"q1": "recipe"}
        assert _is_semantically_resolved(finding, answers) is True


class TestBuildClarificationQuestions:
    def test_no_findings_returns_empty(self):
        result = _build_clarification_questions([], [])
        assert result == []

    def test_basic_questions(self):
        findings = [
            {
                "finding_id": "lens1_cake",
                "term": "cake",
                "severity": "high",
            }
        ]
        llm_questions = [
            {
                "id": "q1",
                "finding_id": "lens1_cake",
                "question": "What type of cake?",
                "options": ["vanilla", "chocolate"],
            }
        ]
        result = _build_clarification_questions(findings, llm_questions)
        assert len(result) == 1
        assert result[0]["finding_id"] == "lens1_cake"

    def test_resolved_finding_deduplicated(self):
        findings = [
            {"finding_id": "lens1_cake", "term": "cake", "severity": "high"},
            {"finding_id": "lens2_allergy", "assumption": "No allergies", "severity": "medium"},
        ]
        llm_questions = [
            {"id": "q1", "finding_id": "lens1_cake", "question": "What type?"},
            {"id": "q2", "finding_id": "lens2_allergy", "question": "Any allergies?"},
        ]
        result = _build_clarification_questions(
            findings,
            llm_questions,
            resolved_findings=["lens1_cake"],
        )
        assert len(result) == 1
        assert result[0]["finding_id"] == "lens2_allergy"

    def test_semantically_resolved_deduplicated(self):
        """If answer 'recipe' resolves a finding about 'cooking recipe', skip it."""
        findings = [
            {"finding_id": "lens1_cake", "term": "cake", "severity": "high"},
            {"finding_id": "lens2_recipe", "assumption": "User wants a cooking recipe", "severity": "medium"},
        ]
        llm_questions = [
            {"id": "q1", "finding_id": "lens1_cake", "question": "What type of cake?"},
            {"id": "q2", "finding_id": "lens2_recipe", "question": "Recipe or receipt?"},
        ]
        result = _build_clarification_questions(
            findings,
            llm_questions,
            resolved_findings=["lens1_cake"],
            resolved_answers={"q1": "recipe"},
        )
        # lens2_recipe should be deduplicated because "recipe" matches the assumption
        assert len(result) == 0

    def test_max_five_questions(self):
        findings = [
            {"finding_id": f"f{i}", "term": f"term{i}", "severity": "high"}
            for i in range(10)
        ]
        result = _build_clarification_questions(findings, [])
        assert len(result) == 5

    def test_auto_generated_questions(self):
        findings = [
            {"finding_id": "lens1_x", "term": "ambiguous", "severity": "high"}
        ]
        result = _build_clarification_questions(findings, [])
        assert len(result) == 1
        assert result[0]["finding_id"] == "lens1_x"
        assert "Please clarify" in result[0]["question"]

    def test_severity_preserved(self):
        findings = [
            {"finding_id": "f1", "term": "x", "severity": "high"}
        ]
        llm_questions = [
            {"id": "q1", "finding_id": "f1", "question": "What?"}
        ]
        result = _build_clarification_questions(findings, llm_questions)
        assert result[0]["severity"] == "high"
