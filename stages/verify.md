---
name: verify
id: verify
version: 1.0.0
type: stage
description: 'Independent verification. Spec-anchored check + discrimination sensor. Author != Verifier. Fix→re-verify loop (max 3).'
---

# STAGE: Verify
<!-- ID: verify -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the independent Verifier.
- DO NOT implement fixes. Report findings only.
- The moment you produce the validation report, your task is FINISHED.
- Modifying code or tests is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.stages.impl.code.done != true` → `status: blocked`, `blocking_condition: implementation not complete`. **EXIT.**
2. Proceed with the steps below.

# Verify — Independent Verification

**Skill:** `verifier`
**Runs when:** `state.stages.verify.done == false`
**Prerequisite:** `state.stages.impl.code.done == true`
**Constraint:** `max_verify_attempts` (default: 3)
**Critical Rule:** Author != Verifier — fresh agent, no inherited mental model.

## Execute — Three-Layer Verification

### Layer 1: Spec-Anchored Outcome Check

**Context slice:** `{blueprint}` + `{spec ACs}` + `{source_code_paths}` + `{test_file_paths}`

For each acceptance criterion:
1. Locate the test that asserts this outcome
2. Verify the asserted value matches the spec-defined expected outcome
3. Trace to `file:line` evidence in both test and implementation
4. Flag spec-precision gaps (AC too vague to test)

| Status | Meaning |
|--------|---------|
| `TRACED` | AC → test → asserted value → file:line evidence |
| `SPEC_DEVIATION` | Implementation differs from spec (documented) |
| `SPEC_GAP` | AC too vague to verify |
| `UNCOVERED` | No test for this AC |

### Layer 2: Discrimination Sensor

**Context slice:** `{test_file_paths}` + `{source_code_paths}` + `{diff_range}`

Inject behavior-level faults in scratch state (never modify working tree):

| Mutation | Purpose |
|----------|---------|
| Remove a guard clause | Confirm test catches missing validation |
| Change an arithmetic operator | Confirm test asserts correct value |
| Short-circuit a conditional | Confirm test exercises the branch |
| Remove an error handler | Confirm test catches unhandled error |

For each mutation:
1. Apply mutation to scratch copy
2. Run affected tests
3. **Killed** — test fails → mutation detected (good)
4. **Survived** — test passes → test has no discriminative power (gap)

Surviving mutations become fix tasks.

### Layer 3: Coverage Audit

**Context slice:** `{blueprint}` + `{all_test_files}`

| Category | Check |
|----------|-------|
| AC Coverage | Every acceptance criterion has a corresponding test |
| Edge Cases | Every edge case from blueprint has a test |
| Error Paths | Every error condition has a test |
| Test Types | Unit + integration coverage as appropriate |

## Validate — Verdict

```
IF all ACs are TRACED or SPEC_DEVIATION
   AND all mutations are KILLED (or documented as non-actionable)
   AND coverage audit shows no UNCOVERED ACs:
    VERDICT: PASS
    state.stages.verify.done = true
ELSE:
    VERDICT: FAIL
    Produce ranked gap list
    state.stages.verify.done = false
    state.stages.impl.code.done = false  # Reset for fix iteration
```

### Write Validation Report

Output to `{artifact-root}/validation-{slug}.md`:

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
| ... | ... | ... |

## Discrimination Sensor

| Mutation | Result | Test |
|----------|--------|------|
| Remove guard X | KILLED | test file:line |
| ... | ... | ... |

## Coverage Audit

| Category | Status |
|----------|--------|
| AC Coverage | 100% |
| Edge Cases | 100% |
| Error Paths | 100% |

## Lessons
{Any surviving mutations or spec gaps distilled as lessons}
```

### Distill Lessons

For each failure (surviving mutant, spec gap, uncovered AC, SPEC_DEVIATION):
1. Extract: context, error, correction, prevention
2. Propose as candidate lesson
3. If same pattern appears in 2+ features → confirmed

## Fix → Re-Verify Loop

- On FAIL: gaps become fix tasks, `impl.code.done = false`
- Loop re-runs impl.code → verify
- Bounded to `max_verify_attempts` (default: 3)
- After 3 iterations still FAIL → escalate to user

## Expected Output

Your final response MUST strictly contain the validation report with verdict, per-AC evidence, sensor results, and gap list. End your generation immediately after the report. Do not write "Next steps".
