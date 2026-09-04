# Chaos Engineering & Resilience Testing

Resilience you haven't tested is resilience you don't have. Chaos engineering is the
practice of deliberately injecting failure to verify the system withstands it — turning
"we think it's resilient" into evidence.

## The principles (Principles of Chaos)
1. **Form a hypothesis** about steady-state behavior (a measurable "healthy" — e.g.
   "checkout success rate stays > 99%").
2. **Vary real-world events**: kill an instance, add network latency, drop a dependency,
   exhaust CPU/memory/disk, introduce clock skew, fail a zone.
3. **Run in production-like conditions** (ideally production, carefully) — staging doesn't
   have real traffic patterns. Start in staging to build confidence.
4. **Minimize blast radius**: start tiny (one instance, a small % of traffic), have an abort
   switch, and expand only as confidence grows.
5. **Automate and run continuously** once trusted, so regressions in resilience are caught.

## What to inject (and what it validates)
- **Instance/pod kill** → validates redundancy, auto-restart, load rebalancing.
- **Network latency / packet loss** → validates timeouts and retry/backoff (see enterprise
  resilience patterns).
- **Dependency outage** (block a downstream) → validates circuit breakers, fallbacks, and
  graceful degradation.
- **Resource exhaustion** (CPU/mem/disk) → validates limits, autoscaling, backpressure.
- **Zone/region failure** → validates failover and multi-AZ/region design.
- **Clock skew / expired certs** → validates time-sensitive and TLS handling.

## Verifying graceful degradation
The goal isn't "nothing breaks" — it's "the *right* things degrade." When recommendations
are down, the product page should still load without recommendations. When a non-critical
write queue backs up, core reads should still serve. Define which features are essential vs.
sheddable *before* the experiment.

## Game days
Scheduled, facilitated exercises where the team injects a realistic failure and practices
the incident response (ties to `sre-operational-readiness`). They validate not just the
system but the runbooks, alerts, and on-call muscle memory. Run them regularly.

## Tooling
Chaos Mesh / LitmusChaos (Kubernetes), AWS Fault Injection Simulator, Gremlin, Toxiproxy
(network faults), or simple scripted instance termination. Start with the simplest thing
that tests your top risk.

## Guardrails
- Always have a documented **abort/rollback** for the experiment.
- Notify on-call; don't surprise the humans (except deliberately, in a game day).
- Never run a destructive data experiment without the backups/confirmation from
  `release-deployment-safety` and the lockout check in `owasp-secure-coding-bdd`.

## BDD-testable resilience properties (also runnable as automated fault-injection tests)
```gherkin
  @reliability
  Scenario: Circuit breaker opens when a dependency is failing
    Given the payment provider is returning errors
    When the failure rate exceeds the circuit-breaker threshold
    Then the breaker opens and requests fail fast with a fallback instead of hanging

  @reliability
  Scenario: Service recovers automatically after an instance is killed
    Given three instances are serving traffic
    When one instance is terminated
    Then traffic is rebalanced to the remaining instances with no failed user requests
    And a replacement instance is started automatically
```
