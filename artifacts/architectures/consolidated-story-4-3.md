# Consolidated Review — Story 4.3: Location Update & Match Recalculation

## Artifact Cross-Reference

| Artifact | Path | Status |
|----------|------|--------|
| Requirements | `.engineering-loop/artifacts/architectures/requirements-story-4-3.md` | Complete |
| Cloud Architecture | `.engineering-loop/artifacts/architectures/cloud-story-4-3.md` | Complete (no changes) |
| Solution Design | `.engineering-loop/artifacts/architectures/solution-story-4-3.md` | Complete |
| BDD Journey Map | `.engineering-loop/artifacts/bdd-journeys/journey-story-4-3-location-recalculation.md` | Reference |

## Gap Analysis

### Requirements → Cloud: No Gaps

| Requirement | Cloud Coverage | Verdict |
|-------------|----------------|---------|
| FR-1: UF change detection | Client-side only — no cloud impact | ✓ Covered |
| FR-2: Profile update | `users/{uid}` update via existing `updateDoc` path | ✓ Covered |
| FR-3: Match recalculation trigger | Client-side `computeMatches` — no cloud calls | ✓ Covered |
| FR-4: Pre-recalculation guards | Client-side state checks (`desireProfile`, `userVehicles`) | ✓ Covered |
| FR-5: Notification display | Client-side UI rendering — no cloud calls | ✓ Covered |
| FR-6: Error handling | Client-side try/catch — no cloud changes | ✓ Covered |
| NFR-1: Performance (<3s) | Client-side computation; no cloud SLA impact | ✓ Covered |
| NFR-2: Race conditions | `submitting` state prevents concurrent saves | ✓ Covered |

### Requirements → Solution: No Gaps

| Requirement | Solution Coverage | Verdict |
|-------------|-------------------|---------|
| FR-1: UF change detection | `previousUF` captured before `updateProfile`; comparison in `handleSave` | ✓ Covered |
| FR-2: Profile update | Reuses existing `updateProfile` call in `handleSave` | ✓ Covered |
| FR-3: Recalculation with location param | `computeMatches` accepts optional `location`; override via `effectiveDesire` spread | ✓ Covered |
| FR-4: Pre-requisite guards | Guard checks for `desireProfile` and `userVehicles.length` before recalc | ✓ Covered |
| FR-5: Notification display | `recalcMessage` / `recalcMessageType` state; conditional banner with link | ✓ Covered |
| FR-6: Recalculation error | Nested try/catch; separate error message from save error | ✓ Covered |
| NFR-1: Performance | Loading state; 3s threshold documented | ✓ Covered |
| NFR-2: Concurrency | `submitting` disables button; state machine prevents re-entry | ✓ Covered |
| NFR-3: Accessibility | `role="status"`, `aria-live="polite"`, `aria-busy="true"` | ✓ Covered |

### Solution → BDD Journeys: Coverage

| Journey | Solution Coverage | Verdict |
|---------|-------------------|---------|
| J1: UF change with new matches | `handleSave` UF detection → `computeMatches` → notification with count diff | ✓ Covered |
| J2: City-only change (same UF) | `ufChanged` check returns early; no recalculation | ✓ Covered |
| J3: No desire profile | Guard check `!desireProfile` → info message | ✓ Covered |
| J4: No published vehicles | Guard check `!userVehicles.length` → info message | ✓ Covered |
| J5: Firestore save failure | Outer catch → `setSubmitError` | ✓ Covered |
| J6: Recalculation failure | Inner catch → `setRecalcMessage` with error | ✓ Covered |
| J7: No change in match count | `newCount === oldCount` → "Nenhuma alteração" message | ✓ Covered |

**All 7 journeys covered. No gaps.**

## Architecture Decision Log

| # | Decision | Alternatives Considered | Rationale |
|---|----------|------------------------|-----------|
| ADR-1 | Client-side recalculation only | Server-side (Firebase Functions) | MVP constraint: no Functions. Client-side is sufficient for single-user scope. |
| ADR-2 | Optional `location` parameter on `computeMatches` | Modify `desireProfile.regions` before calling | Optional parameter preserves backward compatibility; no callers need updating. |
| ADR-3 | Spread `desireProfile` to create `effectiveDesire` | Thread `location` through internal functions | Least invasive; avoids changing signatures of `isLevel1Match`, `isLevel2Match`, etc. |
| ADR-4 | Nested try/catch (save vs recalc) | Single try/catch with error discrimination | Profile save and recalculation are independent concerns; different error messages needed. |
| ADR-5 | Fetch data on-demand in `handleSave` | Pre-fetch in `useEffect` | Fresh data for recalculation; avoids stale state between page load and save. |
| ADR-6 | Separate `recalculating` state from `submitting` | Single loading state | Distinct user feedback for save phase vs recalculation phase. |

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation | Status |
|------|----------|------------|------------|--------|
| `computeMatches` throws on inconsistent data | Medium | Low | Nested try/catch; error message displayed; old matches preserved | Mitigated |
| Race condition: user changes UF twice quickly | Low | Medium | `submitting` state disables save button; state machine prevents re-entry | Mitigated |
| Recalculation >3s on large datasets | Low | Low | 3s threshold is generous for client-side JS; loading state shown | Accepted |
| Stale data between page load and recalc | Low | Low | On-demand fetch in `handleSave` ensures fresh data | Mitigated |
| `effectiveDesire` spread loses deep properties | Low | Low | `regions` is a top-level array; shallow spread is sufficient | Mitigated |

## Invariants Verification

| Invariant | Status | Notes |
|-----------|--------|-------|
| I1: Auth — OAuth only | ✓ Preserved | Story does not touch authentication |
| I2: Match algorithm — 2 levels | ✓ Preserved | Uses existing Level 1 + Level 2 logic |
| I3: Trust score — client-side | ✓ Preserved | `allTrustScores` passed as before |
| I4: No Firestore schema changes | ✓ Preserved | Only writes to existing `state`/`city` fields |
| I5: Client-side computation | ✓ Preserved | No Firebase Functions |
| I6: Dark-mode-first UI | ✓ Preserved | CSS custom properties; no hardcoded colors |
| I7: Portuguese (BR) prose | ✓ Preserved | All messages in Brazilian Portuguese |

## Files Changed

| File | Operation | Lines Affected (estimate) |
|------|-----------|--------------------------|
| `src/pages/ProfilePage.jsx` | Modify | ~60 lines added (state, logic, rendering) |
| `src/lib/match-engine.js` | Modify | ~10 lines modified (signature + override logic) |
| `src/__tests__/match-recalculation.test.js` | Create | ~200 lines (new test file) |
| `src/pages/ProfilePage.css` | Modify | ~20 lines (notification banner styles) |

## Go/No-Go Checklist

| Criterion | Status |
|-----------|--------|
| Requirements artifact complete | ✓ |
| Cloud architecture reviewed (no changes needed) | ✓ |
| Solution design complete | ✓ |
| All BDD journeys covered | ✓ |
| No new security concerns | ✓ |
| No new Firestore indexes needed | ✓ |
| Backward compatibility preserved (`computeMatches` optional param) | ✓ |
| Error handling for all failure modes | ✓ |
| Performance threshold defined | ✓ |
| Accessibility requirements addressed | ✓ |
| Portuguese (BR) prose verified | ✓ |

**Verdict: GO — Ready for implementation.**
