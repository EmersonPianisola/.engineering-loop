# Audit Logging (tamper-evident, compliance-grade)

Audit logs are a **compliance artifact**, distinct from operational logs (covered in
`sre-operational-readiness`). Operational logs help you debug; audit logs prove *who did
what to sensitive data* to an auditor or investigator.

## What to audit
- **Authentication events**: login success/failure, MFA, logout, password/credential
  changes.
- **Authorization events**: access grants/revocations, role/permission changes, privilege
  escalation.
- **Access to sensitive/regulated data**: reads and exports of PII/PHI/financial records
  (especially by privileged users/admins).
- **Changes to sensitive data**: create/update/delete, with before/after (or a reference to
  it).
- **Administrative & configuration actions**: changing security settings, feature flags
  affecting access, data exports, bulk operations.
- **Compliance-relevant events**: consent given/withdrawn, data-subject requests received
  and fulfilled, retention/deletion jobs run.

## What each entry should contain
- **Who** — authenticated identity (user/service), not just an IP.
- **What** — the action and the target (record/resource id).
- **When** — precise, synchronized timestamp (UTC, NTP-synced).
- **Where** — source IP / device / session, and which system.
- **Outcome** — success/failure and reason.
- **Before/after** or a reference for data changes.
Use a **consistent, structured schema** (see the logging-vocabulary idea in
`owasp-secure-coding-bdd`) so audit events are queryable and alertable.

## What must NOT be in audit logs
- Secrets, passwords, tokens, full card numbers, or more PII than necessary to identify the
  action. Log a record *id*, not the sensitive contents. Audit logs are themselves
  sensitive and access-controlled.

## Tamper-evidence & integrity
- Audit logs must be **append-only** and protected from modification/deletion — even by
  admins whose actions they record. Use write-once/immutable storage, a separate
  security-controlled account/system, or cryptographic chaining (hash-linked entries) for
  high assurance.
- Restrict who can read them; monitor access to the audit log itself.
- Consider forwarding to a separate SIEM / log account so a compromised app can't erase its
  own trail.

## Retention
- Retain audit logs per the applicable requirement (varies by framework/sector — often 1
  year minimum, longer for regulated industries). Define it explicitly and enforce it.
- Retention of audit logs can differ from (and outlast) retention of the underlying data.

## Make it real, and testable
- Emit audit events from a central, hard-to-bypass point (middleware/interceptor/data-access
  layer), not scattered ad hoc calls that are easy to forget.
- Add `@compliance` BDD scenarios asserting that sensitive actions produce the expected
  audit entry (see the SKILL.md examples).

## Relationship to operational logging
- **Operational logs** (metrics/traces/app logs) → debugging + reliability
  (`sre-operational-readiness`). May be sampled, shorter-lived, less strictly controlled.
- **Audit logs** → compliance + forensics. Complete (not sampled), tamper-evident, strictly
  retained and access-controlled. Keep them separate.
