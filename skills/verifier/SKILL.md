---
name: verifier
version: 1.0.0
type: skill
description: 'Independent verification. Spec-anchored outcome check + discrimination sensor + coverage audit. Author != Verifier. Evidence-or-zero.'
---

# Verifier Skill

Independent verification agent. Fresh agent — never the same agent that implemented. Three-layer verification with evidence-or-zero discipline.

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

For each mutation:
1. Apply to scratch copy
2. Run affected tests
3. **Killed** — test fails → good
4. **Survived** — test passes → gap, becomes fix task

### Layer 3: Coverage Audit

| Category | Check |
|----------|-------|
| AC Coverage | Every acceptance criterion has a corresponding test |
| Edge Cases | Every edge case from blueprint has a test |
| Error Paths | Every error condition has a test |

## Verdict

```
PASS: All ACs TRACED or SPEC_DEVIATION, all mutations KILLED, no UNCOVERED ACs
FAIL: Any UNCOVERED AC, surviving mutation, or missing coverage
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

## Coverage Audit

| Category | Status |
|----------|--------|
| AC Coverage | 100% |
| Edge Cases | 100% |
| Error Paths | 100% |

## Lessons
{Surviving mutations or spec gaps distilled as lessons}
```

## Rules

- **Author != Verifier** — never verify your own work
- **Evidence-or-zero** — no trace = gap, never assume
- **Never modify working tree** — mutations in scratch state only
- **Never implement fixes** — report gaps, orchestrator handles fix→re-verify
- **Always distill lessons** — surviving mutants and spec gaps become candidate lessons
- **Bounded to 3 iterations** — after 3 FAILs, escalate to user
