---
name: story-flow
id: story-flow
version: 1.0.0
type: skill
stage: post-loop
description: 'Bridges business value with technical validation. Produces narratives connecting real technical validations (E2E tests, data reconciliation, API contracts) to business impact. Evidence-or-zero. Runs POST-validation.'
---

# Story/Flow Skill

## Objective

Produce a structured narrative that connects technical validation outcomes to business value delivery. Every claim must be anchored to mechanical evidence — test results, E2E passes, data reconciliation — never inferred or assumed. This skill runs POST-validation, after verifier, persona-simulator, and E2E stages have produced their artifacts.

**Not essence:** Essence clarifies intent before work. Story/Flow proves value after validation. Essence asks "what do we need?" Story/Flow answers "what did we deliver, and how do we know?"

## Inputs

- Business goal or work item description
- Validation artifacts from completed stages:
  - Verifier reports (`{artifact-root}/validation-{slug}.md`)
  - E2E test results (Playwright JSON reports, trace files)
  - Persona-simulator output (SEQ scores, SUS grade, friction analysis)
  - Unit/integration test summaries (coverage, mutation scores)
  - API contract validation results (if applicable)
  - Data reconciliation reports (if applicable)
- Stage context: `state.stages.post`
- Project decisions: `state.work_item.decisions`

## Permitted Tools

- `read`: Read validation artifacts, test reports, source files
- `glob`: Find validation output files
- `grep`: Search test results for pass/fail patterns

## Protocol

### Step 1: Gather Evidence

Collect all validation artifacts produced by prior stages. For each artifact:

1. **Locate** the file (use `glob` to find `{artifact-root}/` outputs)
2. **Read** the structured output
3. **Extract** pass/fail status, confidence scores, coverage metrics
4. **Record** the file path and relevant line numbers as evidence anchors

| Artifact Type | Source Skill | Key Metrics |
|---|---|---|
| Spec-anchored check | verifier | AC coverage, mutation score, uncovered gaps |
| E2E results | e2e-playwright | Pass/fail count, screenshot diffs, trace links |
| Usability | persona-simulator | SEQ scores, SUS grade, friction score |
| Unit tests | tester-unit | Coverage %, mutation score, assertion quality |
| Integration tests | integration-tester | API contract compliance, component communication |
| Security | sec-review | OWASP findings, severity distribution |
| Performance | perf-check | Response time, bundle size, load targets |
| Accessibility | ux-auditor | WCAG violations, heuristic findings |

**Evidence-or-zero:** If an artifact does not exist, record it as `MISSING`. Do not assume validation was performed.

### Step 2: Map Business Goals to Evidence

Parse the business goal into testable claims. For each claim, find matching evidence:

1. **Decompose** the business goal into value assertions (e.g., "users can complete checkout" → "checkout flow works end-to-end")
2. **Match** each assertion to validation evidence
3. **Classify** the match:

| Status | Meaning |
|---|---|
| `VERIFIED` | Evidence exists, validation passed, traceable to file:line |
| `VERIFIED_WITH_WARNINGS` | Evidence exists, validation passed with non-blocking issues |
| `UNVERIFIED` | No validation evidence found (not the same as failed) |
| `FAILED` | Validation evidence exists but indicates failure |
| `PARTIAL` | Evidence exists but doesn't fully cover the claim |

**Mapping protocol:**
1. Read the business goal literally — extract each value proposition
2. For each proposition, search validation artifacts for matching evidence
3. If evidence spans multiple artifacts, chain the references
4. If no evidence exists, classify as `UNVERIFIED` and record as a gap

### Step 3: Build Narrative

Construct the narrative using the four required dimensions for each validated claim:

| Dimension | Question | Source |
|---|---|---|
| **What** | What was validated? (technical claim) | Validation artifacts |
| **How** | How was it validated? (method + evidence) | Test files, reports, file:line traces |
| **So what** | What does it mean for the user? (business value) | Business goal mapping |
| **Confidence** | How certain are we? (evidence quality) | Computed from evidence completeness |

**Confidence scoring:**

| Score | Basis |
|---|---|
| `0.9-1.0` | Multiple independent validations (E2E + unit + integration), all pass, high mutation score (>80%) |
| `0.7-0.89` | Primary validation passes (E2E or integration), supporting evidence exists |
| `0.5-0.69` | Single validation source passes, no corroborating evidence |
| `0.3-0.49` | Validation exists but has warnings or partial coverage |
| `0.0-0.29` | Validation failed or critically incomplete |

**Narrative structure:** For each business goal component, write one narrative block:

```markdown
### {Goal component}

**Claim:** {What the system delivers}
**Validated by:** {Method: E2E test, unit test, data reconciliation, etc.}
**Evidence:** `{file}:{line}` — {Specific assertion or outcome}
**Confidence:** {0.0-1.0}
**Business impact:** {What this means for the user or business}
```

### Step 4: Identify Gaps

Surface every business claim without validation evidence:

1. List each `UNVERIFIED` claim from Step 2
2. Assess risk of each gap:

| Risk | Assessment |
|---|---|
| `critical` | Core value proposition has no evidence |
| `high` | Major user-facing behavior unvalidated |
| `medium` | Secondary behavior unvalidated |
| `low` | Edge case or cosmetic behavior unvalidated |

3. For each gap, recommend the validation that should exist

### Step 5: Produce Output Artifact

Write the complete narrative to `{artifact-root}/story-{slug}.md` with embedded JSON data.

## Output Format

Write `{artifact-root}/story-{slug}.md`:

```markdown
# Story: {slug}

**Business goal:** {goal statement}
**Verdict:** PASS | PARTIAL | FAIL
**Overall confidence:** {0.0-1.0}
**Date:** {ISO date}
**Validations reviewed:** {count}

## Narrative

### {Goal component 1}

**Claim:** {What the system delivers}
**Validated by:** {Method}
**Evidence:** `{file}:{line}` — {Specific assertion}
**Confidence:** {score}
**Business impact:** {User/business value}

### {Goal component 2}

...

## Evidence Summary

| Validation | Status | Coverage | Key metric |
|---|---|---|---|
| E2E tests | PASS | {n}/{m} scenarios | {detail} |
| Spec-anchored check | PASS | {n}/{m} ACs | {mutation score} |
| Persona simulation | PASS | SUS {score}, friction {score} | {detail} |
| Unit tests | PASS | {coverage}% | {mutation score} |
| Security review | {PASS/FAIL} | {n} findings | {severity distribution} |

## Gaps

| Claim | Risk | Missing Validation |
|---|---|---|
| {unverified claim} | {critical/high/medium/low} | {recommended test} |

## Lessons
{Key observations about validation coverage}
```

Embedded JSON (at end of file, in fenced code block):

```json
{
  "business_goal": "{goal statement}",
  "verdict": "PASS|PARTIAL|FAIL",
  "overall_confidence": 0.85,
  "narrative_blocks": [
    {
      "claim": "Users can complete checkout end-to-end",
      "validated_by": "E2E test",
      "evidence": [
        {
          "file": "tests/e2e/checkout.spec.ts",
          "line": 42,
          "assertion": "expect(paymentConfirm).toBeVisible()",
          "status": "PASS"
        }
      ],
      "confidence": 0.92,
      "business_impact": "Revenue flow is operational — users can purchase without friction",
      "status": "VERIFIED"
    }
  ],
  "evidence_summary": {
    "e2e": { "status": "PASS", "coverage": "12/12 scenarios", "mutation_score": null },
    "verifier": { "status": "PASS", "ac_coverage": "8/8", "mutation_score": 0.87 },
    "persona": { "sus_score": 72.5, "friction_score": 2.1, "grade": "B" },
    "unit": { "coverage": 0.89, "mutation_score": 0.82 },
    "security": { "findings": 0, "severity": "none" }
  },
  "gaps": [
    {
      "claim": "Inventory reconciles after checkout",
      "risk": "critical",
      "missing_validation": "Data reconciliation test for inventory delta post-purchase"
    }
  ],
  "validations_reviewed": 5
}
```

## Mandatory Evidence Rules

- **Every claim traces to evidence** — no narrative block without at least one `file:line` reference
- **Evidence-or-zero** — if no evidence exists for a claim, mark `UNVERIFIED` and list as gap
- **Never fabricate evidence** — if a test file doesn't exist, don't reference it
- **Never infer pass from absence of failure** — explicit pass evidence required
- **Chain references for composite claims** — if a claim requires evidence from multiple artifacts, trace each
- **Confidence must be computed** — never assign confidence without referencing evidence quality
- **Gaps are not failures** — an `UNVERIFIED` gap is different from a `FAILED` validation; report both honestly

## Verdict Criteria

```
PASS: All core business claims VERIFIED, overall confidence >= 0.7, no critical gaps
PARTIAL: Core claims VERIFIED but with gaps (medium+ risk) or confidence < 0.7
FAIL: Any core claim FAILED or critical gaps exist
```

**Core claim** = a value proposition without which the business goal is unmet. Determined by decomposing the business goal in Step 2.

## Success Criteria

- All narrative blocks have `status` of `VERIFIED` or `VERIFIED_WITH_WARNINGS`
- `overall_confidence` >= 0.7
- No `critical` risk gaps
- Evidence summary includes all reviewed validations

## Failure Criteria

- Any core claim has `status` of `FAILED`
- `overall_confidence` < 0.5
- Critical gaps exist without mitigating evidence

## Blocking Criteria

- No validation artifacts exist (cannot produce narrative without evidence)
- Business goal is missing or incomprehensible

## Anti-Patterns

- **Never fabricate evidence** — referencing a test file that doesn't exist invalidates the entire narrative
- **Never skip evidence traces** — a claim without `file:line` is an opinion, not a story
- **Never confuse validation with verification** — E2E "passes" (validation) doesn't mean it tests the right thing (verification); note the distinction
- **Never assume coverage from test count** — 100 passing tests mean nothing if they don't cover the business claims
- **Never downgrade gaps** — if evidence is missing, the gap is `UNVERIFIED`, not "probably fine"
- **Never run before validation** — this skill requires completed validation artifacts; running before verifier/E2E produces hollow narratives
- **Never conflate confidence with opinion** — confidence must derive from evidence quality, not how sure you feel

## Rules

- **Always run POST-validation** — requires verifier, E2E, and persona-simulator artifacts
- **Always decompose the business goal** — monolithic claims produce monolithic gaps
- **Always compute confidence from evidence** — use the scoring table, never arbitrary values
- **Always separate gaps from failures** — `UNVERIFIED` != `FAILED`; report both accurately
- **Always write the embedded JSON** — machine-readable output enables downstream tooling
- **Always distill lessons** — coverage patterns and gap types become reusable knowledge
- **Bound to business goal scope** — don't validate beyond what the business goal requires
- **Cross-reference, don't duplicate** — link to verifier/E2E reports; don't re-state their findings verbatim
