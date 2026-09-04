# API Tokens, Federated Auth, GraphQL & Microservices

Covers: JSON Web Token (JWT), SAML Security, Web Service Security, GraphQL, Microservices Security, Third Party JavaScript Management, Mass Assignment.

## JWT (JSON Web Tokens)
- Always verify the signature server-side on every request — never decode and trust the payload without verification.
- Explicitly whitelist the accepted signing algorithm(s) server-side; never accept whatever `alg` the token header claims (the classic `alg: none` bypass, and the RS256-to-HS256 confusion attack where a public key is fed back in as an HMAC secret both stem from trusting the token's own header).
- Validate `exp` (expiry), `iss` (issuer), and `aud` (audience) claims on every verification, not just signature validity.
- Keep access tokens short-lived (minutes); use a separate, revocable refresh token for longer sessions.
- Support server-side revocation for tokens that must be invalidated before natural expiry (logout, compromise) — a short-lived-token + refresh-token pattern, or a deny-list checked at verification time.
- Store JWTs client-side in a way that limits XSS exposure (an in-memory variable or `HttpOnly` cookie beats `localStorage`, which is readable by any script on the page).

## SAML
- Validate the XML signature on every SAML assertion using a library's built-in validation, never custom XML parsing/comparison.
- Validate the assertion's audience, recipient, and timing (`NotBefore`/`NotOnOrAfter`) fields, not just the signature.
- Disable/guard against XML canonicalization and XXE issues in the SAML XML parser (see file-upload/XXE reference) since SAML assertions are XML.

## OAuth 2.0 / OIDC
- Always use the Authorization Code flow with PKCE for anything involving a browser or public client (SPA, mobile app) — never the deprecated Implicit flow.
- Validate the `state` parameter to prevent CSRF on the OAuth callback.
- Validate redirect URIs against an exact allow-list server-side (no wildcard subdomain matching) to prevent authorization code interception via an open redirect.
- Treat the ID token (OIDC) and access token differently: the ID token is for authenticating the user to your app; the access token is for calling the resource API — don't use one in place of the other.

## Web services / REST / general API security
- Authenticate and authorize every service-to-service call, not just user-facing calls — internal APIs are a common blind spot ("it's internal, it must be trusted").
- Version APIs deliberately and retire old versions on a schedule; an old unmaintained API version is frequently the one still vulnerable to an issue already fixed elsewhere.
- Validate content types and reject unexpected ones; don't silently accept whatever the client sends.

## GraphQL specific
- Disable introspection in production unless the schema is intentionally public.
- Enforce query depth limits and query complexity/cost limits — GraphQL's nested-query flexibility makes it easy to construct a single request that fans out into an enormous amount of backend work (a resource-exhaustion / DoS vector unique to GraphQL).
- Apply field-level and type-level authorization checks, not just checks at the top-level query/mutation — a resolver returning a nested object must still enforce access control on that nested data.
- Rate-limit by query cost, not just request count, since one GraphQL request can do the work of many REST calls.

## Microservices security
- Don't assume the network perimeter is the only boundary — apply authentication and authorization between services (mTLS or signed service tokens), since a compromised service inside the network shouldn't get a free pass to every other service.
- Avoid passing a raw end-user identity/trust assumption across service boundaries without re-verification — a downstream service should still independently authorize the action, not just trust that "it came from another internal service so it must be fine."
- Centralize authn/authz logic (a shared library or a sidecar/gateway pattern) rather than reimplementing it slightly differently in every service, which is how inconsistent enforcement creeps in.
- Apply the same secrets-management practices (see cryptography-secrets.md) to service-to-service credentials as to user-facing secrets.

## Third-party JavaScript / supply chain in the browser
- Use Subresource Integrity (`integrity="sha384-..."` attribute) on any `<script>`/`<link>` tag loading a third-party script from a CDN, so a compromised CDN can't silently serve modified code.
- Minimize the number of third-party scripts loaded, especially ones with write access to the page (analytics/ad scripts have been a real vector for supply-chain XSS).
- Use CSP `script-src` to allow-list exactly which script origins are permitted.

## Mass assignment
- Never bind an incoming request body directly to a full domain/database model without an explicit allow-list of which fields are bindable — a request body containing `"role": "admin"` or `"isVerified": true` should not be able to set those fields unless the endpoint explicitly permits it for the caller's actual permission level.
- Use DTOs/view-models or explicit field allow-lists per endpoint rather than generic "bind everything" model binding, especially for update/create endpoints on sensitive objects (users, permissions, pricing, orders).

## BDD security scenario patterns

```gherkin
@security
Scenario: JWT with alg=none is rejected
  When a request includes a JWT with header alg set to "none" and no signature
  Then the token is rejected as invalid

@security
Scenario: Expired JWT is rejected even with a valid signature
  Given a JWT was issued with an expiry in the past
  When it is used to authenticate a request
  Then the request is rejected as unauthenticated

@security
Scenario: GraphQL query exceeding depth limit is rejected
  When a client submits a GraphQL query nested 20 levels deep
  Then the server rejects the query before executing any resolvers

@security
Scenario: Mass assignment cannot set a privileged field
  Given a non-admin user submits a profile update including "role": "admin"
  When the update is processed
  Then the user's role is unchanged
  And only allow-listed fields from the request are applied
```
