---
name: bmad-personas
id: bmad-personas
version: 1.0.0
type: skill
stage: design.personas
---

# Skill: BMAD Personas & Journey Maps

## Objective
Create data-driven personas and journey maps that translate research findings into actionable design targets. Each persona represents a distinct user segment with specific goals, behaviors, and pain points. Journey maps trace persona interactions through key flows, identifying friction points and opportunities.

## Inputs
- Research findings (`research-findings.md`)
- PRD and product requirements
- User quotes and pain points
- Stage context: `state.stages.design.personas`

## Permitted Tools
- `read`: Read research findings, PRD, project documentation
- `glob`: Find relevant project files

## Persona Creation

### Structure

Each persona follows a standardized structure:

```markdown
## Persona: {Name}

### Demographics
- **Age range:** {Range}
- **Role/Profession:** {Title, industry}
- **Technical literacy:** {Novice / Intermediate / Expert}
- **Context of use:** {Where, when, how they use the product}

### Goals
- **Primary goal:** {What they want to accomplish}
- **Secondary goals:** {Supporting objectives}
- **Business alignment:** {How their goals serve business objectives}

### Frustrations
- {Pain point 1 — tied to research evidence}
- {Pain point 2 — tied to research evidence}
- {Pain point 3 — tied to research evidence}

### Behaviors
- **Decision style:** {Analytical / Intuitive / Social / Habitual}
- **Tool preferences:** {What tools they already use}
- **Information needs:** {What information they need to make decisions}
- **Work patterns:** {How they work: solo, collaborative, scheduled, ad-hoc}

### Quote
> "{Representative quote from research}"

### Design Implications
- {Specific design recommendations for this persona}
- {Accessibility considerations}
- {Feature priorities}
```

### Persona Quality Criteria

| Criterion | Standard |
|-----------|----------|
| **Evidence-based** | Each attribute tied to research finding |
| **Distinct** | No two personas overlap in primary goals |
| **Actionable** | Clear design implications for each |
| **Complete** | Covers all major user segments from research |
| **Realistic** | Based on observed behavior, not stereotypes |

### Persona Archetypes

Common archetype patterns (adapt to domain):

| Archetype | Characteristics | Design Priority |
|-----------|----------------|-----------------|
| **Efficiency-Driven** | Wants to complete tasks fast, values shortcuts | Power features, keyboard shortcuts, automation |
| **Exploration-Driven** | Learns by clicking around, values discovery | Progressive disclosure, guided tours, tooltips |
| **Risk-Averse** | Hesitant to commit, needs reassurance | Undo/redo, confirmation dialogs, clear status |
| **Social** | Collaborates, shares, seeks validation | Sharing features, comments, team visibility |
| **Novice** | First-time user, needs guidance | Onboarding, defaults, error prevention |
| **Expert** | Power user, values control | Customization, advanced settings, bulk operations |

## Journey Maps

### Structure

Each journey map follows a narrative structure with a named protagonist:

```markdown
## Journey: {Flow Name}
**Protagonist:** {Persona name}
**Goal:** {What they're trying to accomplish}
**Context:** {When and why they initiate this flow}

### Beat 1: {Phase Name} — {Emotional State}
- **Action:** {What the user does}
- **Thinking:** {What's on their mind}
- **Feeling:** {Emotional state: curious, frustrated, confident, confused}
- **Touchpoint:** {Which part of the product they interact with}
- **Friction:** {Pain points, if any}
- **Opportunity:** {Design improvement}

### Beat 2: {Phase Name} — {Emotional State}
...

### Climax Beat
The moment of truth — where the user either succeeds or abandons the flow.
- **Success criteria:** {What makes this moment work}
- **Failure mode:** {What causes abandonment}
- **Design priority:** {What to optimize}

### Resolution
- **Outcome:** {What happens when the flow completes}
- **Satisfaction:** {How the user feels about the experience}
- **Next action:** {What they do next}
```

### Journey Map Quality Criteria

| Criterion | Standard |
|-----------|----------|
| **Named protagonist** | Each journey tied to a specific persona |
| **Emotional arc** | Clear emotional states per beat |
| **Climax identified** | Critical decision point highlighted |
| **Friction documented** | Pain points with severity |
| **Opportunities surfaced** | Actionable design improvements |
| **All key flows covered** | Every major user goal has a journey |

### Journey Map Dimensions

For each beat, consider:

| Dimension | Questions |
|-----------|-----------|
| **Cognitive load** | How much thinking does the user need to do? |
| **Emotional state** | Are they confident, anxious, frustrated, curious? |
| **Environmental context** | Are they distracted, in a hurry, multitasking? |
| **Technical context** | Device, network, screen size, accessibility needs |
| **Social context** | Alone, collaborating, being observed? |

## Output Format
```json
{
  "stage": "design.personas",
  "status": "done",
  "artifact": "artifacts/design/personas/personas.md",
  "personas_count": 4,
  "journeys_count": 6,
  "complete": true
}
```

## Output Artifacts

| File | Content |
|------|---------|
| `personas.md` | All personas with full structure |
| `journey-maps.md` | All journey maps with beats and climax |

## Anti-Patterns
- **Never create personas without evidence** — every attribute must trace to research
- **Never make personas stereotypes** — "Tech-savvy Tom" is not a persona
- **Never skip the climax beat** — the moment of truth is where design matters most
- **Never map only happy paths** — journeys must include error states and edge cases
- **Never ignore emotional states** — users make decisions based on feelings, not logic
- **Never create more than 5 personas** — beyond that, the team can't retain them
