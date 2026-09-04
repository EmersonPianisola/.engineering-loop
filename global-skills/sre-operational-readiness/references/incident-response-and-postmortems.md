# Incident Response & Blameless Postmortems

Have this in place *before* the first incident. Improvising the process during an outage is
how small problems become big ones.

## Severity levels (define yours; example)
- **SEV1** — critical: major outage / data loss / security breach affecting many users.
  All-hands, immediate, 24/7 response, exec + status-page comms.
- **SEV2** — significant: important functionality degraded for many users, or a workaround
  exists. Urgent response during and outside hours.
- **SEV3** — minor: limited impact, small user subset, or cosmetic-but-notable. Handle in
  business hours.
Define response-time expectations and who gets notified per level, in advance.

## Incident roles (don't let one person do everything)
- **Incident Commander (IC)** — owns coordination and decisions; does NOT do hands-on
  debugging. Keeps the response organized, assigns tasks, decides on mitigations.
- **Operations/Subject experts** — the people actually investigating and fixing.
- **Communications Lead** — updates stakeholders, status page, and internal channels on a
  cadence so the IC and ops can focus.
- **Scribe** — records the timeline as it happens (feeds the postmortem).
For small incidents one person may wear multiple hats, but name the IC explicitly.

## During the incident: mitigate first, diagnose later
1. **Declare** the incident and severity; open a dedicated channel/bridge.
2. **Mitigate** to restore service ASAP — roll back, flip the kill-switch flag, fail over,
   shed load. Restoring users comes *before* understanding root cause. (Ties directly to
   `release-deployment-safety` rollback mechanisms.)
3. **Communicate** on a regular cadence, even if the update is "still investigating."
4. **Escalate** if the current responders can't make progress — early, not as a last
   resort.
5. **Stand down** when service is restored and stable; schedule the postmortem.

## Blameless postmortems (for every SEV1/2, and by request for others)
Write within a few days while memory is fresh. Structure:
- **Summary** — what happened, in plain language.
- **Impact** — who/what was affected, for how long, quantified (users, revenue, SLO/budget
  burned).
- **Timeline** — detection → response → mitigation → resolution, with timestamps.
- **Root cause(s) & contributing factors** — usually multiple; go past "human error" to
  *why the system allowed* the error to cause an outage (missing guardrail, no canary, no
  alert, confusing UI).
- **What went well / what didn't / where we got lucky.**
- **Action items** — concrete, owned, dated, and tracked to completion. Prefer systemic
  fixes (add a guardrail, an alert, a test) over "be more careful."

## Blameless means blameless
- Assume everyone acted reasonably with the information they had. The goal is to fix the
  *system*, not to assign fault. Blame drives hiding of information, which destroys
  learning and makes the next incident worse.
- "Human error" is a starting point for investigation, never a root cause. Ask what let a
  normal human mistake turn into an outage.

## Close the loop
- Track postmortem action items like any other work, with owners and due dates. Untracked
  action items mean the same incident recurs.
- Periodically review past postmortems for patterns (the same class of failure repeating is
  a signal to invest structurally).

## BDD-adjacent: turn incidents into regression tests
Every incident with a code/logic cause should produce a test (often a
`bdd-comprehensive-testing` non-happy-path scenario, or a `@reliability` scenario) so the
exact failure can never silently return.
