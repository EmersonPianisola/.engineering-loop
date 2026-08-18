---
name: architecture-reviewer
id: architecture-reviewer
version: 1.0.0
type: skill
stage: arch.review
---

# Skill: Architecture Reviewer

## Objective
Perform cross-artifact review of all architecture documents: requirements, solution design, and any supplementary artifacts. Identify gaps, inconsistencies, and risks. Produce a consolidated architecture document that resolves all findings.

## Inputs
- Architecture requirements (`arch-requirements.md`)
- Solution design (`arch-solution.md`)
- Any supplementary architecture artifacts
- Stage context: `state.stages.arch.review`

## Permitted Tools
- `read`: Read all architecture artifacts
- `glob`: Find architecture files
- `grep`: Search for cross-references, TODOs, inconsistencies

## Review Dimensions

### 1. Cross-Artifact Consistency

Verify that all architecture artifacts tell a consistent story:

| Check | Between | What to Look For |
|-------|---------|-----------------|
| **Terminology** | All artifacts | Same terms for same concepts, no ambiguity |
| **Component names** | Requirements ↔ Solution | Every required component exists in solution |
| **Data models** | Requirements ↔ Solution | Same entities, attributes, relationships |
| **API contracts** | Requirements ↔ Solution | Same endpoints, methods, schemas |
| **Non-functional requirements** | Requirements ↔ Solution | Every NFR addressed by a design decision |
| **Assumptions** | All artifacts | No contradictory assumptions |
| **Dependencies** | Requirements ↔ Solution | Every dependency accounted for |

### 2. Gap Analysis

Identify requirements that have no corresponding design decision:

```markdown
## Gap Analysis

| Requirement | Status | Location | Action |
|-------------|--------|----------|--------|
| {REQ-001: Real-time notifications} | COVERED | arch-solution.md#L45 | None |
| {REQ-002: Multi-tenant isolation} | COVERED | arch-solution.md#L78 | None |
| {REQ-003: Audit logging} | GAP | — | Add design section |
| {REQ-004: Data retention policy} | PARTIAL | arch-solution.md#L112 | Expand with retention rules |
| {REQ-005: Rate limiting} | GAP | — | Add API gateway config |
```

**Gap severity:**
- **BLOCKING:** Core functionality missing from design
- **HIGH:** Important feature missing, impacts user experience
- **MEDIUM:** Nice-to-have missing, can be deferred
- **LOW:** Documentation gap, no functional impact

### 3. Quality Attribute Evaluation

Evaluate architecture against quality attributes (ATAM method):

| Attribute | Scenario | Rating | Evidence |
|-----------|---------|--------|----------|
| **Performance** | Handle 10K concurrent users | {Met / Partially Met / Not Met} | {Design decision reference} |
| **Scalability** | 10x data growth in 2 years | {Met / Partially Met / Not Met} | {Design decision reference} |
| **Availability** | 99.9% uptime SLA | {Met / Partially Met / Not Met} | {Design decision reference} |
| **Security** | OWASP Top 10 mitigated | {Met / Partially Met / Not Met} | {Design decision reference} |
| **Maintainability** | New feature in < 2 weeks | {Met / Partially Met / Not Met} | {Design decision reference} |
| **Observability** | Debug issue in < 30 min | {Met / Partially Met / Not Met} | {Design decision reference} |

### 4. Risk Assessment

```markdown
## Risk Assessment

| Risk | Likelihood | Impact | Mitigation | Owner |
|------|-----------|--------|------------|-------|
| {Description} | High/Medium/Low | High/Medium/Low | {Mitigation strategy} | {Team/Role} |
```

**Risk categories:**
- **Technical:** Technology risk, integration complexity, performance uncertainty
- **Operational:** Deployment complexity, monitoring gaps, incident response
- **Business:** Timeline risk, budget risk, scope creep
- **Compliance:** Regulatory risk, data privacy, security audit

### 5. Decision Consolidation

Extract and consolidate all architecture decisions:

```markdown
## Architecture Decisions

| ID | Decision | Rationale | Consequences | Status |
|----|----------|-----------|-------------|--------|
| {AD-NNN} | {What was decided} | {Why this option} | {Trade-offs accepted} | {Accepted / Deferred / Rejected} |
```

## Review Output Structure

```markdown
# Architecture Review Report

## Summary
{Executive summary: overall assessment, key findings, recommendation}

## Consistency Check
{Cross-artifact consistency results}

## Gap Analysis
{Requirements vs solution coverage}

## Quality Attributes
{ATAM evaluation results}

## Risk Assessment
{Identified risks and mitigations}

## Consolidated Architecture
{Resolved architecture document incorporating all findings}

## Recommendations
{Prioritized list of actions before proceeding to implementation}

| Priority | Action | Effort | Rationale |
|----------|--------|--------|-----------|
| P0 | {Action} | {Hours/Days} | {Why this must be done} |
| P1 | {Action} | {Hours/Days} | {Why this should be done} |
```

## Output Format
```json
{
  "stage": "arch.review",
  "status": "done",
  "artifact": "artifacts/architecture/arch-review.md",
  "gaps_found": 3,
  "risks_identified": 5,
  "decisions_consolidated": 12,
  "blocking_issues": 0,
  "complete": true
}
```

## Quality Gates

| Gate | Criteria |
|------|----------|
| **Coverage** | Every requirement traced to solution design |
| **Consistency** | No contradictory statements across artifacts |
| **Risks logged** | All identified risks have mitigation strategies |
| **Decisions consolidated** | All AD-NNN entries captured and resolved |
| **No blocking gaps** | Zero BLOCKING gaps before proceeding |

## Anti-Patterns
- **Never skip cross-artifact checks** — inconsistencies between docs cause implementation errors
- **Never assume requirements are covered** — trace each one explicitly
- **Never ignore quality attributes** — performance and security gaps are expensive to fix later
- **Never defer risk assessment** — unidentified risks become production incidents
- **Never consolidate without evidence** — every decision needs a rationale
- **Never approve with blocking gaps** — P0 gaps must be resolved before implementation
