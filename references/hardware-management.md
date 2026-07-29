---
name: hardware-management
id: hardware
version: 2.0.0
type: reference
description: 'Context management for local hardware. Slicing, compaction, caps, timeouts.'
---

# Hardware Management

Read settings from `{loop-root}/config.yaml` under `hardware:`.

## Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `context_window` | 200000 | Total available context tokens |
| `context_safety_margin` | 0.15 | Reserve 15% (30K buffer) |
| `max_parallel_agents` | 3 | Max concurrent sub-agents |
| `agent_context_limit` | 66666 | Max tokens per sub-agent |
| `stage_timeout_seconds` | 300 | Max seconds per stage |
| `max_artifact_size_lines` | 300 | Cap artifact file size |
| `max_findings_buffer` | 50 | Cap accumulated findings |
| `compact_log_after_iteration` | 3 | Compact log after N iterations |

## Parallel Context Slicing

Each sub-agent receives only its relevant context slice. Total tokens across all agents must stay within `context_window - (context_window * context_safety_margin)`.

| Agent | Receives | Does NOT receive |
|-------|----------|-----------------|
| Blind Hunter | diff + work item + blueprint (relevant sections) | BDD journey, review plan |
| Edge Case Hunter | work item + I/O matrix + diff (edge-case areas) | full blueprint, BDD journey |
| Test Coverage Auditor | BDD journey + ACs + test file paths | full diff, blueprint |
| Impl Validate | diff + blueprint + work item | BDD journey, review plan |
| QA Validate | BDD journey + test files | diff, blueprint |
| Security Reviewer | diff + blueprint + architecture | test files |
| API Contract Validator | blueprint + API source + integration tests | E2E tests, full diff |
| Performance Checker | blueprint + architecture + build output | test files |

## Graphify Context (when enabled)

When `config.graphify.enabled == true`, sub-agents can use graph query as an alternative to Read for structural understanding.

| Agent | Graphify Command | Instead of |
|-------|-----------------|------------|
| Impl Code | `graphify explain <entity>` before modifying | Reading multiple dependency files |
| Security Reviewer | `graphify path <source> <sink>` | Grep for data flow connections |
| API Contract | `graphify query "API endpoints"` | Reading all route files |
| Verifier | `graphify explain <entity>` | Reading dependency chain |
| Architecture | `graphify explain <concept>` + `graphify path` | Reading architecture files |

**Rule:** Graph query provides structure and connections. Read provides implementation details. Use both — never replace Read with query when contract/type/logic is critical.

**Rule:** Never pass the full set of artifacts to any single sub-agent.

## Context Compaction

Trigger: `state.iteration >= compact_log_after_iteration AND state.iteration % compact_log_after_iteration == 0`

```
compact_log():
  1. Keep: frontmatter, current state table, last 5 iteration log rows
  2. Discard: phase details from iterations older than (current - 2)
  3. Summarize: old findings into counts by category
  4. Rewrite log file with compacted content
```

## Findings Buffer Cap

`state.findings` capped at `max_findings_buffer`. When exceeded:

1. Sort by severity (high → medium → low)
2. Keep top N highest-severity
3. Summarize remaining: `summarized: {count} (high: N, medium: N, low: N)`
4. Replace overflow with single summary entry

## Stage Timeout

If a stage exceeds `stage_timeout_seconds`:

1. Set `status: halted`, `blocking_condition: stage timeout exceeded`
2. Save current state to log
3. **EXIT loop**
