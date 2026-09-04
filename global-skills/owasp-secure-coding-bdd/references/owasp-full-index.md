# OWASP Cheat Sheet Series — Complete Local Index (all 120 sheets)

This is the authoritative, no-web-lookup index for the **entire** OWASP Cheat Sheet
Series (120 cheat sheets as published). Every cheat sheet in the series has an entry
here with its condensed, actionable controls, so you never need to go online to know
which sheets exist or what each one requires.

How to use this file in the Step 2 mapping:
1. From the attack surface identified in Step 1 of `SKILL.md`, scan the relevant
   cluster(s) below and read EVERY entry whose "Relevant when" line matches — not just
   the obvious one. Missed applicability is the most common cause of a real-world hole.
2. Apply the listed controls in the implementation (Step 3).
3. Turn each relevant control into an `@security` Gherkin scenario (Step 4).
4. Entries marked "→ deep dive: `references/<file>`" have fuller treatment in a
   companion reference file — read that file when the feature leans heavily on the topic.

Legend for each entry: **Cheat Sheet Name** — *Relevant when …* → controls.

The list is exhaustive by design. If a feature seems to touch something not in a cluster
you're reading, use the "Full alphabetical checklist" at the bottom to confirm you
haven't skipped an applicable sheet.

---

## Cluster 1 — Authentication, identity & account recovery
Deep dive: `references/authentication-session.md`

- **Authentication** — *any login/signup* → server-side credential checks only; generic
  failure messages; rate-limit + lockout with care (see lockout file); no username
  enumeration; require re-auth for sensitive actions.
- **Password Storage** — *storing passwords* → Argon2id (or scrypt/bcrypt); per-user
  salt; never encrypt/hash-only-with-MD5/SHA1; pepper optional in HSM/KMS; upgrade hashes
  on login.
- **Multifactor Authentication** — *any account of value* → offer TOTP/WebAuthn/passkeys;
  avoid SMS where possible; verify MFA on every sensitive action, not just login; secure
  enrollment + recovery codes; rate-limit MFA attempts.
- **Choosing and Using Security Questions** — *KBA present* → prefer to eliminate; if
  required, user-defined questions, treat answers as passwords (hashed), never as sole
  recovery factor.
- **Forgot Password** — *reset flow* → time-limited single-use tokens; identical response
  whether or not account exists; don't reveal account state; invalidate token on use;
  require token + no old-password disclosure.
- **Credential Stuffing Prevention** — *public login* → breached-password checks, MFA,
  device fingerprinting, rate limiting, CAPTCHA/step-up on anomaly, IP reputation.
- **Email Validation and Verification** — *collecting email* → syntactic validation +
  verification link; don't over-restrict with regex; confirm ownership before trusting;
  guard against header injection in mail sending.

## Cluster 2 — Sessions, cookies & tokens
Deep dive: `references/authentication-session.md`, `references/api-tokens-graphql-microservices.md`

- **Session Management** — *any authenticated session* → regenerate ID on login/privilege
  change; short idle + absolute timeouts; server-side invalidation on logout; secure
  random IDs; bind to context where feasible.
- **Cookie Theft Mitigation** — *session cookies* → `HttpOnly`, `Secure`, `SameSite`;
  scope `Domain`/`Path` tightly; consider token binding / device-bound sessions; detect
  and revoke on anomaly.
- **JSON Web Token** — *JWTs* → verify `alg` (reject `none`, pin expected algo);
  validate `iss/aud/exp/nbf`; short lifetimes; don't store secrets in payload; rotate
  signing keys; don't accept unsigned or HS/RS confusion. → deep dive.
- **Transaction Authorization** — *high-value actions (payments, transfers)* → per-
  transaction authorization (What-You-See-Is-What-You-Sign); out-of-band confirmation;
  bind auth to transaction details; guard against replay & tampering of amount/recipient.

## Cluster 3 — Access control & authorization
Deep dive: `references/access-control-authorization.md`

- **Access Control** — *any protected resource* → deny by default; enforce server-side;
  centralize checks; least privilege.
- **Authorization** — *role/permission logic* → check on every request; validate
  ownership + role; avoid client-trusted authz; prefer ABAC/RBAC consistently applied.
- **Insecure Direct Object Reference Prevention** — *IDs in requests* → verify the
  caller owns/may access the object every time; use unguessable references or per-user
  scoping; never rely on obscurity alone.
- **Authorization Regression Testing** — *evolving authz* → maintain a test matrix of
  role × resource × action; run it in CI so an authz change can't silently open access.
  (Feeds directly into `@security` BDD scenarios.)
- **Authorization Testing Automation** — *complex authz* → automate authz assertions
  against every endpoint; generate matrix from route table; fail build on unexpected 200.
- **Multi Tenant Security** — *multi-tenant app* → tenant ID from trusted session not
  request body; row-level security / scoped queries; prevent cross-tenant IDOR; isolate
  caches, files, and background jobs per tenant.

## Cluster 4 — Injection & input validation
Deep dive: `references/injection-input-validation.md`

- **Injection Prevention** — *user data reaching any interpreter* → parameterize;
  context-aware escaping; allow-list validation; least-privilege data access.
- **Injection Prevention in Java** — *Java stack* → use `PreparedStatement`,
  `ProcessBuilder` w/ arg arrays, JPA parameters; ESAPI/OWASP encoders.
- **SQL Injection Prevention** — *SQL* → parameterized queries/ORimize; never string-
  concatenate SQL; least-privilege DB user; validate + escape only as defense-in-depth.
- **Query Parameterization** — *any query language* → bind variables in every driver
  (JDBC, .NET, PHP PDO, Ruby, etc.); examples per language.
- **NoSQL Security** — *MongoDB/etc.* → reject operator objects (`$where`, `$ne`) from
  user input; type-check; parameterize; disable server-side JS.
- **LDAP Injection Prevention** — *LDAP queries* → escape DN and filter metacharacters;
  use framework-safe APIs; allow-list attributes.
- **OS Command Injection Defense** — *shelling out* → avoid shell; use arg arrays / exec
  APIs; never pass user input to a shell; allow-list commands + args.
- **Input Validation** — *all external input* → validate on server; allow-list by type,
  length, range, format; canonicalize before validating; reject not sanitize when possible.
- **Bean Validation** — *Java/Jakarta* → JSR-380 annotations (`@NotNull`, `@Size`,
  `@Pattern`) on DTOs; validate at boundary; custom validators for domain rules.
- **Mass Assignment** — *object binding from request* → explicit allow-list of bindable
  fields; DTOs not domain entities; never bind `isAdmin`/`role` from body. → also in
  `references/api-tokens-graphql-microservices.md`.

## Cluster 5 — Output encoding, XSS, CSRF & browser-side
Deep dive: `references/api-web-security-headers.md`

- **Cross Site Scripting Prevention** — *rendering user content* → context-aware output
  encoding (HTML/attr/JS/URL/CSS); prefer framework auto-escaping; sanitize rich HTML
  with a vetted library.
- **DOM based XSS Prevention** — *client-side rendering* → avoid `innerHTML`/`eval`; use
  `textContent`, safe sinks, Trusted Types; treat URL/`location`/`postMessage` as tainted.
- **XSS Filter Evasion** — *validating anti-XSS defenses* → reference for the payloads to
  test against; use as source of `@security` negative scenarios, not as a filter design.
- **Content Security Policy** — *any web page* → strict CSP (nonce/hash-based),
  `default-src 'self'`, no `unsafe-inline`/`unsafe-eval`; report-uri/`report-to`; roll out
  in report-only first.
- **Cross-Site Request Forgery Prevention** — *state-changing requests* → anti-CSRF
  tokens (synchronizer or double-submit); `SameSite` cookies; verify origin/referer for
  sensitive ops.
- **Clickjacking Defense** — *framable UI* → `frame-ancestors` CSP + `X-Frame-Options`;
  frame-busting only as fallback.
- **HTML5 Security** — *modern browser APIs* → validate `postMessage` origin; sandbox
  iframes; careful with `localStorage` (no secrets), CORS, and drag/drop.
- **DOM Clobbering Prevention** — *user-controlled HTML/ids* → sanitize named
  elements/ids; avoid relying on global lookups; use explicit references.
- **Prototype Pollution Prevention** — *JS object merges* → block `__proto__`/
  `constructor`/`prototype` keys; `Object.create(null)`; freeze prototypes; validate merge
  sources. → also `references/platform-framework-specific.md` (Node).
- **Securing Cascading Style Sheets** — *user-influenced CSS* → don't let user CSS leak
  data or overlay UI; restrict `@import`/`url()`; CSP `style-src`.
- **XS Leaks** — *cross-site info leaks* → mitigate with `SameSite`, CORP/COEP/COOP,
  `Cache-Control`, framing protections; avoid observable timing/status differences.
- **Unvalidated Redirects and Forwards** — *redirect params* → allow-list destinations;
  never redirect to raw user input; use mapping tokens not full URLs.
- **AJAX Security** — *XHR/fetch-heavy apps* → same output encoding + CSRF rules apply to
  JSON endpoints; validate content types; don't `eval` responses; guard JSON hijacking.

## Cluster 6 — HTTP transport, headers & TLS
Deep dive: `references/api-web-security-headers.md`, `references/cryptography-secrets.md`

- **HTTP Headers** — *every HTTP response* → set `Content-Security-Policy`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, remove
  `Server`/version banners.
- **HTTP Strict Transport Security** — *HTTPS sites* → `Strict-Transport-Security` with
  long `max-age`, `includeSubDomains`, consider preload; redirect all HTTP→HTTPS.
- **Transport Layer Security** / **Transport Layer Protection** — *data in transit* →
  TLS 1.2+ only; disable legacy protocols/ciphers; valid cert chain; HSTS; forward secrecy.
- **TLS Cipher String** — *server TLS config* → use a modern, curated cipher suite
  ordering; disable RC4/3DES/CBC-weak/export ciphers; prefer AEAD (GCM/ChaCha20).
- **Pinning** — *mobile/high-assurance clients* → pin to CA/intermediate or public-key
  (SPKI) with backup pins + rotation plan; understand the operational risk before pinning.

## Cluster 7 — Cryptography & secrets
Deep dive: `references/cryptography-secrets.md`

- **Cryptographic Storage** — *encrypting data at rest* → AES-GCM/ChaCha20-Poly1305;
  authenticated encryption; unique nonces; envelope encryption via KMS; no home-grown crypto.
- **Key Management** — *any keys* → generate in HSM/KMS; rotate; separate keys by purpose;
  least-privilege access; never hardcode; documented lifecycle.
- **Secrets Management** — *API keys, DB creds* → vault (HashiCorp Vault/cloud secret
  manager); short-lived dynamic secrets; no secrets in code/env-in-repo/logs; audit access.

## Cluster 8 — Files, SSRF, deserialization & XML
Deep dive: `references/file-upload-ssrf-deserialization.md`

- **File Upload** — *accepting files* → validate type by content not extension; size
  limits; store outside webroot / object storage; random names; scan for malware; never
  execute uploaded content.
- **Server Side Request Forgery Prevention** — *outbound requests to user URLs* → allow-
  list hosts/schemes; block link-local/metadata/private ranges (169.254.169.254, RFC1918);
  resolve+validate DNS; disable redirects to internal.
- **Deserialization** — *deserializing untrusted data* → avoid native deserialization of
  untrusted input; use data-only formats + schema; allow-list types; integrity-check.
- **XML External Entity Prevention** — *XML parsing* → disable DTDs/external entities in
  every parser; use least-feature parser config per language.
- **XML Security** — *XML processing generally* → schema validation; disable entity
  expansion (billion-laughs); safe XSLT; sign/verify where trust matters.

## Cluster 9 — APIs, web services, GraphQL & RPC
Deep dive: `references/api-tokens-graphql-microservices.md`, `references/api-web-security-headers.md`

- **REST Security** — *REST APIs* → authn+authz per request; input validation; proper
  methods+status codes; rate limiting; CORS locked down; no sensitive data in URLs.
- **REST Assessment** — *reviewing an API* → enumerate endpoints, auth model, and
  parameter tampering surface; use to drive negative `@security` scenarios.
- **Web Service Security** — *SOAP/WS-\* services* → WS-Security, schema validation,
  message-level auth, disable verbose faults.
- **GraphQL** — *GraphQL* → depth/complexity/cost limits; disable introspection in prod;
  per-field authz; batching/alias abuse limits; validate + timeout. → deep dive.
- **gRPC Security** — *gRPC* → mTLS; per-method authz; message size limits; validate all
  fields; deadline/timeout; don't leak internals in status details.
- **WebSocket Security** — *WebSockets* → validate `Origin`; authenticate the handshake +
  ongoing messages; rate-limit; no trust in client framing; TLS (`wss`).
- **Microservices Security** — *service mesh* → service identity (mTLS/SPIFFE); don't
  trust the network; propagate + verify auth context; per-service least privilege. → deep dive.
- **Microservices based Security Arch Doc** — *designing the mesh* → document trust
  boundaries, token exchange, and edge-vs-internal authz as an explicit architecture artifact.

## Cluster 10 — AI, LLM & agent security (new cluster)
Deep dive: `references/ai-llm-agent-security.md`

- **LLM Prompt Injection Prevention** — *any LLM call with untrusted content* → treat all
  external/retrieved text as untrusted; separate system vs user content; constrain tools
  the model can call; output filtering; human approval for high-impact actions.
- **AI Agent Security** — *autonomous/tool-using agents* → least-privilege tools; sandbox
  execution; confirm irreversible actions; guard against goal hijacking + tool-output
  injection; log + rate-limit agent actions.
- **RAG Security** — *retrieval-augmented generation* → sanitize + attribute retrieved
  docs; access-control the vector store per user; prevent data poisoning + cross-tenant
  retrieval; treat retrieved text as prompt-injection vector.
- **Secure AI Model Ops** — *training/serving models* → protect training data + model
  artifacts; supply-chain integrity for models; monitor for drift/abuse; access-control
  inference endpoints.
- **Secure Coding with AI** — *using AI to write code* → review AI-generated code for the
  same OWASP issues; never trust generated crypto/authz blindly; keep humans in the loop;
  scan output in CI.
- **MCP Security** — *Model Context Protocol servers/tools* → authenticate + authorize MCP
  tool calls; validate tool inputs/outputs; least-privilege tool exposure; guard against
  malicious tool responses influencing the model.
- **AML Sanctions AI Agent Payments** — *AI agents moving money* → sanctions/AML screening
  before payment; transaction limits + human approval; audit trail; KYC boundaries;
  prevent agent from bypassing financial controls.

## Cluster 11 — Language & framework specifics
Deep dive: `references/platform-framework-specific.md` (Node/Django/Rails/mobile),
plus `references/language-framework-hardening.md` (the rest)

- **Nodejs Security** — *Node apps* → avoid `eval`/`child_process` with input; validate
  everything; `helmet`; keep deps patched; prototype-pollution guards.
- **NodeJS Docker** — *Node in Docker* → non-root user; minimal base image; `npm ci
  --omit=dev`; no secrets in image layers; multi-stage build.
- **NPM Security** — *npm deps* → lockfiles; `npm audit`; verify packages; beware
  typosquatting + install scripts; pin/verify integrity.
- **Django Security** — *Django* → keep `DEBUG=False`; use ORM (SQLi-safe); CSRF middleware
  on; `SECURE_*` settings; template auto-escaping; strong `SECRET_KEY` from secrets store.
- **Django REST Framework** — *DRF APIs* → set default permission classes (deny-by-
  default); serializers as allow-lists; throttling; object-level permissions.
- **Ruby on Rails** — *Rails* → strong parameters (mass-assignment); ORM param binding;
  CSRF protection on; `html_safe` sparingly; credentials via encrypted credentials store.
- **Java Security** — *Java apps* → safe deserialization; secure XML parsers; use vetted
  crypto (JCA); avoid reflection on untrusted input; SecurityManager considerations.
- **JAAS** — *Java auth/authz* → configure login modules correctly; principal/role checks;
  don't roll custom auth where JAAS/framework suffices.
- **DotNet Security** — *.NET/C#* → parameterized ADO/EF; data protection API for secrets;
  antiforgery tokens; `HttpOnly`/`Secure` cookies; disable verbose errors in prod.
- **PHP Configuration** — *PHP* → harden `php.ini` (`display_errors=Off`,
  `disable_functions`, `open_basedir`); disable dangerous functions; secure session config.
- **Laravel** — *Laravel* → Eloquent binding; `$fillable`/`$guarded` for mass assignment;
  CSRF middleware; `.env` secrets not in repo; validation rules on requests.
- **Symfony** — *Symfony* → security component for authz voters; Doctrine param binding;
  CSRF on forms; secrets vault; escape in Twig (default on).
- **C-Based Toolchain Hardening** — *C/C++ builds* → compiler hardening flags
  (`-fstack-protector-strong`, `-D_FORTIFY_SOURCE=2`, RELRO, PIE, `-Wformat-security`);
  ASAN/UBSAN in CI; treat warnings as errors.
- **Browser Extension Vulnerabilities** — *browser extensions* → minimal permissions;
  strict CSP in manifest; validate messages between content/background; no remote code;
  sanitize DOM injection.

## Cluster 12 — Logging, error handling & availability
Deep dive: `references/logging-error-handling-dos.md`

- **Logging** — *any app* → log security events (authn, authz failures, input rejection);
  never log secrets/PII/tokens; tamper-resistant, time-synced, centralized logs.
- **Logging Vocabulary** — *standardizing logs* → use consistent event vocabulary/fields
  so security events are queryable + alertable across services.
- **Error Handling** — *everywhere* → generic messages to clients; full detail server-side
  only; no stack traces/SQL errors leaked; fail closed.
- **Denial of Service** — *any exposed endpoint* → rate limiting, quotas, timeouts,
  payload-size caps, pagination limits, backpressure; guard expensive operations.
- **Bot Management and Anti-Automation** — *public endpoints* → detect automation
  (behavioral, fingerprint, challenge); rate-limit + CAPTCHA on abuse; protect signup/
  login/checkout/scraping-prone endpoints.

## Cluster 13 — Dependencies, supply chain, containers, cloud & CI/CD
Deep dive: `references/third-party-dependency-container.md`

- **Vulnerable Dependency Management** — *any deps* → SCA scanning in CI; patch policy;
  track advisories; fail build on known-critical CVEs.
- **Dependency Graph SBOM** — *releases* → generate SBOM (CycloneDX/SPDX); track transitive
  deps; use for rapid impact analysis on new CVEs.
- **Software Supply Chain Security** — *build/release* → verify provenance (SLSA); signed
  artifacts; pin + verify build tools; protect the build system as a production asset.
- **Third Party Javascript Management** — *external JS/CDN* → Subresource Integrity (SRI);
  pin versions; prefer self-hosting; CSP to constrain; vendor review.
- **Docker Security** — *containers* → non-root; minimal/distroless base; no secrets in
  layers; read-only FS; drop capabilities; scan images.
- **Kubernetes Security** — *K8s* → RBAC least privilege; network policies; pod security
  standards; no privileged pods; secrets via provider; admission controls.
- **Infrastructure as Code Security** — *Terraform/CFN/Bicep/Pulumi* → scan with
  tfsec/checkov; no plaintext secrets; least-privilege IAM; encrypted storage by default;
  block public exposure.
- **CI CD Security** — *pipelines* → least-privilege runners; protect secrets; pin actions;
  isolate build from prod creds; require reviews; sign artifacts.
- **GitHub Actions Security** — *GH Actions* → pin actions to full SHA; `permissions:` least
  privilege; avoid `pull_request_target` misuse; guard secrets from forks; OIDC over long-
  lived creds.
- **Serverless FaaS Security** — *Lambda/functions* → least-privilege function roles; short
  timeouts; validate event input (all sources); no secrets in env plaintext; per-function
  isolation.
- **Secure Cloud Architecture** — *cloud design* → segmentation, least-privilege IAM,
  encryption in transit + at rest, private networking, guardrails/landing zones. → deep dive.
- **Network Segmentation** — *network design* → segment by trust zone; default-deny between
  zones; restrict east-west; isolate management planes.
- **Zero Trust Architecture** — *enterprise access* → never trust by network location;
  authenticate + authorize every request; device posture; micro-segmentation; continuous
  verification.
- **Subdomain Takeover Prevention** — *DNS management* → remove dangling DNS records for
  deprovisioned services; monitor for unclaimed CNAME targets; ownership verification.
- **Automotive Security** — *vehicle/ECU software* → secure CAN/bus boundaries; signed
  firmware + secure boot; segment critical from infotainment; threat model per ISO 21434.
- **Drone Security** — *UAV systems* → authenticated + encrypted C2 links; GPS spoofing/
  jamming resilience; secure firmware update; geofencing + fail-safe.

## Cluster 14 — Databases & data
Deep dive: `references/injection-input-validation.md`, `references/cryptography-secrets.md`

- **Database Security** — *any DB* → least-privilege accounts per app; network isolation;
  encryption at rest + TLS in transit; disable unused features; audit + backup; no shared
  admin creds; parameterized access (see injection cluster).

## Cluster 15 — Mobile
Deep dive: `references/platform-framework-specific.md`

- **Mobile Application Security** — *iOS/Android* → secure local storage (Keychain/
  Keystore, no secrets in prefs); cert pinning where appropriate; obfuscate + anti-tamper
  for high-risk; validate all IPC/deep links; follow MASVS; no sensitive data in logs.

## Cluster 16 — Design, process, privacy & governance
Deep dive: `references/privacy-threat-modeling-business-logic.md`

- **Threat Modeling** — *before building anything non-trivial* → identify assets, entry
  points, trust boundaries, threats (STRIDE), and mitigations; document; revisit on change.
- **Attack Surface Analysis** — *scoping* → enumerate all entry/exit points, data flows,
  and trust boundaries; minimize surface; track changes over time.
- **Abuse Case** — *requirements* → write "how could this be misused" alongside use cases;
  these become `@security` negative scenarios.
- **Business Logic Security** — *stateful/money/quota flows* → enforce invariants server-
  side (order of ops, limits, one-time use, price/qty integrity); can't be caught by
  generic scanners — must be explicitly modeled + tested.
- **Secure Product Design** — *new product/feature* → security requirements up front;
  secure defaults; defense in depth; least privilege; fail securely as design principles.
- **Secure Code Review** — *reviewing code* → structured review against these controls;
  focus on authz, input handling, crypto, secrets; use as PR checklist.
- **User Privacy Protection** — *handling PII* → data minimization; purpose limitation;
  encryption; retention limits; access controls; honor deletion/export; privacy by design.
- **Vulnerability Disclosure** — *any product* → publish a disclosure policy/security.txt;
  triage + remediate reported issues; safe harbor for researchers.
- **Virtual Patching** — *can't fix root cause immediately* → WAF/proxy/config rule to
  block exploitation as a stopgap; track back to a real fix; don't let it become permanent.
- **Legacy Application Management** — *old systems* → inventory + risk-rate; compensating
  controls (segmentation, WAF, monitoring); plan modernization; manage EOL dependencies.
- **Third Party Payment Gateway Integration** — *payments* → keep cardholder data out of
  scope (hosted fields/redirect); verify webhooks (signatures); idempotency; PCI DSS
  alignment; never log full PAN; reconcile server-side, never trust client amount.
- **Security Terminology** — *reference* → shared vocabulary for security discussions;
  use to keep threat models and scenarios precise.

---

## Full alphabetical checklist (all 120 — confirm none skipped)

Use this to verify completeness on any feature review. Each name maps to its cluster above.

A: AI Agent Security · AJAX Security · AML Sanctions AI Agent Payments · Abuse Case ·
Access Control · Attack Surface Analysis · Authentication · Authorization · Authorization
Regression Testing · Authorization Testing Automation · Automotive Security
B: Bean Validation · Bot Management and Anti-Automation · Browser Extension
Vulnerabilities · Business Logic Security
C: C-Based Toolchain Hardening · CI/CD Security · Choosing and Using Security Questions ·
Clickjacking Defense · Content Security Policy · Cookie Theft Mitigation · Credential
Stuffing Prevention · Cross-Site Request Forgery Prevention · Cross Site Scripting
Prevention · Cryptographic Storage
D: DOM Clobbering Prevention · DOM based XSS Prevention · Database Security · Denial of
Service · Dependency Graph SBOM · Deserialization · Django REST Framework · Django
Security · Docker Security · DotNet Security · Drone Security
E: Email Validation and Verification · Error Handling
F: File Upload · Forgot Password
G: GitHub Actions Security · GraphQL · gRPC Security
H: HTML5 Security · HTTP Headers · HTTP Strict Transport Security
I: Infrastructure as Code Security · Injection Prevention · Injection Prevention in Java ·
Input Validation · Insecure Direct Object Reference Prevention
J: JAAS · JSON Web Token · Java Security
K: Key Management · Kubernetes Security
L: LDAP Injection Prevention · LLM Prompt Injection Prevention · Laravel · Legacy
Application Management · Logging · Logging Vocabulary
M: MCP Security · Mass Assignment · Microservices Security · Microservices based Security
Arch Doc · Mobile Application Security · Multi Tenant Security · Multifactor Authentication
N: NPM Security · Network Segmentation · NoSQL Security · NodeJS Docker · Nodejs Security
O: OAuth2 · OS Command Injection Defense
P: PHP Configuration · Password Storage · Pinning · Prototype Pollution Prevention
Q: Query Parameterization
R: RAG Security · REST Assessment · REST Security · Ruby on Rails
S: SAML Security · SQL Injection Prevention · Secrets Management · Secure AI Model Ops ·
Secure Cloud Architecture · Secure Code Review · Secure Coding with AI · Secure Product
Design · Securing Cascading Style Sheets · Security Terminology · Server Side Request
Forgery Prevention · Serverless FaaS Security · Session Management · Software Supply Chain
Security · Subdomain Takeover Prevention · Symfony
T: TLS Cipher String · Third Party Javascript Management · Third Party Payment Gateway
Integration · Threat Modeling · Transaction Authorization · Transport Layer Protection ·
Transport Layer Security
U: Unvalidated Redirects and Forwards · User Privacy Protection
V: Virtual Patching · Vulnerability Disclosure · Vulnerable Dependency Management
W: Web Service Security · WebSocket Security
X: XML External Entity Prevention · XML Security · XS Leaks · XSS Filter Evasion
Z: Zero Trust Architecture

> OAuth2 and SAML Security appear in Cluster 2/9 handling (tokens & API auth) and are
> detailed in `references/api-tokens-graphql-microservices.md`.

**Total: 120 cheat sheets, all represented locally. No web lookup required for routine
work.** For an unusual edge case beyond these condensed controls, a single targeted lookup
of that one sheet is acceptable — but it should be the exception, not the default.
