# Privacy, Threat Modeling, Attack Surface & Business Logic Security

Covers: User Privacy Protection (PII handling), Threat Modeling, Attack Surface Analysis, Abuse Case Cheat Sheet, Vulnerability Disclosure, Business Logic Security.

## Threat modeling (do this deliberately, not just implicitly)
- For any non-trivial feature, before/while designing it, ask explicitly: who are the plausible attackers (external anonymous user, authenticated-but-malicious user, insider, compromised dependency), what do they want (data, money, access, disruption), and what's the easiest path to get it given this design?
- Use STRIDE as a lightweight checklist per component: **S**poofing identity, **T**ampering with data, **R**epudiation (can an action be denied/is it logged?), **I**nformation disclosure, **D**enial of service, **E**levation of privilege. For each, ask "does this feature introduce a new way to do this?"
- Diagram or at least list trust boundaries (where data crosses from less-trusted to more-trusted context — e.g., internet → API, API → database, service A → service B) since most vulnerabilities cluster at boundaries where a check is assumed to have already happened but wasn't.
- Threat model incrementally as part of design/code review for meaningful features, not as a one-time exercise disconnected from the actual code being written.

## Attack surface analysis
- Every new endpoint, input field, file format accepted, third-party integration, and exposed port is new attack surface — enumerate what's new whenever a feature adds one of these, and consciously ask whether it's necessary (unused/unneeded endpoints, debug routes left enabled, or overly permissive file-type acceptance are surface that provides no value but real risk).
- Remove/disable debug endpoints, verbose status pages, and admin interfaces from production builds if they're not meant to be reachable there; don't rely on "security through obscurity" (an unlisted URL) as the actual control.

## Abuse case thinking
- For every legitimate user story, write at least one corresponding "abuse case": what would a malicious actor do with this same feature? (e.g., legitimate story: "user can invite teammates by email" → abuse case: "attacker enumerates valid accounts by spamming invite attempts and observing response differences," or "attacker uses the invite feature to spam arbitrary email addresses at scale, unrelated to team-building.") Feed these into the `@security` BDD scenarios the same as OWASP-specific checks.

## Business logic security
- Not all vulnerabilities are technical injection/access-control bugs — some are the business logic itself allowing something that shouldn't be possible even though every technical control "worked correctly": e.g., a discount code with no usage limit, a workflow that lets a refund be requested twice, a race condition between "check balance" and "deduct balance" that allows overdraft via concurrent requests, a step that can be skipped by calling a later API directly out of sequence.
- Explicitly test business logic invariants under concurrency: if two requests hit "redeem this one-time coupon" simultaneously, does exactly one succeed? If not, that's a real bug regardless of how clean the code looks.
- Validate state transitions, not just individual field values — an order status should only move through valid transitions (`pending → paid → shipped`, not `shipped → pending`) and the server must enforce that, not just the client UI.
- Watch for logic that trusts client-supplied prices, quantities, or discounts instead of recalculating/verifying them server-side against the authoritative source (catalog price, current stock) at the time of the transaction.

## Privacy / PII handling
- Collect only the personal data actually needed for the feature (data minimization) — don't add "just in case" fields that create privacy liability without product value.
- Apply the same encryption-at-rest and access-control discipline (see cryptography and access-control references) specifically to PII, and additionally minimize *who* internally can query it (support/admin tooling access to PII should be logged and limited, not open to every internal role by default).
- Support data deletion/export requirements where applicable (subject access/erasure rights) — design data models so a user's data can actually be located and removed, rather than being scattered in a way that makes deletion impractical later.
- Avoid putting PII or tokens in URLs/query strings (they end up in server logs, browser history, and `Referer` headers to third parties) — use POST bodies or headers instead.
- Mask/redact PII in logs and error messages by default (see logging reference).

## Vulnerability disclosure
- If you discover an existing vulnerability while working (not just a gap in new code), report it clearly and directly to the user rather than quietly fixing it as a side effect of an unrelated commit — the user needs to know a live issue existed, its severity, and what was changed to address it.
- If the codebase is a public/open-source project, suggest the user establish a `SECURITY.md` with a disclosure contact/process if one doesn't exist, so external researchers have a clear, safe channel to report issues instead of public disclosure.

## BDD security scenario patterns

```gherkin
@security
Scenario: One-time coupon cannot be redeemed twice under concurrent requests
  Given a coupon with a single-use limit exists and is unused
  When two redemption requests are submitted simultaneously
  Then exactly one redemption succeeds and the other is rejected

@security
Scenario: Order status cannot transition backward
  Given an order has status "shipped"
  When a request attempts to set its status to "pending"
  Then the transition is rejected as invalid

@security
Scenario: Price is recalculated server-side, not trusted from the client
  Given a product's authoritative price is $50
  When a checkout request submits a client-supplied price of $1
  Then the server charges based on the authoritative $50 price, not the submitted value

@security
Scenario: PII is not exposed in logged request URLs
  When a request includes a user's email address as a URL query parameter
  Then the logged entry does not retain the email in plaintext in the URL
```
