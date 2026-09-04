# Feature Flags (Feature Toggles)

## Why
Decouple **deploy** (code is in prod, dormant) from **release** (feature is on). This turns
risky launches into a config change and misbehaving features into an instant kill switch —
no redeploy, no incident.

## Types of flags (know which you're creating)
- **Release flags** — temporary; gate an in-progress feature during rollout. Remove after
  100% rollout.
- **Kill switches / ops flags** — long-lived; turn off expensive or fragile functionality
  under load or incident.
- **Experiment flags** — A/B tests; tied to an analysis, removed when the experiment ends.
- **Permission/entitlement flags** — long-lived; gate features by plan/tenant. These are
  really product config, not release tooling.

## Patterns
- Evaluate flags server-side where possible; never trust a client to enforce a gate that
  matters for security or billing.
- Default to **off / safe** — if the flag service is unreachable, fall back to the old,
  known-good behavior.
- Target by cohort: user ID, tenant, region, % rollout, internal-employee, ring (dogfood →
  beta → GA).
- Keep flag evaluation fast and cached; a flag check must not add latency or a hard
  dependency on an external service in the request path.

## Flag hygiene (this is where teams rot)
- **Every flag has an owner and an expiry date.** A release flag that outlives its rollout
  is tech debt and a latent bug (two code paths, one untested).
- Name flags consistently: `team.feature-name.purpose` (e.g. `checkout.new-tax-calc.release`).
- Track flags in a registry (the flag platform or a checked-in file) with status:
  active / rolling-out / cleanup-pending.
- **Removing a flag is part of finishing the feature.** After 100% rollout, delete the flag
  and the dead code path in the same PR. Schedule a periodic flag-cleanup sweep.
- Cap the number of concurrent flags on any single flow — combinatorial flag interactions
  are a real source of bugs.

## Tooling
LaunchDarkly, Unleash (open source), Flagsmith, Split, or a simple config-backed
implementation for small projects. Whatever you use, flags must be auditable (who changed
what, when) — a flag flip is a production change.

## BDD scenario patterns
```gherkin
  @release-safety
  Scenario: Flag defaults to safe state when the flag service is unavailable
    Given the feature flag service cannot be reached
    When a request evaluates the "new-pricing" flag
    Then the flag resolves to off and the previous pricing path is used

  @release-safety
  Scenario: Kill switch disables a feature without redeploy
    Given "bulk-export" is enabled and running
    When an operator flips the "bulk-export" kill switch off
    Then new bulk-export requests are rejected gracefully and existing behavior is unaffected
```
