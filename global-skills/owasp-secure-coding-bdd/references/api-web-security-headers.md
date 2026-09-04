# API Security, Web Security Headers, CORS, CSRF & XSS

Covers: REST Security, HTTP Security Response Headers, Cross-Site Request Forgery (CSRF) Prevention, Cross Site Scripting (XSS) Prevention, Clickjacking Defense.

## Cross-Site Scripting (XSS)
- **Context-aware output encoding** is the primary defense: encode user-controlled data for the context it's rendered into — HTML entity encoding for HTML body content, JS string escaping for data injected into `<script>`, URL encoding for data in URLs/attributes. Most modern frameworks (React, Vue, Angular, Blazor) auto-escape by default when using their standard templating/binding — the risk is opting out of it.
- Never use `dangerouslySetInnerHTML` (React), `v-html` (Vue), `[innerHTML]` (Angular), or raw string concatenation into HTML with unsanitized user input. If rendering user-supplied rich text/HTML is a genuine requirement, sanitize it server-side with a vetted allow-list sanitizer (DOMPurify client-side as defense-in-depth, plus a server-side sanitizer as the authoritative control) rather than trying to write custom regex filtering.
- Set a **Content-Security-Policy** header restricting script sources (`script-src 'self'`, avoid `unsafe-inline`/`unsafe-eval`) as defense-in-depth even when output encoding is correct.
- Set cookies `HttpOnly` (see authentication reference) so even a successful XSS can't directly read session cookies.

## DOM-based XSS
- The same encoding principle applies client-side: never write untrusted data into `innerHTML`, `document.write()`, `eval()`, or a URL passed to `location`/`src` without encoding/validating it for that specific DOM sink first.
- Treat `location.hash`, `location.search`, `document.referrer`, and `postMessage` payloads as untrusted input just like server-side request data — a common DOM XSS bypass is trusting client-side-only sources because they "didn't go through the server."
- For `postMessage` listeners, always validate `event.origin` against an explicit allow-list before acting on the message content.

## Unvalidated redirects and forwards
- Never redirect to a URL taken directly from user input (`?next=`, `?redirect=`, `?returnUrl=`) without validating it against an allow-list of permitted destinations (relative paths within the same app, or an explicit list of trusted external domains) — an open redirect is commonly chained into phishing (a link that looks like your trusted domain but bounces to an attacker site) or into OAuth authorization code theft (see the OAuth section in `api-tokens-graphql-microservices.md`).

## DOM clobbering / HTML5 security
- Be cautious with global variable/element lookups by `id`/`name` in JavaScript when the surrounding HTML can contain user-controlled markup — an attacker can define an element with `id="config"` that "clobbers" a global `window.config` your script expects to be a JS object, redirecting logic in unexpected ways. Prefer explicit JS variables over relying on implicit global DOM-to-JS name binding for anything security-relevant.
- Apply the same sanitization discipline (see the XSS section above) to any HTML5 feature that accepts user content: `contenteditable` regions, drag-and-drop file/text handlers, and the Web Storage APIs (don't treat `localStorage`/`sessionStorage` content as trusted just because your own code wrote it there — it's still readable/writable by any script that runs on the page, including an XSS payload).

## Cross-Site Request Forgery (CSRF)
- Relevant for any state-changing request (POST/PUT/PATCH/DELETE) that relies on cookie-based session auth. Not needed for APIs authenticated purely via a bearer token sent in a custom header (browsers don't attach those automatically), but IS needed if the same endpoint also accepts cookie auth.
- Use a CSRF token (synchronizer token pattern) included in forms/AJAX requests and validated server-side, or rely on `SameSite=Strict`/`Lax` cookies as a strong modern mitigation (combine both for defense-in-depth on sensitive actions).
- Never rely on checking the `Referer`/`Origin` header alone as the sole defense — useful as an additional signal, not sufficient on its own.

## CORS (Cross-Origin Resource Sharing)
- Never set `Access-Control-Allow-Origin: *` on any endpoint that requires authentication/returns sensitive data — an open CORS policy combined with credentialed requests lets any website read the authenticated response.
- Explicitly allow-list known, trusted origins rather than reflecting the request's `Origin` header back unconditionally.
- Only set `Access-Control-Allow-Credentials: true` alongside a specific allow-listed origin, never alongside a wildcard.

## Clickjacking
- Set `X-Frame-Options: DENY` (or `SAMEORIGIN` if legitimate same-site framing is needed) and/or the CSP `frame-ancestors` directive to prevent the page from being embedded in a malicious iframe for UI-redress attacks.

## Security response headers (baseline for every web app)
- `Content-Security-Policy` — restrict script/style/resource sources
- `X-Content-Type-Options: nosniff` — prevent MIME-sniffing
- `X-Frame-Options: DENY` / `frame-ancestors 'none'`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Referrer-Policy: strict-origin-when-cross-origin` (avoid leaking full URLs, including tokens in query strings, to third parties)
- Remove/avoid headers that leak stack info (`X-Powered-By`, verbose server version headers)

## REST/API-specific
- Validate `Content-Type` and reject unexpected types (don't parse a body as JSON if it wasn't declared as such, and vice versa).
- Version APIs and deprecate old versions deliberately rather than leaving unmaintained, unpatched endpoints live indefinitely.
- Apply rate limiting per API key/client, not just per IP, since IPs are shared/spoofable.
- Don't expose internal implementation details in API responses (stack traces, ORM error messages, internal IDs that reveal system structure) — return a generic error to the client and log the detail server-side (see logging reference).
- For GraphQL specifically: disable introspection in production if the schema shouldn't be public, enforce query depth/complexity limits to prevent resource-exhaustion via deeply nested queries, and apply the same field-level authorization checks as REST endpoint-level checks.

## BDD security scenario patterns

```gherkin
@security
Scenario: User-supplied text is HTML-encoded when rendered
  Given a user submits a comment containing "<script>alert(1)</script>"
  When the comment is displayed to another user
  Then the script tag is rendered as inert text, not executed

@security
Scenario: State-changing request without a valid CSRF token is rejected
  Given a user is authenticated via a session cookie
  When a POST request to change their email omits a valid CSRF token
  Then the request is rejected

@security
Scenario: CORS does not allow arbitrary origins on authenticated endpoints
  When a request to a protected endpoint includes Origin "https://evil.example"
  Then the response does not include an Access-Control-Allow-Origin matching that origin

@security
Scenario: Response includes baseline security headers
  When any page is requested
  Then the response includes X-Content-Type-Options, X-Frame-Options, and Content-Security-Policy headers
```
