# Requirements — Story 4.3: Location Update & Match Recalculation

## Scope

When the user changes their state (UF) on the ProfilePage, the match engine is recomputed using the new UF as the primary region for proximity matching. The user receives a notification about the result. City-only changes (same UF) do not trigger recalculation.

This is a **feature addition** within the existing architecture. No new cloud services, no schema changes, no security rule modifications.

## Invariants (must not break)

| # | Invariant | Rationale |
|---|-----------|-----------|
| I1 | Auth: OAuth only (Google/Facebook) | Unchanged — story does not touch authentication |
| I2 | Match algorithm: 2 levels only | Recalculation uses existing Level 1 + Level 2 logic |
| I3 | Trust score: client-side only | `allTrustScores` passed to `computeMatches` as before |
| I4 | No schema changes to Firestore | Only reads/writes existing `users/{uid}` fields (`state`, `city`) |
| I5 | Client-side computation only | Match recalculation runs in-browser; no Firebase Functions |
| I6 | Dark-mode-first UI | Notification messages use existing CSS custom properties |
| I7 | Portuguese (BR) prose | All user-facing text in Brazilian Portuguese |

## Functional Requirements

### FR-1: UF Change Detection

**Description:** ProfilePage must detect when the user changes their state (UF) field, distinguishing it from city-only changes.

**Acceptance criteria:**
- [ ] `handleSave` captures the previous UF value before applying the update
- [ ] Comparison `previousUF !== newUF` determines whether recalculation is needed
- [ ] City-only change (same UF) → profile saved, no recalculation, no match notification
- [ ] Both UF and city changed → profile saved, recalculation triggered
- [ ] UF cleared (user deselects state) → treated as a UF change; recalculation triggered with `null` state

### FR-2: Profile Update (Existing Path)

**Description:** Location update reuses the existing `updateProfile` call via `AuthContext`.

**Acceptance criteria:**
- [ ] `updateProfile({ state: formData.state || null, city: formData.city.trim() || null, ... })` persists to Firestore
- [ ] Profile save success is a prerequisite before attempting recalculation
- [ ] Profile save failure → error displayed; recalculation not attempted
- [ ] Existing validation (e.g., empty state inline error) preserved

### FR-3: Match Recalculation Trigger

**Description:** On UF change, `computeMatches` is called with the new location as an override parameter.

**Acceptance criteria:**
- [ ] `computeMatches` receives an optional `location` parameter: `{ state: string, city: string }`
- [ ] When `location` is provided, `location.state` is used as the primary UF for region matching instead of `desireProfile.regions[0]`
- [ ] When `location` is not provided, existing behavior unchanged (uses `desireProfile.regions`)
- [ ] Recalculation uses the same data sources: `allListings`, `allDesires`, `allTrustScores`, `userListings`
- [ ] Recalculation completes within 3 seconds for typical data volumes (<1000 listings)

### FR-4: Pre-Recalculation Guards

**Description:** Recalculation is skipped with an informational message when prerequisites are not met.

**Acceptance criteria:**
- [ ] No desire profile → skip recalculation, show "Defina seu perfil de desejo para recalcular trocas."
- [ ] No published vehicles → skip recalculation, show "Publique um veículo para recalcular trocas."
- [ ] Profile updated with new UF regardless of guard outcome

### FR-5: Notification Display

**Description:** After recalculation, the user receives a notification comparing old vs new match count.

**Acceptance criteria:**

| Scenario | Condition | Message | Link |
|----------|-----------|---------|------|
| New matches found | `newCount > oldCount` | `"{newCount - oldCount} novas trocas encontradas!"` | Yes → swap tab |
| Matches decreased | `newCount < oldCount` | `"Suas trocas foram atualizadas"` | Yes → swap tab |
| No change | `newCount === oldCount` | `"Nenhuma alteração nas suas trocas"` | No |
| Zero matches | `newCount === 0` | `"Suas trocas foram atualizadas"` | No |

### FR-6: Error Handling — Recalculation Failure

**Description:** If `computeMatches` throws after a successful profile save, the error is caught and displayed without invalidating the profile update.

**Acceptance criteria:**
- [ ] Recalculation wrapped in try/catch, separate from profile save try/catch
- [ ] Error message: "Falha ao recalcular trocas. Tente novamente."
- [ ] Old matches remain in place (not cleared)
- [ ] Profile reflects new UF (save was successful)

## Non-Functional Requirements

### NFR-1: Performance

| Metric | Requirement | Measurement |
|--------|-------------|-------------|
| Recalculation time | < 3 seconds | `performance.now()` around `computeMatches` call |
| Profile save latency | < 2 seconds (existing) | Firestore `updateDoc` round-trip |
| UI responsiveness | No main-thread block > 50ms | Loading state shown during async operations |

**Rationale:** Client-side computation over potentially large datasets. A 3-second threshold accounts for worst-case listing counts and match engine complexity (O(n) listings × bidirectional checks).

### NFR-2: Concurrency / Race Conditions

| Risk | Mitigation |
|------|-----------|
| User changes UF twice rapidly | Loading state (`submitting`) disables save button; second click ignored |
| Recalculation runs while user navigates away | No cleanup needed; result discarded if component unmounted |
| Firestore save succeeds, recalculation data stale | Acceptable — user can re-save to trigger fresh recalculation |

### NFR-3: Accessibility

- [ ] Notification message announced via `role="status"` or equivalent live region
- [ ] Loading spinner has `aria-busy="true"` on the form container
- [ ] Error messages associated with the form via `aria-describedby`

## Volumetry

| Dimension | Estimate | Notes |
|-----------|----------|-------|
| Users affected | Single user (self-profile edit) | No broadcast, no multi-user operation |
| Firestore reads | 1 (profile update is write-only) + recalculation reads (existing pattern) | `computeMatches` receives pre-fetched data; no new Firestore reads |
| Firestore writes | 1 (`users/{uid}` update) | Same as existing profile save |
| Computation scope | Client-side only, single device | No server load impact |
| Data volume for recalculation | ~all active listings + all desire profiles + all trust scores | Same dataset as initial match computation |

## Security

- **No new security concerns.** The story uses:
  - Existing Auth context (`useAuth()`) — user is already authenticated
  - Existing Firestore rules — `users/{uid}` update guarded by `request.auth.uid == userId`
  - Existing data access patterns — `computeMatches` receives data already fetched by authorized service calls
- **No new sensitive data** is read, written, or exposed
- **No CSRF/XSS vectors** — form input is validated and trimmed server-side by Firestore rules

## Data Model

**No schema changes.** Existing fields used:

| Collection | Document | Field | Operation |
|------------|----------|-------|-----------|
| `users/{uid}` | user profile | `state` | Write (update) |
| `users/{uid}` | user profile | `city` | Write (update) |
| `users/{uid}` | user profile | `updatedAt` | Write (auto, via `serverTimestamp()`) |

All other data (listings, desires, trust scores) are read-only during recalculation, using existing fetch patterns.

## Dependencies

| Dependency | Status | Source |
|------------|--------|--------|
| `ProfilePage.jsx` — state/city fields, `handleSave` | Exists | `src/pages/ProfilePage.jsx:50-56` |
| `AuthContext.updateProfile` | Exists | Wired in `ProfilePage` |
| `computeMatches` function | Exists | `src/lib/match-engine.js:194` |
| `BRAZIL_STATES` data | Exists | `src/data/brazil-states.js` |
| `ErrorBanner` component | Exists | Used in `ProfilePage` |
| Desire profile fetch (`getDesireProfile`) | Exists | `src/lib/desire-profile.js` |
| Active listings fetch (`fetchActiveListings`) | Exists | `src/lib/listings.js` |
