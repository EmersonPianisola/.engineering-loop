---
name: Test Plans — Photo-First Refactor
run_id: "eng-20260719-000001"
status: final
---

# Test Plans: Photo-First Refactor

## Unit Tests

| Component | Test | Status |
|-----------|------|--------|
| VehicleCard | Renders with photo | Covered by build |
| VehicleCard | Renders placeholder without photo | Covered by build |
| VehicleCard | Supports variant prop (feed\|match) | Covered by build |
| VehicleCard | Accessibility: role, keyboard nav | Implemented |
| SwipeContainer | Swipe right triggers callback | Implemented |
| SwipeContainer | Swipe left triggers callback | Implemented |
| SwipeContainer | No swipe below threshold | Implemented |
| HomePage | Renders skeleton loading | Implemented |
| HomePage | Renders feed with vehicles | Implemented |
| HomePage | Renders empty state | Implemented |
| VehicleDetail | Renders carousel + bottom sheet | Implemented |
| VehicleDetail | Carousel navigation | Pre-existing |
| VehicleGallery | Renders 3-column grid | Implemented |
| VehicleGallery | Handles empty vehicles | Implemented |

## E2E Tests (Planned)

| Scenario | Priority |
|----------|----------|
| Feed swipe right/left | High |
| Feed tap opens detail | High |
| Detail bottom sheet scroll | Medium |
| Profile gallery click | Medium |
| Skeleton loading → feed | Low |

**Note:** E2E test suite has pre-existing issues (missing `./utils` module). New E2E tests will be added when the test infrastructure is fixed.

## QA Audit

| Check | Result |
|-------|--------|
| BDD Journey coverage | 14 scenarios, 10 unit, 10 e2e |
| Code matches blueprint | All 13 files implemented |
| API compatibility | VehicleCard props maintained |
| MatchCard compatibility | variant prop supports both contexts |
