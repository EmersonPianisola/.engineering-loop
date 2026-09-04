# Access Control & Authorization

Covers: Authorization, Insecure Direct Object Reference (IDOR) Prevention, Access Control.

## Core principle
Authentication answers "who are you"; authorization answers "are you allowed to do this specific thing to this specific resource." A huge share of real-world breaches are authorization failures where authentication worked fine but the app never checked ownership/role on the actual resource being accessed.

## Rules
- **Deny by default.** Every route/endpoint/resource requires an explicit authorization check; nothing is accessible just because a request reached the handler.
- **Check authorization server-side, on every request**, not just once at login or only in the UI. A hidden button is not access control.
- **Re-check ownership on every object-level operation** (the classic IDOR bug: `GET /invoices/1234` returns whichever invoice has ID 1234 regardless of who's asking, because the code checked "is this user logged in" but never "does this user own invoice 1234"). Always filter/verify by the resource's owner/tenant in the same query or check, not as an afterthought.
- Never trust client-supplied role/permission claims that aren't cryptographically verified (e.g., a hidden form field `role=admin`, or a JWT claim that isn't signature-checked) — always derive the authoritative role/permission from a server-side source of truth.
- Use non-guessable, non-sequential resource identifiers (UUIDs) where feasible so object IDs can't be enumerated — but treat this as defense in depth, not a substitute for real ownership checks (an attacker with one valid UUID should still be blocked from another user's UUID by the authorization check itself).
- Enforce authorization consistently across every interface to the same data — REST API, GraphQL resolver, admin panel, internal batch job, webhook handler. A common bypass is a secondary code path (an "internal" or "legacy" endpoint) that skips the check the main path has.
- For multi-tenant systems, scope every database query by tenant ID as a structural habit (e.g., a base repository class that always adds the tenant filter), not something each new query has to remember individually.
- Enforce the principle of least privilege for roles: default new roles/accounts to the minimum permission set, require explicit grants for anything more.
- Log authorization failures (who attempted what, on which resource) — a spike of 403s against sequential IDs is a strong IDOR-enumeration signal.

## Function-level access control
- Don't rely solely on hiding a UI element (a menu item, a button) to protect an admin function — the underlying endpoint must independently enforce the role check.
- Apply the same enforcement to "internal" or "debug" endpoints as to public ones; these are common oversight targets.

## BDD security scenario patterns

```gherkin
@security
Scenario: User cannot access another user's resource by ID (IDOR)
  Given user A owns invoice "INV-1001"
  And user B is authenticated as a different user
  When user B requests invoice "INV-1001"
  Then the API returns 403 or 404, not the invoice data

@security
Scenario: Non-admin user cannot reach an admin-only endpoint
  Given a user without the admin role is authenticated
  When they call the admin "delete user" endpoint directly
  Then the API returns 403
  And no user is deleted

@security
Scenario: Client-supplied role claim is ignored in favor of server-side role
  Given a request includes a body field "role": "admin" for a non-admin user
  When the request is processed
  Then the server's stored role is used for the authorization check, not the request body value

@security
Scenario Outline: Sequential/enumerable resource IDs do not leak other tenants' data
  When a user requests resource ID "<id>" belonging to a different tenant
  Then access is denied regardless of ID guessability

  Examples:
    | id      |
    | 1000    |
    | 1001    |
    | 1002    |
```
