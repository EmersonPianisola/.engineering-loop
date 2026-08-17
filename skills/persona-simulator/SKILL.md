---
name: persona-simulator
id: persona-simulator
version: 1.0.0
type: skill
stage: qa.human.flow
---

# Skill: Persona Simulator

## Objective
Simulate a real user navigating through the system's flows. Identify friction points, confusion, jargon, and dead ends from the user's perspective.

## Inputs
- System flows, screens, and interactions (from design artifacts or code)
- Persona profile (selected based on target audience)
- Stage context: `state.stages.qa.human.flow`
- Friction threshold from config: `qa_policy.human.max_friction_score`

## Permitted Tools
- `read`: Read design artifacts, source files, screen descriptions
- `glob`: Find relevant files
- `grep`: Search for UI text and labels

## Persona Profiles

### Novice User
- Low technical literacy
- Needs clear guidance at every step
- Confused by jargon and abbreviations
- Needs reassuring error messages

### Power User
- Efficient, keyboard-driven
- Impatient with unnecessary steps
- Wants shortcuts and customization
- Frustrated by forced workflows

### Accessibility User
- Uses screen reader or keyboard only
- Needs proper ARIA labels
- Requires high contrast
- Needs predictable navigation

### Mobile User
- Small screen, limited space
- Intermittent connectivity
- On-the-go, distracted
- Needs touch-friendly targets

## Friction Score Scale
- **0-2**: Minimal friction, intuitive flow
- **3-4**: Moderate friction, some confusion
- **5-6**: Significant friction, user may abandon
- **7-8**: Severe friction, major redesign needed
- **9-10**: Flow is practically unusable

## Output Format
```json
{
  "verdict": "PASS|FAIL|BLOCKED",
  "qa_type": "heuristic",
  "confidence": 0.85,
  "severity": "info|low|medium|high|critical",
  "persona_name": "Novice User",
  "scenario": "Complete checkout flow",
  "friction_score": 3.5,
  "confusion_points": ["Where do I enter promo code?"],
  "jargon_found": ["API key", "endpoint URL"],
  "dead_ends": [],
  "unexpected_states": [],
  "recommendations": ["Move promo code field above billing info"],
  "findings": [],
  "complete": true
}
```

## Mandatory Evidence
- `friction_score` (0-10)
- `confidence` (0-1, your confidence in the assessment)
- `persona_name` (which persona was used)

## Success Criteria
- `friction_score` <= threshold (default 4)
- `confidence` >= minimum (default 0.70)

## Blocking Criteria
- Cannot access UI or flow information
- Confidence below minimum threshold

## Failure Criteria
- `friction_score` > threshold
- Critical confusion points found
- Multiple dead ends in critical flows
