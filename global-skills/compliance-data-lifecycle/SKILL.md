---
name: compliance-data-lifecycle
description: 'Use whenever a feature handles personal data, regulated data, or must satisfy audit/compliance requirements, AND whenever building or changing how data is stored, migrated, retained, backed up, or recovered. Covers SOC 2 / ISO 27001 control mapping, GDPR/CCPA privacy engineering (data-subject rights, consent, minimization, DPIA), tamper-evident audit logging, data classification + retention/deletion, and data lifecycle at scale: safe schema/data migrations, backups, and disaster recovery (RTO/RPO). Trigger proactively on "PII," "personal data," "GDPR," "CCPA," "HIPAA," "SOC 2," "ISO 27001," "audit," "compliance," "consent," "data retention," "right to be forgotten," "data deletion," "backup," "disaster recovery," "RTO," "RPO," "migration," or handling user/customer data — even without those words. Pairs with owasp-secure-coding-bdd (security controls) and release-deployment-safety (migration mechanics).'
---

# Compliance & Data Lifecycle

## Why this exists

Two things quietly block software from being truly enterprise-ready: it can't prove it
handles data lawfully and safely (compliance/privacy), and it treats data as an
afterthought (migrations, retention, recovery). Enterprise buyers *require* SOC 2 / ISO /
GDPR posture — its absence is a deal-blocker, not a nice-to-have. And the data outlives the
code: a schema migration, a retention rule, or a backup gap can cause irreversible loss or
a regulatory breach. This skill bakes compliance and disciplined data lifecycle into how
features are built, so "handles data" means "handles data lawfully, auditably, and
recoverably."

This is the governance/data half that complements `owasp-secure-coding-bdd` (which enforces
the *security* controls those frameworks require) and `release-deployment-safety` (which
owns the *mechanics* of zero-downtime migrations). This skill adds the *why/what*:
compliance obligations, privacy rights, auditability, retention, and recovery guarantees.

## The core principle

**Know what data you hold, why you're allowed to hold it, how long you keep it, who can
touch it, how you'd prove all of that to an auditor, and how you'd get it back if it's
lost.** If you can't answer those for a feature that touches data, the feature isn't done.

## The workflow

### Step 1: Classify the data the feature touches

Read `references/data-classification-and-retention.md`. Before anything else, identify:
- Is there **personal data** (PII), **sensitive personal data** (health, biometric,
  financial — extra rules), or **regulated data** (PCI cardholder data, PHI)?
- What's the **classification** (public / internal / confidential / restricted)?
- Data classification drives every downstream control: encryption, access, logging,
  retention, and residency.

### Step 2: If personal data is involved → apply privacy-by-design

Read `references/privacy-gdpr-ccpa.md`. Bake in:
- **Lawful basis + purpose limitation**: collect only for a stated, lawful purpose; don't
  repurpose silently.
- **Data minimization**: collect and retain the least data needed. The cheapest data to
  protect is data you never collected.
- **Consent** where required (granular, revocable, logged) — and honor withdrawal.
- **Data-subject rights**: access/export (portability), correction, deletion ("right to be
  forgotten"), and restriction — design the data model so these are actually executable
  (including across backups and downstream systems).
- **DPIA** (Data Protection Impact Assessment) for high-risk processing.
- **Data residency / cross-border transfer** constraints.

### Step 3: Map the feature to compliance controls

Read `references/compliance-frameworks.md`. Identify which controls the work must satisfy
(SOC 2 Trust Services Criteria, ISO 27001 Annex A, and sector rules like HIPAA/PCI DSS if
relevant) and make them real in the implementation, not just documented:
- Access control + least privilege (delegate mechanics to `owasp-secure-coding-bdd`).
- Change management (delegate to `release-deployment-safety`: reviewed, traceable deploys).
- Audit logging (Step 4).
- Encryption in transit + at rest.
- Vendor/subprocessor management for any third party touching the data.
Produce **evidence** as a byproduct (logs, approvals, config) — auditors want proof, not
promises.

### Step 4: Add tamper-evident audit logging for sensitive actions

Read `references/audit-logging.md`. For any access to or change of sensitive/regulated data
and any privileged action, record an **audit log**: who, what, when, from where, before/
after (or a reference), and outcome. Audit logs must be tamper-evident, retained per policy,
access-controlled, and must never themselves contain secrets or unnecessary PII. This is
distinct from operational logging (in `sre-operational-readiness`) — audit logs are a
compliance artifact.

### Step 5: Define retention and deletion — and make deletion real

Back to `references/data-classification-and-retention.md`:
- Every data category gets a **retention period** tied to its purpose/legal basis; delete
  or anonymize when it expires (retaining forever is a liability and often unlawful).
- **Deletion must propagate**: primary store, caches, search indexes, backups (or a
  documented backup-expiry approach), logs, analytics, and downstream/third-party systems.
- Prefer **anonymization/pseudonymization** where the data still has analytical value but
  identity isn't needed.

### Step 6: Make data changes safe and recoverable

Read `references/safe-data-migrations-and-dr.md`:
- **Migrations**: backward-compatible (expand/contract — mechanics in
  `release-deployment-safety`), but here add the data-integrity + auditability lens:
  validate row counts and invariants before/after, keep the migration reversible or backed
  up, and log it as a change.
- **Backups**: automated, encrypted, access-controlled, and **restore-tested** on a
  schedule. An untested backup is not a backup.
- **Disaster recovery**: define **RPO** (max acceptable data loss) and **RTO** (max
  acceptable downtime) per system; design replication/backup/failover to meet them; run DR
  drills.

### Step 7: Encode compliance & data guarantees as tests

Add scenarios (tagged `@compliance` / `@data-lifecycle`) to the BDD suite so these can't
silently regress:

```gherkin
  @compliance
  Scenario: User data export includes all personal data on request
    Given a user requests a data export
    When the export is generated
    Then it contains all personal data held for that user across primary and derived stores

  @compliance
  Scenario: Deletion request removes personal data everywhere it propagated
    Given a user requests account deletion
    When the deletion is processed
    Then their personal data is removed or anonymized in the database, search index, and caches
    And backups are scheduled to expire the data per the retention policy

  @compliance
  Scenario: Access to a sensitive record is audit-logged
    Given an admin views a customer's payment details
    Then an audit log entry records the admin identity, record id, timestamp, and source IP

  @data-lifecycle
  Scenario: Migration preserves row counts and key invariants
    Given a data migration transforms the "orders" table
    When the migration completes
    Then the row count matches the pre-migration count and no order total changed
```

### Step 8: Never let compliance work cause an outage or a lockout

Deletion, retention purges, access tightening, and key rotation are exactly the operations
that cause accidental data loss or self-lockout. Run the lockout/accidental-deletion check
from `owasp-secure-coding-bdd` before executing any of them, and take a verified backup
before irreversible deletions.

## What the big engineering orgs do that this encodes

- Treat compliance as **continuous evidence** produced by the system (automated control
  monitoring), not a once-a-year scramble.
- **Privacy by design**: minimization, purpose limitation, and executable data-subject
  rights built into the data model — not bolted on.
- Every sensitive action is **audit-logged** to a tamper-evident store.
- Data has an explicit **lifecycle**: classified on creation, retained by policy, deleted on
  schedule, recoverable within defined RPO/RTO, and every migration is safe and reversible.

## Reference files

| Topic | File |
|---|---|
| SOC 2, ISO 27001, HIPAA/PCI, control mapping, evidence, continuous compliance | `references/compliance-frameworks.md` |
| GDPR/CCPA, data-subject rights, consent, minimization, DPIA, residency | `references/privacy-gdpr-ccpa.md` |
| Tamper-evident audit logging: what/how to log, retention, access | `references/audit-logging.md` |
| Data classification, retention schedules, deletion/anonymization propagation | `references/data-classification-and-retention.md` |
| Safe data migrations (integrity/audit), backups, restore testing, RTO/RPO, DR | `references/safe-data-migrations-and-dr.md` |
