---
name: essence
id: essence
version: 2.0.0
type: skill
stage: all
---

# Essence Sidecar — Four Lenses Validation (v2.0)

## Objective
Validate that stage inputs are sound before any work begins. Apply four lenses to detect subjective language, hidden assumptions, literal traps, and conflicting priorities. This is a PRE-STAGE gate — it validates inputs, not outputs.

**Critical change in v2.0:** Findings now carry severity based on IMPACT on the solution, not finding type. Significant findings (severity >= threshold) generate clarifying questions for the user. The LLM detects; the policy engine decides.

## Inputs
- Stage inputs for the upcoming stage (per essence input table)
- Work item description
- Relevant artifacts (blueprint, architecture, decisions)
- Stage context: `state.stages.{stage_id}`
- Previous clarifications (if any): `state.work_item.clarifications`
- Resolved findings (if any): `state.essence.resolved_findings`

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
3. Assign severity based on IMPACT of ambiguity on the solution
4. Assign a `finding_id` like `lens1_subject_cake`

**Severity classification (based on IMPACT, NOT finding type):**

| Severity | Definition | Examples |
|----------|-----------|----------|
| `high` | Interpretation fundamentally changes the solution or architecture | "login" = OAuth vs session vs SSO; "database" = SQL vs NoSQL; "cake" with dietary restrictions |
| `medium` | Meaningful decision exists, but a reasonable default is available | "cache" = in-memory vs distributed; "logging" level/format |
| `low` | Decision doesn't significantly change the outcome | "nice UI" aesthetic preference; "clean code" stylistic |

### Lens 2 — Hidden Assumptions

Extract unstated dependencies and implicit requirements.

**Protocol:**
1. Read stage inputs as if you know nothing about the project
2. For each statement, ask: "What does this assume?"
3. State each assumption plainly
4. Assign severity based on risk if assumption is false
5. Assign a `finding_id` like `lens2_assump_no_allergies`

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
4. Assign severity based on impact of misinterpretation
5. Assign a `finding_id` like `lens3_trap_receipt_recipe`

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

## Clarifying Questions

For findings with severity >= threshold, generate clarifying questions.

**Format:**
```json
{
  "id": "essence_q_001",
  "finding_id": "lens1_subject_cake",
  "lens": "lens_1",
  "finding_summary": "'cake' is ambiguous — could be any type",
  "question": "What type of cake?",
  "options": ["vanilla", "chocolate", "carrot", "cheesecake", "other"],
  "severity": "high"
}
```

**Invariants:**
- Every question MUST reference an existing `finding_id`
- Every significant finding MUST have a corresponding question
- Question `severity` mirrors the finding's severity
- Max `max_questions_per_request` questions (default: 5)

## Execution Protocol

### Step 1: Gather Inputs
Read the stage inputs specified for this stage (per essence input table below).
Check for previous clarifications and resolved findings — do not re-ask resolved items.

### Step 2: Apply Four Lenses
Apply each lens to the gathered inputs. Record findings with severity and finding_id.

### Step 3: Generate Clarifying Questions
For findings with severity >= threshold, generate clarifying questions.
The policy engine will decide whether to auto-adjust, ask user, or block.

### Step 4: Output Results
Return structured output with findings, questions, and adjustments.

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
      "finding_id": "lens1_subject_cake",
      "term": "cake",
      "context": "Write a cake recipe",
      "interpretations": ["vanilla", "chocolate", "carrot", "cheesecake"],
      "severity": "high"
    }
  ],
  "lens_2_hidden_assumptions": [
    {
      "finding_id": "lens2_assump_no_allergies",
      "assumption": "No dietary restrictions or allergies",
      "risk": "Recipe may contain allergens user wants to avoid",
      "severity": "medium"
    }
  ],
  "lens_3_literal_traps": [
    {
      "finding_id": "lens3_trap_receipt",
      "phrasing": "receipt",
      "ambiguity": "Likely means 'recipe', not a financial receipt",
      "likely_misinterpretation": "LLM could write a financial document instead of a cooking recipe",
      "severity": "low"
    }
  ],
  "lens_4_conflicts": [],
  "clean": false,
  "adjustments": [],
  "clarifying_questions": [
    {
      "id": "essence_q_001",
      "finding_id": "lens1_subject_cake",
      "lens": "lens_1",
      "finding_summary": "'cake' is ambiguous — could be any type",
      "question": "What type of cake?",
      "options": ["vanilla", "chocolate", "carrot", "cheesecake", "other"],
      "severity": "high"
    },
    {
      "id": "essence_q_002",
      "finding_id": "lens2_assump_no_allergies",
      "lens": "lens_2",
      "finding_summary": "No dietary restrictions stated",
      "question": "Any dietary restrictions or allergies to consider?",
      "options": ["none", "gluten-free", "dairy-free", "vegan", "nut-free", "other"],
      "severity": "medium"
    }
  ],
  "summary": "Found 1 subjective term (high), 1 hidden assumption (medium), 1 literal trap (low). 2 clarifying questions generated."
}
```

## Rules

- **Never skip** — every stage must pass the Four Lenses before invocation
- **Never increment attempts** — essence loop is internal to the pre-stage gate
- **Never escalate Lens 4** — always escalate to user, never resolve yourself
- **Always assign severity** — based on IMPACT of ambiguity, not finding type
- **Always assign finding_id** — unique, descriptive, stable across retries
- **Always link questions to findings** — every question references a finding_id
- **Always run BEFORE stage** — essence validates inputs, not outputs
- **Bound retries** — max 5 essence retries per stage (configurable)
- **Do not re-ask resolved findings** — check `state.essence.resolved_findings`
- **Do not re-ask clarified items** — check `state.work_item.clarifications.answers`

## Anti-Patterns

- **Never skip because "it's obvious"** — obvious is where the traps live
- **Never invent your own definition** for a subjective term and proceed
- **Never resolve conflicting priorities yourself** — ask the user
- **Never use the check as a delay tactic** — keep it tight, move fast
- **Never ask more than max_questions_per_request questions** — batch, then wait
- **Never downgrade severity in questions** — question severity must mirror finding severity
- **Never generate a question without a finding_id** — every question must reference a finding
