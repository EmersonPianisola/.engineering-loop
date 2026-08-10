---
name: qa-performance
id: qa.performance
version: 2.0.0
type: stage
description: 'Performance check. Load targets, bundle size, response time. Active for complex features only.'
---

# STAGE: Performance Check
<!-- ID: qa.performance -->
<!-- Min Complexity: complex -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the performance checker.
- DO NOT implement optimizations. Report findings only.
- The moment you produce the performance report, your task is FINISHED.
- Modifying code is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.stages.qa.api-contract.done != true` → `status: blocked`, `blocking_condition: API contract validation not complete`. **EXIT.**
2. **Complexity Check:** If `state.complexity < "complex"` → `done: true` (deactivated). **SKIP.**
3. Proceed with the steps below.

# Performance Check — Metrics Verification

**Skill:** Self-constructed from web performance best practices
**Runs when:** `state.stages.qa.performance.done == false` AND `state.complexity == "complex"`
**Prerequisite:** `state.stages.qa.api-contract.done == true`

## Execute — Performance Audit

**Context slice:** `{blueprint}` + `{architecture}` + `{build_output}`. Never pass test files.

### Metrics Checklist

| Metric | Target | Check |
|--------|--------|-------|
| Bundle Size | < 500KB initial (gzip) | Analyze build output |
| First Contentful Paint | < 1.5s | Lighthouse / build analysis |
| Time to Interactive | < 3.5s | Lighthouse / build analysis |
| API Response Time | < 200ms (p95) | Architecture capacity check |
| Database Query Time | < 50ms (simple) | Query analysis |
| Image Optimization | WebP/AVIF, lazy loading | Asset review |
| Code Splitting | Route-based splitting | Build config review |
| Caching Strategy | HTTP cache headers, service worker | Config review |
| Font Loading | font-display: swap, preload | CSS review |
| Critical CSS | Inlined critical path | CSS analysis |

### Architecture Performance Checks

| Check | Description |
|-------|-------------|
| CDN Configuration | Static assets served via CDN |
| Database Indexing | Query patterns have appropriate indexes |
| Connection Pooling | DB connections pooled appropriately |
| Caching Layers | Appropriate cache at each layer |
| Async Processing | Long operations offloaded to queues |
| Pagination | Large datasets paginated |

### Severity Classification

| Severity | Criteria |
|----------|----------|
| Critical | Target exceeded by >2x, blocking functionality |
| High | Target exceeded by >50%, noticeable degradation |
| Medium | Target exceeded by <50%, minor impact |
| Low | Optimization opportunity, no current impact |

## Validate

- No critical or high findings → `done = true`
- Critical findings → `done = false`, reset `impl.code.done = false`
- High findings → `done = false`, document for optimization sprint
- Medium/low → log as optimization backlog, `done = true`

## State Update Contract

**MANDATORY.** Follow `{reference-root}/sub-agent-contract.md`. Before returning your response:

1. Write all artifacts to their designated paths in `{artifact-root}/`
2. Update `{loop-root}/state.json`:
   - `stages.qa.performance.done = true` (or `false` on failure)
   - `stages.qa.performance.attempts += 1`
   - `stages.qa.performance.artifact_path = "artifacts/..."` (your output path)
   - `stages.qa.performance.error = null` (or failure description)
3. Record AD-NNN decisions in `{loop-root}/STATE.md ## Decisions` (if applicable)
4. Your response MUST be a single JSON line:
   - Success: `{"stage":"qa.performance","status":"done","artifact":"artifacts/..."}`
   - Failure: `{"stage":"qa.performance","status":"failed","error":"reason"}`

DO NOT include artifact content, summaries, or "Next steps" in your response.
