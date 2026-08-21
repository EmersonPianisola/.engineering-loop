---
name: sub-agent-contract
id: sub-agent-contract
version: 1.0.0
type: reference
description: 'Mandatory contract for all sub-agents. Defines state update, artifact output, and response format.'
---

# Sub-Agent Contract

**MANDATORY.** Every sub-agent invoked by the orchestrator MUST follow this contract. This is the single mechanism that keeps the orchestrator's context minimal and the loop under control.

## Rule 1: Write Artifacts to Disk

If your stage produces output, write it to the designated artifact path BEFORE updating state.

| Artifact Type | Location |
|---|---|
| Stage artifacts | `{artifact-root}/` (blueprints, architectures, validations, etc.) |
| Source code | `{project-root}/` (actual project files) |
| Test files | `{project-root}/` (alongside source) |
| Screenshots | `{artifact-root}/` (E2E, smoke) |
| Lessons | `{artifact-root}/lessons.json` |

**NEVER** return artifact content in your response text. The orchestrator reads from disk.

## Rule 2: Update state.json

After completing (success or failure), you MUST update `{loop-root}/state.json`:

1. `read(state.json)` — load current state first
2. Modify ONLY your stage's fields:
   ```json
   {
     "stages": {
       "{your_stage_id}": {
         "done": true,
         "attempts": <previous + 1>,
         "essence_checked": true,
         "artifact_path": "artifacts/your-output.md",
         "error": null
       }
     }
   }
   ```
3. `write(state.json)` — write the complete updated state back

On failure with upstream reset:
```json
{
  "stages": {
    "{your_stage_id}": {
      "done": false,
      "attempts": <previous + 1>,
      "error": "description of what failed"
    },
    "impl.code": {
      "done": false
    }
  }
}
```

## Rule 3: Minimal Response

Your final response to the orchestrator MUST be a single JSON line:

```json
{"stage":"{stage_id}","status":"done","artifact":"artifacts/path.md"}
```

Or on failure:
```json
{"stage":"{stage_id}","status":"failed","error":"reason"}
```

**DO NOT** include:
- Artifact content
- Summaries
- "Next steps"
- Explanations
- Markdown formatting

The orchestrator reads `state.json` from disk. Your response is only a signal.

## Rule 4: Record Decisions (AD-NNN)

If your stage makes architectural or implementation decisions, append to `{loop-root}/STATE.md`:

```markdown
### AD-NNN
- **Decision**: {What was decided}
- **Reason**: {Why}
- **Trade-off**: {Cost}
- **Scope**: {Where it applies}
- **Origin**: {stage_id}
```

Read the existing file first to determine the next AD-NNN number.

## Rule 5: Execution Boundary

Each stage has a `MANDATORY EXECUTION BOUNDARY` section. You MUST:
- Perform ONLY the work defined in your stage
- NOT transition to other stages
- NOT implement features beyond your stage's scope
- STOP immediately when your stage's work is complete

## Node Types

Not every node in a graph is a worker loop. The distinction matters for what verification is required.

### Worker Nodes
- **Examples:** `impl.code`, `verify`, `e2e.execute`, `qa.*`
- **Require:** verifier + stopping condition
- **Pattern:** discover → plan → execute → verify → repeat until done or max attempts
- **Output:** artifact + `state.json` update + JSON signal

### Transform Nodes
- **Examples:** `init.setup`, `deploy.prepare`, `post`
- **Require:** deterministic execution, no self-verifier needed
- **Pattern:** execute work → write artifacts → signal
- **Output:** artifact + `state.json` update + JSON signal

### Router Nodes
- **Examples:** `dynamic.architect` (proposes topology), `meta.executor` (routes steps)
- **Require:** no verifier (they are the routing mechanism)
- **Pattern:** analyze → propose/route → signal
- **Output:** `state.json` update + JSON signal

### Rule

Every worker node must have a verifier and a stopping condition. Not every node needs to be a loop. Deterministic transforms and routers are valid nodes that don't need loops.

## Verification Checklist

Before returning your response, verify:

- [ ] Artifact written to correct path (if applicable)
- [ ] `state.json` updated with your stage's `done`, `attempts`, `artifact_path`, `error`
- [ ] AD-NNN decisions recorded in `STATE.md` (if applicable)
- [ ] Response is a single JSON line matching the format above
