# FF Routing — Execution Tiers (v14)

The planner (Claude, cloud) decides, per block, how much the local executor
authors. Goal: the best cost/benefit in processing. Cloud tokens (the planner's
subscription quota) go to planning, specification and validation; the local model
writes everything it can write reliably.

**Rule of thumb:** the planner specifies and validates; it does not write what the
local model can write.

---

## 1. Tiers

| Tier | The executor (local) | The planner delivers | Done when |
|------|----------------------|----------------------|-----------|
| **T0 — mechanical** | Applies C/O/E steps exactly (copy, overwrite, verbatim edit) | Every byte: `plan/content/` files, oldString/newString | The block check passes |
| **T1 — guided** | Writes the implementation of one well-bounded change | Spec (exact paths, symbols, signatures, contracts, examples, "do not") + tests written first | The planner's tests and the block check pass |
| **T2 — high effort** | Same as T1 with more volume: several functions, up to 3 files, ordered steps | Same as T1 + an ordered step list inside the block | The planner's tests and the block check pass |

Planning, architecture, the judge, the critical review and the final gate are
**always** cloud work. No tier ever hands the executor a decision.

### Beta size limits (calibrated in the beta — see `references/executor-calibration.md`)

| Tier | Files written by the executor | Lines authored by the executor (approx.) |
|------|-------------------------------|------------------------------------------|
| T0 | ≤ 3 hand-edited (scripted rewrites do not count) | 0 |
| T1 | 1-2 | ≤ 150 |
| T2 | ≤ 3 | ≤ 400 |

Over the T2 limit: split the block.

---

## 2. Routing rubric (apply to every block)

A block is eligible for **T1/T2** only if ALL of these hold. Record the result in
`blocks.yaml` (`rubric`: the ids that hold; `exec_tier`).

| Id | Criterion | Why (evidence) |
|----|-----------|----------------|
| R1 | Every path the executor reads or writes is named exactly | The local model invents paths and symbols (> 60% in the loop-motor era) |
| R2 | Every symbol it must use or create is named, with its signature | Same |
| R3 | An executable test written by the planner defines "done", and it FAILS before the change (red) | Self-report is not evidence; tests are the contract |
| R4 | No architecture decision, no new dependency, no choice between libraries or patterns | Open judgement is where the local model fails |
| R5 | No long prose (docs > ~40 lines of new text) | Long prose authoring was unreliable |
| R6 | The files to read for context are listed (read list), and the block stays within the beta size limits | Context overflow and drift |
| R7 | The output is code or config checked by tests — never free-form JSON that another step must parse | Schema drift in the loop-motor era |

If any criterion fails: **T0** (the planner writes the content) — or, for ≤ 2
files with clear instructions, the planner does it inline without FF.
When in doubt, choose the lower tier. The beta data decides when to move up.

**T2 instead of T1** when the change needs more than one function or more than one
file, but every step can still be written as an ordered, testable instruction.

---

## 3. Tests for T1/T2 blocks

- The planner writes the tests (project tests, e.g. `tests/test_x.py`) into
  `plan/content/` and the work order installs them with **C steps first**.
- Installed tests are **protected**: listed in `blocks.yaml` `protected` and in the
  work order header. The executor never edits a protected file after its C step.
- The block check (`plan/checks/{block_id}.py`) runs the project tests (or calls the
  code directly) and also asserts that every protected file still equals its
  `plan/content/` source (line endings normalized).
- Planner dry-run for T1/T2: apply the C steps on a throwaway copy, run the check,
  and confirm it FAILS for the expected reason (missing symbol, failing assertion)
  — red before green. Record the failing scenario ids in `plan/dry-run.txt`. The
  planner does NOT write the implementation for the dry-run (that would spend the
  cloud tokens the tier is meant to save); the judge checks that the tests are
  satisfiable by the spec.

---

## 4. Work order templates

### T0
Unchanged from v13: header, rules, `### E<n>` / `### O<n>` / `### C<n>` steps, check,
`git add` / `git commit`. See SKILL.md Step 1.4.

### T1 / T2

```markdown
# Work Order — {block_id} — {title}

**Tier:** T1 (guided) · **Check:** `python .ff/traces/{sid}/plan/checks/{block_id}.py`
**Scope (committed):** `src/pkg/slug.py`, `tests/test_slug.py` — you write `src/pkg/slug.py`
**Protected (never edit after their C step):** `tests/test_slug.py`
**Read for context (do not edit):** `src/pkg/__init__.py`, `src/pkg/text.py`

## Rules (read first)
1. Write ONLY the files in scope. Never edit protected files after their C step, `plan/`, `.env`. Never push, never delete.
2. Do not add dependencies or imports outside the standard library and the files named here.
3. Do not change the given names or signatures. Do not create other files.
4. If the spec is unclear or contradicts the tests: do not guess — block (ff-exec "Block and end").

## Steps
### C1 — copy: `plan/content/tests/test_slug.py` → `tests/test_slug.py`

### I1 — implement: `src/pkg/slug.py`
**Goal:** one sentence.
**Signature:** `def slugify(text: str, max_len: int = 64) -> str`
**Contract:** inputs, output, errors (exact exception types and messages).
**Examples:** `slugify("Olá Mundo") == "ola-mundo"`; `slugify("") raises ValueError("empty")`.
**Do not:** use regex libraries other than `re`; touch `text.py`.

(T2 only) ### I2 … — ordered; each step names its file, symbols and the tests it makes pass.

## Check and commit
1. Run the check. Attempt 2 (self-repair) is allowed: read the failing lines, fix ONLY the files in scope, run it again.
2. `git add src/pkg/slug.py tests/test_slug.py`
3. `git commit -m "ff({sid}): {block_id}"`
```

---

## 5. Attempt ladder (every tier)

| Attempt | Actor | What happens |
|---------|-------|--------------|
| 1 | executor (local) | Applies the work order, runs the check |
| 2 | executor (local, self-repair) | Reads the check output and fixes within scope (T0: redo the steps that differ; T1/T2: fix the implementation, never protected files), runs the check again |
| 3 | planner (cloud) → executor | The planner diagnoses the failure (trace, saved diff, check output) and re-dispatches ONE corrected order: a `rework_instruction` (committed block) or a corrected work order (blocked block); it may downgrade the tier (e.g. T1 → T0 with the content written). The executor runs it once — no self-repair on attempt 3 |
| user | user | Still failing → the planner escalates to the user with the evidence and 2-3 options |

The cloud spends at most **one** correction round per block. A corrected work order
that keeps the block's scope and acceptance needs no fresh judge (planner dry-run +
new `handoff.json` hashes); a change of scope or acceptance does.

---

## 6. Cost levers (planner)

- **Judge cap:** at most 3 judge rounds per session. Before a 4th: simplify the plan
  (lower tiers, fewer blocks) or ask the user.
- **Judge clean view, minimal:** artifacts + this file + the Phase 1 gate of
  `manifest.md`; not the whole protocol.
- **Spec, not code:** a T1/T2 spec is a fraction of the code it replaces. Do not
  pre-write the implementation "to be safe" — use T0 instead if the block is not
  T1/T2-eligible.
- **KPI:** `local_authorship_ratio` = lines authored by the executor / (executor +
  planner-authored lines). Tracked per session in `state.json` `cost`.

---

## 7. Anti-patterns (from the loop-motor era and v13)

| Don't | Do |
|-------|----|
| Let the executor infer a path, symbol or import | Name it (R1, R2) |
| Ask the executor to choose a library, pattern or design | Decide in the plan; T0 if needed (R4) |
| Hand long prose or docs to T1/T2 | T0 with planner-written content (R5) |
| Make the executor emit JSON another step parses | Code + tests; the executor's only JSON is its trace (R7) |
| Put tests in the executor's writable scope | C-install them as protected files |
| "Improve", "refactor as needed", "clean up" | Exact goal, contract and examples |
| Trust the executor's timestamps or self-report | Shell timestamps; the planner re-runs every check |
| Pre-write T1 code in the plan "to be safe" | Choose T0 honestly or trust the tests |

---

## 8. Models

One local model per session (1 GPU, one model loaded at a time). `handoff.json`
records `executor_model` (the `model` of the project's `.opencode/opencode.json`);
the planner dispatches without `-m`, so opencode runs the configured model, and the
executor stops if that model differs from `executor_model`. Token usage per dispatch comes from the saved
`execution/{block_id}.events.jsonl`. When another local model is
provisioned, compare models through the calibration data before changing the default.
