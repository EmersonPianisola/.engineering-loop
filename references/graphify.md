---
name: graphify-reference
id: graphify
version: 1.0.0
type: reference
description: 'Knowledge graph integration via Graphify. Opt-in. AST-based code mapping (zero LLM cost). Query-first for architecture questions.'
---

# Graphify — Knowledge Graph Integration

Opt-in knowledge graph layer. Maps codebases via tree-sitter AST (deterministic, zero LLM, nothing leaves machine). Provides structural index for sub-agents to query instead of reading files.

## Configuration

All settings in `{loop-root}/config.yaml` under `graphify:`.

| Setting | Default | Purpose |
|---------|---------|---------|
| `enabled` | `false` | Opt-in toggle |
| `build_on_init` | `true` | Auto-build graph during INIT if codebase exists |
| `build_on_commit` | `false` | Install git post-commit hook for auto-rebuild |
| `update_after_impl` | `true` | Run `graphify update .` after impl.code completes |
| `skip_if_small` | `true` | Skip build if `state.complexity == "small"` |

## When Graphify Adds Value

| Scenario | Benefit |
|-----------|---------|
| Codebase >50 files, multiple modules | `graphify path` replaces 5-10 Reads |
| Refactoring across files | Understand impact before modifying code |
| Onboarding (existing project) | GRAPH_REPORT.md = instant structural summary |
| Project with dense docs (.md, PDF, ADRs) | Graph maps references between docs and code |
| `complexity >= medium` | Cost/benefit ratio is favorable |

## When to Skip

| Scenario | Reason |
|----------|--------|
| New project (zero code) | Empty graph, useless build |
| `complexity: small` (≤3 files) | 1 Read < query overhead |
| Work item isolated to 1 module | Graph adds latency without benefit |
| Code changes every commit | Graph goes stale, trust decays |
| No Python/uv available | Extra dependency with no ROI |

## Commands

| Command | When | Cost |
|---------|------|------|
| `graphify .` | Initial build | AST: free. Docs: LLM cost |
| `graphify . --update` | Incremental (changed files only) | AST: free. Docs: LLM cost for changed |
| `graphify explain <entity>` | Understand one concept | Free (reads graph.json) |
| `graphify path A B` | Trace connection between two things | Free |
| `graphify query "<question>"` | Scoped subgraph for natural language | Free |

## Rules for Sub-Agents

### USE graphify when

- Need to understand relationship between entities (A → B)
- Mapping impact before modifying code
- Understanding architecture of unfamiliar module
- Work item mentions specific entities

### USE Read/Grep when

- Need to see contract, type, function signature
- Need to understand implementation logic
- File is small (<200 lines)
- Task is isolated to 1-2 known files
- Graph doesn't exist or is stale

### NEVER

- Trust an `INFERRED` edge without verifying source
- Use generic query ("auth", "database") — be specific
- Substitute Read with query when contract/type is critical
- Skip Read after `graphify explain` — graph is the map, Read is the terrain

## Confidence Tags

Every edge carries a confidence tag. Sub-agents must respect them:

| Tag | Meaning | Trust Level |
|-----|---------|-------------|
| `EXTRACTED` | Explicit in source code | High — treat as fact |
| `INFERRED` | Derived by graph resolution | Medium — verify with Read if critical |
| `AMBIGUOUS` | Uncertain relationship | Low — must verify with Read |

## Graph Health

If `graphify diagnostics` (or Step 4.5 in the skill) reports warnings:
- Surface warning as a finding in the current stage
- Do NOT abort — graph is still usable
- If `dangling_endpoint_edges` or `missing_endpoint_edges` > 0, prefer Read over query for affected entities

## Integration Points

| Stage | Graphify Usage |
|-------|---------------|
| `init` | Build graph (if enabled + codebase exists) |
| `arch.requirements` | `graphify query` for existing architecture context |
| `arch.solution` | `graphify path` to trace data flows |
| `impl.code` | `graphify explain <entity>` before modifying files |
| `verify` | `graphify explain` to validate impact scope |
| `qa.security` | `graphify path` to trace data flow for security audit |
| `qa.api-contract` | `graphify query` for API endpoint inventory |
| `doc.project` | `graph.html` and `GRAPH_REPORT.md` as architecture reference |

## Post-Implementation Update

When `update_after_impl: true` and `impl.code` completes:

```
graphify update .
```

This re-extracts only changed files (AST only, zero LLM cost). Keeps graph current for subsequent stages.

## Git Integration

Files to commit (recommended):

```
graphify-out/
├── graph.json          ← Commit (team shares the map)
├── GRAPH_REPORT.md     ← Commit
├── graph.html          ← Commit (interactive visualization)
├── manifest.json       ← Commit (portable, relative paths)
├── cost.json           ← Gitignore (local tracking)
└── cache/              ← Gitignore (local optimization)
```

Git merge driver is installed by default — parallel commits union-merge `graph.json` automatically.

## Stale Detection

If `graph.json` exists but `manifest.json` indicates files have changed since last build:
- Warn sub-agent: "Graph may be stale. Run `graphify update .` before querying."
- Sub-agent should prefer Read for entities that may have changed.

## Error Handling

| Error | Action |
|-------|--------|
| `graphify: command not found` | Log warning "graphify not installed". Skip graph operations. Continue loop. |
| `ERROR: Graph is empty` | Log warning. Skip graph operations. Continue loop. |
| `ERROR: refused to shrink graph.json` | Log warning. Graph was intentionally reduced. Run `graphify . --force` if needed. |
| `GRAPH HEALTH WARNING` | Surface as finding. Continue with caution. |
