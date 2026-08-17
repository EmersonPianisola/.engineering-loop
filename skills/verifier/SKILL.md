---
name: verifier
version: 2.0.0
type: skill
description: 'Independent verification. Spec-anchored outcome check + discrimination sensor + coverage audit + mutation feedback loop. Author != Verifier. Evidence-or-zero. Equivalent mutant filtering prevents false gaps.'
---

# Verifier Skill

Independent verification agent. Fresh agent — never the same agent that implemented. Four-layer verification with evidence-or-zero discipline and mutation feedback loop.

## Execution Protocol

### Layer 1: Spec-Anchored Outcome Check

For each acceptance criterion:

1. **Locate** the test that asserts this outcome
2. **Verify** the asserted value matches the spec-defined expected outcome
3. **Trace** to `file:line` evidence in both test and implementation
4. **Classify**:

| Status | Meaning |
|--------|---------|
| `TRACED` | AC → test → asserted value → file:line evidence |
| `SPEC_DEVIATION` | Implementation differs from spec (acceptable if documented) |
| `SPEC_GAP` | AC too vague to verify (non-blocking, document) |
| `UNCOVERED` | No test for this AC (blocking gap) |

**Evidence-or-zero:** If you cannot trace an AC to a test with a specific asserted value and file:line, it is UNCOVERED. Do not assume coverage.

### Layer 2: Discrimination Sensor

Inject behavior-level faults in scratch state (never modify working tree):

| Mutation | Purpose |
|----------|---------|
| Remove a guard clause | Confirm test catches missing validation |
| Change an arithmetic operator | Confirm test asserts correct value |
| Short-circuit a conditional | Confirm test exercises the branch |
| Remove an error handler | Confirm test catches unhandled error |
| Invert a boolean | Confirm test catches wrong logic |
| Remove a return value | Confirm test catches missing output |
| Flip boundary operator (`>` → `>=`) | Confirm test covers boundary values |
| Replace `throw` with silent return | Confirm test catches missing error propagation |

For each mutation:
1. Apply to scratch copy
2. Run affected tests
3. **Killed** — test fails → good
4. **Survived** — test passes → gap, becomes fix task

### Layer 3: Equivalent Mutant Filtering

Not all surviving mutants represent real gaps. Filter before reporting:

| Category | Example | Action |
|----------|---------|--------|
| **Equivalent** | `i <= n-1` → `i < n` (same behavior) | Exclude from report, mark `EQUIVALENT` |
| **Semantically identical** | `x + 0` → `x` (no behavioral change) | Exclude from report, mark `EQUIVALENT` |
| **Dead code mutation** | Mutation in unreachable branch | Exclude from report, mark `DEAD_CODE` |
| **Real gap** | Mutation changes observable behavior but test passes | Report as `SURVIVED`, generate fix task |

**Filtering protocol:**
1. For each surviving mutant, ask: "Does this mutation change the program's observable behavior?"
2. If no → mark `EQUIVALENT`, exclude from mutation score denominator
3. If yes → mark `SURVIVED`, include in report
4. When uncertain → mark `SURVIVED` (conservative: better to over-report than under-report)

**Mutation Score:** `killed / (killed + survived)`. Equivalent mutants are excluded from denominator.

### Layer 4: Mutation Feedback Loop

When surviving mutants are found (after filtering):

```
Iteration 1: Agent generates tests → Mutation tool runs → Surviving mutants identified
Iteration 2: Surviving mutants fed as prompt context → Agent strengthens/adds tests → Mutation tool runs
Iteration 3: Repeat with remaining survivors
Iteration 4: Final attempt — plateau expected here
```

**Key guidance:**
- The kill rate plateaus around 4 iterations (per MUTGEN research on HumanEval-Java)
- Beyond 4 iterations, diminishing returns dominate and equivalent mutants the filter missed start surfacing
- Feed surviving mutants as structured prompt: describe mutation, line number, suggested test direction
- Do NOT modify existing tests — only add new tests or strengthen assertions
- If mutation score > 80% after 4 iterations, stop and report remaining survivors as known gaps

### Layer 5: Coverage Audit

| Category | Check |
|----------|-------|
| AC Coverage | Every acceptance criterion has a corresponding test |
| Edge Cases | Every edge case from blueprint has a test |
| Error Paths | Every error condition has a test |
| Boundary Values | Every boundary condition (0, -1, max, empty, null) has a test |
| Discrimination | Mutation score >= threshold (default 80%) |

## Verdict

```
PASS: All ACs TRACED or SPEC_DEVIATION, all non-equivalent mutations KILLED, no UNCOVERED ACs, mutation score >= 80%
FAIL: Any UNCOVERED AC, surviving non-equivalent mutation, or missing coverage
```

## Output Format

Write `{artifact-root}/validation-{slug}.md`:

```markdown
# Validation Report

**Feature:** {slug}
**Verdict:** PASS | FAIL
**Iteration:** {n}
**Diff Range:** {commit_range}

## Spec-Anchored Check

| AC | Status | Evidence |
|----|--------|----------|
| AC-01 | TRACED | test file:line → impl file:line |

## Discrimination Sensor

| Mutation | Result | Test |
|----------|--------|------|
| Remove guard X | KILLED | test file:line |

## Equivalent Mutants Filtered

| Mutation | Classification | Rationale |
|----------|---------------|-----------|
| `i <= n-1` → `i < n` | EQUIVALENT | Same loop behavior for integer bounds |

## Mutation Score

| Metric | Value |
|--------|-------|
| Total mutants | 24 |
| Killed | 19 |
| Survived (non-equivalent) | 2 |
| Equivalent (filtered) | 3 |
| Mutation score | 90.5% |

## Coverage Audit

| Category | Status |
|----------|--------|
| AC Coverage | 100% |
| Edge Cases | 100% |
| Error Paths | 100% |
| Boundary Values | 100% |
| Discrimination | 90.5% |

## Lessons
{Surviving mutations or spec gaps distilled as lessons}
```

## Rules

- **Author != Verifier** — never verify your own work
- **Evidence-or-zero** — no trace = gap, never assume
- **Never modify working tree** — mutations in scratch state only
- **Never implement fixes** — report gaps, orchestrator handles fix→re-verify
- **Always filter equivalents** — raw mutation output is >50% noise without filtering
- **Bound feedback loop to 4 iterations** — plateau expected; don't chase diminishing returns
- **Always distill lessons** — surviving mutants and spec gaps become candidate lessons
- **Bound to 3 verification rounds** — after 3 FAILs, escalate to user
