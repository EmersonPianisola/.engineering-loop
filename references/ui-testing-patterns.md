---
name: ui-testing-patterns
id: ui-testing
version: 1.0.0
type: reference
description: 'UI testing patterns: auth bypass, common failures, locator strategy, auto-fix procedures. Used by e2e.execute and smoke.test stages.'
---

# UI Testing Patterns

## Auth Bypass Patterns

### Clerk

```js
// playwright.config.js
use: {
  contextOptions: {
    extraHTTPHeaders: {
      '__dev_bypass': '1',
    },
  },
}

// Or via cookie
await page.context().addCookies([{
  name: '__dev_bypass',
  value: '1',
  domain: 'localhost',
  path: '/',
}]);
```

### NextAuth

```js
// Mock session in middleware
// Add to test setup:
await page.evaluate(() => {
  window.__NEXT_AUTH_SESSION = {
    user: { name: 'Test User', email: 'test@example.com' },
    expires: new Date(Date.now() + 86400000).toISOString(),
  };
});
```

### Supabase

```js
// Use service role key for tests
const supabase = createClient(SUPABASE_URL, SERVICE_ROLE_KEY);

// Or bypass RLS in middleware
// Set env: SUPABASE_JWT_SECRET=test-secret
```

### Custom JWT

```js
// Inject token into localStorage
await page.evaluate(() => {
  localStorage.setItem('token', 'test-jwt-token');
  localStorage.setItem('auth', JSON.stringify({
    user: { id: 'test-user', role: 'admin' },
    expires: Date.now() + 86400000,
  }));
});
```

## Common Failures + Auto-Fix Lookup

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| `TimeoutError: waiting for locator` | Element not in DOM, wrong selector | Switch to role-based locator |
| `Element not visible` | CSS `display: none`, overlay blocking | Check z-index, wait for animation |
| `Route not found (404)` | Route not registered, wrong path | Verify router config, check path |
| `Auth redirect loop` | Auth middleware not bypassed | Apply auth bypass pattern |
| `Hydration mismatch` | SSR/CSR mismatch | Warn (non-blocking) |
| `Module not found` | Missing import, typo | Check import path, verify file exists |
| `API 401` | Auth not passed to API calls | Add auth header, bypass middleware |
| `API 404` | Endpoint doesn't exist | Verify API routes, check backend |
| `State not persisting` | State reset on navigation | Check state management (Redux, Context) |
| `Form validation error` | Field name mismatch | Check form schema, verify field names |
| `Blank white screen` | Component crash, unhandled error | Check console errors, verify imports |
| `Stale build cache` | Old `.next/` or `dist/` | Delete cache, rebuild |
| `Port conflict` | Another process on port | Find available port, restart |
| `Missing dependency` | Package not installed | `npm install <package>` |
| `crypto.randomUUID` error | HTTP vs HTTPS | Add fallback for HTTP |

## Locator Strategy

### Priority Order (MANDATORY)

1. **`getByRole()`** — Accessibility role + name (most resilient)
2. **`getByLabel()`** — Form label text
3. **`getByText()`** — Visible text content
4. **`getByPlaceholder()`** — Input placeholder (fallback)
5. **`getByTestId()`** — `data-testid` attribute (last resort)

### NEVER Use

- CSS selectors like `.class-name` or `#id` — break on refactor
- XPath — brittle, non-standard
- Index-based locators like `nth(0)` — break on reorder
- Implementation details like `div > button:first-child`

### Adding data-testid (last resort)

If role-based locators cannot uniquely identify an element:

```jsx
// Add to component
<button data-testid="submit-button" onClick={handleSubmit}>
  Submit
</button>

// Test
await page.getByTestId('submit-button').click();
```

## Playwright CLI vs MCP

**Use CLI** — it writes screenshots to disk instead of injecting into context window.

| Metric | CLI | MCP |
|--------|-----|-----|
| Token usage | ~27K | ~114K |
| Determinism | High | Medium |
| Speed | Fast | Slower |
| Context impact | Low | High |

Source: Microsoft benchmarks

## Storage State (Auth Reuse)

Avoid logging in for every test. Use Playwright's `storageState`:

```js
// playwright.config.js
projects: [
  {
    name: 'setup',
    testMatch: /auth-setup\.js/,
  },
  {
    name: 'chromium',
    use: {
      ...devices['Desktop Chrome'],
      storageState: 'auth.json',
    },
    dependencies: ['setup'],
  },
];

// e2e/auth-setup.js
test('authenticate', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill('test@example.com');
  await page.getByLabel('Password').fill('password123');
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  // Saves cookies + localStorage to auth.json
});
```

## Parallel vs Serial Execution

| Scenario | Mode | Reason |
|----------|------|--------|
| E2E tests | Serial (`fullyParallel: false`) | Deterministic state, shared auth |
| Smoke tests | Serial | Full journey requires ordered steps |
| Unit tests | Parallel | Independent, no shared state |

## Video + Trace Configuration

```js
use: {
  trace: 'retain-on-failure',    // Trace only on failure
  video: 'retain-on-failure',     // Video only on failure
  screenshot: 'on',               // Always screenshot
},
```

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `APP_PORT` | Application port | `5173` (dev), `3000` (prod) |
| `START_COMMAND` | Dev server command | `npm run dev` |
| `SMOKE_TEST_BYPASS` | Enable auth bypass | `false` |
| `PLAYWRIGHT_HEADLESS` | Headless mode | `true` |
