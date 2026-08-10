---
name: doc-decisions
id: doc.decisions
version: 2.0.0
type: stage
description: 'Consolidate AD-NNN decisions from STATE.md into formal MADR decision log. Decisions are already recorded continuously.'
---

# STAGE: Documentation — Decision Log Consolidation
<!-- ID: doc.decisions -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the documentation specialist for decision consolidation.
- DO NOT implement code, write tests, or modify artifacts.
- The moment you produce the consolidated decision log, your task is FINISHED.
- Discovering new decisions is a CRITICAL VIOLATION — decisions are already recorded as AD-NNN.

## Procedure

1. **Prerequisite Check:** If `state.stages.deploy.prepare.done != true` → `status: blocked`, `blocking_condition: deploy preparation not complete`. **EXIT.**
2. **Essence Gate:** Run Essence sidecar validation before proceeding. If Essence fails, adjust inputs and re-validate.
3. Proceed with the steps below.

# Documentation — Decision Log Consolidation

**Skill:** Documentation specialist (self-constructed from MADR v4.0 + C4 Model)
**Runs when:** `state.stages.doc.decisions.done == false`
**Constraint:** `max_doc_decisions_attempts` (default: 2)

## Design

- Input: `STATE.md ## Decisions` section (AD-NNN entries already recorded continuously), `artifacts/stage-results-{slug}.md`.
- Template: `{reference-root}/decision-template.md` (MADR-based ADR format).
- Output: `{artifact-root}/decision-log-{slug}.md`
- Enforce `max_artifact_size_lines`. Store path in `state.artifacts.decision_log`.

### Consolidation Process

Decisions have been recorded continuously as AD-NNN entries in `STATE.md` throughout all stages. This stage ONLY consolidates them into formal MADR format.

1. **Read** `STATE.md ## Decisions` section
2. **For each AD-NNN entry:**
   - Map AD-NNN → ADR-NNN (sequential renumbering for the formal log)
   - Expand compact format into full MADR template
   - Categorize by C4 Model level
   - Tag with originating stage
3. **Deduplicate** — if the same decision appears in multiple entries, merge
4. **Format** — apply MADR template from `{reference-root}/decision-template.md`
5. **Index** — produce summary table with all ADRs
6. **Write** — output to `{artifact-root}/decision-log-{slug}.md`

### C4 Categorization

| Category | C4 Level | Decision Scope |
|----------|----------|----------------|
| `context` | C1 | System boundaries, external integrations, tech stack |
| `container` | C2 | Services, data stores, communication protocols |
| `component` | C3 | Module boundaries, API contracts, data models |
| `code` | C4 | Framework choices, libraries, coding patterns |
| `process` | Cross-cutting | CI/CD, testing, security, observability |

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
```

## Validate

- **Completeness:** Every AD-NNN in STATE.md has a corresponding ADR
- **Format:** Each ADR follows MADR template (Context, Options, Outcome, Consequences)
- **Categorization:** Every ADR has a valid C4 category
- **Traceability:** Each ADR references its originating stage
- **No gaps:** All `[TBD]` and `[DECIDE LATER]` are resolved or documented as open questions

### Validation Checklist

- [ ] All AD-NNN entries from STATE.md are consolidated
- [ ] Each ADR has: context, options, outcome, consequences
- [ ] Categories align with C4 levels
- [ ] Index table is complete and accurate
- [ ] No duplicate decisions
- [ ] All ADRs have sequential IDs

All pass → `done = true`. Gaps → `done = false` (loop re-runs).

## State Update Contract

**MANDATORY.** Follow `{reference-root}/sub-agent-contract.md`. Before returning your response:

1. Write all artifacts to their designated paths in `{artifact-root}/`
2. Update `{loop-root}/state.json`:
   - `stages.doc.decisions.done = true` (or `false` on failure)
   - `stages.doc.decisions.attempts += 1`
   - `stages.doc.decisions.artifact_path = "artifacts/..."` (your output path)
   - `stages.doc.decisions.error = null` (or failure description)
3. Record AD-NNN decisions in `{loop-root}/STATE.md ## Decisions` (if applicable)
4. Your response MUST be a single JSON line:
   - Success: `{"stage":"doc.decisions","status":"done","artifact":"artifacts/..."}`
   - Failure: `{"stage":"doc.decisions","status":"failed","error":"reason"}`

DO NOT include artifact content, summaries, or "Next steps" in your response.
