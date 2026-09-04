# Runbooks & Production-Readiness Review

## Runbooks
A runbook is what lets a tired on-call engineer who didn't write the code recover it at
3 a.m. Write one per service *before* launch, keep it version-controlled next to the code,
and link it from alerts.

A good runbook contains:
- **What the service does** and its critical dependencies (and what happens if each is
  down).
- **Key dashboards** (links) and what healthy looks like.
- **Common failure modes** and the specific steps to diagnose and fix each.
- **How to deploy and roll back** (link to `release-deployment-safety` procedures).
- **Kill switches / feature flags** available and what they do.
- **Escalation contacts** and dependencies' on-call.
- **Break-glass** access procedures.

Keep runbooks executable and current — a stale runbook that lies is worse than none. Prefer
copy-pasteable commands over prose. Where possible, automate the runbook step (a script or
a one-click action) rather than documenting a manual sequence.

## Production-Readiness Review (PRR)
A checklist gate a service passes *before* it takes production traffic. Don't launch what
nobody can operate. Sample PRR checklist:

**Reliability & scale**
- [ ] SLIs/SLOs defined; error-budget policy agreed
- [ ] Capacity planned for expected + peak load; load tested to target (see
      `comprehensive-test-strategy` if present)
- [ ] Autoscaling / limits configured; known bottlenecks documented
- [ ] Graceful degradation for non-critical dependency failures

**Observability**
- [ ] Four golden signals instrumented; service dashboard exists
- [ ] Alerts defined (symptom-based, burn-rate), each linked to a runbook
- [ ] Structured logging with correlation IDs; tracing enabled

**Operability**
- [ ] Runbook written and reviewed
- [ ] Deploy + rollback tested (ties to `release-deployment-safety`)
- [ ] Health checks (liveness/readiness) implemented
- [ ] On-call rotation staffed and aware of the service

**Resilience**
- [ ] Failure modes of each dependency understood + handled (timeouts, retries with
      backoff, circuit breakers — see enterprise-architecture-standards resilience)
- [ ] Backups configured; RPO/RTO defined; restore tested
- [ ] No single points of failure for critical paths

**Security & compliance** (delegates to `owasp-secure-coding-bdd` /
`compliance-data-lifecycle` if present)
- [ ] Secrets managed properly; least-privilege access
- [ ] Audit logging for sensitive actions
- [ ] Data handling meets retention/privacy requirements

## Capacity planning & toil
- Plan capacity from measured per-unit cost (e.g. requests/sec per instance) × expected
  demand + headroom; revisit as traffic grows. Don't guess.
- Track **toil** (manual, repetitive, automatable operational work) and drive it down;
  toil that grows with traffic is a scaling blocker. Automate the top sources first.

## Launch is not the end
Re-review readiness after major changes and periodically. A service that was ready a year
ago may have drifted (new dependencies, higher load, stale runbook).
