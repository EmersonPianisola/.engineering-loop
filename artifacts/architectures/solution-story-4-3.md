# Solution Design — Story 4.3: Location Update & Match Recalculation

## Overview

Three files are modified to implement location-triggered match recalculation:

| File | Change Type | Summary |
|------|-------------|---------|
| `src/pages/ProfilePage.jsx` | Modify | UF change detection, recalculation trigger, notification display, error boundaries |
| `src/lib/match-engine.js` | Modify | `computeMatches` accepts optional `location` parameter |
| `src/__tests__/match-recalculation.test.js` | New | Unit tests for UF detection, location parameter, notification messages |

## Architecture Diagram (Flow)

```
ProfilePage.handleSave
  │
  ├─ 1. Capture previousUF = profile?.state
  │
  ├─ 2. updateProfile({ state, city, ... })  ──→  Firestore users/{uid}
  │       │
  │       ├─ SUCCESS
  │       │     │
  │       │     ├─ 3. UF changed? (previousUF !== formData.state)
  │       │     │     │
  │       │     │     ├─ NO → exit (profile saved, no recalc)
  │       │     │     │
  │       │     │     └─ YES → 4. Pre-requisites check
  │       │     │              │
  │       │     │              ├─ No desireProfile → show guard message
  │       │     │              ├─ No userVehicles   → show guard message
  │       │     │              │
  │       │     │              └─ Both OK → 5. Recalculate
  │       │     │                            │
  │       │     │                            ├─ Fetch data (listings, desires, trust)
  │       │     │                            ├─ computeMatches(..., location: {state, city})
  │       │     │                            ├─ Compare oldCount vs newCount
  │       │     │                            └─ Display notification
  │       │     │
  │       │     └─ catch: "Falha ao recalcular trocas. Tente novamente."
  │       │
  │       └─ FAILURE → setSubmitError("Falha ao salvar localizacao.")
  │
  └─ 6. setSubmitting(false)
```

## File 1: `src/pages/ProfilePage.jsx`

### New State Variables

```javascript
const [recalculating, setRecalculating] = useState(false);
const [recalcMessage, setRecalcMessage] = useState(null);
const [recalcMessageType, setRecalcMessageType] = useState(null); // 'success' | 'info' | 'error'
const [previousMatchCount, setPreviousMatchCount] = useState(0);
```

### Modified `handleSave` Function

The existing `handleSave` is extended with recalculation logic:

```javascript
const handleSave = async (e) => {
  e.preventDefault();
  setSubmitError(null);
  setRecalcMessage(null);
  clearError();
  setSubmitting(true);

  const previousUF = profile?.state;

  try {
    // Step 1: Save profile (existing path)
    await updateProfile({
      name: formData.name.trim(),
      phone: formData.phone.trim() || null,
      cpf: formData.cpf || null,
      state: formData.state || null,
      city: formData.city.trim() || null,
    });

    // Step 2: Detect UF change
    const ufChanged = previousUF !== formData.state;
    if (!ufChanged) {
      setEditing(false);
      setSubmitting(false);
      return;
    }

    // Step 3: Pre-requisites guard
    if (!desireProfile) {
      setRecalcMessage('Defina seu perfil de desejo para recalcular trocas.');
      setRecalcMessageType('info');
      setEditing(false);
      setSubmitting(false);
      return;
    }

    if (!userVehicles || userVehicles.length === 0) {
      setRecalcMessage('Publique um veículo para recalcular trocas.');
      setRecalcMessageType('info');
      setEditing(false);
      setSubmitting(false);
      return;
    }

    // Step 4: Recalculate matches
    setRecalculating(true);

    try {
      const allListings = await fetchActiveListings();
      const oldCount = previousMatchCount;
      const newMatches = computeMatches(
        user.uid,
        desireProfile,
        userVehicles,
        allListings,
        allDesires,   // fetched or from existing data
        allTrustScores,
        { state: formData.state, city: formData.city }
      );
      const newCount = newMatches.length;

      // Step 5: Display notification
      if (newCount > oldCount) {
        setRecalcMessage(`${newCount - oldCount} novas trocas encontradas!`);
        setRecalcMessageType('success');
      } else if (newCount < oldCount) {
        setRecalcMessage('Suas trocas foram atualizadas');
        setRecalcMessageType('success');
      } else {
        setRecalcMessage('Nenhuma alteração nas suas trocas');
        setRecalcMessageType('info');
      }

      setPreviousMatchCount(newCount);
    } catch {
      setRecalcMessage('Falha ao recalcular trocas. Tente novamente.');
      setRecalcMessageType('error');
    } finally {
      setRecalculating(false);
    }

    setEditing(false);
  } catch {
    setSubmitError('Ops! Não foi possível salvar as alterações.');
  } finally {
    setSubmitting(false);
  }
};
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Separate `recalculating` state from `submitting` | Profile save and recalculation are independent phases; user should see distinct feedback |
| Nested try/catch for recalculation | Profile save error and recalculation error produce different messages; save success is not rolled back by recalc failure |
| `previousMatchCount` in component state | Tracks match count across save cycles; initialized from existing match data when available |
| Loading state blocks re-submission | `submitting` disables the save button, preventing race conditions from double-clicks |

### Notification Rendering

The recalculation message is rendered as a notification banner below the form, using the existing `ErrorBanner` pattern for errors and a new success/info banner for results:

```jsx
{recalcMessage && (
  <div className={`profile-page__recalc-banner profile-page__recalc-banner--${recalcMessageType}`}
       role="status" aria-live="polite">
    {recalcMessage}
    {(recalcMessageType === 'success' && newCount !== oldCount) && (
      <button onClick={() => onNavigateToSwaps?.()} type="button">
        Ver trocas
      </button>
    )}
    {recalculating && (
      <span className="profile-page__spinner" aria-label="Recalculando..." />
    )}
  </div>
)}
```

### Data Fetching for Recalculation

The recalculation needs `allDesires` and `allTrustScores`, which are fetched the same way as the initial match computation. Two approaches:

| Approach | Pros | Cons |
|----------|------|------|
| Fetch on-demand in `handleSave` | Fresh data; no stale state | Additional latency; ~2 Firestore reads per other user |
| Pre-fetch in `useEffect` (existing pattern) | Already available in component | Data may be stale since last page load |

**Selected approach:** Fetch on-demand in `handleSave` (within the recalculation block). This ensures the recalculation uses the most current data. The existing `useEffect` that loads `desireProfile` and `userVehicles` on mount provides those; `allListings`, `allDesires`, and `allTrustScores` are fetched inline.

## File 2: `src/lib/match-engine.js`

### Signature Change

```javascript
// BEFORE
export function computeMatches(
  currentUserId,
  desireProfile,
  userListings,
  allListings,
  allDesires,
  allTrustScores
)

// AFTER
export function computeMatches(
  currentUserId,
  desireProfile,
  userListings,
  allListings,
  allDesires,
  allTrustScores,
  location  // optional: { state: string, city: string }
)
```

### Location Override Logic

When the `location` parameter is provided, the primary UF used for region matching is overridden. The change affects two functions that reference `desireProfile.regions[0]`:

#### `isLevel1Match` — Region Check

```javascript
// The effective UF for region matching:
const primaryUF = location
  ? location.state
  : (desireProfile.regions && desireProfile.regions[0]);
```

The `isLevel1Match` function at line 75 currently does:
```javascript
if (!areUFsAdjacent(listing.region, desire.regions ? desire.regions[0] : null))
```

This becomes:
```javascript
const effectiveUF = (location && location.state)
  ? location.state
  : (desire.regions ? desire.regions[0] : null);
if (!areUFsAdjacent(listing.region, effectiveUF))
```

#### `isLevel2Match` — Region Check

The `checkRegionMatch` function at line 116 receives `desiredRegions`. When `location` is provided, we construct a synthetic `desiredRegions` array with the new state:

```javascript
const effectiveRegions = (location && location.state)
  ? [location.state]
  : desireProfile.regions;
```

This array is passed through to `checkRegionMatch` and `isLevel1Match`.

### Implementation Pattern

Rather than threading `location` through every internal function, the override is applied at the `computeMatches` entry point by creating a modified desire profile:

```javascript
export function computeMatches(currentUserId, desireProfile, userListings, allListings, allDesires, allTrustScores, location) {
  // ... existing validation ...

  // Override region if location parameter provided
  const effectiveDesire = location
    ? { ...desireProfile, regions: [location.state] }
    : desireProfile;

  // Rest of function uses effectiveDesire instead of desireProfile
  // ...
}
```

**Rationale:** This is the least-invasive change. It avoids modifying the signatures of `isLevel1Match`, `isLevel2Match`, `checkRegionMatch`, and `isBidirectional`. The spread operator creates a shallow copy, so the original `desireProfile` is not mutated.

### Backward Compatibility

The `location` parameter is optional and defaults to `undefined`. All existing callers of `computeMatches` (without the 7th argument) behave identically to the current implementation.

## File 3: `src/__tests__/match-recalculation.test.js`

### Test Structure

```
match-recalculation.test.js
├── UF Change Detection
│   ├── same UF → no recalculation
│   ├── different UF → recalculation triggered
│   └── UF cleared → treated as change
│
├── computeMatches with location parameter
│   ├── location.state overrides desire.regions[0]
│   ├── no location → uses desire.regions[0] (unchanged)
│   ├── location.state with adjacent UF listings
│   └── location.state with non-adjacent UF listings
│
├── Pre-requisite Guards
│   ├── no desire profile → skip recalc
│   └── no user vehicles → skip recalc
│
├── Notification Messages
│   ├── newCount > oldCount → "X novas trocas encontradas!"
│   ├── newCount < oldCount → "Suas trocas foram atualizadas"
│   ├── newCount === oldCount → "Nenhuma alteração nas suas trocas"
│   └── newCount === 0 → "Suas trocas foram atualizadas"
│
└── Error Handling
    ├── computeMatches throws → error message displayed
    └── profile save fails → save error message displayed
```

### Test Framework

Uses the existing test framework in the project. Mock dependencies:
- `computeMatches` from `match-engine.js` (unit tests — real function)
- `ProfilePage` component (integration tests — rendered with React Testing Library or equivalent)
- `updateProfile` (mocked via `useAuth` context)
- `fetchActiveListings`, `getDesireProfile` (mocked)

## Error Boundaries

| Error Source | Scope | Recovery |
|--------------|-------|----------|
| Firestore `updateProfile` failure | Outer try/catch | `setSubmitError`; user stays in edit mode |
| `computeMatches` throws | Inner try/catch | `setRecalcMessage` with error; profile already saved |
| Data fetch fails (`fetchActiveListings`) | Inner try/catch | Same as computeMatches error |
| Component unmounts during async | No explicit cleanup needed | React discards state updates on unmounted component |

## State Machine

```
                ┌─────────────┐
                │  IDLE       │
                └──────┬──────┘
                       │ user clicks "Salvar"
                ┌──────▼──────┐
                │  SAVING     │ ← submitting = true, button disabled
                └──────┬──────┘
                       │ updateProfile result
           ┌───────────┼───────────┐
           │ FAIL      │           │ SUCCESS
           ▼           │           ▼
    ┌────────────┐     │    ┌──────────────┐
    │  ERROR     │     │    │  CHECK UF    │
    │  (save)    │     │    └──────┬───────┘
    └────────────┘     │           │
                       │     ┌─────┴─────┐
                       │     │ SAME UF   │ DIFF UF
                       │     │           │
                       │     ▼           ▼
                       │  ┌────────┐  ┌────────────┐
                       │  │ DONE   │  │ GUARD CHECK│
                       │  └────────┘  └────┬───────┘
                       │                   │
                       │          ┌────────┼────────┐
                       │          │ FAIL   │ PASS   │
                       │          ▼        ▼        │
                       │     ┌────────┐ ┌──────────┐
                       │     │ DONE   │ │ RECALC   │
                       │     │ (info) │ │ (loading)│
                       │     └────────┘ └────┬─────┘
                       │                     │
                       │            ┌────────┼────────┐
                       │            │ OK     │ FAIL   │
                       │            ▼        ▼        │
                       │       ┌────────┐ ┌────────┐ │
                       └──────►│ DONE   │ │ DONE   │
                               │(notify)│ │(error) │
                               └────────┘ └────────┘
```

## CSS Requirements

Minimal CSS additions for the recalculation notification banner:

```css
.profile-page__recalc-banner {
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm);
  margin: var(--spacing-md) 0;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.profile-page__recalc-banner--success {
  background: color-mix(in srgb, var(--color-success) 15%, transparent);
  border: 1px solid var(--color-success);
  color: var(--color-success);
}

.profile-page__recalc-banner--info {
  background: color-mix(in srgb, var(--color-info) 15%, transparent);
  border: 1px solid var(--color-info);
  color: var(--color-info);
}

.profile-page__recalc-banner--error {
  background: color-mix(in srgb, var(--color-error) 15%, transparent);
  border: 1px solid var(--color-error);
  color: var(--color-error);
}
```

Colors reference existing CSS custom properties from the dark-mode-first design system.
