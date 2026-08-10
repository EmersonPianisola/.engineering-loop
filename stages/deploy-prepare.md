---
name: deploy-prepare
id: deploy.prepare
version: 2.0.0
type: stage
description: 'Deploy preparation. Build, lint, environment configuration, migration verification.'
---

# STAGE: Deploy Preparation
<!-- ID: deploy.prepare -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the deploy preparer.
- DO NOT push to remote or deploy to production.
- The moment deploy preparation is verified, your task is FINISHED.
- Deploying to production is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.stages.verify.done != true` → `status: blocked`, `blocking_condition: verification not complete`. **EXIT.**
2. **E2E prerequisite:** If project has UI and `state.stages.e2e.execute.done != true` → `status: blocked`, `blocking_condition: E2E browser testing not complete`. **EXIT.**
3. **QA prerequisite:** If `state.complexity >= "medium"` and `state.stages.qa.security.done != true` → `status: blocked`. **EXIT.**
4. Proceed with the steps below.

# Deploy Preparation — Build and Verification

**Runs when:** `state.stages.deploy.prepare.done == false`
**Prerequisite:** `state.stages.verify.done == true` + `state.stages.e2e.execute.done == true` (if UI project) + QA stages if active

## Execute — Build Pipeline

### 1. Build

- Run production build command
- Verify build succeeds with zero errors
- Check build output size against performance targets
- Verify all assets generated correctly

### 2. Lint

- Run linter (ESLint, Stylelint, or project equivalent)
- Zero lint errors required
- Warnings logged but not blocking

### 3. Type Check

- Run type checker (TypeScript, or project equivalent)
- Zero type errors required

### 4. Environment Configuration

- Verify environment variables documented
- Check `.env.example` or equivalent is complete
- Verify no secrets committed to repository
- Check environment-specific configurations

### 5. Database Migrations

- Verify migration files exist and are ordered
- Check migration rollback capability
- Verify migration documentation

### 6. Deployment Artifacts

- Verify Dockerfile (if applicable)
- Check CI/CD configuration files
- Verify deployment scripts
- Check health check endpoints

### 7. Final Verification

- Run full test suite one final time
- All tests pass
- Build artifacts are clean

## Validate

- All checks pass → `done = true`
- Build/lint/type errors → `done = false`, reset `impl.code.done = false`
- Missing config → `done = false`, document missing items

## State Update Contract

**MANDATORY.** Follow `{reference-root}/sub-agent-contract.md`. Before returning your response:

1. Write all artifacts to their designated paths in `{artifact-root}/`
2. Update `{loop-root}/state.json`:
   - `stages.deploy.prepare.done = true` (or `false` on failure)
   - `stages.deploy.prepare.attempts += 1`
   - `stages.deploy.prepare.artifact_path = "artifacts/..."` (your output path)
   - `stages.deploy.prepare.error = null` (or failure description)
3. Record AD-NNN decisions in `{loop-root}/STATE.md ## Decisions` (if applicable)
4. Your response MUST be a single JSON line:
   - Success: `{"stage":"deploy.prepare","status":"done","artifact":"artifacts/..."}`
   - Failure: `{"stage":"deploy.prepare","status":"failed","error":"reason"}`

DO NOT include artifact content, summaries, or "Next steps" in your response.
