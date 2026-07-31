---
name: smoke-test
id: smoke.test
version: 1.0.0
type: stage
description: 'Final user journey smoke test. Full login→navigate→CRUD→reports→logout flow. Screenshots at each step. Last gate before done.'
---

# STAGE: Smoke Test (User Journey)
<!-- ID: smoke.test -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the smoke test executor.
- DO NOT modify application source code directly (except in auto-fix loop).
- DO NOT transition to other stages.
- The moment the smoke test report is produced, your task is FINISHED.

## Procedure

1. **Prerequisite Check:** If `state.stages.deploy.prepare.done != true` → `status: blocked`, `blocking_condition: deploy preparation not complete`. **EXIT.**
2. **UI Detection:** Check if project contains frontend files. If NO UI → `done: true` (deactivated). **SKIP.**
3. Proceed with the steps below.

# Smoke Test — Full User Journey Validation

**Skill:** `e2e-playwright`
**Runs when:** `state.stages.smoke.test.done == false`
**Prerequisite:** `state.stages.deploy.prepare.done == true`
**Constraint:** `max_smoke_test_attempts` (default: 3)

## Execute — Smoke Test Pipeline

### Step 1: Build Production Binary

Smoke test runs against the production build, not dev server:

```bash
npm run build
# Start production server
npm start  # or npm run serve, depending on framework
```

If production build fails → `done = false`, reset `impl.code.done = false`. ESCALATE.

### Step 2: Define Critical Paths

Identify the application's critical paths from:

1. **BDD Journeys** — Primary happy paths from user journeys
2. **Blueprint** — Core user flows from implementation design
3. **Route Discovery** — All routes derived from file structure

Critical paths typically include:

| Path | Description |
|------|-------------|
| Authentication | Login, logout, session persistence |
| Navigation | All menus open, all routes accessible |
| Primary CRUD | Create, Read, Update, Delete main entity |
| Search/Filter | Data retrieval and filtering |
| Reports/Dashboard | Data visualization, summary views |
| Error States | 404 page, error boundaries, empty states |

### Step 3: Write Smoke Test Spec

A single comprehensive test file covering the full journey:

```js
import { test, expect } from '@playwright/test';

test.describe('Smoke Test — Full User Journey', () => {
  // Authentication
  test('01-login', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill('test@example.com');
    await page.getByLabel('Password').fill('password123');
    await page.getByRole('button', { name: /sign in|login/i }).click();
    await expect(page).toHaveURL(/\/dashboard|\/home/i);
    await page.screenshot({ path: 'smoke/01-login.png', fullPage: true });
  });

  // Navigation
  test('02-navigation-menus', async ({ page }) => {
    // Navigate to each major route
    const routes = ['/dashboard', '/users', '/settings'];
    for (const route of routes) {
      await page.goto(route);
      await expect(page).not.toHaveURL(/\/404|\/error/i);
      await page.screenshot({ path: `smoke/02-${route.replace(/\//g, '')}.png`, fullPage: true });
    }
  });

  // CRUD: Create
  test('03-create-entity', async ({ page }) => {
    await page.goto('/create');
    // Fill form
    await page.getByLabel(/name|title/i).fill('Test Item');
    await page.getByRole('button', { name: /create|save|submit/i }).click();
    // Verify creation
    await expect(page.getByText('Test Item')).toBeVisible();
    await page.screenshot({ path: 'smoke/03-create.png', fullPage: true });
  });

  // CRUD: Read
  test('04-read-entity', async ({ page }) => {
    await page.goto('/items');
    await expect(page.getByText('Test Item')).toBeVisible();
    await page.screenshot({ path: 'smoke/04-read.png', fullPage: true });
  });

  // CRUD: Update
  test('05-update-entity', async ({ page }) => {
    await page.getByRole('button', { name: /edit|update/i }).click();
    await page.getByLabel(/name|title/i).fill('Updated Item');
    await page.getByRole('button', { name: /save|update/i }).click();
    await expect(page.getByText('Updated Item')).toBeVisible();
    await page.screenshot({ path: 'smoke/05-update.png', fullPage: true });
  });

  // CRUD: Delete
  test('06-delete-entity', async ({ page }) => {
    await page.getByRole('button', { name: /delete|remove/i }).click();
    // Confirm if dialog appears
    const dialog = page.waitForEvent('dialog').catch(() => null);
    if (dialog) {
      const d = await Promise.race([dialog, page.waitForTimeout(2000)]);
      if (d && d.type === 'dialog') await d.accept();
    }
    await expect(page.getByText('Updated Item')).not.toBeVisible();
    await page.screenshot({ path: 'smoke/06-delete.png', fullPage: true });
  });

  // Reports/Dashboard
  test('07-dashboard-reports', async ({ page }) => {
    await page.goto('/dashboard');
    // Verify charts/tables render
    await expect(page.locator('canvas, table, [role="grid"]')).first().toBeVisible();
    await page.screenshot({ path: 'smoke/07-dashboard.png', fullPage: true });
  });

  // Logout
  test('08-logout', async ({ page }) => {
    await page.getByRole('button', { name: /logout|sign out/i }).click();
    await expect(page).toHaveURL(/\/login/i);
    await page.screenshot({ path: 'smoke/08-logout.png', fullPage: true });
  });
});
```

### Step 4: Console + Network Monitoring

Wrap each test with console and network monitoring:

```js
test.use({
  baseURL: 'http://localhost:' + (process.env.APP_PORT || '3000'),
});

test.beforeEach(async ({ page }) => {
  test.info().consoleErrors = [];
  test.info().networkErrors = [];

  page.on('console', msg => {
    if (msg.type() === 'error') {
      test.info().consoleErrors.push(msg.text());
    }
  });

  await page.route('**/*', async (route) => {
    const response = await route.fetch();
    if (response.status() >= 400) {
      test.info().networkErrors.push({
        url: route.request().url(),
        status: response.status(),
      });
    }
    await route.continue();
  });
});

test.afterEach(({ testInfo }) => {
  // Console errors are non-blocking warnings
  if (testInfo.consoleErrors?.length > 0) {
    console.warn('Console errors:', testInfo.consoleErrors);
  }
  // Network errors ARE blocking
  if (testInfo.networkErrors?.length > 0) {
    testInfo.annotations = [{ type: 'FAIL', description: 'Network errors detected' }];
  }
});
```

### Step 5: Run Smoke Tests

```bash
npx playwright test smoke --reporter=list
```

### Step 6: Evaluate

```
IF all smoke tests pass
    AND zero network errors
    AND screenshots captured for each step:
    VERDICT: PASS
    state.stages.smoke.test.done = true
ELSE:
    VERDICT: FAIL
    state.stages.smoke.test.done = false
    state.stages.impl.code.done = false  # Reset for auto-fix
```

## Auto-Fix Loop

On FAIL, attempt fixes (max `max_smoke_test_attempts`):

| Issue | Auto-Fix |
|-------|----------|
| Route 404 | Check routing config, verify route exists |
| Auth redirect | Apply auth bypass, verify session handling |
| Form not submitting | Check form validation, fix field bindings |
| Component not rendering | Check imports, verify component registration |
| API 404 | Verify API routes, check backend connectivity |
| State not persisting | Check state management, verify storage |

After each fix:
1. Rebuild: `npm run build`
2. Re-run failed smoke tests
3. If still failing → next attempt or ESCALATE

### Write Smoke Report

Output to `{artifact-root}/smoke-report-{slug}.md`:

```markdown
# Smoke Test Report

**Feature:** {slug}
**Verdict:** PASS | FAIL
**Iteration:** {n}

## Journey Steps

| Step | Route | Status | Screenshot |
|------|-------|--------|------------|
| 01-Login | /login | PASS | smoke/01-login.png |
| 02-Navigation | /dashboard | PASS | smoke/02-dashboard.png |
| 03-Create | /create | PASS | smoke/03-create.png |
| 04-Read | /items | PASS | smoke/04-read.png |
| 05-Update | /items/edit | PASS | smoke/05-update.png |
| 06-Delete | /items | PASS | smoke/06-delete.png |
| 07-Dashboard | /dashboard | PASS | smoke/07-dashboard.png |
| 08-Logout | / | PASS | smoke/08-logout.png |

## Console Errors

| Step | Message |
|------|---------|
| {step} | {error} |

## Network Errors

| Step | URL | Status |
|------|-----|--------|
| {step} | {url} | {code} |

## Summary

| Metric | Value |
|--------|-------|
| Steps Passed | {count} |
| Steps Failed | {count} |
| Screenshots | {count} |
| Console Errors | {count} |
| Network Errors | {count} |
```

## Expected Output

Your final response MUST strictly contain the smoke test report with verdict, per-step results, screenshots, and error tables. End your generation immediately after the report. Do not write "Next steps".
