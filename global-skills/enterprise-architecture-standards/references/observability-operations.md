# Observability & Operations

Covers: Logging/metrics/tracing (the three pillars), SLIs/SLOs/SLAs, health checks, alerting, capacity planning.

## The three pillars of observability

### Logging
- Log structured data (JSON or a consistent key-value format), not free-text strings — structured logs are queryable/aggregable in a log platform, free text requires fragile regex parsing later.
- Include correlation/trace IDs in every log line for a given request so logs from every service touched by that request can be tied together (essential in a microservices/distributed system — without this, debugging a cross-service issue means manually correlating timestamps across systems).
- Log at the right level (error/warn/info/debug) consistently across the codebase — a system where "info" sometimes means "routine" and sometimes means "something's wrong" makes alerting on log level meaningless.
- Follow the sensitive-data logging rules from `owasp-secure-coding-bdd`'s logging reference — never log secrets, full credentials, or unmasked PII.

### Metrics
- Track the **RED** method for services (Rate, Errors, Duration) and the **USE** method for resources (Utilization, Saturation, Errors) as baseline coverage for any new service — these give a fast, standard answer to "is this healthy" without needing custom dashboards designed from scratch for every service.
- Emit business-relevant metrics too, not just infrastructure metrics — "orders placed per minute" catches problems (a broken checkout flow) that CPU/memory graphs won't show at all.
- Use histograms/percentiles (p50, p95, p99) for latency, not just averages — an average can look healthy while a meaningful fraction of users have a bad, slow experience; p99 is what your worst-affected users actually feel.

### Tracing
- Propagate a trace ID across every service boundary a request crosses (via standard mechanisms like W3C Trace Context, OpenTelemetry) so a distributed request's full path, including time spent in each service, is reconstructable — this is the single highest-leverage observability investment for a microservices architecture, since without it, diagnosing "why is this request slow" across 6 services is close to guesswork.
- Instrument at service boundaries at minimum (incoming request, outgoing calls to other services/databases); deeper instrumentation of business logic internals is valuable but secondary to having boundary-level tracing working reliably first.

## SLIs, SLOs, and SLAs
- **SLI (Service Level Indicator)** — a specific, measured metric (e.g., "% of requests completing under 300ms," "% of requests returning a non-5xx status").
- **SLO (Service Level Objective)** — an internal target for that SLI (e.g., "99.9% of requests succeed over a rolling 30 days") — this is what the team designs and operates toward.
- **SLA (Service Level Agreement)** — an external, often contractual commitment (usually looser than the internal SLO, to leave margin) with consequences for breach.
- Define SLOs before building the system where possible — they drive real architecture decisions (how much redundancy, what resilience patterns from `resilience-reliability-patterns.md` are actually justified) rather than being written retroactively to match whatever the system happens to already do.
- Track error budgets (the allowed failure rate under the SLO) as an actual operational tool — when the error budget for a period is exhausted, that's a signal to prioritize reliability work over new features, not just a retrospective number.

## Health checks
- Distinguish **liveness** (is the process running/responsive at all — used to decide whether to restart an instance) from **readiness** (is the instance currently able to serve traffic correctly, including its dependencies — used to decide whether to route traffic to it). Conflating the two causes real incidents: an instance with a failing database connection is "alive" (the process runs fine) but not "ready" (it can't actually serve most requests) — a liveness-only check would keep sending it traffic it can't handle.
- A readiness check should verify the dependencies the service actually needs to function (can it reach its database, its critical downstream services), not just return a static 200 — a health check that always returns healthy regardless of actual dependency state provides false confidence and delays incident detection.

## Alerting
- Alert on symptoms that indicate actual user/business impact (elevated error rate, latency breaching SLO, a critical queue backing up) rather than every possible internal metric fluctuation — alert fatigue from too many low-signal alerts is what causes real incidents to be missed or ignored.
- Every alert should be actionable — if firing the alert doesn't lead to a clear next step, either fix the underlying issue it's flagging or remove the alert; a non-actionable alert just trains people to ignore alerts generally.
- Tie alerts to the SLOs defined above where possible (alert when the error budget burn rate suggests the SLO will be breached, not just on any error) rather than arbitrary static thresholds picked without a real basis.

## Capacity planning
- Base capacity planning on actual measured growth trends and known upcoming events (a marketing campaign, a seasonal peak), not guesswork — track resource utilization trends over time as a routine practice, not just when something's already close to a limit.
- Load test against realistic traffic patterns and realistic data volumes (not a clean synthetic dataset far smaller than production) before a known high-traffic event, and validate the specific bottlenecks found (database connection limits, third-party API rate limits, autoscaling reaction time) rather than assuming "it scaled in the load test" covers every real dependency.
- Plan for graceful scaling behavior (autoscaling triggers with headroom, not scaling only after saturation is already causing user-facing errors) — autoscaling that reacts after the fact is a mitigation, not a substitute for capacity planning ahead of known load.

## BDD / operational scenario patterns

```gherkin
Scenario: Readiness check fails when the database is unreachable
  Given the service's database connection is down
  When the readiness endpoint is checked
  Then it returns unhealthy
  And the load balancer stops routing traffic to this instance

Scenario: Trace ID propagates across a multi-service request
  Given a request enters through the API gateway
  When it is processed by three downstream services
  Then all resulting log entries and spans share the same trace ID

Scenario: Alert fires when error rate breaches the SLO burn rate threshold
  Given the SLO allows a 0.1% error rate over 30 days
  When the current error rate would exhaust the error budget within 24 hours at the current burn rate
  Then an alert is triggered
```
