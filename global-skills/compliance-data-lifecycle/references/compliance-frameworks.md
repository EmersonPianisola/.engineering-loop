# Compliance Frameworks & Control Mapping

The goal isn't paperwork — it's building the system so that satisfying an auditor is a
byproduct of how it already works. Map each obligation to a real control and let the system
produce the evidence.

## The major frameworks (know which apply)
- **SOC 2** — the common B2B SaaS bar (US-centric). Based on five **Trust Services
  Criteria**: Security (always), Availability, Processing Integrity, Confidentiality,
  Privacy (include based on what you promise customers). Type I = controls designed at a
  point in time; Type II = controls operating effectively over a period (what buyers really
  want).
- **ISO/IEC 27001** — international standard for an Information Security Management System
  (ISMS); certification against Annex A controls. Broader/organizational; overlaps heavily
  with SOC 2 technically.
- **HIPAA** — US health data (PHI). Requires safeguards + Business Associate Agreements.
- **PCI DSS** — payment card data. Best strategy: **stay out of scope** (use a hosted
  payment provider / tokenization so raw card data never touches your systems — see
  `owasp-secure-coding-bdd` payment guidance).
- **GDPR / CCPA** — privacy laws, covered in `privacy-gdpr-ccpa.md`.
- **FedRAMP / GovCloud, SOX, GLBA** — sector/region specific; apply if relevant.

## Common technical controls (satisfy several frameworks at once)
Most frameworks want the same underlying engineering hygiene. Build these and you cover the
bulk of SOC 2 + ISO 27001:
- **Access control & least privilege** — RBAC, SSO/MFA, joiner-mover-leaver process, access
  reviews. (Mechanics: `owasp-secure-coding-bdd`.)
- **Change management** — every prod change is reviewed, tested, traceable, and reversible.
  (Delegate to `release-deployment-safety` — its deployment records ARE change-management
  evidence.)
- **Encryption** — TLS in transit; encryption at rest with managed keys. (`owasp` crypto.)
- **Audit logging & monitoring** — see `audit-logging.md` and `sre-operational-readiness`.
- **Vulnerability & patch management** — SCA/dependency scanning, patch SLAs. (`owasp`
  dependency guidance.)
- **Backup & disaster recovery** — see `safe-data-migrations-and-dr.md`.
- **Incident response** — documented process. (`sre-operational-readiness`.)
- **Vendor/subprocessor management** — track third parties touching data; DPAs; review
  their compliance.
- **Data classification & retention** — see `data-classification-and-retention.md`.
- **Security awareness / policies** — organizational, but engineering must follow.

## Evidence & continuous compliance
- Auditors want **proof controls operate over time**, not a description. Design controls so
  they emit evidence automatically: access logs, PR approvals, deploy records, scan
  results, backup-success logs, access-review exports.
- Prefer **compliance-as-code / continuous control monitoring** (Vanta, Drata, Secureframe,
  or in-house checks) that continuously verify controls rather than a once-a-year manual
  scramble.
- Keep a **control matrix**: control → requirement(s) it satisfies → how it's implemented →
  where the evidence lives. This is the single most useful artifact for an audit.

## Practical guidance when building a feature
- Ask: which controls does this feature implicate? (Almost always access control + audit
  logging + encryption; often retention + change management.)
- Implement the control in the code/infra, and make sure it leaves an evidence trail.
- Don't reinvent: reuse the org's existing SSO, secret manager, logging pipeline, and
  deploy process so the feature inherits already-audited controls.
- Flag to the user when a feature introduces a **new** category of regulated data or a new
  subprocessor — that can expand audit scope and needs a deliberate decision.
