---
name: essence
id: essence
version: 1.0.0
type: skill
stage: all
---

# Essence Sidecar — Four Lenses Validation

## Objective
Validate that stage inputs are sound before any work begins. Apply four lenses to detect subjective language, hidden assumptions, literal traps, and conflicting priorities. This is a PRE-STAGE gate — it validates inputs, not outputs.

## Inputs
- Stage inputs for the upcoming stage (per essence input table)
- Work item description
- Relevant artifacts (blueprint, architecture, decisions)
- Stage context: `state.stages.{stage_id}`

## Permitted Tools
- `read`: Read stage inputs, artifacts, work item
- `glob`: Find relevant files

## The Four Lenses

### Lens 1 — Subjective Terms

Detect ambiguous language disguised as requirements. Flag terms that have no shared definition and propose concrete interpretations.

**Common culprits:**
`robust` | `simple` | `clean` | `fast` | `good` | `proper` | `correct` |
`scalable` | `elegant` | `comprehensive` | `thorough` | `minimal` | `intuitive` |
`secure` | `performant` | `maintainable` | `production-ready`

**Protocol:**
1. Scan stage inputs for subjective terms
2. For each term, propose 2-3 concrete interpretations
3. Flag for clarification if the term cannot be anchored to observable criteria

**Example:**
- Input: "Make the API robust"
- Finding: "robust" → network resilience? data integrity? error recovery? load handling?
- Action: Flag for Lens 4 if multiple interpretations are plausible

### Lens 2 — Hidden Assumptions

Extract unstated dependencies and implicit requirements.

**Protocol:**
1. Read stage inputs as if you know nothing about the project
2. For each statement, ask: "What does this assume?"
3. State each assumption plainly
4. Flag assumptions that could invalidate the entire approach

**Common patterns:**
- Unstated dependencies: "This needs service X" (without saying so)
- Implicit requirements: "Make it work with the API" (which API? which version?)
- Source of truth: "The source of truth is A" — what if it's B?
- User behavior: "The user will always do X" — what if they don't?
- Reliability: "This dependency is reliable" — what if it fails?
- Current approach: "The current approach is correct" — what if it's the problem?

### Lens 3 — Literal Traps

Detect phrasing that invites wrong LLM interpretation. Ambiguous wording that looks like a clear instruction but can be misunderstood.

**Protocol:**
1. Read each instruction literally
2. Identify multiple plausible interpretations
3. Flag the misinterpretation an LLM is likely to make
4. Propose the correct interpretation

**Common traps:**
- "Fix X" — fix what about X? (bug? performance? UX?)
- "Handle errors" — log? retry? fail gracefully? propagate?
- "The user data" — which user? which fields? raw or processed?
- "It's broken" — what is "it"? what does "broken" look like?
- "Make it work" — work in what way, under what conditions?
- "Add logging" — what level? what context? where output?

### Lens 4 — Conflicting Priorities

Identify competing goals that need human resolution.

**Protocol:**
1. Extract all goals from stage inputs
2. Identify tensions between goals
3. State the conflict: "You want X and Y, which typically conflict because Z"
4. **ESCALATE to user** — never resolve conflicts yourself

**Common conflicts:**
- Fast vs. thorough
- Simple vs. complete
- Flexible vs. constrained
- Generic vs. optimized
- Security vs. usability
- Performance vs. maintainability

## Execution Protocol

### Step 1: Gather Inputs
Read the stage inputs specified for this stage (per essence input table below).

### Step 2: Apply Four Lenses
Apply each lens to the gathered inputs. Record findings.

### Step 3: Classify Findings

| Lens | Action |
|------|--------|
| Lenses 1-3 | Auto-adjust inline, re-run essence |
| Lens 4 | Escalate to user, await resolution |
| No findings | Mark clean, proceed |

### Step 4: Output Results
Return structured output with findings per lens.

## Essence Input Per Stage

| Stage | Essence Validates |
|-------|-------------------|
| `init` | Work item completeness, clarity of intent |
| `init.ideate` | Work item ready for ideation decomposition |
| `init.bdd` | PRD features, UX flows, user stories sufficient for journey mapping |
| `init.refine` | Raw user request: clarity, scope, intent |
| `arch.requirements` | Work item + planning artifacts provide sufficient context |
| `arch.solution` | Requirements artifact + UX designs are sufficient |
| `arch.review` | All architecture artifacts exist and are consistent |
| `impl.design` | Architecture (or work item for small/medium) is complete |
| `impl.code` | Blueprint is complete, contracts are defined |
| `doc.update` | Implementation diff available, project files exist to update |
| `verify` | Code implementation + tests are complete |
| `e2e.execute` | Blueprint, Behavior Map (if exists), running dev server available |
| `qa.static` | Source code available for static analysis |
| `qa.unit` | Source code available, test framework configured |
| `qa.integration` | API specs + component source available |
| `qa.security` | Code diff + architecture artifacts available |
| `qa.performance` | Blueprint + architecture + build output available |
| `qa.human.flow` | Running application available for heuristic testing |
| `qa.human.ux` | Running application available for WCAG audit |
| `deploy.prepare` | All QA stages complete, code is ready |
| `smoke.test` | Production build available, critical paths defined |
| `doc.decisions` | STATE.md Decisions section has entries to consolidate |
| `doc.project` | Decision log exists, project structure is clear |
| `post` | All stages complete, artifacts ready for finalization |

## Output Format

```json
{
  "lens_1_subjective_terms": [
    {
      "term": "robust",
      "context": "Make the API robust",
      "interpretations": ["network resilience", "data integrity", "error recovery"]
    }
  ],
  "lens_2_hidden_assumptions": [
    {
      "assumption": "The payment service is always available",
      "risk": "If payment service is down, entire checkout flow fails",
      "severity": "high"
    }
  ],
  "lens_3_literal_traps": [
    {
      "phrasing": "Fix the login",
      "ambiguity": "Fix bug? Improve UX? Add authentication method?",
      "likely_misinterpretation": "LLM will fix the most obvious bug, not the root cause"
    }
  ],
  "lens_4_conflicts": [
    {
      "goal_a": "Complete in 2 weeks",
      "goal_b": "Comprehensive test coverage (90%+)",
      "tension": "Speed vs. thoroughness — achieving 90% coverage in 2 weeks requires more engineers or reduced scope",
      "requires_user_resolution": true
    }
  ],
  "clean": false,
  "adjustments": [
    "Clarified 'robust' to mean 'error recovery with retry logic'"
  ],
  "summary": "Found 1 subjective term, 1 hidden assumption, 1 literal trap, 1 priority conflict. Lens 4 conflict requires user resolution."
}
```

## Rules

- **Never skip** — every stage must pass the Four Lenses before invocation
- **Never increment attempts** — essence loop is internal to the pre-stage gate
- **Never escalate Lenses 1-3** — auto-adjust inline, re-validate
- **Always escalate Lens 4** — human resolution required for priority tensions
- **Always capture Lens 4 in context.md** — user decisions recorded for traceability
- **Always run BEFORE stage** — essence validates inputs, not outputs
- **Bound retries** — max 5 essence retries per stage (configurable)

## Anti-Patterns

- **Never skip because "it's obvious"** — obvious is where the traps live
- **Never invent your own definition** for a subjective term and proceed
- **Never resolve conflicting priorities yourself** — ask the user
- **Never use the check as a delay tactic** — keep it tight, move fast
- **Never ask more than 3 clarifying questions at once** — batch, then wait
