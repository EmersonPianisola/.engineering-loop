---
name: enterprise-architecture-standards
description: Use for EVERY non-trivial piece of code, service, database schema, or integration the agent builds — new services, new endpoints, schema changes, refactors, and anything described as "production," "enterprise," "scalable," or "for a large team." Applies technical/system architecture, database architecture, sound algorithmic and coding principles, microservices and integration patterns, resilience/reliability patterns, and performance/scalability practices at the standard expected from senior engineering teams at large companies. Trigger proactively whenever the user asks to design, architect, build, scale, or refactor a system, service, database, or API, or asks how "properly built" or "enterprise-grade" software should look — even without those exact words, e.g. "add a new service," "design the schema for X," "how should these services talk to each other," "this needs to handle more load."
---

# Enterprise Architecture & Engineering Standards

## Why this exists

Most systems don't fail because nobody knew the right pattern — they fail because the right pattern wasn't applied consistently under deadline pressure. This skill makes architectural rigor the default rather than something bolted on after a system already has scaling problems, data integrity bugs, or an unmaintainable service boundary. It complements (doesn't replace) `bdd-comprehensive-testing` and `owasp-secure-coding-bdd`: those cover behavior verification and security; this one covers whether the system is actually well-designed — the right shape, the right data model, the right resilience posture, the right performance characteristics — before those tests even get written.

## The workflow

### Step 1: Classify what's being built

Different work calls for different reference files. Identify which of these apply — most substantial tasks touch more than one:

- **New service or system boundary** (a new microservice, a new bounded context, splitting a monolith) → `references/software-architecture-styles.md` + `references/microservices-patterns.md`
- **Database schema, data model, or persistence choice** (new tables, new data store, migration, sharding) → `references/database-architecture.md`
- **Any non-trivial function, class, or module** (the actual code, regardless of scale) → `references/coding-principles.md`
- **Service-to-service communication, external integration, or public/internal API** → `references/api-integration-design.md`
- **Anything that can fail, time out, or cascade** (calls to other services, databases, queues) → `references/resilience-reliability-patterns.md`
- **Anything with a load, latency, or scale requirement**, or that touches a hot path → `references/performance-scalability.md`
- **Anything that needs to be operated, monitored, or debugged in production** → `references/observability-operations.md`
- **Any significant design decision, tradeoff, or standard that should outlive this conversation** → `references/enterprise-governance-standards.md`

Read only the reference files relevant to the task — don't load all nine for a one-line bug fix.

### Step 2: Make the architecture decision explicit before writing code

For anything beyond a trivial change, briefly state (to yourself and, for significant decisions, to the user):
- What are the 2-3 realistic options?
- What does each trade off (complexity vs. flexibility, consistency vs. availability, latency vs. throughput, cost vs. resilience)?
- Which one fits this system's actual current scale and team size — not the scale it might have in five years. Over-engineering (premature microservices, premature sharding, speculative abstraction layers) is as much a violation of sound architecture as under-engineering. Match the solution to the problem's actual current and near-term requirements.

For decisions with real long-term consequences (a new service boundary, a database technology choice, an API contract other teams will depend on), write this down as a lightweight Architecture Decision Record — see `references/enterprise-governance-standards.md` for the format — rather than letting the reasoning live only in chat history.

### Step 3: Apply the relevant principles as you build, not as an afterthought

Each reference file gives concrete, actionable guidance — not just naming patterns, but when to use them and when NOT to (most of these files spend real space on anti-patterns and misuse, because knowing when *not* to apply a pattern is the actual senior-engineer skill; "microservices everywhere" and "normalize everything to 3NF always" are both common ways teams over-apply a real principle past the point it helps). Apply this while writing the implementation, the same way `owasp-secure-coding-bdd` changes the implementation rather than only the tests.

### Step 4: Cross-check against the other engineering skills

- Every service/endpoint/schema this skill touches should still get full happy/non-happy-path BDD coverage from `bdd-comprehensive-testing`, stored in the same permanent feature-file index.
- Every service/endpoint touching auth, data, input, or permissions should still get the `owasp-secure-coding-bdd` threat-modeling pass, including its mandatory lockout-prevention step for any permission/access/deletion change (schema migrations that drop columns/tables, and IAM/role changes for new services, both qualify).
- These three skills are meant to run together on real feature work, not in isolation — architecture soundness, behavioral correctness, and security are three different questions about the same code.

### Step 5: Don't let "enterprise" become "over-engineered"

A recurring failure mode at the opposite extreme from sloppiness is architecture astronautics — introducing a message bus, a microservice, a generic plugin framework, or a distributed cache for a problem that a single well-structured module and a database index would solve better and more cheaply. When applying these principles, always check: does this system's actual current scale, team size, and change-rate justify this complexity? State the justification, don't just apply the pattern because it's "best practice" in the abstract. Simplicity that meets the actual requirement is itself a core enterprise architecture principle, not a shortcut around one.

## Reference file index

| File | Covers |
|---|---|
| `software-architecture-styles.md` | Monolith, modular monolith, microservices, SOA, event-driven, serverless; layered/hexagonal/clean/onion architecture; when to choose which |
| `microservices-patterns.md` | Service decomposition via DDD bounded contexts, API gateway, service discovery, sync/async communication, saga pattern, event sourcing, CQRS, strangler fig migration, data-per-service |
| `database-architecture.md` | Relational design/normalization, NoSQL data models and fit, sharding/partitioning, replication, CAP/PACELC tradeoffs, indexing, transactions, polyglot persistence, migrations |
| `coding-principles.md` | SOLID, DRY/KISS/YAGNI, design patterns (creational/structural/behavioral) and when they're overkill, clean code practices, code review standards |
| `resilience-reliability-patterns.md` | Circuit breaker, retry with backoff/jitter, bulkhead, timeouts, rate limiting, graceful degradation, idempotency, disaster recovery (RTO/RPO), chaos engineering |
| `performance-scalability.md` | Caching strategies, load balancing algorithms, async/queue processing, horizontal vs. vertical scaling, query optimization, connection pooling, the N+1 problem |
| `api-integration-design.md` | REST/GraphQL/gRPC design standards, versioning, contract-first design, pub/sub and event streaming, ESB vs. point-to-point, idempotency keys |
| `observability-operations.md` | Logging/metrics/tracing (three pillars), SLIs/SLOs/SLAs, health checks, alerting, capacity planning |
| `enterprise-governance-standards.md` | Architecture Decision Records, non-functional requirements, technical debt tracking, documentation standards, definition of done |
