---
name: bmad-user-research
id: bmad-user-research
version: 1.0.0
type: skill
stage: design.user-research
---

# Skill: BMAD User Research

## Objective
Conduct or simulate user research to understand user needs, pain points, behaviors, and context. Produce research findings that inform persona creation, journey mapping, and design decisions. When real users are unavailable, use structured synthetic research methods grounded in industry data.

## Inputs
- PRD (Product Requirements Document)
- Any existing research artifacts
- Work item description
- Stage context: `state.stages.design.user-research`

## Permitted Tools
- `read`: Read PRD, existing research, project documentation
- `glob`: Find relevant project files

## Research Methods

### Primary Research (when real users available)

| Method | Purpose | Output |
|--------|---------|--------|
| **User Interviews** | Deep understanding of needs, motivations, contexts | Transcripts, key quotes, themes |
| **Contextual Inquiry** | Observe users in their natural environment | Field notes, behavioral patterns |
| **Usability Testing** | Evaluate existing or prototype solutions | Task success rates, friction points |
| **Surveys** | Quantitative validation of qualitative findings | Statistical data, trend analysis |

### Synthetic Research (when real users unavailable)

When actual user access is not possible, apply structured synthetic methods:

| Method | Source | Purpose |
|--------|--------|---------|
| **Industry Benchmark Analysis** | Published UX research, usability studies | Ground findings in validated data |
| **Competitive Analysis** | Direct competitor products, reviews | Identify gaps, patterns, opportunities |
| **Proxy Research** | Support tickets, forum posts, app reviews | Extract real user pain points |
| **Persona-Based Scenario Simulation** | Industry persona databases | Simulate user decision paths |

**Synthetic research protocol:**
1. Identify target user segments from PRD/market data
2. For each segment, gather 3+ data sources (industry reports, competitor reviews, support forums)
3. Extract pain points, needs, and behaviors from each source
4. Cross-validate findings across sources — only retain findings supported by 2+ sources
5. Flag assumptions where data is thin

### Competitive Analysis Framework

For each competitor product:

| Dimension | What to Assess |
|-----------|---------------|
| **Onboarding** | First-time user experience, time to value |
| **Core Workflows** | Primary task completion, friction points |
| **Information Architecture** | Navigation clarity, findability |
| **Visual Design** | Aesthetic, consistency, brand alignment |
| **Accessibility** | WCAG compliance, assistive technology support |
| **User Feedback** | App store reviews, G2/Capterra ratings, support tickets |

### Contextual Inquiry Protocol

When observing users (real or proxy):

1. **Setting:** Observe in user's natural environment (physical or digital)
2. **Master-Apprentice:** User does the task, researcher asks "why" at each step
3. **Artifacts:** Document tools, workarounds, and environmental factors
4. **Patterns:** Look for recurring behaviors, not one-off incidents
5. **Contrast:** Compare stated goals vs. actual behavior

## Research Output Structure

### `research-findings.md`

```markdown
# Research Findings

## Research Goals
{What questions this research aimed to answer}

## Methodology
{Methods used, participant count, duration, limitations}

## Key Findings
{Numbered findings, each with evidence and source}

### Finding 1: {Title}
- **Evidence:** {Specific data point, quote, or observation}
- **Source:** {Interview #, survey response, review, etc.}
- **Implication:** {What this means for design decisions}

## User Quotes
{Verbatim quotes that capture user sentiment}

## Pain Points
{Prioritized list of user pain points with severity}

| Pain Point | Severity | Frequency | Source |
|------------|----------|-----------|--------|
| {Description} | High/Medium/Low | {N users} | {Source} |

## Assumptions & Gaps
{Areas where data is insufficient, logged as assumptions for later validation}

| Assumption | Confidence | Validation Plan |
|------------|------------|-----------------|
| {Statement} | High/Medium/Low | {How to validate later} |

## Research Questions
{Open questions that need further investigation}
```

### `research-questions.md`

```markdown
# Research Questions

## Answered
{Questions this research session answered}

## Open
{Questions that need follow-up research}

## Assumptions to Validate
{Assumptions that should be validated before launch}
```

## Quality Gates

| Gate | Criteria |
|------|----------|
| **Source Diversity** | >= 3 distinct data sources or user-validated primary research |
| **Finding Specificity** | Each finding has specific evidence (not generic statements) |
| **Assumption Logging** | All gaps logged as assumptions with confidence level |
| **Cross-Validation** | Key findings supported by 2+ sources |
| **Actionability** | Each finding has a stated design implication |

## Output Format
```json
{
  "stage": "design.user-research",
  "status": "done",
  "artifact": "artifacts/design/user-research/research-findings.md",
  "findings_count": 8,
  "sources_count": 5,
  "assumptions_count": 3,
  "pain_points_count": 6,
  "complete": true
}
```

## Anti-Patterns
- **Never fabricate user quotes** — if no real users, use proxy data with clear attribution
- **Never skip competitive analysis** — understanding alternatives is as important as understanding users
- **Never conflate wants with needs** — users describe symptoms, not solutions
- **Never assume one user segment** — always identify and differentiate segments
- **Never skip assumption logging** — untracked assumptions become untracked risks
- **Never present opinions as findings** — every finding must have evidence
