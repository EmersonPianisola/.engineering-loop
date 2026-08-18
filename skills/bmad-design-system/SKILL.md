---
name: bmad-design-system
id: bmad-design-system
version: 1.0.0
type: skill
stage: design.design-system
---

# Skill: BMAD Design System

## Objective
Build a coherent design system: tokens, components, and guidelines that ensure visual consistency, enable rapid development, and scale with the product. Follow Atomic Design principles: atoms (tokens) → molecules (components) → organisms (layouts) → templates (pages).

## Inputs
- Interaction patterns and component behaviors
- Wireframes and IA artifacts
- Brand assets (if available)
- Stage context: `state.stages.design.design-system`

## Permitted Tools
- `read`: Read interaction specs, wireframes, brand assets
- `glob`: Find relevant project files
- `grep`: Search for existing design tokens, component definitions

## Design System Architecture

### Atomic Design Hierarchy

```
Atoms (Design Tokens)
  ├── Color tokens
  ├── Typography tokens
  ├── Spacing tokens
  ├── Elevation tokens
  └── Motion tokens

Molecules (Components)
  ├── Input components (Button, Input, Select, Toggle)
  ├── Display components (Card, Badge, Avatar, Icon)
  ├── Feedback components (Toast, Modal, Spinner)
  └── Navigation components (Tab, Breadcrumb, Pagination)

Organisms (Composite Components)
  ├── Form sections
  ├── Data tables
  ├── Navigation bars
  └── Content cards

Templates (Page Layouts)
  ├── Dashboard layout
  ├── Detail view layout
  ├── List view layout
  └── Settings layout
```

### 1. Design Tokens

Tokens are the single source of truth for visual values. Defined in YAML, consumed by code.

```yaml
# Color Tokens
colors:
  primary:
    50: "#f0f7ff"
    100: "#e0effe"
    200: "#b9dffd"
    500: "#3b82f6"
    700: "#1d4ed8"
    900: "#1e3a8a"
  neutral:
    50: "#f9fafb"
    100: "#f3f4f6"
    500: "#6b7280"
    700: "#374151"
    900: "#111827"
  semantic:
    success: "#22c55e"
    warning: "#f59e0b"
    error: "#ef4444"
    info: "#3b82f6"

# Typography Tokens
typography:
  font-family:
    primary: "Inter, system-ui, sans-serif"
    monospace: "JetBrains Mono, monospace"
  font-size:
    xs: "0.75rem"    # 12px
    sm: "0.875rem"   # 14px
    base: "1rem"     # 16px
    lg: "1.125rem"   # 18px
    xl: "1.25rem"    # 20px
    "2xl": "1.5rem"  # 24px
    "3xl": "1.875rem" # 30px
    "4xl": "2.25rem"  # 36px
  font-weight:
    regular: 400
    medium: 500
    semibold: 600
    bold: 700
  line-height:
    tight: 1.25
    normal: 1.5
    relaxed: 1.75

# Spacing Tokens (8-point grid)
spacing:
  0: "0"
  1: "0.25rem"   # 4px
  2: "0.5rem"    # 8px
  3: "0.75rem"   # 12px
  4: "1rem"      # 16px
  5: "1.25rem"   # 20px
  6: "1.5rem"    # 24px
  8: "2rem"      # 32px
  10: "2.5rem"   # 40px
  12: "3rem"     # 48px
  16: "4rem"     # 64px
  20: "5rem"     # 80px

# Elevation Tokens
elevation:
  0: "none"
  1: "0 1px 2px rgba(0,0,0,0.05)"
  2: "0 4px 6px rgba(0,0,0,0.07)"
  3: "0 10px 15px rgba(0,0,0,0.1)"
  4: "0 20px 25px rgba(0,0,0,0.15)"

# Border Radius Tokens
radius:
  none: "0"
  sm: "0.25rem"
  md: "0.375rem"
  lg: "0.5rem"
  full: "9999px"

# Motion Tokens
motion:
  duration:
    fast: "150ms"
    normal: "200ms"
    slow: "300ms"
  easing:
    standard: "cubic-bezier(0.2, 0, 0, 1)"
    decelerate: "cubic-bezier(0, 0, 0, 1)"
    spring: "cubic-bezier(0.34, 1.56, 0.64, 1)"
```

**Token naming convention:**
- Semantic names (not literal): `colors.semantic.error` not `colors.red`
- Consistent scale: spacing uses 8-point grid, colors use 50-900 scale
- Platform agnostic: tokens define values, not implementation

### 2. Component Library

Each component has a visual spec and behavioral spec:

```markdown
## Component: {Component Name}
**Category:** {Input / Display / Feedback / Navigation}
**Maturity:** {Draft / In Review / Stable / Deprecated}

### Visual Spec
| Variant | Description | Token References |
|---------|-------------|-----------------|
| Default | Primary usage | {Tokens} |
| Variant | Secondary usage | {Tokens} |
| Destructive | Danger actions | {Tokens} |

### States
| State | Visual Change | Token |
|-------|---------------|-------|
| Default | {Description} | {Token} |
| Hover | {Description} | {Token} |
| Focus | {Description} | {Token} |
| Disabled | {Description} | {Token} |
| Error | {Description} | {Token} |

### Sizes
| Size | Height | Font Size | Padding |
|------|--------|-----------|---------|
| SM | {Value} | {Token} | {Token} |
| MD | {Value} | {Token} | {Token} |
| LG | {Value} | {Token} | {Token} |

### Accessibility
- **Keyboard:** {Tab behavior, Enter/Space activation}
- **Screen reader:** {ARIA role, label pattern}
- **Focus:** {Visible focus ring, outline style}
- **Color contrast:** {Minimum 4.5:1 for text, 3:1 for UI components}

### Usage Guidelines
- **Do:** {Correct usage examples}
- **Don't:** {Common misuses to avoid}
```

### 3. Design Guidelines

```markdown
# Design Guidelines

## Layout Principles
- **8-point grid:** All spacing uses spacing tokens
- **Content width:** Max 1200px for primary content, 1440px for dashboards
- **Gutters:** 16px (mobile), 24px (tablet), 32px (desktop)
- **Breakpoints:** SM < 640px, MD < 768px, LG < 1024px, XL < 1280px

## Typography Rules
- **Scale:** Use typography tokens, never hardcode font sizes
- **Hierarchy:** H1 > H2 > H3 > Body > Caption
- **Line length:** 45-75 characters per line for readability
- **Paragraph spacing:** Use spacing tokens, not margin hacks

## Color Usage
- **Primary:** Brand color for CTAs and key interactions
- **Neutral:** Text, borders, backgrounds
- **Semantic:** Success/warning/error/info — never use color alone (pair with icon)
- **Dark mode:** All colors must have dark-mode variants

## Iconography
- **Style:** {Outline / Filled / Duotone}
- **Size:** 16px, 20px, 24px (match spacing scale)
- **Stroke:** 1.5px for outline icons
- **Custom icons:** Must match existing style (stroke width, corner radius)

## Imagery
- **Style:** {Photography / Illustration / Abstract}
- **Format:** WebP with JPEG fallback
- **Aspect ratios:** 16:9 (hero), 1:1 (avatar), 4:3 (card)
- **Alt text:** Required for all images

## Governance Model
| Role | Responsibility |
|------|---------------|
| **Design System Team** | Owns tokens, components, guidelines |
| **Product Designers** | Consume system, propose changes |
| **Developers** | Implement components, report bugs |
| **Change Process** | RFC → Review → Implement → Document → Release |
```

## Output Format
```json
{
  "stage": "design.design-system",
  "status": "done",
  "artifact": "artifacts/design/design-system/design-tokens.md",
  "tokens_defined": 80,
  "components_specified": 20,
  "complete": true
}
```

## Output Artifacts

| File | Content |
|------|---------|
| `design-tokens.md` | Color, typography, spacing, elevation, motion tokens (YAML) |
| `component-library.md` | Visual + behavioral specs per component |
| `design-guidelines.md` | Layout, typography, color, iconography, imagery rules |

## Quality Gates

| Gate | Criteria |
|------|----------|
| **Token coverage** | All visual values expressed as tokens |
| **Component coverage** | Every component in wireframes has a library entry |
| **Token references** | Components reference tokens, not hardcoded values |
| **Governance** | Clear ownership and change process defined |

## Anti-Patterns
- **Never hardcode values in components** — always reference tokens
- **Never use literal color names** — use semantic names (error, not red)
- **Never skip dark mode** — every token needs a dark variant
- **Never create components without states** — default, hover, focus, disabled, error
- **Never ignore the governance model** — without governance, the system decays
- **Never break the 8-point grid** — consistency is the point of the system
