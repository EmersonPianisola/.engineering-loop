# Alerting & On-Call

The goal: **page a human only when a human must act now.** Every unnecessary page erodes
trust in alerting and burns out the on-call. Alerting quality is itself a reliability
property.

## Alert on symptoms, not causes
- Good: "checkout success rate is below SLO" / "p99 latency > 2s for 5 min" / "error-budget
  fast-burn." These mean users are hurting.
- Bad (as pages): "CPU > 80%", "disk 70% full", "pod restarted." These are *causes* that
  may or may not affect users. Route them to dashboards/tickets, or alert only when they
  actually threaten a symptom (e.g. "disk will be full in 4 hours at current rate").
- Rule of thumb: if the alert fires and users are fine, it shouldn't have paged.

## Error-budget burn-rate alerting (the modern default)
Alert on how fast you're spending the error budget, using multi-window multi-burn-rate:
- **Fast burn** (e.g. 14.4x over 1h, confirmed over 5m) → page immediately; a large chunk
  of the monthly budget is vanishing.
- **Slow burn** (e.g. 3x over 6h) → ticket, not a page; investigate during business hours.
This catches both sudden outages and slow degradations without noise.

## Every alert must be actionable
- Links to a **runbook** describing what to check and do.
- Has a clear owner (which team/service).
- Has a severity and expected response.
- If there's nothing a human can do about it right now, it's not a page.

## Alert hygiene
- Review alerts regularly; delete or downgrade ones that are noisy or never actionable.
- Track **alert volume per on-call shift**; sustained high volume is a bug to fix, not a
  badge of honor.
- Avoid duplicate alerts for the same root cause (dedupe/group). One incident, one page.
- Set sane thresholds with a duration ("for 5 minutes") to avoid flapping.

## On-call practices (sustainable, not heroic)
- A rotation with enough people that no one is perpetually on call (a common floor is 6–8
  so shifts are ~1 week every 6–8 weeks).
- Clear **escalation policy**: if primary doesn't ack in N minutes → secondary → manager.
- **Handoff**: each shift ends with a short handoff of ongoing issues.
- **Toil budget**: track time spent on repetitive manual work; cap it (Google's guideline
  is <50% of SRE time on toil) and automate the top offenders.
- Compensate/recognize on-call; it's real work and burnout is a reliability risk.

## Tooling
PagerDuty, Opsgenie, Grafana OnCall, or similar for routing/escalation. Alertmanager /
cloud-native for alert rules. Whatever you use, alerts and pages should be auditable.

## BDD-testable alerting property
```gherkin
  @reliability
  Scenario: Fast error-budget burn triggers a page
    Given the checkout SLO is 99.9% over 30 days
    When the error rate sustains a 14.4x burn rate for 5 minutes
    Then a high-severity page is sent to the on-call with a link to the checkout runbook
```
