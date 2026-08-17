---
name: e2e-playwright
description: 'Implements end-to-end tests using Playwright from a Behavior Map. Handles infrastructure setup, Page Objects, fixtures, test authoring, visual regression, trace debugging, and Playwright MCP integration. Use for Phase 3b of the engineering loop or any task requiring E2E test implementation.'
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
     reporter: [['list'], ['html', { open: 'never' }], ['json', { outputFile: 'e2e-results.json' }]],
     use: {
       baseURL: 'http://localhost:5173',
       trace: 'on-first-retry',
       screenshot: 'only-on-failure',
       video: 'retain-on-failure',
       actionTimeout: 10000,
       navigationTimeout: 30000,
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
   "test:e2e:ui": "playwright test --ui",
   "test:e2e:report": "playwright show-report"
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

### Step 5: Visual Regression (Optional)

For UI-critical flows, add visual regression checks:

```js
// Full page screenshot comparison
await expect(page).toHaveScreenshot('dashboard.png', { maxDiffPixels: 50 });

// Element-specific comparison
await expect(page.locator('.chart')).toHaveScreenshot('chart.png', { maxDiffPixels: 20 });

// Partial screenshot (ignores dynamic content)
await expect(page.locator('.static-section')).toHaveScreenshot('header.png', {
  mask: [page.locator('.dynamic-data')],
});
```

**Visual regression rules:**
- Store baseline screenshots in `e2e/snapshots/`
- Use `maxDiffPixels` tolerance for anti-aliasing differences
- Mask dynamic content (timestamps, user names, random data)
- Update baselines intentionally: `npx playwright test --update-snapshots`

### Step 6: Trace Viewer Debugging

Configure trace collection for debugging:

```js
// In playwright.config.js — collect traces on retry
trace: 'on-first-retry'

// For full trace collection (development only)
trace: '{ mode: "on", retainAfterFailingTest: true }'

// View traces
npx playwright show-trace trace.zip
```

**Debugging workflow:**
1. Test fails → trace file generated
2. Run `npx playwright show-trace trace.zip`
3. Inspect DOM snapshots, network requests, console logs, actions timeline
4. Identify root cause: timing issue, missing element, wrong assertion
5. Fix test or application code

### Step 7: Run and Verify

1. `npm run test:e2e`
2. All tests must pass on both Mobile and Desktop projects
3. Cross-reference passing tests against Behavior Map `@e2e` scenarios — every scenario must have a passing test

## Playwright MCP Integration

For AI-assisted test generation and debugging:

```json
// In .claude.json or MCP client config
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@anthropic-ai/mcp-server-playwright"]
    }
  }
}
```

**MCP use cases:**
- AI explores the app and generates test cases from natural language
- AI verifies code changes in a real browser after implementation
- AI assists with debugging failed tests using trace data
- AI generates Page Object methods from UI descriptions

**MCP limitations:**
- AI-generated tests may vary between runs — always review
- AI may assume missing context — provide Behavior Map as reference
- AI cannot replace human understanding of business logic

## Quality Gates

- [ ] Playwright infrastructure configured
- [ ] Page Objects for all tested pages
- [ ] Every `@e2e` scenario has a corresponding test
- [ ] All tests pass on Mobile + Desktop
- [ ] Tests are independent
- [ ] Explicit waits, no `page.waitForTimeout()`
- [ ] Screenshots/video on failure
- [ ] **Zero console errors** (mandatory)
- [ ] **Zero network 4xx/5xx** (mandatory)
- [ ] **Role-based locators only** (no CSS/XPath)
- [ ] **BDD→E2E 1:1 coverage** (mandatory)
- [ ] **Dimension assertions** (CSS collapse detection)
- [ ] **Auth bypass configured** (if auth exists)
- [ ] **JSON report generated** (`e2e-results.json`)

## Anti-Patterns

- **Never use `page.waitForTimeout()`** — use `expect().toBeVisible()`
- **Never use CSS/XPath selectors** — use `getByRole()`, `getByLabel()`, `getByText()`
- **Never share state between tests** — each test independently runnable
- **Never test internals** — only observable user-facing behavior
- **Never skip mobile viewport** — PWA tested on mobile dimensions
- **Never ignore flaky tests** — fix root cause
- **Never ignore console errors** — zero errors is mandatory
- **Never ignore network errors** — zero 4xx/5xx is mandatory
- **Never skip auth bypass** — tests must reach protected routes
- **Never skip BDD→E2E coverage check** — every `@e2e` scenario needs a test
- **Never test against dev server for smoke tests** — use production build
- **Never skip screenshots** — visual evidence is mandatory
- **Never commit trace files** — they are large and transient; use for debugging only
