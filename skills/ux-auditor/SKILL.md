---
name: ux-auditor
id: ux-auditor
version: 2.0.0
type: skill
stage: qa.human.ux
---

# Skill: UX Auditor

## Objective
Audit user experience quality: WCAG 2.2 accessibility compliance, cognitive load, step bloat, navigation consistency, Nielsen's heuristics, and quantitative SEQ/SUS scoring.

## Inputs
- UI components, screens, and interactions
- Design system tokens and components
- Stage context: `state.stages.qa.human.ux`
- Friction threshold from config: `qa_policy.human.max_friction_score`

## Permitted Tools
- `read`: Read source files, components, design tokens
- `glob`: Find UI components
- `grep`: Search for accessibility attributes, labels

## WCAG 2.2 AA Checklist

| Criterion | Check |
|-----------|-------|
| 1.1.1 Non-text Content | Alt text on images, icons, media |
| 1.3.1 Info and Relationships | Semantic HTML, heading hierarchy |
| 1.3.4 Orientation | Content usable in both portrait and landscape |
| 1.3.5 Identify Input Purpose | Autocomplete attributes on form fields |
| 1.4.3 Contrast (Minimum) | Text contrast ratio >= 4.5:1 |
| 1.4.4 Resize Text | Text scalable to 200% without loss |
| 1.4.11 Non-text Contrast | UI components and icons >= 3:1 contrast |
| 1.4.12 Text Spacing | Line-height 1.5, spacing 3x after paragraphs |
| 2.1.1 Keyboard | All functionality keyboard accessible |
| 2.1.2 No Keyboard Trap | Focus can move away from any element |
| 2.4.1 Bypass Blocks | Skip navigation links |
| 2.4.2 Page Titled | Descriptive page titles |
| 2.4.3 Focus Order | Logical tab order |
| 2.4.4 Link Purpose | Link text conveys destination |
| 2.4.5 Multiple Ways | More than one way to find content |
| 2.4.7 Focus Visible | Visible focus indicator |
| 2.5.1 Pointer Gestures | Single-click/ tap alternatives |
| 2.5.2 Target Size | Touch targets >= 44x44 CSS pixels |
| 2.5.8 Target Size (Minimum) | 24x24 CSS pixels minimum |
| 3.1.1 Language of Page | `lang` attribute on `<html>` |
| 3.2.4 Consistent Identification | Same components identified consistently |
| 3.3.1 Error Identification | Clear error messages |
| 3.3.2 Labels or Instructions | Labels provided for all inputs |
| 3.3.7 Redundant Entry | Minimize repeated information entry |
| 4.1.2 Name, Role, Value | ARIA attributes correct |
| 4.1.3 Status Messages | Status messages in `role="status"` or `aria-live` |

## Nielsen's 10 Usability Heuristics

| # | Heuristic | Check |
|---|-----------|-------|
| 1 | Visibility of System Status | Does the system keep users informed via appropriate feedback within reasonable time? |
| 2 | Match Between System and Real World | Does the system use users' language, words, and concepts — not system-oriented terms? |
| 3 | User Control and Freedom | Do users have emergency exits (undo/redo, cancel, back) without confirmation dialogs? |
| 4 | Consistency and Standards | Does the system follow platform conventions and internal consistency? |
| 5 | Error Prevention | Does the system prevent problems before they occur (confirmation for destructive actions, constraints)? |
| 6 | Recognition Rather Than Recall | Are objects, actions, and options visible? Minimal memory load? |
| 7 | Flexibility and Efficiency of Use | Are accelerators (shortcuts, abbreviations, advanced techniques) available for experienced users? |
| 8 | Aesthetic and Minimalist Design | Is there no irrelevant or rarely needed information? Every extra unit competes with relevant units? |
| 9 | Help Users Recognize, Diagnose, and Recover from Errors | Are error messages expressed in plain language, indicate the problem, and constructively suggest a solution? |
| 10 | Help and Documentation | Is help easy to search, focused on the user's task, and not too lengthy? |

## SEQ Step Scoring

Score each critical interaction step on four dimensions (1-7):

| Metric | What It Captures |
|--------|-----------------|
| `SEQ` (overall ease) | Perceived difficulty of completing the action |
| `efficiency` | Whether the path was direct and fast |
| `clarity` | How understandable the UI element or response was |
| `confidence` | How certain the user felt about the action and outcome |

**Thresholds:** SEQ ≤ 3 → flag as friction point. SEQ ≤ 2 → critical.

## SUS Scoring (Session-Level)

After scoring all steps in a flow, compute SUS:

```
SUS = (X + Y) × 2.5
  X = Σ (score − 1) for positive items
  Y = Σ (5 − score) for negative items
```

**Grading (Sauro-Lewis):** A+ ≥ 90.3, A ≥ 84.1, B+ ≥ 76, C ≥ 60, F < 51.7. Industry average: 68.

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
  "sus_score": 72.5,
  "sus_grade": "B",
  "wcag_violations": [
    {
      "criterion": "1.4.3",
      "severity": "high",
      "element": "CTA button on /checkout",
      "detail": "Contrast ratio 3.1:1, minimum 4.5:1 required"
    }
  ],
  "nielsen_violations": [
    {
      "heuristic": 1,
      "name": "Visibility of System Status",
      "detail": "No loading indicator on form submission"
    }
  ],
  "seq_scores": [
    {"step": 1, "action": "Fill name", "seq": 6, "efficiency": 5, "clarity": 7, "confidence": 6},
    {"step": 2, "action": "Select plan", "seq": 3, "efficiency": 2, "clarity": 4, "confidence": 3}
  ],
  "cognitive_load": "medium",
  "step_bloat": 0,
  "navigation_issues": [],
  "accessibility_issues": [],
  "recommendations": ["Increase CTA button contrast", "Add loading indicator on submit"],
  "findings": [],
  "complete": true
}
```

## Mandatory Evidence
- `friction_score` (0-10)
- `sus_score` (computed from SEQ step scores)
- `sus_grade` (Sauro-Lewis letter grade)
- `wcag_violations` (array, may be empty)
- `nielsen_violations` (array, may be empty)
- `seq_scores` (per-step scores for critical interactions)
- `confidence` (0-1)

## Success Criteria
- `friction_score` <= threshold (default 4)
- `sus_score` >= 68 (industry average)
- No critical WCAG violations (severity: `high` or `critical`)
- `confidence` >= minimum (default 0.70)

## Blocking Criteria
- No UI project (set `blocked_reason: NOT_APPLICABLE`)
- Cannot access design artifacts

## Failure Criteria
- `friction_score` > threshold
- `sus_score` < 68
- Critical WCAG violations found (AA level)
- Cognitive load is "high"
- Nielsen heuristic violations >= 3

## Anti-Patterns
- **Never audit without SEQ scores** — qualitative observations without quantitative scoring lack rigor
- **Never skip WCAG 2.2 criteria** — 2.1 is outdated; 2.2 adds touch target, motion, and focus visibility
- **Never ignore contrast on interactive elements** — 1.4.11 (non-text contrast) catches icons and buttons WCAG 2.1 missed
- **Never conflate cognitive load with step count** — a 3-step flow with ambiguous labels has higher cognitive load than a 6-step flow with clear labels
- **Never skip Nielsen heuristics** — WCAG covers accessibility; Nielsen covers usability. Both are needed.
