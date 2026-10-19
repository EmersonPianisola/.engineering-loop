---
name: executor-calibration
id: ff-calibration
version: 1.0.0
type: reference
description: 'Beta calibration of the FF local executor — the per-block calibration record (.ff/calibration.jsonl), how to aggregate it across projects, and the rules that move the routing rubric and the tier size limits.'
---

# Executor Calibration (beta, FF v14)

FF v14 routes blocks to tiers (T0 mechanical, T1 guided, T2 high effort —
`global-skills/ff/routing.md`). The rubric and the size limits start as beta
values. They change only on evidence collected while FF delivers real projects.

## 1. The record — `.ff/calibration.jsonl`

One JSON object per line, one line per block, appended by the planner in Phase 4
(per project; `.ff/` is gitignored). Never rewrite earlier lines.

```json
{"session_id": "ff-20261020-001", "block_id": "block-003", "repo": "Estoque",
 "work_type": "feature", "exec_tier": "T1", "task_kind": "code-new",
 "model": "llamaLocal/Qwen3.8-27B-Fable-5-Coding-Distilled.Q6_K.gguf",
 "resolved_at_attempt": 2, "verdict": "approved",
 "lines_authored_local": 64, "planner_authored_lines": 38,
 "wall_seconds": 412, "files_in_scope": 2, "scenarios": 6,
 "failure_kind": "assertion", "notes": "missed the empty-input example on attempt 1"}
```

| Field | Values |
|-------|--------|
| `exec_tier` | `T0` · `T1` · `T2` |
| `task_kind` | `copy` · `edit` · `code-new` · `code-modify` · `test-fix` · `config` · `docs` |
| `resolved_at_attempt` | `1` · `2` · `3` · `"user"` (from `review/{block_id}.json`) |
| `wall_seconds` | sum of `ended_at - started_at` over the executor's attempts (shell timestamps) |
| `failure_kind` | `null` · `assertion` · `import` · `syntax` · `scope` (wrote outside scope or a protected file) · `spec` (spec unclear/contradictory) · `timeout` · `other` — the first failure seen |

Sources: `execution/{block_id}.json` (tier, model, attempts, lines) and
`review/{block_id}.json` (verdict, `resolved_at_attempt`, planner lines).

## 2. Session KPI

`state.json` `cost.local_authorship_ratio = lines_local / (lines_local + lines_planner)`.
It is 0 for an all-T0 session; the beta aims to raise it without raising the
planner corrections per block.

## 3. Aggregation (end of the beta)

The beta ends after **≥ 30 T1/T2 blocks** across projects, or when the user calls it.
The planner concatenates every project's `.ff/calibration.jsonl` and groups by
`(exec_tier, task_kind, model)`:

- `local_rate` = share of blocks with `resolved_at_attempt` in {1, 2}
- `first_try_rate` = share with `resolved_at_attempt` = 1
- `escalation_rate` = share with `"user"`
- median `wall_seconds`, median `lines_authored_local`, and the group's `local_authorship_ratio` = Σ `lines_authored_local` / Σ (`lines_authored_local` + `planner_authored_lines`)

## 4. Decision rules

| Group result (≥ 5 blocks) | Decision |
|---------------------------|----------|
| `local_rate` ≥ 80% and `escalation_rate` ≤ 5% | Keep the tier; raise its size limit by ~50% for that task kind |
| 50% ≤ `local_rate` < 80% | Keep the tier; tighten the spec template (more examples, smaller blocks) |
| `local_rate` < 50% or `escalation_rate` > 15% | Demote that task kind one tier (T2 → T1, T1 → T0) |
| `failure_kind = scope` in any block | Add an explicit rule to the work-order template; review the rubric criterion that missed it |
| Recurring `spec` failures | Planner lesson: the rubric criterion R1/R2 was judged too leniently |

Groups with fewer than 5 blocks are reported but do not change the rules.
Changes go through an FF session on the framework repo (`routing.md`, version bump).

## 5. Comparing models

One GPU, one model at a time: compare models across sessions, never within one.
A second local model is worth provisioning only if its group results beat the
current model on `local_rate` for the same `(exec_tier, task_kind)` at an
acceptable `wall_seconds`.
