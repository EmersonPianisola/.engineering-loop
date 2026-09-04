---
name: release-deployment-safety
description: 'Use whenever code will be deployed, released, rolled out, or migrated — new services, new versions, schema/data migrations, config or feature changes, or any change to how software reaches production. Enforces how elite engineering teams ship at scale WITHOUT outages: zero-downtime deploys, progressive delivery (canary/blue-green/rolling), feature flags, instant rollback, and backward-compatible database migrations (expand/contract). Trigger proactively on "deploy," "release," "ship," "roll out," "migration," "cutover," "hotfix," "rollback," "feature flag," "blue-green," "canary," or any change that alters what runs in production — even without those words. Pairs with bdd-comprehensive-testing (tests gate the release) and enterprise-architecture-standards (system shape).'
---

# Release & Deployment Safety

## Why this exists

Most production outages are not caused by bad code — they're caused by *how* good code was shipped: a migration that locked a table, a deploy with no rollback path, a change that assumed old and new versions would never run at the same time. The difference between a hobby project and infrastructure that scales is not the architecture, it's that every change can be released gradually, observed, and undone in seconds. This skill makes safe release the default, so "it works" becomes "it ships without anyone noticing the seam."

This skill is about the *delivery* half of CI/CD. The `bdd-comprehensive-testing` skill wires tests into the pipeline (continuous integration); this skill governs what happens after the tests pass (continuous delivery/deployment). Use them together.

## The core principle

**Every change must be independently deployable, backward-compatible, observable while rolling out, and reversible within minutes.** If any of those four is missing, the change is not ready to ship — regardless of whether the code is correct. Treat a deploy without a rollback plan the same way you'd treat code without tests.

## The workflow

### Step 1: Classify the change and pick a rollout strategy

Identify what kind of change this is — it determines the safe path:

- **Stateless app/service code change** → rolling or canary deploy behind a load balancer.
- **Risky or user-visible behavior change** → feature flag (dark launch), then progressive rollout.
- **Database schema change** → expand/contract migration (never a breaking change in one step). See `references/zero-downtime-db-migrations.md`.
- **Data backfill / large data migration** → batched, resumable, throttled background job. Same reference.
- **Config or infrastructure change** → treat as a deploy: version it, roll it out gradually, be able to revert.
- **Breaking API change** → version the API and run old + new in parallel; never break existing clients. (See enterprise-architecture-standards `api-integration-design.md`.)

Read `references/deployment-strategies.md` for how to choose and configure blue-green vs. canary vs. rolling.

### Step 2: Guarantee backward compatibility (the rule that makes zero-downtime possible)

During any rollout, **two versions of your code run simultaneously** (old instances not yet replaced, new instances already live). Everything must work in that mixed state:

- New code must read data written by old code, and old code must tolerate data written by new code.
- Never deploy a schema change and the code that requires it in the same release — expand first, deploy code, then contract later. See `references/zero-downtime-db-migrations.md`.
- Message queues, caches, and API contracts must be forward- and backward-compatible across one version step.

If a change *cannot* be made backward-compatible, it must be split into a sequence of releases that each are. This is non-negotiable and is the single most common thing teams get wrong.

### Step 3: Put risky changes behind a feature flag

Decouple **deploy** (code is in production, dormant) from **release** (feature is turned on). Read `references/feature-flags.md`. Use flags to:

- Dark-launch: ship code off, turn on for internal users, then 1% → 10% → 100%.
- Kill-switch: turn a misbehaving feature off instantly without a redeploy.
- Targeted rollout: enable per tenant/region/user cohort.

Flags are not free — every flag is a branch in your code and a cleanup obligation. The reference file covers flag hygiene (naming, ownership, expiry, removing dead flags).

### Step 4: Roll out progressively and watch the right signals

Never flip 100% at once for anything non-trivial. Progressive rollout + automated guardrails:

1. Deploy to a canary (1 instance / small % of traffic).
2. Watch the **golden signals** — error rate, latency, saturation, traffic — plus business KPIs, for the canary vs. baseline. (Defined in the `sre-operational-readiness` skill if present.)
3. Auto-promote if healthy; auto-rollback if error budget burns. Only then widen to 10%, 50%, 100%.

Read `references/deployment-strategies.md` for canary analysis criteria and bake times.

### Step 5: Have a rollback path BEFORE you deploy — and make it fast

Read `references/rollback-and-recovery.md`. Before shipping, answer explicitly:

- How do I revert this in under 5 minutes? (Redeploy previous artifact / flip flag / route back to blue.)
- Is the rollback *safe* given any migrations already applied? (Expand/contract makes rollback safe; a destructive migration does not — this is why we contract last.)
- What's the "break glass" procedure if automated rollback fails?

A change with no rollback plan is not ready. If a change is genuinely irreversible (a destructive data migration), that must be called out loudly to the user and gated behind extra confirmation — and it should trigger the lockout/accidental-deletion check in the `owasp-secure-coding-bdd` skill.

### Step 6: Automate the pipeline from commit to production

Read `references/ci-cd-delivery-pipeline.md`. The delivery pipeline should:

- Build **once**, promote the *same immutable artifact* through environments (never rebuild per environment).
- Deploy through environments in order (dev → staging → prod) with gates.
- Run DB migrations as an explicit, ordered, idempotent, reversible pipeline step — not by hand.
- Tag/version every release; keep a deployment record (what shipped, when, by whom, git SHA).
- Prefer GitOps (declarative desired state in git, reconciled automatically) for infra and k8s.

### Step 7: Add release-safety scenarios to the BDD suite

Release safety is testable. Add scenarios (in the same `.feature` files the `bdd-comprehensive-testing` skill maintains) that prove the safety properties hold:

```gherkin
  @release-safety
  Scenario: New and old schema versions coexist during rollout
    Given the "expand" migration has been applied
    And instances running both the previous and new code version are live
    When each version reads and writes a user record
    Then both versions operate correctly with no errors

  @release-safety
  Scenario: Feature can be disabled instantly via kill switch
    Given the "new-checkout" feature flag is enabled
    When the flag is set to off
    Then subsequent requests use the previous checkout path without a redeploy

  @release-safety
  Scenario: Canary rollback triggers on elevated error rate
    Given a canary release is receiving 5% of traffic
    When the canary error rate exceeds the baseline by the configured threshold
    Then the canary is automatically rolled back and traffic returns to the stable version
```

### Step 8: Don't let a deploy become an outage or a lockout

If the release touches permissions, credentials, network rules, or deletes anything, run the lockout/accidental-deletion check from `owasp-secure-coding-bdd` before shipping. A "successful" deploy that cuts off legitimate access is a failed deploy.

## What the big engineering orgs do that this encodes

- Deploy dozens to thousands of times a day *because* each deploy is small, flagged, canaried, and reversible — not despite it.
- Separate deploy from release so a bad feature is a flag flip, not an incident.
- Treat database migrations as the highest-risk operation and always make them backward-compatible.
- Measure deploys with DORA metrics: deployment frequency, lead time for changes, change failure rate, and mean time to restore. Optimizing these four is the operational definition of "elite."

## Reference files

| Topic | File |
|---|---|
| Choosing/configuring blue-green, canary, rolling, progressive delivery, GitOps | `references/deployment-strategies.md` |
| Feature flags: patterns, targeting, kill switches, flag hygiene/cleanup | `references/feature-flags.md` |
| Zero-downtime & reversible DB schema/data migrations (expand/contract) | `references/zero-downtime-db-migrations.md` |
| Rollback strategies, break-glass, safe-vs-unsafe reverts, DORA MTTR | `references/rollback-and-recovery.md` |
| Build-once/promote pipelines, environment gates, GitOps, deployment records | `references/ci-cd-delivery-pipeline.md` |
