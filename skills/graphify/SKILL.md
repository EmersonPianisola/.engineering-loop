---
name: graphify
id: graphify
version: 1.0.0
type: skill
description: 'Knowledge graph skill for Engineering Loop. Query-first for architecture questions. AST-based code mapping.'
---

# Graphify Skill

Knowledge graph layer for Engineering Loop stages. Provides structural index of codebase via Graphify.

## Invocation

This skill is invoked by the orchestrator during INIT (graph build) and referenced by sub-agents during stages that benefit from structural awareness.

## Graph Build (INIT stage)

When `config.graphify.enabled` is true and codebase exists:

1. **Check CLI:** Verify `graphify` is available
2. **Build:** Run `graphify .` on project root
3. **Register:** Record graph stats in STATE.md
4. **Git:** If `commit_graph: true`, stage `graphify-out/`

```
graphify . --no-viz          # Build graph, skip HTML for speed
# or
graphify .                   # Build graph with HTML visualization
```

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
