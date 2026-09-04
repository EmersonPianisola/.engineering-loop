# Logging, Error Handling & Denial of Service

Covers: Logging, Error Handling, Denial of Service prevention at the application layer.

## Error handling
- Never return stack traces, ORM/SQL error text, internal file paths, or framework debug pages to the client in production — return a generic error message and a request/correlation ID the user can quote for support.
- Ensure this is enforced by environment config (debug mode off in production), not just by convention — verify the actual production config, since "debug mode left on" in production is a very common real-world leak.
- Fail securely: if an error occurs mid-authorization-check, the default outcome must be **deny**, never "allow because the check didn't complete." Same principle for any security-relevant check — an exception during the check is not an implicit pass.
- Handle all exceptions from external calls (DB, third-party API, file I/O) explicitly rather than letting an unhandled exception potentially leave the system in an inconsistent security state (e.g., a payment marked complete before confirmation actually succeeded).

## Logging
- Log security-relevant events: authentication successes/failures, authorization failures, password/MFA changes, admin actions, input validation failures at scale, rate-limit triggers.
- Never log sensitive data in plaintext: passwords, full credit card numbers, full tokens/API keys, full session IDs, government IDs, health data. Mask/truncate if the value's presence needs to be logged (e.g., log the last 4 digits of a card, never the full PAN).
- Include enough context to investigate: timestamp, source IP, user/account identifier, action attempted, outcome — without including the sensitive payload itself.
- Protect log storage itself: restrict access, and treat logs as containing sensitive metadata even when payloads are excluded.
- Ensure logs are tamper-evident/centralized (shipped to a log aggregator) rather than only living on a single instance's disk where an attacker with that instance could delete evidence.
- Don't let logging itself become an injection vector — sanitize/encode user input before writing to logs to prevent log injection (e.g., a user submitting a username containing newlines to forge fake log entries) and be cautious with any downstream tool that renders logs as HTML.

## Denial of Service (application-layer)
- Enforce request size limits (body size, header size, number of form fields/array items in a JSON payload) — an unbounded array/object in a request body is a classic resource-exhaustion vector even without any "attack" beyond a huge payload.
- Enforce pagination limits on any endpoint returning a list — never allow an unbounded `?limit=999999999` to force the server to load and serialize an enormous result set.
- Guard against algorithmic complexity attacks: validate input against catastrophic-backtracking regex patterns (test your own validation regexes for ReDoS, especially nested quantifiers like `(a+)+`), and cap the size of input before running any O(n²) or worse operation on user-controlled data.
- Rate-limit expensive endpoints (search, report generation, password reset email sending, file processing) more aggressively than cheap ones.
- For any endpoint that triggers async/background work (report generation, image processing, email sending), enforce a queue/concurrency limit per user so one user can't exhaust shared worker capacity.
- Set timeouts on all outbound calls (DB queries, third-party APIs) so a slow/hanging dependency can't tie up application threads/connections indefinitely and starve the whole service.

## BDD security scenario patterns

```gherkin
@security
Scenario: Production error response does not leak stack trace or internal details
  Given the application is running in production mode
  When an unhandled exception occurs during a request
  Then the client receives a generic error message and a correlation ID
  And no stack trace, file path, or SQL text is included in the response

@security
Scenario: Authorization check failure defaults to deny
  Given the authorization service is unavailable or throws an error
  When a user requests a protected resource
  Then access is denied, not granted by default

@security
Scenario: Oversized request body is rejected before processing
  When a client submits a request body exceeding the configured size limit
  Then the server rejects it with 413 before parsing the full body

@security
Scenario: List endpoint enforces a maximum page size
  When a client requests a list with limit=1000000
  Then the server caps the response to the configured maximum page size

@security
Scenario: Sensitive fields are not present in application logs
  Given a user submits a login with a password
  When the request is logged
  Then the logged entry does not contain the plaintext password
```
