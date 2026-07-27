---
name: architecture-refinements
stage: architecture
run_id: "eng-20250726-000000"
---

# Architecture: Rota 101 Refinements

## 1. REQUIREMENTS ARCHITECTURE

### Functional Requirements

| ID | Feature | Requirement | Priority |
|----|---------|-------------|----------|
| FR-01 | Palette | Replace all CSS color tokens with B/W/Gray (#121212 base) | High |
| FR-02 | Palette | Remove all earthy/brown tones from design tokens | High |
| FR-03 | Palette | Apply new tokens to all pages, components, modals, toasts | High |
| FR-04 | Detail | New route /veiculos/:id with image-first layout (60% viewport) | High |
| FR-05 | Detail | Match engine info always visible: brand, model, year, FIPE, region, trust | High |
| FR-06 | Detail | Collapsible sections for secondary details (km, fuel, transmission) | Medium |
| FR-07 | Detail | Photo zoom: pinch mobile (1-4×), scroll desktop (1-4×), double-tap toggle | High |
| FR-08 | Detail | Image gallery with thumbnails | Medium |
| FR-09 | Calculator | Compute delta: (FIPE_A × (1+adj_A%)) - (FIPE_B × (1+adj_B%)) | High |
| FR-10 | Calculator | Display "Você paga R$ X" / "Você recebe R$ X" / "Valores equivalentes" | High |
| FR-11 | Calculator | Text-only differentiation (no colors, no icons) | High |
| FR-12 | Calculator | Show delta during match flow (pre-confirmation) | High |
| FR-13 | Calculator | Handle offline: show "Sem conexão" message | Medium |
| FR-14 | Calculator | Handle missing FIPE: show "Valor FIPE indisponível" | Medium |
| FR-15 | Calculator | Handle missing adjustment: default to 0% | Medium |
| FR-16 | Match UI | Add ❤️/❌ buttons (48×48px) below swipe card | High |
| FR-17 | Match UI | Retain existing swipe gestures (right=like, left=dislike) | High |
| FR-18 | Match UI | Anti-duplication: button + swipe = single action | Medium |
| FR-19 | Match UI | Persist like/dislike to Firestore | High |

### Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-01 | Touch targets | ≥ 48×48px (WCAG) |
| NFR-02 | Contrast ratios | WCAG AA minimum |
| NFR-03 | Zoom performance | 60fps on mid-range mobile |
| NFR-04 | Calculator latency | < 500ms for delta computation |
| NFR-05 | Image loading | Lazy-load gallery, LQIP for main image |
| NFR-06 | Offline | Graceful degradation for calculator |

### Data Model Changes

```
listings/{listingId}
  + ownerAdjustment: number (0-50, default 0)  // percentage adjustment

user-interactions/{userId}/{interactionId}
  + type: "like" | "dislike"
  + targetVehicleId: string
  + targetUserId: string
  + timestamp: serverTimestamp
  + method: "swipe" | "button"
```

### Decisions

#### ADR-001: Hash routing for vehicle detail
- **Context**: App uses React Router. Need new route for /veiculos/:id.
- **Decision**: Use hash routing (#veiculo/{id}) for Capacitor compatibility.
- **Consequences**: URL not SEO-friendly (acceptable for PWA/native). Consistent with existing routing patterns.

#### ADR-002: Owner adjustment stored on listing document
- **Context**: Swap calculator needs owner's price adjustment percentage.
- **Decision**: Store `ownerAdjustment` as field on `listings/{listingId}`.
- **Consequences**: Single read for listing + adjustment. Validated in Firestore rules (0-50%).

---

## 2. CLOUD ARCHITECTURE

### Firebase Services

#### Firestore
- **New field**: `listings/{id}.ownerAdjustment` (number, 0-50)
- **New subcollection**: `user-interactions/{userId}/{interactionId}` for like/dislike persistence
- **Rules impact**: Add validation for `ownerAdjustment` range. Allow read/write on `user-interactions` for authenticated user only.
- **Indexes**: Compound index on `user-interactions` (targetVehicleId + timestamp) for deduplication.

#### Firebase Storage
- **Current**: Vehicle photos stored at original resolution
- **Requirement**: Zoom 4× needs sufficient resolution
- **Decision**: Store original high-res images. Generate derivatives (800px, 1200px) on upload. Use 1200px for zoom source.
- **Cost**: ~2x storage per image. Estimated impact: minimal for current scale.

#### Firebase Auth
- **No changes**: Existing auth flow unchanged.

### Cost Estimation
- Firestore reads: +2 reads per match (listing + interaction) — negligible
- Storage: +1 derivative per image — ~50MB/month at current scale
- Bandwidth: +1200px image on zoom — ~2MB per detail page view

### Decisions

#### ADR-003: Canvas-based image derivatives
- **Context**: Need multiple image resolutions for zoom.
- **Decision**: Generate derivatives client-side on upload (Canvas API). Store original + 800px + 1200px variants.
- **Consequences**: Upload latency increases. Better zoom quality than server-side resize. No Firebase Functions needed.

#### ADR-004: Like/dislike in separate collection
- **Context**: Need to persist user interactions for match engine.
- **Decision**: New `user-interactions` collection, keyed by userId.
- **Consequences**: Isolates interaction data. Easy to query per user. Scalable.

---

## 3. SOLUTION ARCHITECTURE

### Component Design

#### New Components
1. **`VehicleDetail.jsx/.css`** — Full detail page
   - Props: `vehicleId` (from route params)
   - Sections: ImageGallery, MatchInfoBar, CollapsibleDetails, OwnerInfo, GalleryThumbnails
   - Data: Fetches from `listings/{id}` + `users/{userId}` for owner info

2. **`SwapCalculator.jsx/.css`** — Delta calculation display
   - Props: `userVehicle`, `targetVehicle`, `onConfirm`
   - States: loading, success (paga/recebe/equivalente), error (offline/no FIPE)
   - Computation: Uses `computeSwapDeltaWithAdjustment()` from `src/lib/swap-value.js`

3. **`MatchButtons.jsx/.css`** — ❤️/❌ buttons
   - Props: `onLike`, `onDislike`, `disabled`
   - Behavior: Calls same callbacks as swipe. Anti-duplication via `isAnimating` state.

#### Modified Components
1. **`HomePage.jsx`** (Pista tab) — Integrate MatchButtons below swipe card
2. **`SwipeContainer.jsx`** — Expose like/dislike callbacks for MatchButtons
3. **`MatchCard.jsx`** — Style updates for B/W/Gray
4. **`MatchList.jsx`** / Match confirmation screen — Integrate SwapCalculator

### File Map

#### New Files
```
src/pages/VehicleDetail.jsx
src/pages/VehicleDetail.css
src/components/SwapCalculator.jsx
src/components/SwapCalculator.css
src/components/MatchButtons.jsx
src/components/MatchButtons.css
src/lib/swap-value.js              // New: swap delta calculator
```

#### Modified Files
```
src/App.jsx                        // Add VehicleDetail route
src/tokens.css                     // Full rewrite: B/W/Gray tokens
src/index.css                      // Remove film grain, update selection/focus
src/pages/HomePage.jsx             // Integrate MatchButtons
src/pages/HomePage.css             // B/W/Gray styles
src/components/SwipeContainer.jsx  // Expose callbacks, anti-dup
src/components/SwipeContainer.css  // B/W/Gray styles
src/components/MatchCard.jsx       // B/W/Gray styles
src/components/MatchCard.css       // Strip colored backgrounds
src/pages/MatchList.jsx            // Integrate SwapCalculator
src/pages/MatchList.css            // B/W/Gray styles
src/lib/match-engine.js            // No changes (read-only)
src/lib/fipe-data.js               // No changes (catalog only)
src/lib/listings.js                // Add ownerAdjustment field
```

### Data Flow

```
VehicleDetail Page:
  Route params → listings/{id} (Firestore) → Vehicle data
                              → users/{userId} → Owner info
                              → Storage → Images (original + derivatives)

SwapCalculator:
  Match event → listings/{userVehicleId} + listings/{targetVehicleId}
             → computeSwapDeltaWithAdjustment(FIPE_A, adj_A, FIPE_B, adj_B)
             → Delta display (text-only)

MatchButtons:
  Button tap → SwipeContainer.onLike() / onDislike()
            → Firestore write (user-interactions)
            → Match engine re-evaluation (existing flow)
```

### State Management
- **VehicleDetail**: Local state + Firestore listeners. No global state needed.
- **SwapCalculator**: Local state (loading/success/error). Data from match context.
- **MatchButtons**: Local state (animating). Callbacks to SwipeContainer.

### Decisions

#### ADR-005: swap-value.js as pure module
- **Context**: Need delta calculation logic.
- **Decision**: New `src/lib/swap-value.js` with pure functions (no framework deps).
- **Consequences**: Testable in isolation. Reusable in components and tests.

#### ADR-006: VehicleDetail as new page, not modal
- **Context**: User wants detailed vehicle view with zoom.
- **Decision**: Full page navigation (not overlay/modal) for better zoom UX on mobile.
- **Consequences**: Full viewport for image. Native back button works. Consistent with app navigation patterns.

---

## 4. CONSOLIDATED ARCHITECTURE

### Cross-Check Matrix

| Requirement | Cloud | Solution | Status |
|-------------|-------|----------|--------|
| FR-01 to FR-03 (Palette) | N/A | tokens.css rewrite | ✅ |
| FR-04 to FR-08 (Detail) | Storage derivatives | VehicleDetail component | ✅ |
| FR-09 to FR-15 (Calculator) | listings.ownerAdjustment | SwapCalculator + swap-value.js | ✅ |
| FR-16 to FR-19 (Match UI) | user-interactions | MatchButtons + SwipeContainer | ✅ |
| NFR-01 to NFR-06 | Rules validation | Component implementation | ✅ |

### Implementation Phases

| Phase | Files | Description |
|-------|-------|-------------|
| 1 | tokens.css, index.css | B/W/Gray palette — foundation for all features |
| 2 | VehicleDetail.*, App.jsx | Vehicle detail page with zoom |
| 3 | swap-value.js, SwapCalculator.* | Swap calculator with adjustment |
| 4 | MatchButtons.*, SwipeContainer.* | Like/dislike buttons with anti-dup |
| 5 | All .css files | Final B/W/Gray application across app |

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Image resolution insufficient for 4× zoom | Poor UX | Guardrail: limit zoom to 2× if image < 800px |
| Owner adjustment not set by user | Calculator uses 0% | Default to 0%, show hint to set adjustment |
| Swipe + button duplication | Double action | `isAnimating` flag blocks concurrent actions |
| Offline calculator | User confusion | Clear "Sem conexão" message, still allow match |
| Palette inconsistency | Visual regression | CSS custom properties — single source of truth |

### Final Decisions

#### ADR-007: Phase 1 (palette) first
- **Context**: All features depend on B/W/Gray tokens.
- **Decision**: Implement palette change first, then features.
- **Consequences**: Each subsequent phase builds on consistent tokens. Easier review.

#### ADR-008: Inter as single typeface
- **Context**: Current app uses Oswald + Barlow Condensed.
- **Decision**: Switch to Inter for all text (matches minimalist B/W/Google design language).
- **Consequences**: Better readability. Single font = faster load. Needs Google Fonts import.

#### ADR-009: Zoom guardrail based on image resolution
- **Context**: 4× zoom on low-res images = blurry.
- **Decision**: Detect image natural width. If < 800px, cap zoom at 2×. If ≥ 800px, allow 4×.
- **Consequences**: Adaptive zoom quality. No user-facing message needed.
