---
name: bmad-ideation
version: 2.0.0
role: design
domain: ideation-decomposition
stage: init > ideate
description: >
  Transforms raw, under-specified work items into rich, decomposed work flows
  using BMAD-derived patterns: Party Mode (9-role analysis), Brainstorming
  (62 techniques), SDD extraction, impact-gated decomposition, Hourglass Framework,
  and idea evaluation matrix.
---

# BMAD Ideation Skill

## Purpose

Transform a raw, under-specified work item into a concrete, decomposed set of
atomic tasks with acceptance criteria, code maps, edge cases, and impact
classification. Uses BMAD-derived patterns embedded in
`{reference-root}/bmad-ideation-patterns.md` and the Hourglass Ideation Framework
— no external BMAD installation required.

## Inputs

- `state.work_item` — raw work item (ad-hoc user request)
- `{reference-root}/bmad-ideation-patterns.md` — embedded BMAD patterns

## Output

- `{artifact-root}/ideation/ideation-{slug}.md` — Party Mode + Brainstorming log
- `{artifact-root}/ideation/sdd-{slug}.md` — Software Design Document
- `{artifact-root}/ideation/flows-{slug}.md` — Decomposed work flows
- Updated `state.work_item` — enriched with all fields

## The Hourglass Ideation Framework

The ideation process follows the Hourglass Framework: diverge wide, then converge narrow.

```
Phase 1 (Diverge): Party Mode → Brainstorming → Many ideas
Phase 2 (Evaluate):  Idea Evaluation Matrix → Score and compare
Phase 3 (Converge): SDD Extraction → Decomposition → Focused tasks
```

### Divergence Phase
- **Goal:** Maximize idea quantity and diversity
- **Methods:** Party Mode (multiple perspectives), Brainstorming (multiple techniques)
- **Rule:** No criticism during divergence — all ideas are valid

### Evaluation Phase
- **Goal:** Assess ideas against objective criteria
- **Method:** Idea Evaluation Matrix (see below)
- **Rule:** Score each idea independently before comparing

### Convergence Phase
- **Goal:** Select best ideas, decompose into actionable tasks
- **Methods:** SDD extraction, impact-gated decomposition
- **Rule:** Every selected idea must trace to a task

## Execution Phases

### Phase 1: Party Mode Analysis (9 Roles)

Load the 9 role definitions from the reference document. For each role, analyze
the raw work item independently and produce:

```markdown
## Role: {Role Name} ({Focus})

**Requirements:**
- What this role sees as necessary

**Risks:**
- What could go wrong from this perspective

**Opportunities:**
- Hidden value this role identifies

**Gaps:**
- What's missing that this role needs
```

Roles: Product Manager (John), Business Analyst (Mary), Architect (Winston),
Developer (Amelia), UX Designer (Sally), Scrum Master (Bob), Test Architect
(Murat), Technical Writer (Paige), Product Strategist (John — strategy lens).

**Key rule:** Roles run in parallel conceptually. Each role's output is
independent — no role should reference another role's findings. Conflicts between
roles are valuable and must be preserved.

### Phase 2: Brainstorming (2-3 Techniques)

Select 2-3 techniques from the 62 available based on the work item's domain.
Use the **Technique Selection Heuristics** table in the reference document.

For each selected technique:
1. State the technique name and category
2. Apply the facilitation prompt to the work item
3. Generate 3-7 concrete ideas, alternatives, or edge cases
4. Tag each idea with its source technique

Output format:

```markdown
## Technique: {Name} ({Category})

**Prompt applied:** {prompt text}

**Ideas generated:**
1. [idea] — {brief rationale}
2. [idea] — {brief rationale}
3. ...
```

### Phase 3: Idea Evaluation Matrix

Score each idea from Party Mode + Brainstorming:

| Idea | Value (1-5) | Feasibility (1-5) | Effort (1-5, 5=low) | Risk (1-5, 5=low) | Score | Decision |
|------|-------------|-------------------|---------------------|-------------------|-------|----------|
| [description] | 4 | 3 | 4 | 3 | 14/20 | Include |

**Scoring:** `Value + Feasibility + Effort + Risk`. Threshold: >= 14/20 to include.

**Convergence techniques:**
- **Impact/Effort Matrix:** Plot ideas on 2x2 grid; prioritize high-impact, low-effort
- **Dot Voting:** Each Party Mode role gets 3 dots to distribute across ideas
- **Must/Should/Could/Won't (MoSCoW):** Categorize ideas by priority

### Phase 4: SDD Extraction

Compile Party Mode findings + evaluated Brainstorming ideas into a structured Software
Design Document following the SDD template in the reference document.

Sections:
1. Overview (title, intent, scope, non-goals)
2. Functional Requirements (FR-NNN, source role, priority)
3. Non-Functional Requirements (performance, security, reliability, etc.)
4. Interfaces & Contracts (APIs, external services, data sources, UI)
5. Data & State (entities, transitions, flow, migration)
6. Components & Architecture (diagram, responsibilities, dependencies, tech choices)
7. Edge Cases & Error Paths (happy paths, error paths, edge cases, recovery)
8. Constraints & Risks (technical, business, with mitigation)
9. Decomposition — Atomic Sub-Tasks (task table)
10. Success Metrics (quantitative, qualitative, validation)

**Traceability rule:** Every FR-NNN must cite its source: which Party Mode role
identified it, or which brainstorming technique generated it.

### Phase 5: Decomposition + Impact Gate

Convert the SDD's task table into executable work flows with impact
classification.

#### Task Format

```markdown
## Task T-NNN: {Description}

**Acceptance Criteria:**
- Given {precondition}
- When {action}
- Then {expected outcome}

**Files:** {file paths, or "new: {path}" for new files}
**Dependencies:** T-NNN, T-NNN (or "None")
**Impact:** {Low | Medium | High | Critical}
**Rationale:** {why this impact level}
```

#### Impact Classification

| Level | Criteria |
|-------|----------|
| **Low** | ≤3 files, ≤3 sub-tasks, known domain, no external integrations |
| **Medium** | ≤10 files, ≤8 sub-tasks, may have integrations, no new domains |
| **High** | >10 files, new domain, external integrations, architectural impact |
| **Critical** | Residual ambiguity, user-facing breaking change, security/PII, regulatory impact, architectural pattern change |

#### Gate Enforcement

- **Low/Medium/High:** Auto-execute. Record in `state.ideation.gates_passed`.
- **Critical:** **PAUSE**. Present the critical findings to the user:
  - List each critical item with its rationale
  - Ask: "These items require your confirmation before proceeding. Confirm or adjust?"
  - Await user response
  - If confirmed: proceed, record in `state.ideation.critical_confirmed`
  - If adjusted: re-run ideation on the adjusted items only

## Post-Execution

1. Write all three artifacts (ideation log, SDD, flows)
2. Update `state.work_item` with enriched fields:
   - `title` — from SDD overview
   - `intent` — from SDD overview
   - `acceptance_criteria` — compiled from task ACs
   - `code_map` — from task files
   - `edge_cases` — from SDD section 7
   - `non_goals` — from SDD overview
   - `success_metrics` — from SDD section 10
   - `impact_classification` — overall: highest individual task level
3. Set `state.ideation.completed = true`
4. Set `state.ideation.artifacts = { ideation_log, sdd, flows }`
5. Set `state.ideation.techniques_used = [list]`
6. Set `state.ideation.role_conflicts = [list of conflicting findings]`
7. Set `state.ideation.evaluation_matrix = [matrix data]`

## Anti-Patterns

- **Never skip Party Mode** — multi-perspective analysis is the foundation
- **Never use all 62 techniques** — select 2-3; more creates noise, not signal
- **Never resolve role conflicts** — preserve them; they indicate real tensions
- **Never skip traceability** — every requirement must cite its source
- **Never auto-execute Critical** — human confirmation is mandatory
- **Never produce unstructured output** — follow the SDD template exactly
- **Never skip the evaluation matrix** — un-scored ideas lead to biased selection
- **Never converge before diverging** — premature convergence kills creativity
