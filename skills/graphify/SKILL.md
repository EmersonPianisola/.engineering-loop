---
name: graphify
id: graphify
version: 2.0.0
type: skill
description: 'Knowledge graph skill for Engineering Loop. Query-first for architecture questions. AST-based code mapping with data flow tracing, dead code detection, and incremental updates.'
---

# Graphify Skill

Knowledge graph layer for Engineering Loop stages. Provides structural index of codebase via Graphify with enhanced capabilities for data flow tracing and dead code detection.

## Invocation

This skill is invoked by the orchestrator during INIT (graph build) and referenced by sub-agents during stages that benefit from structural awareness.

## Graph Build (INIT stage)

When `config.graphify.enabled` is true and codebase exists:

1. **Check CLI:** Verify `graphify` is available
2. **Build:** Run `graphify update .` on project root
3. **Register:** Record graph stats in STATE.md
4. **Git:** If `commit_graph: true`, stage `graphify-out/`

```
graphify update .            # Build/update graph (AST extraction, no LLM)
```

## Incremental Update Strategy

After code changes, update the graph incrementally rather than full rebuild:

```
# After impl.code completes — re-extracts only changed files
graphify update .

# Full rebuild (use only when graph health degrades)
graphify rebuild .

# Check graph health
graphify health .
```

**When to incrementally update:**
- After `impl.code` stage completes
- Before `qa.*` stages that need current structure
- When `graphify health` reports stale edges

**When to full rebuild:**
- Major refactoring (>30% files changed)
- Graph health score < 80%
- After dependency graph changes (new packages, removed modules)

## Query Usage (Sub-Agent Instructions)

Sub-agents should follow these rules when graph exists:

### Before modifying code

```
graphify explain <entity-name>
```

Returns: source location, community, degree, and connections. Use to understand impact scope.

### Before tracing data flow

```
graphify path <source> <destination>
```

Returns: shortest path with hop-by-hop connections.

### Before understanding architecture

```
graphify query "<specific question>"
```

Returns: scoped subgraph relevant to the question.

### Data Flow Tracing

Trace how data moves through the system:

```
# Trace from entry point to data sink
graphify flow <entry-point> <sink>

# Trace all paths from a source
graphify flows-from <source>

# Trace all paths to a destination
graphify flows-to <destination>
```

**Use cases:**
- Security audit: trace user input to database writes (identify injection points)
- Debugging: trace where a specific value is transformed
- Impact analysis: trace what changes when a data field is modified

### Dead Code Detection

Walk call and reference edges from entry points to surface unreachable functions:

```
# Find unreachable functions
graphify dead-code .

# Find unused exports
graphify unused-exports .

# Find orphaned modules (no incoming edges)
graphify orphans .
```

**Dead code categories:**

| Category | Description | Action |
|----------|-------------|--------|
| **Unreachable function** | No call path from any entry point | Safe to remove |
| **Unused export** | Exported but never imported | Remove export or add usage |
| **Orphaned module** | File with no incoming edges | Review if needed |
| **Dead import** | Imported but never used | Remove import |

**Caution:** Some code is intentionally unreachable (plugins, hooks, runtime-loaded modules). Verify before removing.

## Confidence Rules

| Edge Tag | Action |
|----------|--------|
| `EXTRACTED` | Trust — explicit in source |
| `INFERRED` | Verify if critical — derived by resolution |
| `AMBIGUOUS` | Do not trust — must Read source |

## Anti-Patterns

| Anti-pattern | Rule |
|---|---|
| Generic query | `graphify query "auth"` returns noise. Use `graphify explain AuthMiddleware` |
| Trusting INFERRED blindly | Verify with Read when contract/type is critical |
| Skipping Read entirely | Graph = map, Read = terrain. Both are needed |
| Querying stale graph | Check if code changed since last build. Run `graphify update .` if needed |
| Over-querying | For tasks isolated to 1-2 files, Read is faster than query |
| Ignoring dead code | Run `graphify dead-code` periodically; accumulated dead code degrades graph quality |
| Full rebuild on every change | Use incremental updates; full rebuild is expensive and unnecessary |

## Post-Implementation

After `impl.code` completes, update graph:

```
graphify update .
```

Re-extracts only changed files. AST only. Zero LLM cost.

## Error Handling

- If `graphify` not found: Log warning, skip, continue.
- If graph empty: Log warning, skip, continue.
- If graph health warning: Surface as finding, proceed with caution.
