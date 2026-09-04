# Safe Data Migrations, Backups & Disaster Recovery

`release-deployment-safety` owns the zero-downtime *mechanics* (expand/contract, batched
backfills). This file adds the **data-integrity, auditability, and recoverability** lens
that compliance and long-term data health require.

## Migrations: the data-integrity lens
Beyond making a migration zero-downtime, make it **provably correct and recoverable**:
- **Backward-compatible** via expand/contract (see release-deployment-safety) so old + new
  code coexist and rollback stays possible.
- **Validate invariants before and after**: row counts match (accounting for intended
  changes), sums/totals preserved, no orphaned foreign keys, no unintended nulls. Automate
  this as a migration self-check, not a manual eyeball.
- **Reversible or backed-up**: keep a tested `down`, or take a point-in-time backup
  immediately before an irreversible transformation.
- **Idempotent & resumable**: safe to re-run; checkpoints so an interrupted backfill
  resumes without double-processing (see release-deployment-safety backfill guidance).
- **Audited**: log the migration as a change (what ran, when, by whom) — this doubles as
  change-management evidence for `compliance-frameworks.md`.
- **Dry-run** against production-like data and volumes first; a migration that's instant on
  1k rows can lock a table for minutes on 100M.

## Backups
- **Automated** on a schedule matched to your RPO (below).
- **Encrypted** at rest and in transit; access-controlled (a backup is a full copy of your
  most sensitive data — same classification as the source).
- **Geographically separated** from primary (a backup in the same failure domain isn't DR).
- **Immutable / retention-locked** where ransomware resilience matters (can't be deleted by
  a compromised account).
- **Restore-tested regularly** — an untested backup is a hope. Schedule restore drills and
  measure how long they actually take (feeds RTO).

## Disaster Recovery: RPO & RTO
- **RPO (Recovery Point Objective)** — the maximum acceptable *data loss*, i.e. how far back
  in time you'd fall to the last recoverable point. Drives backup/replication frequency
  (RPO of 5 min ⇒ near-continuous replication; RPO of 24h ⇒ daily backups).
- **RTO (Recovery Time Objective)** — the maximum acceptable *downtime* to restore service.
  Drives your DR architecture (a cold backup restore might be hours; hot standby is
  minutes).
- Set RPO/RTO **per system** based on business impact; don't over-engineer non-critical
  systems or under-engineer critical ones.

## DR strategies (cost vs. RTO/RPO trade-off)
- **Backup & restore** — cheapest; highest RTO. Restore from backups into new infra.
- **Pilot light** — core minimal version always running; scale up on disaster.
- **Warm standby** — scaled-down full copy running; scale up and cut over.
- **Hot standby / multi-region active-active** — near-zero RTO/RPO; most expensive.
Pick per the system's RTO/RPO and budget.

## DR drills
- Test the DR plan on a schedule (not just document it). A plan never executed will fail
  when you need it. Involve the on-call/incident process (`sre-operational-readiness`).
- Measure actual achieved RTO/RPO in the drill vs. the target; close the gap.

## Safety guardrails (always)
- Any destructive migration, purge, or restore-over-production is high-risk: run the
  lockout/accidental-deletion check (`owasp-secure-coding-bdd`), confirm a verified backup
  exists, and get explicit confirmation before executing. Call irreversibility out loudly.

## Testable properties
```gherkin
  @data-lifecycle
  Scenario: Backup can be restored within the RTO
    Given a nightly encrypted backup exists
    When a restore drill is performed into a clean environment
    Then the system is recoverable and the restore completes within the defined RTO

  @data-lifecycle
  Scenario: Migration aborts if an integrity check fails
    Given a migration that must preserve total order value
    When the post-migration total does not match the pre-migration total
    Then the migration aborts and rolls back rather than committing corrupt data
```
