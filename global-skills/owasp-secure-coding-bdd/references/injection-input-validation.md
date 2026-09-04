# Injection Prevention & Input Validation

Covers: Input Validation, SQL Injection Prevention, OS Command Injection Defense, LDAP Injection Prevention, NoSQL Injection.

## Core principle
Never build a query, command, or interpreter statement by concatenating or string-formatting untrusted input into it. Use an API that separates code from data (parameterization) so the input can never be interpreted as syntax, no matter what characters it contains.

## SQL injection
- Always use **parameterized queries / prepared statements** (`?` or named placeholders bound separately from the SQL text) — every ORM (Sequelize, SQLAlchemy, Entity Framework, Hibernate/JPA, ActiveRecord) does this by default when used correctly; the risk is raw SQL string building.
- Never concatenate user input into a query string, including for things that feel "safe" like sort-column or table names — for identifiers that can't be parameterized, validate against an allow-list of known-safe values, never pass the raw input through.
- If a stored procedure or raw query is unavoidable, use the database driver's parameter binding, never string interpolation.
- Apply least-privilege DB accounts: the application's DB user should not have permissions beyond what the app needs (no DROP/ALTER for a read/write app account).

## NoSQL injection (MongoDB, etc.)
- Don't pass raw user-supplied JSON/objects directly into query builders — an attacker can inject operators like `{"$ne": null}` or `{"$gt": ""}` where a scalar was expected.
- Explicitly cast/validate expected types before building the query (e.g., ensure a "username" field is actually a string, not an object) — reject non-scalar input where a scalar is expected.
- Use the driver's parameterized/builder APIs rather than constructing query documents from raw request bodies.

## OS command injection
- Avoid invoking a shell with user input at all if possible — use language APIs that take an argument array (e.g., `subprocess.run([...], shell=False)` in Python, `execFile`/`spawn` with an args array in Node, avoiding `Runtime.exec(String)` in Java) rather than a single shell string.
- If shelling out is unavoidable, strictly allow-list acceptable characters/values for anything derived from user input, and never rely on blocklisting special characters (`;`, `|`, `&&`, backticks) as the only defense — allow-listing the whole value against known-good patterns is far more reliable.

## Query parameterization, generally
- The same "separate code from data" principle in the SQL section applies to any query language your stack touches: parameterize Elasticsearch/OpenSearch query bodies (don't string-build a query DSL from raw input), Cypher (Neo4j), and any templated query builder — the pattern to check for is always "am I building a query string by concatenation, or am I passing data through a binding API." When a library offers both a raw/string mode and a parameterized/builder mode, default to the parameterized one and treat the raw mode as requiring explicit justification.

## LDAP injection
- Use parameterized LDAP query APIs where available, or explicitly escape LDAP special characters (`* ( ) \ NUL`) in any user input used to build a filter.

## General input validation
- Validate on the **server side always** — client-side validation is a UX nicety, never a security control.
- Prefer **allow-list validation** (define what's acceptable: format, length, character set, range) over deny-list validation (trying to block "bad" patterns, which is always incomplete).
- Validate: type, length/size bounds, numeric range, format (regex for email/date/etc. using a well-tested pattern, not a hand-rolled one), and business-logic constraints (e.g., a quantity field must be a positive integer).
- Reject invalid input outright rather than trying to "sanitize" it silently — silent sanitization hides bugs and can be bypassed with encoding tricks; explicit rejection with a clear error is safer and more debuggable.
- Canonicalize/normalize input (e.g., URL-decode, Unicode-normalize) before validating, so encoded attack payloads can't slip past a filter that only checks the raw encoded form.
- Apply the same validation consistently across every entry point that accepts the same kind of data (API, admin panel, batch import, webhook) — a validation rule enforced in one place and skipped in another is a common bypass.

## BDD security scenario patterns

```gherkin
@security
Scenario Outline: Rejects SQL injection payloads in search field
  When a user searches for "<payload>"
  Then the query executes as a parameterized statement
  And no database error is returned to the client
  And the result set is empty or a normal "no results" response

  Examples:
    | payload                    |
    | ' OR '1'='1                |
    | '; DROP TABLE users; --    |
    | admin'--                   |

@security
Scenario: Rejects NoSQL operator injection in login field
  When a user submits password as {"$ne": null}
  Then the request is rejected as invalid input, not treated as a query operator

@security
Scenario: Rejects shell metacharacters in filename parameter
  When a user uploads a file named "report.pdf; rm -rf /"
  Then the filename is rejected or sanitized to a safe allow-listed pattern
  And no shell command is constructed from the raw filename
```
