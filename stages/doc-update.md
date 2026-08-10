---
name: doc-update
id: doc.update
version: 1.0.0
type: stage
description: 'Update existing project files with implementation results. Runs after impl.code for all complexity levels.'
---

# STAGE: Documentation — Update Existing Project Files
<!-- ID: doc.update -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the project documentation updater.
- DO NOT implement code, write tests, or create new features.
- The moment all existing project files are updated, your task is FINISHED.
- Implementing code changes is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.stages.impl.code.done != true` → `status: blocked`, `blocking_condition: code implementation not complete`. **EXIT.**
2. **Essence Gate:** Run Essence sidecar validation before proceeding. If Essence fails, adjust inputs and re-validate.
3. Proceed with the steps below.

# Documentation — Update Existing Project Files

**Skill:** Project Documentation Updater (self-constructed from conventional-changelog + README best practices)
**Runs when:** `state.stages.doc.update.done == false`
**Constraint:** `max_doc_update_attempts` (default: 2)

## Design

- Input: Git diff of changes, blueprint, work item, existing project files.
- Output: Updated existing files + stage results artifact.
- Enforce `max_artifact_size_lines` per document.

### Files to Update

| File | Action | Source |
|------|--------|--------|
| `README.md` | Update sections: features, setup, structure, tech stack | Implementation diff + blueprint |
| `CHANGELOG.md` | Append entry for this change | Work item + implementation summary |
| `docs/*.md` | Update any docs that became outdated | Implementation diff + new behavior |
| Inline comments | Update JSDoc/docstrings in modified files | Implementation changes |
| `artifacts/stage-results-{slug}.md` | Create structured stage summary | All stage outputs |

## Execute

### 1. Capture Git Diff

```
git diff HEAD~{N} --stat          # Files changed
git diff HEAD~{N}                 # Full diff for context
```

Where N = number of commits made in this loop run.

### 2. Update README.md

If `README.md` exists:

1. **Read** existing README
2. **Identify sections** that need updating:
   - Features list — add new features
   - Tech stack — update versions, add new dependencies
   - Project structure — reflect new directories/files
   - Setup instructions — update if dependencies or commands changed
   - API documentation — update if endpoints changed
3. **Update** sections in place, preserving existing content and formatting
4. **DO NOT** create a new README from scratch — modify what exists

If `README.md` does not exist, skip (doc.project will create it).

### 3. Update CHANGELOG.md

If `CHANGELOG.md` exists:

1. **Read** existing CHANGELOG
2. **Append** new entry following existing format (keep-a-changelog convention)
3. **Categorize** changes: Added / Changed / Deprecated / Removed / Fixed / Security

```markdown
## [Unreleased]

### Added
- {New feature or capability}

### Changed
- {Behavior changes, breaking changes}

### Fixed
- {Bug fixes}
```

If `CHANGELOG.md` does not exist, skip (doc.project will create one if needed).

### 4. Update Existing Docs

Scan `docs/` directory for files that may be affected:

1. **Identify affected docs** — files whose topic overlaps with implemented changes
2. **Read** each affected doc
3. **Update** outdated sections:
   - API documentation — update endpoints, parameters, responses
   - Architecture diagrams — update if components changed
   - User guides — update if UI/UX changed
   - Configuration docs — update if config options changed
4. **Preserve** existing structure, only update what's outdated

### 5. Update Inline Code Comments

For files modified in `impl.code`:

1. **Check** if functions/modules have JSDoc/docstring comments
2. **Update** comments that are now inaccurate:
   - Parameter descriptions
   - Return value descriptions
   - Function purpose
   - Usage examples
3. **Add** comments to public APIs that lack them
4. **DO NOT** modify implementation logic

### 6. Generate Stage Results Artifact

Create `artifacts/stage-results-{slug}.md`:

```markdown
# Stage Results

**Run ID:** {run_id}
**Generated:** {date}

## Stages Executed

| Stage | Status | Output | Decisions |
|-------|--------|--------|-----------|
| init | done | work item validated | — |
| impl.design | done | blueprint-{slug}.md | AD-001 |
| impl.code | done | {N} files created, {M} modified | AD-002, AD-003 |
| ... | ... | ... | ... |

## Implementation Summary

- **Files created:** {list}
- **Files modified:** {list}
- **Tests added:** {count}
- **Decisions made:** {count} (see STATE.md ## Decisions)

## Changes Made

{Brief description of what was implemented, referencing blueprint tasks}

## Affected Documentation

- README.md: {sections updated}
- CHANGELOG.md: {entry added}
- docs/{file}: {sections updated}
```

## Validate

### Validation Checklist

- [ ] README.md updated (if exists) — sections reflect current implementation
- [ ] CHANGELOG.md updated (if exists) — entry for this change
- [ ] Existing docs reviewed — outdated sections updated
- [ ] Inline comments accurate — public APIs documented
- [ ] Stage results artifact created
- [ ] No implementation code was modified
- [ ] No new features were added
- [ ] Existing file formatting and conventions preserved

All pass → `done = true`. Gaps → `done = false` (loop re-runs).

## State Update Contract

**MANDATORY.** Follow `{reference-root}/sub-agent-contract.md`. Before returning your response:

1. Write all artifacts to their designated paths in `{artifact-root}/`
2. Update `{loop-root}/state.json`:
   - `stages.doc.update.done = true` (or `false` on failure)
   - `stages.doc.update.attempts += 1`
   - `stages.doc.update.artifact_path = "artifacts/..."` (your output path)
   - `stages.doc.update.error = null` (or failure description)
3. Record AD-NNN decisions in `{loop-root}/STATE.md ## Decisions` (if applicable)
4. Your response MUST be a single JSON line:
   - Success: `{"stage":"doc.update","status":"done","artifact":"artifacts/..."}`
   - Failure: `{"stage":"doc.update","status":"failed","error":"reason"}`

DO NOT include artifact content, summaries, or "Next steps" in your response.
