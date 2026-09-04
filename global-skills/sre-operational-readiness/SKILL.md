---
name: sre-operational-readiness
description: 'Use whenever building, launching, or operating a service that runs in production — new services, endpoints, or any system that must stay up and be debuggable. Applies Google-style Site Reliability Engineering: define SLIs/SLOs and error budgets, instrument the four golden signals, write symptom-based alerts that don''t page on noise, and prepare incident response, blameless postmortems, runbooks, and a production-readiness review BEFORE launch. Trigger proactively on "SLO," "SLA," "uptime," "reliability," "monitoring," "alerting," "on-call," "incident," "postmortem," "runbook," "observability," "metrics," "dashboards," "goes down," "how do we know if it breaks," or any production launch — even without those words. Pairs with enterprise-architecture-standards (observability), release-deployment-safety (canary signals), and bdd-comprehensive-testing.'
---

# SRE & Operational Readiness

## Why this exists

Software that "works" and software that "runs reliably at scale" are different disciplines. The gap is operational: knowing your service is healthy from the *user's* perspective, being paged only when it matters, resolving incidents fast, and learning from failure without blame. Elite orgs (Google SRE, and the teams that copied them) treat reliability as a measured, budgeted engineering property — not a hope. This skill makes a service *operable* before it's launched, not after the first 2 a.m. page.

It complements the `enterprise-architecture-standards` observability reference (which covers instrumentation mechanics) by adding the SRE *practices* around it: what to measure, when to page, how to respond, and how to learn.

## The core principle

**100% reliability is the wrong target.** The right target is an explicit SLO (e.g. 99.9%) with an **error budget** — the allowed amount of unreliability. That budget turns reliability into a shared, quantitative decision: if you're within budget, ship features fast; if you've burned it, freeze features and fix reliability. Everything below serves this loop: measure user-facing health → alert on it → respond → learn → adjust.

## The workflow

### Step 1: Define SLIs and SLOs before launch

Read `references/slis-slos-error-budgets.md`. For each user-facing service:

- Pick **SLIs** (Service Level Indicators) that reflect *user experience*: availability
  (successful requests / total), latency (% of requests under N ms), correctness,
  freshness. Measure at the point closest to the user.
- Set **SLOs** (targets) that are realistic and tied to user needs, not vanity 99.999%.
- Derive the **error budget** (100% − SLO) and the policy for what happens when it's spent.
- Distinguish SLO (internal target) from **SLA** (external contractual promise, always
  looser than the SLO).

### Step 2: Instrument the four golden signals

Read `references/observability-golden-signals.md`. Every service emits, at minimum:

- **Latency** (split success vs. error latency; track p50/p95/p99, not just averages)
- **Traffic** (requests/sec, throughput)
- **Errors** (rate and type)
- **Saturation** (how full the system is — CPU, memory, queue depth, connection pools)

Plus the three pillars: **metrics** (aggregate health), **logs** (structured, correlated —
see `bdd`/`owasp` logging guidance), and **traces** (request flow across services). Add
correlation IDs so a single request can be followed end to end.

### Step 3: Alert on symptoms, not causes — and don't page on noise

Read `references/alerting-and-oncall.md`. The discipline:

- Page a human **only** for user-impacting problems that need action *now* (SLO burn,
  hard-down). Everything else is a ticket or a dashboard, not a page.
- Alert on **symptoms** ("checkout error rate > SLO burn rate") not **causes** ("CPU high")
  — CPU can be high and users fine, or CPU fine and users broken.
- Use **error-budget burn-rate alerts** (fast burn = page now; slow burn = ticket).
- Every alert must be **actionable** and link to a runbook. An alert nobody acts on trains
  people to ignore alerts (alert fatigue is a reliability risk in itself).

### Step 4: Prepare incident response before you need it

Read `references/incident-response-and-postmortems.md`. Have, in advance:

- **Severity levels** (SEV1–SEV3/4) with clear definitions and response expectations.
- **Roles**: Incident Commander (coordinates), Communications Lead, Operations/subject
  experts. One person does not do all three.
- **Comms plan**: status page, stakeholder updates cadence, where the team coordinates.
- **Mitigate first, diagnose later** — restore service (roll back, flip flag, failover)
  before root-causing. Ties to `release-deployment-safety` rollback.

### Step 5: Run blameless postmortems for every significant incident

Same reference. After a SEV, write a **blameless postmortem**: timeline, impact, root
cause(s), what went well, what didn't, and concrete action items with owners and due
dates. Blameless = focus on systems and contributing factors, never individual blame —
people act reasonably given the information they had; fix the system that let a mistake
become an outage. Track action items to completion or they're theater.

### Step 6: Write runbooks and pass a production-readiness review

Read `references/runbooks-and-production-readiness.md`. Before launch:

- Write **runbooks** for the service: how to deploy, roll back, common failure modes and
  their fixes, key dashboards, escalation contacts. A runbook is what lets a tired on-call
  engineer who didn't write the code recover it at 3 a.m.
- Pass a **Production Readiness Review (PRR)** checklist: SLOs defined, monitoring +
  alerting in place, runbooks written, rollback tested, capacity planned, dependencies +
  failure modes understood, on-call staffed. Don't launch a service nobody can operate.

### Step 7: Encode operational guarantees as tests where possible

Some reliability properties are testable — add them to the BDD suite (`@reliability` tag)
so they don't silently regress:

```gherkin
  @reliability
  Scenario: Health check reflects dependency failure
    Given the database is unreachable
    When the readiness endpoint is polled
    Then it reports "not ready" so the load balancer stops sending traffic

  @reliability
  Scenario: Requests carry a correlation ID through the call chain
    When a request enters the system without a correlation ID
    Then one is generated and propagated to all downstream service calls and logs

  @reliability
  Scenario: Graceful degradation when a non-critical dependency is down
    Given the recommendations service is unavailable
    When a user loads the product page
    Then the page renders without recommendations rather than failing
```

## What the big engineering orgs do that this encodes

- Reliability is a **budget**, not a goal of perfection — this aligns feature velocity and
  stability instead of pitting them against each other.
- On-call is **sustainable**: alerts are few, actionable, and runbook-linked; toil is
  tracked and automated away.
- Every incident produces a **blameless postmortem** with tracked action items — failure
  becomes organizational learning.
- Nothing launches without a **production-readiness review**. Operability is a launch
  requirement, not a follow-up.

## Reference files

| Topic | File |
|---|---|
| SLIs, SLOs, SLAs, error budgets, burn-rate policy | `references/slis-slos-error-budgets.md` |
| Golden signals, metrics/logs/traces, correlation, dashboards | `references/observability-golden-signals.md` |
| Symptom-based alerting, burn-rate alerts, on-call, alert fatigue | `references/alerting-and-oncall.md` |
| Incident severities, roles, comms, mitigation, blameless postmortems | `references/incident-response-and-postmortems.md` |
| Runbooks, production-readiness review checklist, capacity, toil | `references/runbooks-and-production-readiness.md` |
