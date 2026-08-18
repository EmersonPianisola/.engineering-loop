---
name: bmad-visual-design
id: bmad-visual-design
version: 1.0.0
type: skill
stage: design.visual-design
---

# Skill: BMAD Visual Design

## Objective
Apply visual polish to the design system: typography scale, color usage, layout system, micro-animations, and accessibility contrast targets. Every visual decision ties to a business goal or user need. Visual design is the layer that makes a product feel intentional, not assembled.

## Inputs
- Design tokens
- Component library
- Brand assets (if available)
- Interaction patterns
- Stage context: `state.stages.design.visual-design`

## Permitted Tools
- `read`: Read design tokens, component library, brand assets
- `glob`: Find relevant project files

## Visual Design Framework

### 1. Visual Identity & Aesthetic Direction

```markdown
# Visual Identity

## Aesthetic Direction
{Describe the visual personality in 3-5 words: e.g., "Clean, confident, approachable"}

## Visual References
{List 3-5 products/brands that share similar aesthetic qualities}

## Differentiators
{What makes this product visually distinct from competitors}

## Mood Board
| Category | Reference | Rationale |
|----------|-----------|-----------|
| Color palette | {Reference} | {Why this direction} |
| Typography | {Reference} | {Why this typeface} |
| Imagery | {Reference} | {Why this style} |
| Iconography | {Reference} | {Why this style} |
| Layout | {Reference} | {Why this approach} |
```

### 2. Typography Scale

Build a modular type scale based on a ratio:

```markdown
# Typography Scale

## Base Settings
- **Font family:** {Primary font}
- **Base size:** 16px (1rem)
- **Scale ratio:** {1.25 Major Third / 1.125 Minor Third / 1.333 Perfect Fourth}
- **Line heights:** Tight (1.25) for headings, Normal (1.5) for body

## Scale
| Level | Size | Weight | Line Height | Letter Spacing | Use |
|-------|------|--------|-------------|----------------|-----|
| Display | {Value} | Bold | Tight | Tight | Hero sections |
| H1 | {Value} | Semibold | Tight | None | Page titles |
| H2 | {Value} | Semibold | Tight | None | Section titles |
| H3 | {Value} | Medium | Normal | None | Subsection titles |
| Body LG | {Value} | Regular | Normal | None | Lead paragraphs |
| Body | {Value} | Regular | Normal | None | Default text |
| Body SM | {Value} | Regular | Normal | None | Secondary text |
| Caption | {Value} | Medium | Tight | Wide | Labels, metadata |
| Overline | {Value} | Semibold | Tight | Wider | Section labels |
| Code | {Value} | Regular | Normal | None | Inline code |

## Responsive Typography
| Breakpoint | Scale Adjustment |
|------------|-----------------|
| Mobile (< 640px) | Heading sizes -1 step |
| Tablet (640-1024px) | Base scale |
| Desktop (> 1024px) | Heading sizes +0.5 step |
```

### 3. Color Usage System

```markdown
# Color Usage

## Color Roles
| Role | Token | Usage |
|------|-------|-------|
| Primary action | `colors.primary.500` | CTAs, key links, active states |
| Secondary action | `colors.primary.700` | Secondary buttons, hover states |
| Text primary | `colors.neutral.900` | Headings, body text |
| Text secondary | `colors.neutral.500` | Captions, placeholders, metadata |
| Border | `colors.neutral.200` | Dividers, card borders |
| Background | `colors.neutral.50` | Page background |
| Surface | `colors.neutral.0` | Cards, modals, dropdowns |

## Semantic Colors
| Meaning | Token | Usage |
|---------|-------|-------|
| Success | `colors.semantic.success` | Confirmation, valid state |
| Warning | `colors.semantic.warning` | Caution, pending state |
| Error | `colors.semantic.error` | Error messages, invalid state |
| Info | `colors.semantic.info` | Informational messages |

## Color Accessibility
| Combination | Contrast Ratio | WCAG Level |
|-------------|---------------|------------|
| Text primary on background | >= 7:1 | AAA |
| Text secondary on background | >= 4.5:1 | AA |
| Primary on white | >= 4.5:1 | AA |
| Semantic colors on white | >= 3:1 | AA (large text) |

## Dark Mode
| Role | Light Mode Token | Dark Mode Token |
|------|-----------------|-----------------|
| Text primary | `neutral.900` | `neutral.50` |
| Text secondary | `neutral.500` | `neutral.400` |
| Background | `neutral.50` | `neutral.900` |
| Surface | `neutral.0` | `neutral.800` |
| Border | `neutral.200` | `neutral.700` |
```

### 4. Layout System

```markdown
# Layout System

## Grid
- **Columns:** 12 (desktop), 8 (tablet), 4 (mobile)
- **Gutter:** 24px (desktop), 16px (tablet/mobile)
- **Margin:** 32px (desktop), 16px (tablet/mobile)
- **Max width:** 1440px (dashboard), 1200px (content), 768px (reading)

## Spacing Scale
All spacing uses design tokens (8-point grid):
| Token | Value | Use |
|-------|-------|-----|
| `spacing.2` | 8px | Tight component padding |
| `spacing.4` | 16px | Default component padding |
| `spacing.6` | 24px | Section spacing |
| `spacing.8` | 32px | Major section dividers |
| `spacing.12` | 48px | Page-level spacing |

## Component Layout Patterns
| Pattern | Description | When to Use |
|---------|-------------|-------------|
| **Stack** | Vertical arrangement | Forms, lists, cards |
| **Row** | Horizontal arrangement | Toolbars, action bars |
| **Grid** | 2D arrangement | Dashboard cards, galleries |
| **Sidebar + Main** | Split layout | Settings, detail views |
| **Overlay** | Modal/tooltip | Contextual actions, tooltips |
```

### 5. Micro-Animations & Polish

```markdown
# Micro-Animations

## Principles
1. **Feedback:** Confirm user actions (button press, toggle switch)
2. **Transition:** Smooth state changes (page navigation, modal open)
3. **Reveal:** Progressive disclosure (accordion, expandable sections)
4. **Delight:** Subtle personality (success checkmark, loading skeleton)

## Animation Catalog
| Animation | Trigger | Duration | Easing | Properties |
|-----------|---------|----------|--------|------------|
| Button press | Click | 100ms | Standard | Scale 0.97 |
| Toggle switch | Change | 200ms | Spring | TranslateX + background |
| Modal enter | Open | 300ms | Decelerate | Opacity + translateY |
| Modal exit | Close | 200ms | Accelerate | Opacity + translateY |
| Skeleton load | Mount | 1200ms | Loop | Shimmer gradient |
| Toast enter | Show | 300ms | Decelerate | TranslateY + opacity |
| Toast exit | Hide | 200ms | Accelerate | TranslateY + opacity |
| Page transition | Navigate | 400ms | Standard | Fade + slide |
| Success check | Complete | 500ms | Spring | Draw + scale |
| Error shake | Invalid | 400ms | Standard | TranslateX ±4px |

## Reduced Motion
All animations respect `prefers-reduced-motion`:
- Replace transitions with instant state changes
- Replace skeleton loaders with static placeholders
- Replace scroll animations with static content
- Keep functional animations (focus indicators, loading spinners)
```

### 6. Visual Do's & Don'ts

```markdown
# Visual Do's & Don'ts

## Typography
| Do | Don't |
|----|-------|
| Use type scale tokens | Hardcode font sizes |
| Limit to 2 font families | Mix more than 2 typefaces |
| Use letter spacing for caps | Use all-caps for long text |
| Keep line length 45-75 chars | Let text run full viewport width |

## Color
| Do | Don't |
|----|-------|
| Use semantic color names | Use literal color names (red, blue) |
| Pair color with icon for meaning | Rely on color alone to convey state |
| Test contrast ratios | Assume colors are accessible |
| Provide dark mode variants | Design only for light mode |

## Layout
| Do | Don't |
|----|-------|
| Use spacing tokens | Hardcode pixel values |
| Design mobile first | Design desktop, then shrink |
| Maintain consistent gutters | Vary spacing arbitrarily |
| Use max-width for readability | Let content stretch full width |

## Animation
| Do | Don't |
|----|-------|
| Animate state changes | Animate for decoration |
| Respect reduced-motion | Force animations on all users |
| Keep durations under 500ms | Use long, dramatic transitions |
| Provide loading feedback | Leave users wondering if something happened |
```

## Output Format
```json
{
  "stage": "design.visual-design",
  "status": "done",
  "artifact": "artifacts/design/visual-design/visual-spec.md",
  "typography_levels": 10,
  "color_roles": 8,
  "animations_defined": 10,
  "complete": true
}
```

## Output Artifacts

| File | Content |
|------|---------|
| `visual-spec.md` | Typography, color, layout, animations |
| `visual-dos-donts.md` | Do's and don'ts for each visual dimension |

## Quality Gates

| Gate | Criteria |
|------|----------|
| **Token references** | All visual values reference design tokens |
| **Business alignment** | Visual decisions tied to business goals |
| **Accessibility** | All color combinations meet WCAG AA contrast |
| **Dark mode** | All tokens have dark mode variants |
| **Reduced motion** | All animations have reduced-motion fallback |

## Anti-Patterns
- **Never hardcode visual values** — always reference design tokens
- **Never use more than 2 font families** — consistency over variety
- **Never rely on color alone** — always pair with icon or text for meaning
- **Never skip dark mode** — design for both light and dark from the start
- **Never animate for decoration** — motion must serve function
- **Never ignore contrast ratios** — accessibility is not optional
