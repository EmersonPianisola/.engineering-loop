# Data Classification, Retention & Deletion

You can't protect, retain, or delete data correctly if you don't know what it is and where
it lives. Classification is the foundation; retention and deletion are the consequences.

## Classification
Assign every data element a class on creation; the class drives all downstream controls.
A common scheme:
- **Public** — no harm if disclosed (marketing pages).
- **Internal** — not for public, low sensitivity (internal docs).
- **Confidential** — business-sensitive (contracts, source, financials).
- **Restricted** — highest (PII, PHI, secrets, cardholder data); strongest encryption,
  access control, logging, and retention limits.

Maintain a **data inventory / map**: what data you hold, its class, where it's stored
(primary DB, replicas, caches, search, analytics, backups, logs, third parties), and its
lawful basis + retention. This map is what makes deletion, export, and audits possible.

## Retention
- Every data category gets an explicit **retention period** tied to its purpose and legal
  basis. "Keep forever" is a liability (bigger breach blast radius) and often unlawful under
  storage-limitation rules.
- Some data has **minimum** retention (tax, financial, audit logs) and some has **maximum**
  (personal data past its purpose). Reconcile both.
- Automate enforcement: scheduled jobs that delete/anonymize expired data, with their own
  audit trail.

## Deletion — must be complete and propagated
A "delete" that only removes the primary row is a compliance failure. Deletion must reach:
- Primary datastore **and** read replicas.
- **Caches** (Redis/Memcached/CDN) holding the data.
- **Search indexes** (Elasticsearch/OpenSearch/Algolia).
- **Analytics / data warehouse / data lake** copies.
- **Logs** that captured the data (avoid logging PII in the first place).
- **Backups** — either purge, or (more commonly) document that backups expire on a defined
  cycle and the data won't be restored into production after a deletion request. State this
  approach explicitly.
- **Third parties / subprocessors** that received the data — propagate the deletion.

Prefer **soft-delete then hard-delete/anonymize** on a schedule where you need a grace
period, but ensure the hard step actually runs.

## Anonymization vs. deletion
- Where data has ongoing analytical value but identity doesn't matter,
  **anonymize/aggregate** instead of hard-deleting (e.g. keep "an order happened" without
  the person). True anonymization removes it from privacy scope — but verify it can't be
  re-identified by combining fields.

## Backups & the deletion tension
- Deletion requests vs. immutable backups is a real tension. The accepted approach:
  time-boxed backup retention + a documented policy that deleted data is not restored to
  prod, rather than surgically editing every backup. Make this explicit and defensible.

## Safety
- Retention purges and deletions are **destructive and often irreversible** — run the
  lockout/accidental-deletion check from `owasp-secure-coding-bdd`, take a verified backup
  before large purges, and dry-run against counts first.
- Test deletion/anonymization jobs like any critical code (idempotent, resumable, audited).

## Testable properties
Add `@compliance` scenarios asserting: expired data is purged on schedule; a deletion
request removes data across all stores listed above; anonymized data can't be
re-identified from remaining fields. (See SKILL.md examples.)
