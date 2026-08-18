---
name: bmad-info-arch
id: bmad-info-arch
version: 1.0.0
type: skill
stage: design.info-arch
---

# Skill: BMAD Information Architecture

## Objective
Design the structural organization of information, navigation, and content within the product. Create sitemaps, wireframes, and navigation specifications that make content findable and tasks completable. Ensure every persona has a clear path through the information architecture.

## Inputs
- Personas and journey maps
- Research findings
- PRD and product requirements
- Content inventory (if available)
- Stage context: `state.stages.design.info-arch`

## Permitted Tools
- `read`: Read personas, journeys, PRD, research
- `glob`: Find relevant project files
- `grep`: Search for content patterns, existing navigation structures

## Information Architecture Process

### 1. Content Inventory

Catalog all content types and data entities the product manages:

| Content Type | Examples | Primary Action | Secondary Actions |
|-------------|----------|---------------|-------------------|
| {Entity} | {Examples} | {Create/View/Edit} | {Delete, Share, Export} |

**Card Sorting Methodology:**
When uncertain about content grouping, apply card sorting logic:
1. List all content items/features
2. Group by user mental model (not technical structure)
3. Validate against persona goals
4. Iterate until grouping feels intuitive

### 2. Information Hierarchy

Design the hierarchical structure:

```
Level 0: {Product Name}
├── Level 1: {Primary Section}
│   ├── Level 2: {Subsection}
│   │   └── Level 3: {Content/Action}
│   └── Level 2: {Subsection}
├── Level 1: {Primary Section}
│   └── ...
└── Level 1: {Primary Section}
```

**Hierarchy principles:**
- Maximum 3-4 levels deep (beyond that, use faceted navigation)
- No more than 7 primary sections (Miller's Law: 7 ± 2)
- Each level serves a distinct user goal
- Labels match user vocabulary (not internal terminology)

### 3. Sitemap Design

```markdown
# Sitemap

## Primary Navigation
{Top-level sections with labels and descriptions}

### {Section Name}
- {Page/View} — {Purpose}
- {Page/View} — {Purpose}

## Secondary Navigation
{Contextual navigation within sections}

## Utility Navigation
{Global actions: search, settings, help, account}
```

**Sitemap quality criteria:**
- Every persona has a named path to their primary goal
- No orphaned pages (every page reachable from navigation)
- No more than 3 clicks to any primary task
- Labels are scannable and distinct

### 4. Wireframe Design

Create low-fidelity wireframes for each key screen:

```markdown
## Wireframe: {Screen Name}
**Route:** {URL or screen identifier}
**Purpose:** {What this screen accomplishes}

```
+--------------------------------------------------+
|  [Header: Logo | Primary Nav | Utility Nav]     |
+--------------------------------------------------+
|  [Sidebar: Secondary Nav]  |  [Main Content]    |
|                             |                    |
|  - Item 1                    |  +-------------+  |
|  - Item 2                    |  | Component 1 |  |
|  - Item 3                    |  +-------------+  |
|                             |                    |
|                             |  +-------------+  |
|                             |  | Component 2 |  |
|                             |  +-------------+  |
+--------------------------------------------------+
|  [Footer: Links | Copyright]                      |
+--------------------------------------------------+
```

**Annotations:**
- **Component 1:** {Purpose, behavior, data source}
- **Component 2:** {Purpose, behavior, data source}

**States:**
- Normal: {Description}
- Empty: {What shows when no data}
- Loading: {Skeleton/shimmer/progress indicator}
- Error: {Error message + recovery action}
```

**Wireframe quality criteria:**
- Every screen has a clear primary action
- Visual hierarchy matches information priority
- All states covered (normal, empty, loading, error)
- Responsive considerations noted

### 5. Navigation Specification

```markdown
# Navigation Specification

## Primary Navigation
| Item | Route | Visible To | Mobile Behavior |
|------|-------|-----------|-----------------|
| {Label} | {/route} | {All / Role} | {Tab bar / Hamburger} |

## Breadcrumbs
{Breadcrumb structure for deep navigation}

## Search
{Search scope, filters, result ranking}

## Deep Linking
{Direct links to specific content/actions}

## Navigation Patterns
| Pattern | Where Used | Rationale |
|---------|-----------|-----------|
| {Tab bar} | {Mobile primary nav} | {Familiar, thumb-reachable} |
| {Sidebar} | {Desktop secondary nav} | {Expandable, context-aware} |
| {Breadcrumbs} | {Deep content} | {Orientation, back-navigation} |
```

## Output Format
```json
{
  "stage": "design.info-arch",
  "status": "done",
  "artifact": "artifacts/design/info-arch/sitemaps.md",
  "screens_count": 12,
  "navigation_items": 8,
  "complete": true
}
```

## Output Artifacts

| File | Content |
|------|---------|
| `sitemaps.md` | Full sitemap with hierarchy |
| `wireframes.md` | Low-fidelity wireframes with annotations |
| `navigation-spec.md` | Navigation patterns, routes, behaviors |

## Quality Gates

| Gate | Criteria |
|------|----------|
| **Persona coverage** | Every persona has a named path through IA |
| **Journey coverage** | All key journeys land on covered surfaces |
| **Screen coverage** | Every surface has a wireframe |
| **State coverage** | All wireframes cover normal/empty/loading/error |
| **Navigation depth** | No more than 3 clicks to primary tasks |

## Anti-Patterns
- **Never organize by technical structure** — IA follows user mental models, not database schema
- **Never use internal terminology** — labels must match user vocabulary from research
- **Never skip empty states** — empty states are first experiences for new users
- **Never create deep hierarchies** — beyond 3 levels, use faceted navigation or search
- **Never ignore mobile** — navigation patterns must work on all target devices
- **Never forget utility navigation** — search, settings, and help are always needed
