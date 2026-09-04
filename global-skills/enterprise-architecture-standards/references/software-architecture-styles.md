# Software Architecture Styles

Covers: Monolith, Modular Monolith, Microservices, SOA, Event-Driven Architecture, Serverless, CQRS, Event Sourcing, Domain-Driven Design (DDD), Space-Based/Pipeline/Microkernel/Cell-based, and Layered/Hexagonal/Clean/Onion Architecture — plus a comparative trade-off table, a pattern-selection framework (Conway's Law, domain complexity, tech ecosystem), and guidance on hybrid architectures.

## Choosing a system-level style

Pick based on actual team size, deployment cadence needs, and domain complexity — not on what's fashionable. Ask:
- How many teams need to deploy independently, and how often?
- How coupled/decoupled are the domain boundaries really (can you cleanly draw a line, or is everything one tangled transaction)?
- What's the operational maturity of the team (CI/CD, observability, on-call practices)? Distributed systems demand more of this, not less.
- What's the actual current scale (requests/sec, data volume, team headcount)? Design for 3-5x current scale, not for a hypothetical hyperscale future that may never arrive.

### Monolith (single deployable unit)
- Right default for: new products, small-to-medium teams (roughly under ~15-20 engineers on one codebase), unclear domain boundaries, early-stage products where requirements are still shifting fast.
- Strength: simplest to develop, test, deploy, and debug — one transaction can span the whole domain, no network calls between components, one deployment pipeline.
- Failure mode to avoid: a "big ball of mud" with no internal structure — a monolith still needs clean internal module boundaries (see modular monolith below); "monolith" describes the deployment unit, not an excuse for tangled code.

### Modular monolith
- A single deployable unit with strict internal module boundaries (enforced via package/namespace structure, internal APIs, and build-time boundary checks, e.g. ArchUnit/dependency-cruiser) that mirror what would be service boundaries if split later.
- Right default for most teams that think they need microservices but don't yet have the operational scale or team-count to justify the distributed-systems tax. Gives most of the maintainability benefit of clear boundaries without the network/deployment/data-consistency complexity of actual service splits.
- This is frequently the *correct* enterprise architecture choice, not a stepping-stone compromise — don't treat it as something to graduate away from unless a concrete driver (independent team deployment cadence, wildly different scaling needs per module, need for polyglot tech per component) actually shows up.

### Microservices
- Justify with a concrete driver, not by default: independent deployability needed by multiple autonomous teams, genuinely different scaling profiles per component (one part needs 100x the throughput of another), or a regulatory/organizational need for strict isolation.
- Decompose along Domain-Driven Design bounded contexts (see `microservices-patterns.md`), not by technical layer (never "a service for the database layer" — that's a distributed monolith with extra latency, not microservices).
- Each service owns its own data store; no service reaches directly into another's database (see database-per-service in `microservices-patterns.md`).
- Cost to budget for honestly: distributed transactions/eventual consistency complexity, network failure modes, service discovery, per-service observability, and a real increase in operational overhead (each service needs its own CI/CD, monitoring, on-call runbook).

### SOA (Service-Oriented Architecture)
- A predecessor pattern to microservices, typically centered on a shared Enterprise Service Bus (ESB) for integration. Still seen in large enterprises with legacy systems and heavy governance requirements.
- If you're integrating with an existing SOA/ESB environment, follow its existing contract and governance conventions rather than introducing an incompatible microservices-native pattern alongside it without a migration plan.

### Event-Driven Architecture
- Fits domains where actions naturally produce facts that multiple independent consumers care about (order placed → inventory, billing, notifications, analytics all react independently) rather than a single request needing an immediate synchronous response.
- Decouples producers from consumers in time and identity — a producer doesn't need to know who's listening. This is a major strength for extensibility (new consumers can be added without changing the producer) and a major source of debugging difficulty if overused (a synchronous request/response interaction forced through async events becomes hard to trace and reason about).
- Use for genuinely asynchronous, fan-out, or eventually-consistent workflows; don't use it to route a simple synchronous "give me this data now" request through a message broker just because "events are the modern way."

### Serverless (FaaS)
- Strong fit for: unpredictable/spiky traffic, event-driven glue code, low-maintenance-overhead requirements, and workloads that are naturally short-lived and stateless.
- Weak fit for: long-running processes, workloads with strict low-latency requirements sensitive to cold starts, and highly stateful logic that fights the platform's execution model.
- Watch vendor lock-in and cost-at-scale tradeoffs explicitly — serverless pricing that's cheap at low volume can become expensive at sustained high volume compared to provisioned infrastructure; do the math for the actual expected load rather than assuming "serverless = cheap" universally.

### CQRS (Command Query Responsibility Segregation)
- Separates the **write model** (commands that change state) from the **read model**
  (queries), so each can be modeled, scaled, and stored optimally. At its simplest this is
  just separate read/write models against the same database; at its fullest it's separate
  data stores (e.g. a normalized write store + denormalized read store/projection kept in
  sync asynchronously).
- Justify with a concrete driver: a large read/write ratio imbalance, complex read models
  that fight the write schema, or collaborative domains with contention. Don't apply it
  uniformly — for ordinary CRUD it's needless complexity.
- Cost to budget for: **eventual consistency** between write and read sides, plus the
  synchronization machinery. Frequently paired with Event Sourcing and event-driven
  architecture, but does not require them.

### Event Sourcing
- Persist state as an **append-only log of events** (facts that happened) rather than
  storing only current state; current state is derived by replaying events. Gives a
  complete audit trail, temporal queries ("what did this look like last Tuesday"), and
  natural fit with event-driven systems and CQRS read projections.
- Strong fit for domains needing auditability, complex temporal logic, or where the history
  itself is valuable (finance, ledgers, order lifecycles).
- Real costs: schema/versioning of events over time, rebuilding projections, eventual
  consistency, and a steeper mental model. Don't adopt it just for CRUD — it's a
  significant commitment. When used, the event log becomes the source of truth and must be
  treated with corresponding care (immutability, retention, replayability).

### Domain-Driven Design (DDD) — a design approach that drives the choices above
- Not itself a deployment topology, but the discipline that tells you *where the boundaries
  are*. It shapes whether you pick a modular monolith or microservices and where to draw
  the seams.
- Key concepts to apply: **bounded contexts** (explicit boundaries within which a model is
  consistent), **ubiquitous language** (developers and domain experts share one vocabulary
  reflected in the code), **aggregates** (consistency boundaries for writes), **domain
  events**, and **context mapping** (how bounded contexts relate/integrate).
- Use it for complex domains with rich, evolving business rules; it's overkill for simple
  CRUD/technical utilities. When splitting a system, **microservice boundaries should
  follow bounded contexts** (see `microservices-patterns.md`) — never split by technical
  layer.

### Other styles worth knowing (apply where the shoe fits)
- **Space-Based Architecture** — keeps data in a replicated in-memory data grid to remove
  the database as the bottleneck; fits extreme, spiky, high-concurrency workloads where a
  central DB can't keep up. High complexity; niche.
- **Pipeline / Pipes-and-Filters** — data flows through a sequence of independent
  processing stages; natural for ETL, stream processing, and data pipelines.
- **Microkernel / Plugin** — a minimal core plus plugins that add features; fits products
  with a stable core and extensible feature set (IDEs, platforms with third-party
  extensions).
- **Cell-based architecture** — partition the system into independent, isolated "cells"
  each serving a slice of traffic/tenants, to bound blast radius and scale horizontally;
  used by large SaaS providers for fault isolation at scale.

## Comparing the system-level styles (trade-offs at a glance)

| Style | Scalability | Flexibility | Operational complexity | Deployment | Best fit |
|---|---|---|---|---|---|
| Monolith | Moderate (scale the whole unit) | Low–moderate | Low | Single unit | New products, small teams, unclear boundaries |
| Modular monolith | Moderate | Moderate–high | Low–moderate | Single unit | Most teams wanting clean boundaries without the distributed tax |
| Microservices | High (per service) | High | High | Independent services | Many autonomous teams; genuinely different per-component scaling |
| SOA (ESB) | Moderate | Moderate | Moderate–high | Service-based | Legacy-heavy enterprises with shared services + governance |
| Event-driven | High | High | High | Varies | Async fan-out, real-time reactions, decoupled consumers |
| Serverless (FaaS) | High (auto) | Moderate | Low–moderate (ops) | Functions | Spiky/unpredictable load, event glue, low ops overhead |
| CQRS | High (reads) | Moderate | High | Separate read/write | High read/write imbalance, complex read models |
| Hexagonal (internal) | n/a (internal) | High | Moderate | n/a | Isolating core logic from infra; applies within any of the above |

Note the columns interact: microservices and event-driven buy scalability/flexibility with
a real, ongoing operational-complexity bill that a monolith or serverless approach doesn't
incur. There is no free lunch — no style optimizes every column at once.

## Selecting a pattern (the decision framework)

Don't pick by fashion. Work through these deliberately (this expands the questions at the
top of the file):

1. **Requirements & quality attributes** — which non-functionals dominate (scale,
   latency, auditability, time-to-market, regulatory isolation)? No architecture maximizes
   all of them; decide what you're optimizing for and what you'll trade.
2. **Domain complexity** — simple/stable domain → layered monolith is fine. Complex/evolving
   rules → DDD, likely modular monolith or microservices. Data-heavy read/write imbalance →
   consider CQRS. Integration-heavy → event-driven or SOA.
3. **Organizational structure (Conway's Law)** — systems mirror the communication structure
   of the teams that build them. Many autonomous teams map well to microservices; a single
   small team is usually better served by a (modular) monolith than by paying the
   distributed-systems tax. Design the team topology and the architecture together.
4. **Technology ecosystem** — existing investments and skills constrain feasible choices.
   Cloud-native/greenfield favors microservices+containers or serverless; legacy
   integration favors SOA or hexagonal adapters; real-time needs favor event-driven.
5. **Growth & change** — will you need 10x/100x scale? How often do requirements churn?
   How volatile is the regulatory landscape? Choose a style that can evolve without a
   rewrite, and prefer reversible decisions early.
6. **Implement incrementally** — validate the choice on a small scope first; use the
   **Strangler Fig** pattern to migrate legacy gradually (see `microservices-patterns.md`);
   continuously re-evaluate whether the architecture is still delivering the expected
   benefit.

## Hybrid architectures are the norm, not a compromise

Real enterprise systems rarely follow one pattern dogmatically — the most successful ones
deliberately **combine** patterns to fit each part's needs. A common shape: microservices
overall, with a modular-monolith or layered structure *inside* each service, event-driven
integration *between* services, CQRS+event sourcing *within* the few services that need it,
and hexagonal organization everywhere. Treat "which pattern" as a per-boundary decision
guided by the framework above, not a single system-wide religion. Guided by principles
rather than dogma is what yields the best results.

## Evolutionary architecture (keep the choice honest over time)
- Architecture is not decided once. Use **architecture fitness functions** — automated
  checks that guard important properties (e.g. build-time dependency/boundary rules via
  ArchUnit/dependency-cruiser, latency budgets, coupling metrics) — so the system doesn't
  silently drift away from its intended design as it grows.
- Record significant decisions as **ADRs** (see `enterprise-governance-standards.md`) so the
  *why* behind the chosen style survives team turnover and can be revisited deliberately.

## Internal code organization patterns (apply within any of the above)

### Layered architecture
- Classic separation: presentation → business logic → data access. Simple, well understood, but can leak database concerns into business logic if layers aren't enforced (e.g., business logic depending directly on ORM entities rather than domain models).

### Hexagonal (Ports & Adapters) / Clean Architecture / Onion Architecture
- Core idea shared by all three: business logic sits at the center, has zero dependency on frameworks, databases, or delivery mechanisms (HTTP, message queues); those are "adapters" plugged in through interfaces ("ports") the core defines.
- Benefit: the domain logic is testable without a database or web server, and swapping infrastructure (a new database, a new message broker, a new API framework) doesn't touch business logic.
- Apply this even inside a "simple" monolith or a single microservice — it's an internal code-organization principle independent of the deployment topology chosen above, and is one of the more consistently high-value patterns to apply regardless of scale.
- Anti-pattern to avoid: adding ports/adapters ceremony (interfaces with exactly one implementation, forever) for genuinely simple CRUD modules with no real infrastructure-swapping need — apply this rigor where the domain logic is actually non-trivial, not uniformly on every file.

## Migrating between styles
- Moving a monolith toward microservices (or the reverse, consolidating an overgrown microservice landscape back toward a modular monolith) is itself a major architectural decision — see the Strangler Fig pattern in `microservices-patterns.md` for how to do this incrementally rather than a risky big-bang rewrite.
