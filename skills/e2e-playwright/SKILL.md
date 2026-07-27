---
name: e2e-playwright
description: 'Implements end-to-end tests using Playwright from a Behavior Map. Handles infrastructure setup, Page Objects, fixtures, and test authoring. Use for Phase 3b of the engineering loop or any task requiring E2E test implementation.'
---

# E2E Playwright Tester

**Role:** Execute — implements E2E tests from the Behavior Map's `@e2e` scenarios.

**Output:** `e2e/{feature}.spec.js` files with Playwright tests.

## Input

- Behavior Map artifact (from `bmad-bdd-mapper`)
- Implementation Blueprint (from Phase 2a)
- Running dev server (or ability to start one)

## Workflow

### Step 1: Infrastructure Setup

If Playwright is not configured:

1. **Install:**
   ```bash
   npm install -D @playwright/test
   npx playwright install --with-deps chromium
   ```

2. **Create `playwright.config.js`:**
   ```js
   import { defineConfig, devices } from '@playwright/test';

   export default defineConfig({
     testDir: './e2e',
     fullyParallel: true,
     forbidOnly: !!process.env.CI,
     retries: process.env.CI ? 2 : 0,
     workerTimeout: 120000,
     reporter: [['list'], ['html', { open: 'never' }]],
     use: {
       baseURL: 'http://localhost:5173',
       trace: 'on-first-retry',
       screenshot: 'only-on-failure',
       video: 'retain-on-failure',
     },
     projects: [
       { name: 'Mobile Chrome', use: { ...devices['Pixel 5'] } },
       { name: 'Desktop Chrome', use: { ...devices['Desktop Chrome'] } },
     ],
     webServer: {
       command: 'npm run dev',
       port: 5173,
       timeout: 120000,
       reuseExistingServer: !process.env.CI,
     },
   });
   ```

3. **Create `e2e/helpers/fixture.js`:**
   ```js
   import { test as base } from '@playwright/test';
   export const test = base.extend({
     page: async ({ page }, use) => {
       await page.route('**/*', async (route) => {
         await route.continue();
       });
       await use(page);
     },
   });
   export { expect } from '@playwright/test';
   ```

4. **Create `e2e/helpers/pages/`** with Page Object classes per major page.

5. **Add scripts to project config:**
   ```json
   "test:e2e": "playwright test",
   "test:e2e:ui": "playwright test --ui"
   ```

### Step 2: Map Scenarios to Test Files

Group `@e2e` scenarios by feature area:

| Feature Area | Test File |
|-------------|-----------|
| {Feature} | `e2e/{feature}.spec.js` |

### Step 3: Implement Tests

For each `@e2e` scenario, write a Playwright test:

```js
import { test, expect } from '../helpers/fixture.js';
import { SomePage } from '../helpers/pages/SomePage.js';

test.describe('Feature Area', () => {
  test('scenario-name', async ({ page }) => {
    // Given: precondition
    const pageObj = new SomePage(page);
    await pageObj.goto();

    // When: action
    await pageObj.doSomething();

    // Then: observable outcome
    await expect(page.locator('.expected-element')).toBeVisible();
  });
});
```

**Naming:** Use Behavior Map scenario name as test title.
**Comments:** Annotate with `// Given`, `// When`, `// Then`.

### Step 4: Service Mocking Strategy

For tests requiring backend services:

1. **Pre-seed:** Setup hooks to seed test data
2. **Network interception:** Intercept service calls with `page.route()`
3. **Local state:** Set mock auth/user state in localStorage

### Step 5: Run and Verify

1. `npm run test:e2e`
2. All tests must pass on both Mobile and Desktop projects
3. Cross-reference passing tests against Behavior Map `@e2e` scenarios — every scenario must have a passing test

## Quality Gates

- [ ] Playwright infrastructure configured
- [ ] Page Objects for all tested pages
- [ ] Every `@e2e` scenario has a corresponding test
- [ ] All tests pass on Mobile + Desktop
- [ ] Tests are independent
- [ ] Explicit waits, no `page.waitForTimeout()`
- [ ] Screenshots/video on failure

## Anti-Patterns

- **Never use `page.waitForTimeout()`** — use `expect().toBeVisible()`
- **Never hard-select by implementation details** — use semantic selectors
- **Never share state between tests** — each test independently runnable
- **Never test internals** — only observable user-facing behavior
- **Never skip mobile viewport** — PWA tested on mobile dimensions
- **Never ignore flaky tests** — fix root cause
