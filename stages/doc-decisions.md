---
name: doc-decisions
id: doc.decisions
version: 1.0.0
type: stage
description: 'Extract decisions from all stage artifacts, produce consolidated decision log in MADR format.'
---

# STAGE: Documentation — Decision Log
<!-- ID: doc.decisions -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the documentation specialist for decision extraction.
- DO NOT implement code, write tests, or modify artifacts.
- The moment you produce the decision log, your task is FINISHED.
- Implementing changes to existing artifacts is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.stages.review.done != true` → `status: blocked`, `blocking_condition: review stage not complete`. **EXIT.**
2. **Essence Gate:** Run Essence sidecar validation before proceeding. If Essence fails, adjust inputs and re-validate.
3. Proceed with the steps below.

# Documentation — Decision Log

**Skill:** Documentation specialist (self-constructed from MADR v4.0 + C4 Model)
**Runs when:** `state.stages.doc.decisions.done == false`
**Constraint:** `max_doc_decisions_attempts` (default: 2)

## Design

- Input: All stage artifacts + work item + consolidated architecture + blueprint.
- Template: `{reference-root}/decision-template.md` (MADR-based ADR format).
- Output: `{artifact-root}/decision-log-{slug}.md`
- Enforce `max_artifact_size_lines`. Store path in `state.artifacts.decision_log`.

### Extraction Sources

Extract decisions from:

| Source | What to Extract |
|--------|----------------|
| `arch.requirements` | Volumetry, scalability, security decisions |
| `arch.cloud` | Infrastructure, service selection, deployment model |
| `arch.solution` | Component design, data architecture, API patterns |
| `arch.review` | Cross-artifact consistency decisions, gap resolutions |
| `impl.design` | File structure, interface contracts, execution order |
| `impl.code` | Implementation patterns, error handling, library choices |
| `impl.review` | Review findings that became decisions |

### C4 Categorization

Categorize each decision by C4 Model level:

| Category | C4 Level | Decision Scope |
|----------|----------|----------------|
| `context` | C1 | System boundaries, external integrations, tech stack |
| `container` | C2 | Services, data stores, communication protocols |
| `component` | C3 | Module boundaries, API contracts, data models |
| `code` | C4 | Framework choices, libraries, coding patterns |
| `process` | Cross-cutting | CI/CD, testing, security, observability |

## Execute

1. **Scan artifacts** — read each source artifact identified in the extraction table.
2. **Extract decisions** — for each decision found:
   - Assign sequential ADR ID (ADR-001, ADR-002, ...).
   - Categorize by C4 level.
   - Record: decision, rationale, considered alternatives, consequences.
   - Tag with originating stage.
3. **Deduplicate** — if the same decision appears in multiple artifacts, merge into one ADR.
4. **Format** — apply MADR template from `{reference-root}/decision-template.md`.
5. **Index** — produce summary table with all ADRs.
6. **Write** — output to `{artifact-root}/decision-log-{slug}.md`.
7. **Validate** — run validation checks.

### Decision Log Structure

```markdown
# Decision Log

**Project:** {project name}
**Generated:** {date}
**Source:** Engineering Loop run {run_id}

## Index

| ID | Category | Title | Status | Stage |
|----|----------|-------|--------|-------|
| ADR-001 | context | ... | accepted | arch.cloud |
| ... | ... | ... | ... | ... |

---

## ADR-001: {Title}

{Full MADR record per decision-template.md}

---

## ADR-002: {Title}

{Full MADR record per decision-template.md}
```

## Validate

- **Completeness:** Every stage artifact with decisions has at least one ADR.
- **Format:** Each ADR follows MADR template (Context, Options, Outcome, Consequences).
- **Categorization:** Every ADR has a valid C4 category.
- **Traceability:** Each ADR references its originating stage.
- **No gaps:** All `[TBD]` and `[DECIDE LATER]` from architecture are resolved or documented as open questions.

### Validation Checklist

- [ ] All architecture decisions extracted
- [ ] All implementation decisions extracted
- [ ] Each ADR has: context, options, outcome, consequences
- [ ] Categories align with C4 levels
- [ ] Index table is complete and accurate
- [ ] No duplicate decisions
- [ ] All ADRs have sequential IDs

All pass → `done = true`. Gaps → `done = false` (loop re-runs).

## Expected Output

Your final response MUST strictly contain the decision log document in MADR format. End your generation immediately after the decision log block. Do not write "Next steps".
