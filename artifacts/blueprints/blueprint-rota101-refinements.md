---
name: blueprint-rota101-refinements
stage: impl.design
run_id: "eng-20250726-000000"
---

# Implementation Blueprint: Rota 101 Refinements

## File Structure

### Modified Files (12)
```
src/tokens.css                    # Full rewrite: B/W/Gray tokens
src/index.css                     # Remove film grain, update selection/focus
src/lib/swap-value.js             # Add computeSwapDeltaWithAdjustment()
src/pages/VehicleDetail.jsx       # Add collapsible sections, match info bar
src/pages/VehicleDetail.css       # B/W/Gray + collapsible styles
src/pages/HomePage.css            # B/W/Gray styles, button sizing
src/components/SwipeContainer.css # B/W/Gray stamp colors
src/components/MatchCard.css      # B/W/Gray styles
src/pages/MatchList.jsx           # Integrate SwapCalculator inline
src/pages/MatchList.css           # B/W/Gray + calculator styles
src/pages/HomePage.jsx            # Button sizing (48×48px)
src/App.css                       # B/W/Gray shell styles
```

### No New Files Needed
Existing components cover all features:
- VehicleDetail: Already has zoom, carousel, specs, owner info
- HomePage: Already has ❤️/❌ action buttons
- swap-value.js: Already has delta calculation + formatting
- SwipeContainer: Already has swipe gestures

## Interface Contracts

### swap-value.js — New Function
```javascript
/**
 * Compute swap delta with owner adjustment.
 * @param {number} userFipePrice — FIPE price of user's vehicle
 * @param {number} userAdjustment — Owner adjustment percentage (0-50)
 * @param {number} targetFipePrice — FIPE price of target vehicle
 * @param {number} targetAdjustment — Target owner adjustment percentage (0-50)
 * @returns {{ hasDelta: boolean, delta: number, absolute: number, type: 'pay'|'receive'|'equal'|'unknown', userAdjusted: number, targetAdjusted: number }}
 */
export function computeSwapDeltaWithAdjustment(userFipePrice, userAdjustment, targetFipePrice, targetAdjustment)

// Examples:
computeSwapDeltaWithAdjustment(80000, 5, 85000, 0)
// → { hasDelta: true, delta: -3000, absolute: 3000, type: 'pay', userAdjusted: 84000, targetAdjusted: 85000 }

computeSwapDeltaWithAdjustment(80000, 0, 80000, 0)
// → { hasDelta: true, delta: 0, absolute: 0, type: 'equal', userAdjusted: 80000, targetAdjusted: 80000 }

computeSwapDeltaWithAdjustment(null, 0, 80000, 0)
// → { hasDelta: false, delta: 0, absolute: 0, type: 'unknown', userAdjusted: 0, targetAdjusted: 0 }
```

### VehicleDetail — Modified Props
```javascript
// Current props (unchanged):
{ vehicle, onBack, onOwnerClick, onSwapClick }

// Vehicle data shape (new field):
vehicle.ownerAdjustment // number, 0-50, default 0
```

### tokens.css — New Token Values
```css
:root {
  /* Colors — B/W/Gray only */
  --color-primary: #E0E0E0;
  --color-primary-dark: #BDBDBD;
  --color-primary-light: #F5F5F5;
  --color-secondary: #9E9E9E;
  --color-secondary-dark: #757575;
  --color-secondary-light: #BDBDBD;
  --color-accent: #E0E0E0;       /* Was #FFC107 — now gray */
  --color-accent-dark: #BDBDBD;
  --color-accent-light: #F5F5F5;

  --color-background: #121212;    /* Was #1A1A24 */
  --color-background-light: #1E1E1E;
  --color-card: #2A2A2A;          /* Was #2A2A38 */
  --color-bottom-sheet: #1E1E1E;

  --color-text: #FFFFFF;          /* Was #ECEFF1 */
  --color-text-dark: #121212;
  --color-muted: #9E9E9E;         /* Was #90A4AE */

  --color-chrome: #9E9E9E;        /* Was #B0BEC5 */

  /* Semantic — grayscale */
  --color-success: #E0E0E0;       /* Was #43A047 */
  --color-warning: #BDBDBD;       /* Was #FFC107 */
  --color-error: #9E9E9E;         /* Was #E53935 */
  --color-info: #BDBDBD;          /* Was #1E88E5 */

  /* Typography — Inter only */
  --font-display: 'Inter', -apple-system, sans-serif;       /* Was Oswald */
  --font-heading: 'Inter', -apple-system, sans-serif;       /* Was Barlow Condensed */
  --font-body: 'Inter', -apple-system, sans-serif;          /* Unchanged */

  /* Remove */
  /* --glow-cta: ... */           /* Remove red glow */
}
```

## Data Flows

### Feature 1: B/W/Gray Palette
```
tokens.css (new values)
  → All components consume CSS variables
  → index.css (remove film grain overlay)
  → No JS changes needed
```

### Feature 2: Vehicle Detail Enhancements
```
App.jsx → VehicleDetail (existing overlay pattern)
  → vehicle prop already has: brand, model, year, fipePrice, region, trustTier
  → Add: vehicle.ownerAdjustment (from Firestore)
  → UI changes: collapsible sections for secondary details
  → Zoom already exists (1-5×) — adjust to 4× max + resolution guardrail
```

### Feature 3: Swap Calculator
```
MatchList.jsx (match confirmation)
  → Fetches user vehicle + target vehicle listings
  → computeSwapDeltaWithAdjustment(userFipe, userAdj, targetFipe, targetAdj)
  → formatSwapMessage(result) — existing function
  → Display: text-only delta (no colors, no icons)
```

### Feature 4: Match Buttons
```
HomePage.jsx → pista-feed__actions (existing buttons)
  → Resize to 48×48px (currently 64px container, 32px icon)
  → Same callbacks: handleSwipeLeft, handleSwipeRight
  → Anti-dup: Add isAnimating flag to prevent double-action
```

## Execution Order

### Phase 1: Design Tokens (Foundation)
**Task 1.1**: Rewrite `src/tokens.css` — B/W/Gray palette, Inter font
- Replace all color tokens
- Switch display/heading fonts to Inter
- Remove `--glow-cta`
- Update semantic colors to grayscale

**Task 1.2**: Update `src/index.css` — Remove film grain, update selection/focus
- Remove `::before` film grain overlay
- Update `::selection` colors
- Update input focus ring

**Task 1.3**: Update all CSS files — B/W/Gray application
- `src/App.css`
- `src/pages/HomePage.css`
- `src/components/SwipeContainer.css`
- `src/components/MatchCard.css`
- `src/pages/VehicleDetail.css`
- `src/pages/MatchList.css`
- All remaining `.css` files

### Phase 2: Vehicle Detail Enhancements
**Task 2.1**: Modify `src/pages/VehicleDetail.jsx`
- Add collapsible sections (accordion pattern) for secondary details
- Make match engine info always visible (brand, model, year, FIPE, region, trust)
- Add resolution guardrail for zoom (cap at 2× if image < 800px)
- Adjust max zoom from 5× to 4×

**Task 2.2**: Update `src/pages/VehicleDetail.css`
- B/W/Gray styles
- Collapsible section styles (accordion animation, 250ms)
- Match info bar styling

### Phase 3: Swap Calculator
**Task 3.1**: Extend `src/lib/swap-value.js`
- Add `computeSwapDeltaWithAdjustment()` function
- Keep existing `computeSwapDelta()` for backward compatibility
- Add unit tests

**Task 3.2**: Modify `src/pages/MatchList.jsx`
- Integrate calculator in match confirmation flow
- Display delta with text-only differentiation
- Handle offline/no-FIPE states

**Task 3.3**: Update `src/pages/MatchList.css`
- Calculator display styles
- Typography treatment for delta (weight/size, no color)

### Phase 4: Match Buttons
**Task 4.1**: Modify `src/pages/HomePage.jsx`
- Resize action buttons to 48×48px
- Add `isAnimating` flag for anti-duplication
- Ensure buttons and swipe share same callbacks

**Task 4.2**: Update `src/pages/HomePage.css`
- Button sizing: 48×48px touch target
- B/W/Gray button styles

**Task 4.3**: Modify `src/components/SwipeContainer.jsx`
- Expose `isAnimating` state for anti-duplication
- Add `onLike`/`onDislike` props alongside swipe callbacks

### Phase 5: Firestore Schema
**Task 5.1**: Add `ownerAdjustment` field to listings
- Default: 0
- Range: 0-50 (percentage)
- Update Firestore rules for validation

## Error Handling

| Error | Component | Strategy | Message (pt-BR) |
|-------|-----------|----------|-----------------|
| No internet | MatchList (calculator) | Show message, allow match | "Sem conexão — calculadora indisponível" |
| Missing FIPE | MatchList (calculator) | Skip delta, show info | "Valor FIPE indisponível" |
| Missing adjustment | swap-value.js | Default to 0% | (silent) |
| Image < 800px | VehicleDetail (zoom) | Cap zoom at 2× | (silent) |
| Vehicle not found | VehicleDetail | ErrorBanner | "Veículo não encontrado." |
| Swipe + button dup | HomePage | isAnimating flag | (silent, blocks second action) |

## Cross-Cutting Concerns

### Accessibility
- All new interactive elements: 48×48px minimum touch target
- B/W/Gray palette: All text combinations pass WCAG AA
- Calculator delta: Differentiated by text content (no color dependency)
- Zoom overlay: Focus trap, Escape to close, keyboard controls

### Performance
- CSS variables: Single source of truth, no runtime cost
- Collapsible sections: CSS height transition (GPU-accelerated)
- Zoom: Existing implementation uses `transform` (GPU-accelerated)
- Calculator: Pure function, < 1ms computation

### i18n
- All user-facing text in Portuguese (pt-BR)
- Currency formatting: `Intl.NumberFormat('pt-BR')`
- No new translation keys needed (existing patterns)

## Decisions

| ID | Category | Decision | Rationale | Alternatives | Consequences |
|----|----------|----------|-----------|-------------|--------------|
| IB-001 | tokens | B/W/Gray CSS variables | Single source of truth, instant app-wide update | Per-component colors | Easier maintenance, consistent palette |
| IB-002 | font | Inter for all text | Minimalist, readable, single font family | Keep Oswald/Barlow | Faster load, consistent typography |
| IB-003 | zoom | Guardrail: 2× if < 800px | Prevents blurry images on low-res photos | Fixed 4× always | Adaptive quality, no user message |
| IB-004 | calculator | Extend swap-value.js | Existing module, pure functions, testable | New module | Backward compatible, single source |
| IB-005 | buttons | Modify existing HomePage buttons | Already have ❤️/❌ with correct callbacks | New MatchButtons component | Less code, no new imports |
| IB-006 | detail | Collapsible sections in existing VehicleDetail | Component exists with correct data flow | New page component | Leverages existing zoom, carousel, navigation |
| IB-007 | anti-dup | isAnimating flag in HomePage | Simple, effective, no new dependencies | Debounce, mutex | Prevents double-action on swipe+button |
| IB-008 | film grain | Remove from index.css | Inconsistent with minimalist B/W/Gray | Keep as subtle texture | Cleaner aesthetic, matches user preference |
| IB-009 | red glow | Remove --glow-cta | Color-based effect conflicts with B/W/Gray | Grayscale glow | Simpler visual language |
