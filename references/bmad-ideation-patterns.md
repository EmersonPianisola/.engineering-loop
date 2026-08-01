---
name: bmad-ideation-patterns
id: bmad-ideation
version: 1.0.0
type: reference
description: 'BMAD-derived patterns embedded for offline use. Party Mode roles, Brainstorming techniques, SDD structure. Extracted from BMAD-METHOD framework.'
---

# BMAD Ideation Patterns — Embedded Reference

Patterns extracted from the BMAD-METHOD framework for use by the `bmad-ideation` skill. Self-contained — no external files required.

## Party Mode Roles (9 Perspectives)

Each role analyzes a work item from a distinct professional lens. All 9 run in parallel on the raw input.

| Role | Name | Focus | Key Questions |
|------|------|-------|---------------|
| **Product Manager** | John | Business value, market fit, prioritization | Why this? Who benefits? What's the MVP? What risks the business case? |
| **Business Analyst** | Mary | Requirements elicitation, stakeholder needs, market research | What are the root causes? What evidence supports this? What stakeholder voices are missing? |
| **Architect** | Winston | System design, scalability, technology selection | How does this fit the existing architecture? What are the integration points? What boring technology solves this? |
| **Developer** | Amelia | Implementation details, code structure, TDD | What files change? What's the red-green-refactor path? What tests cover each task? |
| **UX Designer** | Sally | User experience, interaction flows, accessibility | What does the user feel? Where are the friction points? What edge cases affect the user? |
| **Product Manager (Strategy)** | John | Competitive analysis, user behavior, data-driven decisions | What data backs this? What's the measurable impact? What assumptions need validation? |
| **Scrum Master** | Bob | Story preparation, sprint planning, agile flow | Is this story-ready? Are acceptance criteria clear? What's the definition of done? |
| **Test Architect** | Murat | Risk-based testing, quality gates, CI/CD | What's the risk vs value? What tests mirror usage patterns? Where is flaky test debt? |
| **Technical Writer** | Paige | Documentation, knowledge transfer, clarity | What needs to be documented? What concepts need explanation? How do users find this? |

### Role Output Format

Each role produces:
- **Requirements:** What this role sees as necessary
- **Risks:** What could go wrong from this perspective
- **Opportunities:** Hidden value this role identifies
- **Gaps:** What's missing that this role needs

## Brainstorming Techniques (62 techniques, 10 categories)

Select 2-3 techniques per session based on domain analysis. Each technique has a facilitation prompt.

### Creative (11 techniques)

| Technique | Prompt |
|-----------|--------|
| What If Scenarios | "What if [constraint] didn't exist? What if the opposite were true?" |
| Analogical Thinking | "How would [unrelated domain] solve this problem?" |
| Reversal Inversion | "What if we did the exact opposite? What assumptions does that expose?" |
| First Principles Thinking | "What are the fundamental truths? Strip away all assumptions." |
| Forced Relationships | "Combine [concept A] with [concept B]. What emerges?" |
| Time Shifting | "How was this solved 50 years ago? How will it be solved in 50 years?" |
| Metaphor Mapping | "If this system were a [natural phenomenon], how would it behave?" |
| Cross-Pollination | "What can we borrow from [different industry]?" |
| Concept Blending | "Merge [idea A] and [idea B] into something new." |
| Reverse Brainstorming | "How could we cause this problem? Now reverse each answer." |
| Sensory Exploration | "Describe this experience through each of the five senses." |

### Deep Analysis (8 techniques)

| Technique | Prompt |
|-----------|--------|
| Five Whys | "Why? Why? Why? Why? Why? — drill to root cause." |
| Morphological Analysis | "List independent dimensions. Combine one from each." |
| Provocation Technique | "Imagine [absurd statement]. What does it reveal?" |
| Assumption Reversal | "List assumptions. Reverse each. Explore the flipped world." |
| Question Storming | "Generate only questions. No answers. Cluster by theme." |
| Constraint Mapping | "What constraints exist? Which are real vs perceived?" |
| Failure Analysis | "How could this fail? At what point? With what impact?" |
| Emergent Thinking | "What pattern emerges when we look at all pieces together?" |

### Wild (8 techniques)

| Technique | Prompt |
|-----------|--------|
| Chaos Engineering | "What breaks if [component] fails randomly?" |
| Guerrilla Gardening | "Plant an idea in an unexpected place. What grows?" |
| Pirate Code | "What rules are worth breaking? What would a pirate do?" |
| Zombie Apocalypse | "With zero resources, how do we survive? What's essential?" |
| Anti-Solution | "Design the worst possible solution. Invert it." |
| Quantum Superposition | "Hold two contradictory ideas simultaneously. What's the synthesis?" |
| Elemental Forces | "If fire/water/earth/air shaped this, how would each transform it?" |
| Drunk History | "Retell this without filters. What raw truth surfaces?" |

### Structured (7 techniques)

| Technique | Prompt |
|-----------|--------|
| SCAMPER | Substitute, Combine, Adapt, Modify, Put-to-other-uses, Eliminate, Reverse |
| Six Thinking Hats | White (facts), Red (emotions), Black (caution), Yellow (optimism), Green (creativity), Blue (process) |
| Mind Mapping | "Central concept → branches → sub-branches. What connections emerge?" |
| Resource Constraints | "Solve this with 10% of the budget. Then with 1%." |
| Decision Tree Mapping | "Map each decision point. What paths lead to success?" |
| Solution Matrix | "Row: approaches. Column: criteria. Score each cell." |
| Trait Transfer | "What trait makes [successful thing] work? Transfer it here." |

### Introspective Delight (6 techniques)

| Technique | Prompt |
|-----------|--------|
| Inner Child Conference | "What would your curious 8-year-old self ask about this?" |
| Shadow Work Mining | "What are we avoiding? What uncomfortable truth is hidden?" |
| Values Archaeology | "What core value does this serve? Dig deeper." |
| Future Self Interview | "Your future self (5 years) looks back. What do they say worked?" |
| Body Wisdom Dialogue | "Where do you feel resistance? What does your gut say?" |
| Permission Giving | "What would you do if you knew you couldn't fail?" |

### Theatrical (6 techniques)

| Technique | Prompt |
|-----------|--------|
| Time Travel Talk Show | "Interview experts from past, present, and future about this." |
| Alien Anthropologist | "An alien observes this for the first time. What seems strange?" |
| Dream Fusion Laboratory | "Describe the ideal solution as a dream. Extract principles." |
| Emotion Orchestra | "How does each emotion (joy, fear, anger, sadness) view this?" |
| Parallel Universe Cafe | "In a universe where [opposite rule], how is this solved?" |
| Persona Journey | "Walk through this as [archetype]. What do they experience?" |

### Collaborative (5 techniques)

| Technique | Prompt |
|-----------|--------|
| Yes And Building | "Each idea builds on the last. No negation. Only addition." |
| Brain Writing Round Robin | "Silent writing → pass → build → pass → build." |
| Random Stimulation | "Pick a random word. Force a connection to the problem." |
| Role Playing | "Speak as [stakeholder]. What do they need? What do they fear?" |
| Ideation Relay Race | "30 seconds per person. Chain ideas. No repetition." |

### Cultural (4 techniques)

| Technique | Prompt |
|-----------|--------|
| Indigenous Wisdom | "What traditional knowledge applies here?" |
| Fusion Cuisine | "Blend two cultural approaches. What emerges?" |
| Ritual Innovation | "What ritual or ceremony would embody this solution?" |
| Mythic Frameworks | "Which archetype (hero, mentor, trickster) frames this problem?" |

### Quantum (3 techniques)

| Technique | Prompt |
|-----------|--------|
| Observer Effect | "How does measuring this change it?" |
| Entanglement Thinking | "What seems unrelated but is deeply connected?" |
| Superposition Collapse | "Hold all options open. What constraint forces the right choice?" |

### Biomimetic (3 techniques)

| Technique | Prompt |
|-----------|--------|
| Nature's Solutions | "How does nature solve a similar problem?" |
| Ecosystem Thinking | "What's the ecosystem here? Who depends on whom?" |
| Evolutionary Pressure | "What pressure would evolve the best solution?" |

### Technique Selection Heuristics

| Work Item Type | Recommended Techniques |
|----------------|------------------------|
| Vague idea | First Principles, Five Whys, What If Scenarios |
| Feature request | SCAMPER, Six Thinking Hats, Reverse Brainstorming |
| Architecture decision | Morphological Analysis, Failure Analysis, Ecosystem Thinking |
| UX problem | Alien Anthropologist, Persona Journey, Sensory Exploration |
| Performance issue | Constraint Mapping, Resource Constraints, Nature's Solutions |
| New domain | Cross-Pollination, Analogical Thinking, Indigenous Wisdom |
| Integration | Entanglement Thinking, Forced Relationships, Solution Matrix |

## SDD (Software Design Document) Structure

Output template for the SDD Extraction phase. Compile Party Mode findings + Brainstorming into structured design.

### 1. Overview

- **Title:** One-line summary
- **Intent:** What problem this solves (not how)
- **Scope:** In scope / Out of scope
- **Non-Goals:** Explicitly what this does not address

### 2. Functional Requirements

Numbered list of user-facing behaviors. Each requirement:
- **ID:** FR-001, FR-002, ...
- **Description:** One-sentence behavior
- **Source:** Which Party Mode role identified it
- **Priority:** Must / Should / Could / Won't

### 3. Non-Functional Requirements

- **Performance:** Response time, throughput, latency targets
- **Scalability:** User count, data volume, growth factors
- **Security:** Auth, authz, data protection, compliance
- **Reliability:** Uptime, fault tolerance, recovery
- **Accessibility:** WCAG level, screen reader, keyboard nav
- **Observability:** Logging, metrics, tracing

### 4. Interfaces & Contracts

- **API Endpoints:** Method, path, request/response schema
- **External Services:** Third-party APIs, webhooks, message queues
- **Data Sources:** Databases, caches, file storage
- **User Interfaces:** Screens, components, states

### 5. Data & State

- **Entities:** Core domain objects, relationships
- **State Transitions:** Lifecycle states, transition rules
- **Data Flow:** Where data originates, transforms, persists
- **Migration:** Schema changes, backward compatibility

### 6. Components & Architecture

- **Component Diagram:** Boxes and lines (text-based)
- **Responsibilities:** What each component owns
- **Dependencies:** Internal and external
- **Technology Choices:** Frameworks, libraries, languages — with rationale

### 7. Edge Cases & Error Paths

- **Happy Paths:** Expected flow
- **Error Paths:** Network failure, invalid input, empty state, permission denied, concurrent modification
- **Edge Cases:** Boundary values, race conditions, resource exhaustion
- **Recovery:** Rollback, retry, compensation

### 8. Constraints & Risks

- **Technical Constraints:** Platform limits, legacy dependencies, budget
- **Business Constraints:** Timeline, regulatory, contractual
- **Risks:** Identified by Party Mode roles, with mitigation strategy

### 9. Decomposition — Atomic Sub-Tasks

| Task ID | Description | Acceptance Criteria | Files Affected | Dependencies | Impact Level |
|---------|-------------|---------------------|----------------|--------------|--------------|
| T-001 | ... | Given/When/Then | ... | None | Low/Medium/High/Critical |

### 10. Success Metrics

- **Quantitative:** Performance numbers, error rates, user metrics
- **Qualitative:** User satisfaction, developer experience
- **Validation:** How each metric is measured

## Impact Gate Classification

| Level | Criteria | Action |
|-------|----------|--------|
| **Low** | ≤3 files, ≤3 tasks, known domain, no external integrations | Auto-execute, no pause |
| **Medium** | ≤10 files, ≤8 tasks, may have integrations, no new domains | Auto-execute, log to STATE.md |
| **High** | >10 files, new domain, external integrations, architectural impact | Log detailed rationale, proceed without pause |
| **Critical** | Ambiguity remains after ideation, user-facing impact, breaking changes, security implications | **PAUSE** — present findings and request explicit user confirmation |

### Critical Gate Triggers

Any of these force a Critical gate:
- Residual ambiguity in core intent after Party Mode analysis
- Breaking API/UI changes affecting existing users
- Security-sensitive data handling (PII, payment, auth)
- Architectural pattern change (e.g., sync → async, monolith → microservices)
- Regulatory/compliance implications (GDPR, HIPAA, SOC2)
- Performance SLA impact (response time degradation)

## Anti-Patterns

- **Never skip Party Mode** — even simple ideas benefit from multi-perspective analysis
- **Never use all 62 techniques** — select 2-3 based on domain; more creates noise
- **Never assume single-role consensus** — conflicting role findings are valuable, not errors
- **Never skip the SDD structure** — unstructured output defeats the decomposition purpose
- **Never auto-execute Critical items** — human confirmation is mandatory
- **Never discard role conflicts** — they indicate Lens 4 tensions that need documentation
