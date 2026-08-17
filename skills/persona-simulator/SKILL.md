---
name: persona-simulator
id: persona-simulator
version: 2.0.0
type: skill
stage: qa.human.flow
---

# Skill: Persona Simulator

## Objective
Simulate a real user navigating through the system's flows. Identify friction points, confusion, jargon, and dead ends from the user's perspective. Uses structured persona profiles with configurable attributes and step-level SEQ scoring for quantitative usability assessment.

## Inputs
- System flows, screens, and interactions (from design artifacts or code)
- Persona profile (selected based on target audience)
- Stage context: `state.stages.qa.human.flow`
- Friction threshold from config: `qa_policy.human.max_friction_score`

## Permitted Tools
- `read`: Read design artifacts, source files, screen descriptions
- `glob`: Find relevant files
- `grep`: Search for UI text and labels

## Structured Persona Profiles

Each persona is defined by configurable attributes that shape scoring behavior:

| Field | Options | Description |
|-------|---------|-------------|
| `digital_literacy` | `expert` / `intermediate` / `beginner` / `very_low` | Technical fluency level |
| `primary_device` | `desktop_keyboard` / `desktop_mouse` / `tablet_touch` / `mobile_touch` | Primary interaction modality |
| `reading_speed` | `fast` / `normal` / `slow` | Content consumption pace |
| `tolerance_for_friction` | `high` / `medium` / `low` / `very_low` | Abandonment threshold |
| `prior_experience` | Free text | Domain-specific background |
| `description` | 3-4 sentence narrative | Persona identity for LLM embodiment |
| `common_friction_types` | Labels: `waiting`, `confusion`, `searching`, `error`, `repeated_action` | Friction categories to surface |

### Built-in Personas

### Novice User
- `digital_literacy`: `very_low`
- `primary_device`: `mobile_touch`
- `reading_speed`: `slow`
- `tolerance_for_friction`: `very_low`
- `common_friction_types`: `confusion`, `error`, `searching`
- Needs clear guidance at every step, confused by jargon, needs reassuring error messages

### Power User
- `digital_literacy`: `expert`
- `primary_device`: `desktop_keyboard`
- `reading_speed`: `fast`
- `tolerance_for_friction`: `low`
- `common_friction_types`: `repeated_action`, `waiting`
- Efficient, keyboard-driven, impatient with unnecessary steps, wants shortcuts

### Accessibility User
- `digital_literacy`: `intermediate`
- `primary_device`: `desktop_keyboard`
- `reading_speed`: `normal`
- `tolerance_for_friction`: `low`
- `common_friction_types`: `confusion`, `error`
- Uses screen reader or keyboard only, needs proper ARIA labels, high contrast, predictable navigation

### Mobile User
- `digital_literacy`: `beginner`
- `primary_device`: `mobile_touch`
- `reading_speed`: `normal`
- `tolerance_for_friction`: `medium`
- `common_friction_types`: `waiting`, `confusion`
- Small screen, intermittent connectivity, on-the-go, needs touch-friendly targets

## SEQ Scoring (Step-Level)

Each navigation step is scored using the Single Ease Question methodology extended with four dimensions (1-7 scale):

| Metric | What It Captures |
|--------|-----------------|
| `SEQ` (overall ease) | Perceived difficulty of completing the action |
| `efficiency` | Whether the path to the action was direct and fast |
| `clarity` | How understandable the UI element or system response was |
| `confidence` | How certain the user felt about the action and its outcome |

**Scoring thresholds:**
- 6-7: Easy — no action needed
- 4-5: Acceptable — minor improvement possible
- 3: Borderline — flag for review
- 1-2: Friction point — immediate action required

## SUS Scoring (Session-Level)

After completing a full flow, compute the System Usability Scale score:

```
SUS = (X + Y) × 2.5
  X = Σ (score − 1) for positive items
  Y = Σ (5 − score) for negative items
```

**Grading (Sauro-Lewis curved scale):**

| Grade | SUS Score | Percentile |
|-------|-----------|------------|
| A+ | ≥ 90.3 | 99th |
| A | 84.1 - 90.2 | 93rd |
| A- | 80.0 - 84.0 | 87th |
| B+ | 76.0 - 79.9 | 80th |
| B | 72.0 - 75.9 | 73rd |
| B- | 68.0 - 71.9 | 65th |
| C+ | 64.0 - 67.9 | 55th |
| C | 60.0 - 63.9 | 45th |
| C- | 56.0 - 59.9 | 35th |
| D+ | 51.7 - 55.9 | 23rd |
| F | < 51.7 | 14th |

**Industry benchmark:** Average SUS score is 68. Threshold for concern: < 68.

## Friction Score Scale

| Score | Severity | Description |
|-------|----------|-------------|
| 0-2 | Minimal | Intuitive flow, no action needed |
| 3-4 | Moderate | Some confusion, minor improvements recommended |
| 5-6 | Significant | User may abandon, redesign needed |
| 7-8 | Severe | Major redesign required |
| 9-10 | Critical | Flow is practically unusable |

## Simulation Protocol

### Step 1: Select Persona
Choose persona based on target audience. Multiple personas can be simulated for comparative analysis.

### Step 2: Navigate Flow
Walk through each step of the user flow as the persona would:
1. Read the screen/element description
2. Apply persona attributes to assess comprehension and actionability
3. Score each step using SEQ dimensions
4. Flag friction points by type

### Step 3: Identify Issues
For each step with SEQ ≤ 3:
- Classify friction type
- Describe what confused the persona
- Suggest specific fix
- Note whether issue is structural or cosmetic

### Step 4: Compute SUS
Aggregate step scores into SUS session score and grade.

### Step 5: Produce Recommendations
Prioritize by:
1. Critical friction points (SEQ ≤ 2)
2. Structural issues affecting multiple steps
3. Issues affecting personas with lowest tolerance

## Output Format
```json
{
  "verdict": "PASS|FAIL|BLOCKED",
  "qa_type": "heuristic",
  "confidence": 0.85,
  "severity": "info|low|medium|high|critical",
  "persona": {
    "name": "Novice User",
    "digital_literacy": "very_low",
    "primary_device": "mobile_touch",
    "reading_speed": "slow",
    "tolerance_for_friction": "very_low"
  },
  "scenario": "Complete checkout flow",
  "steps": [
    {
      "step": 1,
      "action": "Navigate to checkout",
      "seq": 5,
      "efficiency": 4,
      "clarity": 6,
      "confidence": 5,
      "friction_type": null,
      "note": "Acceptable — CTA button visible but not prominent"
    }
  ],
  "sus_score": 68.5,
  "sus_grade": "C+",
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
- `steps` array with SEQ scores per step
- `sus_score` computed from step data
- `friction_score` (0-10)
- `confidence` (0-1, your confidence in the assessment)
- `persona` object with all fields

## Success Criteria
- `friction_score` <= threshold (default 4)
- `sus_score` >= 68 (industry average benchmark)
- `confidence` >= minimum (default 0.70)
- No steps with SEQ ≤ 2 (critical friction)

## Blocking Criteria
- Cannot access UI or flow information
- Confidence below minimum threshold

## Failure Criteria
- `friction_score` > threshold
- `sus_score` < 68 (below industry average)
- Critical friction points (SEQ ≤ 2) in primary flow
- Multiple dead ends in critical flows

## Anti-Patterns
- **Never simulate without a persona** — a score without a user context is meaningless
- **Never average across personas without reporting variance** — expert and novice scores will diverge; both matter
- **Never skip SUS computation** — step scores alone miss the holistic usability picture
- **Never use SEQ for non-user-facing steps** — SEQ measures perceived ease, not technical correctness
- **Never ignore low-tolerance personas** — they reveal abandonment risks that experts miss
