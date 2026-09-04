# FF Autonomy Harness

The autonomy harness governs when the FF protocol can act autonomously.
**Always active. Cannot be disabled.**

---

## Philosophy

Autonomy comes from **clarity of information**, not from the nature of the task.

A `rm -rf` with crystal-clear instructions still asks.
A production deploy with clear instructions, passing tests, and explicit scope can run.

---

## Hard Rules (Never Override)

These operations **ALWAYS require human confirmation**, regardless of context
or autonomy score. No exceptions.

### Destructive Operations
- `rm`, `rm -rf`, `rmdir /S`, `del /F` — any file deletion
- `git push --force`, `git reset --hard`, `git checkout --` — destructive git
- `truncate`, `shred`, `format` — any data destruction
- `DROP TABLE`, `DELETE FROM` (without WHERE) — database destruction
- `DROP DATABASE`, `mongodump --drop` — database destruction

### External Writes
- Writes to Firebase / Firestore / any external database
- Writes to remote APIs (POST, PUT, DELETE to external URLs)
- Writes to deployment targets (production, staging servers)
- `firebase deploy`, `npm publish`, `git push` to remote

### Configuration Changes
- Changes to `.env` or environment variable files
- Changes to CI/CD pipeline configs (`.github/`, `Jenkinsfile`)
- Changes to deployment configs (`Dockerfile`, `docker-compose`, `k8s/`)
- Changes to security configs (firewall rules, IAM policies)
- Changes to DNS, SSL certificates, domain records

### Boundary Violations
- Operations outside the project workspace root
- Operations on files matching `.gitignore` patterns (unless explicitly targeted)
- Operations on system directories (`/etc/`, `C:\Windows\`, `~/.ssh/`)

---

## Soft Rules (Score-Based)

Operations below the hard rules use the autonomy score:

| Operation | Default Autonomy | Override |
|-----------|-----------------|----------|
| Read any file | Always auto | — |
| Create new file (write) | Auto | — |
| Edit existing file | Semi-auto | Full auto if ≤ 20 lines changed |
| Run tests | Always auto | — |
| Run linter/formatter | Always auto | — |
| Install dependencies (`npm install`) | Semi-auto | Show what will be installed |
| Run dev server | Semi-auto | — |
| Run build | Always auto | — |
| Git commit (local) | Semi-auto | — |
| Git add / stage | Auto | — |

---

## Autonomy Score Calculation

Calculated per block, not per task:

```
clarity = available_info / needed_info              (0-1)
complexity = 1 - (dependency_count / task_count)    (0-1)
risk = weighted average of task risk levels          (0-1)

risk_levels:
  0.0  = read-only operations
  0.3  = create new files
  0.5  = edit existing files
  0.7  = run commands with side effects
  1.0  = destructive operations (hard rule — always blocked)

autonomy_score = (clarity * 0.4) + (complexity * 0.4) + ((1 - risk) * 0.2)
```

### Scoring Examples

| Scenario | Clarity | Complexity | Risk | Score | Mode |
|----------|---------|------------|------|-------|------|
| Read 5 files, summarize | 1.0 | 1.0 | 0.0 | 1.0 | FULL AUTO |
| Fix 3 test files, known pattern | 0.8 | 0.8 | 0.5 | 0.74 | SEMI AUTO |
| Rewrite auth module, unclear deps | 0.4 | 0.3 | 0.5 | 0.42 | MANUAL |
| Docs update from spec | 0.9 | 0.9 | 0.3 | 0.86 | FULL AUTO |

### Mode Behavior

| Score | Mode | Behavior |
|-------|------|----------|
| ≥ 0.8 | FULL AUTO | Execute blocks without asking. Report results after each block. |
| 0.5-0.7 | SEMI AUTO | Show block plan → wait for "go" → execute → report. |
| < 0.5 | MANUAL | Ask before each block. Show task details. Wait for confirmation. |

### User Override

The user can always override the calculated mode:
- "go", "execute", "run it", "autonomous" → force FULL AUTO
- "show me first", "step by step", "manual" → force MANUAL
- A specific score threshold → "autonomy 0.7" → use that threshold

---

## Escalation Protocol

### When a Block Gate Fails

```
1. Retry failed rows once (max 1 retry per row)

2. IF retry passes → continue to next block

3. IF retry fails → escalate:
   Show:
     - Task ID and scope
     - What was attempted
     - Error output (first 50 lines)
     - 2-3 suggested fix options

4. Wait for human input:
   - "try X" → one more attempt with guidance
   - "skip" → mark task skipped, continue block
   - "abort" → halt entire run
   - "I'll fix it" → halt, let human take over

5. IF one more attempt fails → HALT, mark as blocked
   Capture as lesson: what failed, why, what was attempted
```

### When Context is Insufficient

```
1. Detect: needed_info > available_info
2. Ask specific questions (max 3):
   - "What should happen when X?"
   - "Which files should this touch?"
   - "Is Y the correct pattern to follow?"
3. With answers → recalculate clarity → proceed
4. Without answers → lower autonomy score → ask more
```

### When a Hard Rule is Triggered

```
1. STOP — do not proceed
2. Show:
   - What operation was attempted
   - Why it triggered the hard rule
   - The exact scope (which files, which data)
3. Ask: "This operation requires confirmation. Proceed?"
4. IF confirmed → execute with extra caution
5. IF declined → skip or propose alternative
```

---

## Recovery

### Session Interruption

If the session is interrupted mid-block:
1. Read `.ff/state.json` from disk
2. Identify last completed block
3. Resume from the next block
4. Re-check autonomy score (context may have changed)

### Block Corruption

If a block produces invalid output:
1. Discard that block's outputs
2. Re-run the block from scratch
3. If re-run fails → escalate

### Full Run Recovery

If the entire FF run needs to restart:
1. Read state.json for context
2. Re-run Phase 1 (PLAN BUILD) with lessons from previous run
3. Re-calculate autonomy score
4. Resume from Block 0
