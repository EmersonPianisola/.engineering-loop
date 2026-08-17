---
name: ux-auditor
id: ux-auditor
version: 1.0.0
type: skill
stage: qa.human.ux
---

# Skill: UX Auditor

## Objective
Audit user experience quality: WCAG accessibility compliance, cognitive load, step bloat, and navigation consistency.

## Inputs
- UI components, screens, and interactions
- Design system tokens and components
- Stage context: `state.stages.qa.human.ux`
- Friction threshold from config: `qa_policy.human.max_friction_score`

## Permitted Tools
- `read`: Read source files, components, design tokens
- `glob`: Find UI components
- `grep`: Search for accessibility attributes, labels

## WCAG 2.1 AA Checklist

| Criterion | Check |
|-----------|-------|
| 1.1.1 Non-text Content | Alt text on images, icons, media |
| 1.3.1 Info and Relationships | Semantic HTML, heading hierarchy |
| 1.4.3 Contrast | Text contrast ratio >= 4.5:1 |
| 2.1.1 Keyboard | All functionality keyboard accessible |
| 2.4.1 Bypass Blocks | Skip navigation links |
| 2.4.6 Headings and Labels | Descriptive headings and labels |
| 3.3.1 Error Identification | Clear error messages |
| 4.1.2 Name, Role, Value | ARIA attributes correct |

## Cognitive Walkthrough
For each critical task:
1. Will the user know what to do?
2. Will the user notice the correct action?
3. Will the user know what happens when they act?
4. Will the user understand the feedback?

## Cognitive Load Assessment
- **Low**: Intuitive, minimal mental effort
- **Medium**: Requires some learning, acceptable
- **High**: Overwhelming, needs simplification

## Step Bloat Analysis
- Flag flows requiring > 5 steps
- Identify redundant confirmations
- Detect unnecessary screen splits

## Output Format
```json
{
  "verdict": "PASS|FAIL|BLOCKED",
  "qa_type": "heuristic",
  "confidence": 0.85,
  "severity": "info|low|medium|high|critical",
  "friction_score": 3.0,
  "wcag_violations": ["Low contrast on CTA button"],
  "cognitive_load": "medium",
  "step_bloat": 0,
  "navigation_issues": [],
  "accessibility_issues": [],
  "recommendations": ["Increase CTA button contrast"],
  "findings": [],
  "complete": true
}
```

## Mandatory Evidence
- `friction_score` (0-10)
- `confidence` (0-1)

## Success Criteria
- `friction_score` <= threshold (default 4)
- No critical WCAG violations
- `confidence` >= minimum (default 0.70)

## Blocking Criteria
- No UI project (set `blocked_reason: NOT_APPLICABLE`)
- Cannot access design artifacts

## Failure Criteria
- `friction_score` > threshold
- Critical WCAG violations found
- Cognitive load is "high"
