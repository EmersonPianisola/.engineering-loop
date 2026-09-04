# Observability: Golden Signals & the Three Pillars

Observability = being able to answer "what's wrong and why" from the outside, *without
shipping new code to find out*. The `enterprise-architecture-standards` skill covers
instrumentation mechanics; this covers what to measure and how to make it useful.

## The four golden signals (Google SRE)
Instrument every user-facing service with at least these:
1. **Latency** — how long requests take. **Split successful vs. failed** latency (a fast
   500 shouldn't look "fast"). Track p50/p95/p99.
2. **Traffic** — demand on the system (requests/sec, transactions/sec, concurrent users).
3. **Errors** — rate of failed requests, by type/status. This is usually your primary SLI.
4. **Saturation** — how "full" the system is (CPU, memory, disk I/O, queue depth,
   connection-pool utilization, thread pools). Saturation predicts *imminent* failure.

(For resource-oriented systems, the **USE** method — Utilization, Saturation, Errors per
resource — complements this. For request-oriented systems, the **RED** method — Rate,
Errors, Duration — is the same idea framed per service.)

## The three pillars
- **Metrics** — cheap, aggregate, always-on numbers for dashboards + alerting (Prometheus,
  Datadog, CloudWatch, OpenTelemetry metrics). Good for "is something wrong?"
- **Logs** — structured (JSON), leveled, and correlated. Never log secrets/PII (see the
  logging guidance in `owasp-secure-coding-bdd`/`bdd-comprehensive-testing`). Good for
  "what exactly happened?"
- **Traces** — follow one request across services with spans and timings (OpenTelemetry,
  Jaeger, Tempo, Zipkin). Good for "where in the call chain is the latency/error?"

## Correlation is what makes it usable
- Propagate a **correlation/trace ID** from the entry point through every downstream call
  and into every log line. Without it, three pillars are three disconnected haystacks.
- Standardize on **OpenTelemetry** for vendor-neutral instrumentation of all three pillars.
- Tag telemetry with consistent dimensions: service, version, environment, region,
  tenant (where safe). This lets you slice by "the version we just deployed."

## Dashboards
- One **service overview** dashboard per service showing the four golden signals + SLO
  attainment + error-budget burn. This is the first thing on-call opens.
- Dashboards should answer questions, not just display everything. Avoid "wall of graphs"
  nobody reads.
- Include a deploy/annotation overlay so you can see "did this get worse right after a
  release?" (ties to `release-deployment-safety` deployment records).

## Health checks
- **Liveness**: is the process alive? (restart if not)
- **Readiness**: can it serve traffic *right now*? (includes critical dependency checks;
  fail readiness → load balancer stops routing to it, no user-facing errors)
- Keep health checks cheap and honest — a readiness check that always returns 200 is
  useless.

## BDD-testable observability properties
```gherkin
  @reliability
  Scenario: Errors are emitted as metrics with a type dimension
    When a request fails with a validation error
    Then an error metric is incremented tagged with error_type "validation" and the service version

  @reliability
  Scenario: Trace context propagates across a service call
    Given a request with trace ID "abc123"
    When service A calls service B
    Then service B's logs and spans reference trace ID "abc123"
```
