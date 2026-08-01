---
name: e2e-execute
id: e2e.execute
version: 1.0.0
type: stage
description: 'Mandatory E2E browser testing. Playwright headless with DOM, console, network asserts. Auto-fix loop. BDD→E2E 1:1 coverage enforcement.'
---

# STAGE: E2E Execute (Browser Testing)
<!-- ID: e2e.execute -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the E2E test executor.
- DO NOT modify application source code directly (except in auto-fix loop).
- DO NOT transition to other stages.
- The moment the E2E report is produced, your task is FINISHED.

## Procedure

1. **Prerequisite Check:** If `state.stages.verify.done != true` → `status: blocked`, `blocking_condition: verification not complete`. **EXIT.**
2. **UI Detection:** Check if project contains frontend files (React, Vue, Angular, Svelte, Next.js, etc.). If NO UI → `done: true` (deactivated). **SKIP.**
3. Proceed with the steps below.

# E2E Execute — Playwright Headless Browser Testing

**Skill:** `e2e-playwright`
**Runs when:** `state.stages.e2e.execute.done == false`
**Prerequisite:** `state.stages.verify.done == true`
**Constraint:** `max_e2e_execute_attempts` (default: 3)

## Execute — E2E Test Pipeline

### Step 1: Infrastructure Setup

If Playwright is not configured, set it up:

```bash
npm install -D @playwright/test
npx playwright install --with-deps chromium
```

Create `playwright.config.js` with headless, serial execution:

```js
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,       // Serial for deterministic state
  retries: 0,
  workerTimeout: 120000,
  reporter: [['list'], ['html', { open: 'never' }], ['json', { outputFile: 'e2e-results.json' }]],
  use: {
    baseURL: 'http://localhost:' + (process.env.APP_PORT || '5173'),
    trace: 'retain-on-failure',
    screenshot: 'on',          // Always capture screenshots
    video: 'retain-on-failure',
    headless: true,
  },
  webServer: {
    command: process.env.START_COMMAND || 'npm run dev',
    port: parseInt(process.env.APP_PORT || '5173'),
    timeout: 120000,
    reuseExistingServer: !process.env.CI,
  },
});
```

### Step 2.5: Confirmed Lessons — Mandatory E2E Rules

**L-001 (Confirmed):** API-only E2E tests miss SSR fetch errors in Server Components.
- **Rule:** Every E2E test suite MUST include page-level tests that navigate to and render actual routes, not just API endpoint tests.
- **Check:** For each page with server-side data fetching, write at least one `page.goto()` test that verifies the page renders without server errors.
- **Monitor:** Browser console for `ERR_INVALID_URL` during test runs.

**L-002 (Confirmed):** E2E tests that only assert element presence miss broken navigation links.
- **Rule:** For every navigation link or button that triggers a route change, the E2E test MUST click it and verify the destination page renders — not just assert the element is visible.
- **Pattern:** click link → `waitForURL` → assert destination content.
- **Apply to:** All action buttons (Novo Cliente, Novo Pedido, Editar, etc.).

### Step 3: Detect Auth Provider + Wire Bypass

Detect the authentication provider and configure bypass for testing:

| Provider | Bypass Mechanism | Reference |
|----------|-----------------|-----------|
| Clerk | `__dev_bypass` cookie = `1` | `{reference-root}/ui-testing-patterns.md` |
| NextAuth | Session mock in middleware | `{reference-root}/ui-testing-patterns.md` |
| Supabase | Service role key, RLS bypass | `{reference-root}/ui-testing-patterns.md` |
| Custom JWT | localStorage token injection | `{reference-root}/ui-testing-patterns.md` |
| None | Skip | — |

### Step 3: Load Lessons

1. Load shared lessons: `{artifact-root}/lessons-shared.json` (if exists)
2. Load project lessons: `{artifact-root}/lessons.json` (if exists)
3. Filter confirmed lessons with `origin_stage` containing "e2e" or "qa"
4. Apply all prevention rules before writing tests

**L-001 (Confirmed):** API-only E2E tests miss SSR fetch errors in Server Components.
- **Rule:** Every E2E test suite MUST include page-level tests that navigate to and render actual routes, not just API endpoint tests.
- **Check:** For each page with server-side data fetching, write at least one `page.goto()` test that verifies the page renders without server errors.
- **Monitor:** Browser console for `ERR_INVALID_URL` during test runs.

**L-002 (Confirmed):** E2E tests that only assert element presence miss broken navigation links.
- **Rule:** For every navigation link or button that triggers a route change, the E2E test MUST click it and verify the destination page renders — not just assert the element is visible.
- **Pattern:** click link → `waitForURL` → assert destination content.
- **Apply to:** All action buttons (Novo Cliente, Novo Pedido, Editar, etc.).

### Step 4: Derive Test Scenarios

Generate E2E scenarios from multiple sources (in order of priority):

1. **BDD Behavior Map** — Every `@e2e` scenario must have a corresponding test
2. **Implementation Blueprint** — User-facing flows from file structure
3. **Route Discovery** — File paths → browser routes (fallback)

Cross-reference: every `@e2e` scenario from the Behavior Map MUST have a test. Orphaned scenarios are FAIL conditions.

### Step 5: Create Page Objects

For each major page/route, create a Page Object class:

```js
// e2e/pages/DashboardPage.js
export class DashboardPage {
  constructor(page) {
    this.page = page;
    this.url = '/dashboard';
  }

  async goto() {
    await this.page.goto(this.url);
  }

  // Locators using role-based selectors (resilient to CSS changes)
  get menuButton() {
    return this.page.getByRole('button', { name: /menu|navigation/i });
  }

  get sidebar() {
    return this.page.getByRole('navigation');
  }

  // Actions
  async openMenu() {
    await this.menuButton.click();
  }

  // Assertions
  async expectMenuVisible() {
    await expect(this.sidebar).toBeVisible();
  }
}
```

**Locator Strategy (MANDATORY):**
- Use `getByRole()`, `getByLabel()`, `getByText()` — NEVER CSS/XPath selectors
- Role-based locators survive CSS class changes and visual refactors
- Fallback: `data-testid` attributes (add to source if role-based fails)

### Step 6: Generate Test Specs

For each scenario, write a Playwright test with four assertion layers:

```js
import { test, expect } from '@playwright/test';
import { DashboardPage } from '../pages/DashboardPage.js';

test.describe('Dashboard', () => {
  test('user can open navigation menu', async ({ page }) => {
    // Given
    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    // DOM assert — page loaded correctly
    await expect(page).toHaveTitle(/dashboard/i);

    // When
    await dashboard.openMenu();

    // Then — DOM assertion
    await dashboard.expectMenuVisible();

    // Then — Dimension assertion (CSS collapse detection)
    const boundingBox = await dashboard.sidebar.boundingBox();
    expect(boundingBox.width).toBeGreaterThan(0);
    expect(boundingBox.height).toBeGreaterThan(0);
  });
});
```

### Step 7: Run Tests with Four-Layer Assertions

Each test must assert four layers:

| Layer | What It Catches | Assertion |
|-------|----------------|-----------|
| **DOM** | Element exists, is visible, has correct text | `expect(locator).toBeVisible()` |
| **Dimension** | CSS collapse, zero-size elements | `boundingBox().width > 0` |
| **Console** | JavaScript errors, React warnings | Filter `page.on('console')` for errors |
| **Network** | 4xx/5xx responses, failed API calls | Intercept `page.route()`, check status |

### Step 8: Console Error Gate

Capture and assert on browser console output:

```js
const consoleErrors = [];
page.on('console', msg => {
  if (msg.type() === 'error') {
    consoleErrors.push(msg.text());
  }
});

// After test actions
expect(consoleErrors).toHaveLength(0);
```

Known warnings to ignore (configure in `playwright.config.js`):
- React DevTools messages
- Hydration mismatches (non-blocking warning)
- Third-party library warnings

### Step 9: Network Error Gate

Intercept and assert on network responses:

```js
const failedRequests = [];
await page.route('**/*', async (route) => {
  const response = await route.fetch();
  const status = response.status();
  if (status >= 400) {
    failedRequests.push({ url: route.request().url(), status });
  }
  await route.continue();
});

// After test actions
expect(failedRequests).toHaveLength(0);
```

### Step 10: Screenshot Evidence

Capture screenshot at the end of every test (pass or fail):

```js
test.afterEach(async ({ page }, testInfo) => {
  await page.screenshot({
    path: `e2e/screenshots/${testInfo.title}-${testInfo.status}.png`,
    fullPage: true,
  });
});
```

### Step 11: Run and Evaluate

```bash
npx playwright test --reporter=list
```

Evaluate results:

```
IF all tests pass
    AND zero console errors
    AND zero network 4xx/5xx
    AND BDD→E2E coverage is 100%:
    VERDICT: PASS
    state.stages.e2e.execute.done = true
ELSE:
    VERDICT: FAIL
    Produce gap report with screenshots
    state.stages.e2e.execute.done = false
    state.stages.impl.code.done = false  # Reset for auto-fix
```

## Auto-Fix Loop

On FAIL, attempt to fix common issues (max `max_e2e_execute_attempts`):

| Issue | Auto-Fix |
|-------|----------|
| Selector not found | Switch to role-based locator, or add `data-testid` |
| Auth blocking route | Apply auth bypass pattern |
| Port conflict | Find available port, restart server |
| Missing dependency | `npm install <package>` |
| Stale build cache | Clear cache, rebuild |
| Hydration mismatch | Warn (non-blocking) |
| Console error from missing asset | Verify asset exists, fix path |

After each fix:
1. Run regression gate: `tsc --noEmit && npm run lint` (if applicable)
2. Re-run failed tests
3. If still failing → next attempt or ESCALATE

## BDD→E2E Coverage Check

Cross-reference Behavior Map `@e2e` scenarios against implemented tests:

```
FOR each @e2e scenario in Behavior Map:
    IF no corresponding test exists:
        ORPHANED — generate test or flag as gap
    IF test exists but fails:
        FAILED — becomes fix task
    IF test passes:
        COVERED — good
```

**100% coverage is mandatory.** Orphaned scenarios reset `done = false`.

## Validate — Verdict

```
PASS: All tests pass, zero console errors, zero network errors, 100% BDD→E2E coverage
FAIL: Any test failure, console error, network error, or orphaned scenario
```

### Write E2E Report

Output to `{artifact-root}/e2e-report-{slug}.md`:

```markdown
# E2E Report

**Feature:** {slug}
**Verdict:** PASS | FAIL
**Iteration:** {n}

## Test Results

| Scenario | Status | Screenshot |
|----------|--------|------------|
| {name} | PASS/FAIL | {path} |

## Console Errors

| Message | Test |
|---------|------|
| {error} | {test} |

## Network Errors

| URL | Status | Test |
|-----|--------|------|
| {url} | {code} | {test} |

## BDD→E2E Coverage

| Scenario | Tag | Test | Status |
|----------|-----|------|--------|
| {name} | @e2e | {file} | COVERED/ORPHANED |

## Coverage Summary

| Metric | Value |
|--------|-------|
| BDD→E2E Coverage | {percentage}% |
| Tests Passed | {count} |
| Tests Failed | {count} |
| Console Errors | {count} |
| Network Errors | {count} |
```

## Expected Output

Your final response MUST strictly contain the E2E report with verdict, per-test results, console/network errors, and BDD→E2E coverage table. End your generation immediately after the report. Do not write "Next steps".
