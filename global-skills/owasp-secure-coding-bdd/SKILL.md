---
name: owasp-secure-coding-bdd
description: Use for EVERY feature touching user input, auth, sessions, data storage, files, APIs, external requests, permissions, dependencies, or infra config — most features. Run a threat-modeling pass against the FULL OWASP Cheat Sheet Series (bundled locally in reference files, no web lookup needed), apply matching secure-coding measures, write results as @security Gherkin scenarios, and ALWAYS run the lockout/accidental-deletion safety check before any permission, access, credential, or deletion change. Trigger on login, passwords, sessions, tokens, forms, uploads, DB queries, outbound HTTP, deserialization, admin/role checks, permissions, firewall/IAM rules, keys, dependencies, or AI/LLM/agent/RAG/MCP code — even without the words "security" or "OWASP." All 120 OWASP cheat sheets are bundled locally in references/owasp-full-index.md.
---

# OWASP Secure Coding & Threat Modeling in BDD

## Why this exists

Most vulnerabilities are not exotic — they're the same handful of well-documented mistakes (injection, broken auth, broken access control, insecure crypto, etc.) shipped over and over because nobody checked the relevant checklist before writing the code. This skill makes that checklist-check a default part of building anything with an attack surface, and turns the resulting requirements into executable BDD scenarios so "secure" isn't just a claim, it's a test that runs on every build.

This skill bundles condensed, actionable checklists covering the OWASP Cheat Sheet Series directly in its reference files, so you do not need to search the web every time you write code. Read the relevant reference file(s) from disk instead.

**Coverage is complete, not a curated subset.** `references/owasp-full-index.md` contains an entry for **every one of the 120 cheat sheets in the series**, each with its condensed local controls — it is the master list and your starting point. The other reference files are deep dives for the highest-traffic topics. Always scan the full index first so no applicable cheat sheet is missed; then open the matching deep-dive file(s) for topics the feature leans on heavily.

## The workflow

### Step 0 (always, no exceptions): the lockout/accidental-deletion safety check

Before applying ANY change that revokes, restricts, deletes, or rotates a permission, role, credential, key, account, firewall rule, or resource — regardless of which feature or cheat sheet topic triggered the work — read `references/lockout-prevention-safe-changes.md` and follow it. This applies even to changes that are clearly "the secure thing to do" (tightening a permission, revoking an old key, deleting a stale account): secure and available are both real requirements, and this step exists specifically because hardening work is what causes accidental self-lockouts. This step runs in addition to, not instead of, the topic-specific steps below.

### Step 1: Identify the attack surface of the feature

Before or while implementing, ask what the feature actually touches. Check each of these — most non-trivial features touch several:

- **User input** of any kind (form fields, query params, file uploads, headers, JSON/XML bodies, GraphQL queries)
- **Authentication** (login, signup, password reset, MFA, SSO/OIDC/SAML, security questions)
- **Sessions or tokens** (cookies, JWTs, API keys, OAuth tokens)
- **Authorization/access control** (role checks, ownership checks, multi-tenant boundaries, mass-assignment-prone endpoints)
- **Queries against a database** or any data store (SQL, NoSQL, LDAP, search engines, graph DBs)
- **Sensitive data** storage or transmission (PII, credentials, payment info, secrets, encryption keys)
- **Rendering user-controlled content** back to a browser (HTML, JS, SVG, DOM manipulation)
- **File uploads** or **file serving**
- **Outbound HTTP requests** to a URL that's user-influenced in any way (webhooks, link previews, imports)
- **Deserialization** of data (JSON, XML, YAML, pickled objects, binary formats)
- **APIs** (REST, GraphQL, RPC, SAML/OAuth flows, service-to-service/microservices calls)
- **Third-party dependencies**, **containers**, **cloud infrastructure/IaC**, or **CI/CD pipelines**
- **Mobile app** or **platform-specific framework** code (NodeJS, Django, Rails, iOS, Android)
- **Permissions, access, credentials, or deletion** of any kind — always triggers Step 0 above, regardless of feature type
- **Business logic** with state, money, quotas, or one-time/limited-use semantics

### Step 2: Map the attack surface to the relevant reference files

**Start with `references/owasp-full-index.md`** — it lists all 120 cheat sheets grouped into clusters, so you can confirm which ones apply (including specialized ones like AI/LLM, WebSockets, subdomain takeover, payment gateways, automotive, etc. that aren't in the summary table below). Then read only the deep-dive files that match what Step 1 found — don't read all of them for a feature that doesn't touch that surface, that's wasted context. Deep-dive mapping:

| Attack surface from Step 1 | Reference file |
|---|---|
| ANYTHING — confirm the complete set of applicable cheat sheets first | `references/owasp-full-index.md` (all 120, always check) |
| Login, signup, password reset, MFA, security questions, session/token handling | `references/authentication-session.md` |
| Any user input reaching a query, shell command, or interpreter (SQL, NoSQL, LDAP, OS commands, search/graph query languages) | `references/injection-input-validation.md` |
| Role checks, ownership checks, permissions, multi-tenant data, mass assignment | `references/access-control-authorization.md` |
| Storing secrets, encrypting data, TLS, key management | `references/cryptography-secrets.md` |
| REST APIs, HTTP responses, CORS, rendering user content, CSRF, XSS (reflected/stored/DOM-based), open redirects, DOM clobbering, security headers | `references/api-web-security-headers.md` |
| File uploads, outbound requests to user-influenced URLs (SSRF), deserializing data, XML/XXE parsing | `references/file-upload-ssrf-deserialization.md` |
| Logging, error messages, rate limiting, resource exhaustion/DoS | `references/logging-error-handling-dos.md` |
| JWT, OAuth2/OIDC, SAML, GraphQL, web services, microservices-to-microservices auth, third-party JS/CDN scripts, mass assignment | `references/api-tokens-graphql-microservices.md` |
| LLM/AI calls, autonomous agents, RAG, MCP tools/servers, AI-generated code, AI-initiated payments | `references/ai-llm-agent-security.md` |
| NodeJS, Django, Ruby on Rails specifics, mobile apps (iOS/Android) | `references/platform-framework-specific.md` |
| Java/Jakarta, .NET/C#, PHP/Laravel/Symfony, C/C++ toolchain, browser extensions | `references/language-framework-hardening.md` |
| npm/pip/maven/nuget dependencies, Docker, Kubernetes, Infrastructure as Code, cloud architecture, virtual patching, CI/CD supply chain | `references/third-party-dependency-container.md` |
| PII/privacy handling, threat modeling, attack surface analysis, abuse cases, business logic invariants, vulnerability disclosure | `references/privacy-threat-modeling-business-logic.md` |
| ANY permission/access/credential/deletion change, on any of the above | `references/lockout-prevention-safe-changes.md` (mandatory — see Step 0) |

### Step 3: Apply the relevant secure-coding measures

Each reference file gives concrete, actionable "do this / never do this" guidance, not just theory. Apply it to the actual code you're writing — parameterize the query, validate the input server-side, set the cookie flags, hash the password with the specified algorithm, verify the JWT claims, etc. This step changes the implementation, not just the tests.

### Step 4: Write the threat model findings as BDD security scenarios

For every relevant risk identified in Steps 1-2, add a `Scenario` (or `Scenario Outline`) tagged `@security` to the feature's `.feature` file (the same file the `bdd-comprehensive-testing` skill produces and permanently stores — security scenarios are additional scenarios in that file, not a separate testing system). Format:

```gherkin
  @security
  Scenario: Rejects SQL injection payload in username field
    Given the login form is available
    When a user submits username "' OR '1'='1" and any password
    Then the login is rejected with a generic authentication error
    And no database error or stack trace is exposed to the client
    And the attempt is logged with the source IP and timestamp

  @security
  Scenario: Session cookie is not accessible to JavaScript
    Given a user has successfully logged in
    Then the session cookie is set with HttpOnly, Secure, and SameSite=Strict

  @security @lockout-prevention
  Scenario: Revoking a role does not remove the last administrator
    Given exactly one active administrator account exists
    When a request attempts to revoke that account's admin role
    Then the operation is rejected or requires explicit override confirmation
```

Each reference file includes example scenario patterns specific to its topic — use those as templates rather than writing every scenario from scratch.

### Step 5: Wire these into the same CI/CD pipeline as the functional BDD scenarios

No separate pipeline needed — `@security` scenarios run in the same suite set up by `bdd-comprehensive-testing`, and are stored permanently in the same feature-file index that skill maintains (see its "Storing BDD scenarios permanently" section). If the project has a Software Composition Analysis (dependency vulnerability scanning) or IaC-scanning gap, also recommend adding `npm audit` / `pip-audit` / `dotnet list package --vulnerable` / OWASP Dependency-Check / `tfsec`/`checkov` as a CI step (see `references/third-party-dependency-container.md`) — that's a complementary automated check, not a BDD scenario, and it belongs in the same pipeline.

### Step 6: Don't let severity get lost

If, during this process, you find something that's already a live vulnerability in existing code (not just a gap in a new feature), say so clearly and directly to the user rather than quietly folding it into a routine scenario list — flag it, explain the risk in concrete terms, and recommend prioritizing the fix.

### Step 7: Never let a security fix become an outage

If applying a secure-coding fix requires touching permissions, credentials, or deleting anything (see Step 0), the fix is not "done" until you've confirmed it doesn't lock out the human user or your own continued access to the system. A vulnerability fixed by breaking legitimate access isn't a clean fix — flag the tension to the user if a fully non-disruptive path isn't available, rather than silently picking one side.

## Keeping this current

The bundled reference files are condensed, original summaries of well-established OWASP Cheat Sheet Series guidance — the underlying principles are stable and don't change year to year. If a specific situation calls for detail beyond what's bundled (a narrow edge case not covered here, or a claim you want to double-check against the current published version), a targeted web lookup for that specific gap is reasonable — but for the vast majority of features, the bundled checklists are sufficient and should be your first stop, not the web.
