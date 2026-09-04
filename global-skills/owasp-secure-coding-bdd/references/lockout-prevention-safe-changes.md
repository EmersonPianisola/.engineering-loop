# Preventing Lockouts, Accidental Deletion & Broken Access During Secure Hardening

This file is not tied to a single OWASP cheat sheet — it's a mandatory safety layer that applies to EVERY secure-coding change, because tightening security is exactly the kind of work that causes self-inflicted outages: revoking a permission that was actually load-bearing, deleting a "test" account that was the only admin, rotating a key that's still in use, or locking a firewall rule that cuts off the only access path. This has caused real lockouts before — treat this file as non-negotiable, not optional caution.

## Read this before touching any of the following
Permissions/roles/IAM policies, API keys/secrets/tokens, SSH keys or authorized_keys, firewall/security group rules, admin/user accounts, database grants, file/directory permissions, `.env`/config files controlling access, CI/CD deploy credentials, DNS records tied to access, encryption keys for data already at rest.

## Core rules

1. **Never make a destructive or access-revoking change as the sole, un-reviewed action.** Before revoking, deleting, or restricting anything, identify: what currently depends on it, and what the rollback path is if this turns out to be load-bearing. If you can't answer both, stop and ask the user rather than proceeding.

2. **Never remove the last admin/owner/break-glass path.** Before deleting, disabling, or downgrading any account, role, or credential, verify there is still at least one other functioning path with equivalent access for both the human user and, where relevant, the automation/AI acting on their behalf. Never leave a system in a state where zero accounts can perform admin recovery actions.

3. **Additive before subtractive, whenever the order matters.** When replacing a permission scheme (e.g., moving from a broad role to least-privilege roles), grant and verify the new access first, confirm it actually works end-to-end, and only then revoke the old broad access — never revoke first and grant second "to be safe," since a mistake in the new grant then leaves nobody with access at all.

4. **Test permission/access changes in a reversible way.** Prefer a dry-run, plan/preview, or staging-environment application of the change before applying it to production (e.g., `terraform plan` before `apply`, IAM policy simulator before attaching a policy, a firewall rule change reviewed before it goes live). If the platform has no dry-run mode, apply the change in a way you can immediately undo (keep the previous config/value in hand, not just in version control history you'd need extra steps to restore) — read and note the exact prior state before changing it, in the same turn.

5. **Never revoke or rotate a credential/key that's still actively referenced** without first locating every place it's used (config files, CI/CD secrets, running service instances, other developers' environments) and confirming a replacement is deployed everywhere it's needed. A key rotation is a two-sided change (new key works everywhere) not a one-sided deletion (old key removed).

6. **Confirm before irreversible deletion.** Deleting an account, a database record, an encryption key with no backup, a file, or a cloud resource is not something to do silently as a side effect of a security task ("cleaning up" while hardening). Flag exactly what will be deleted and ask for explicit confirmation first, unless the user's request already explicitly and unambiguously named that exact deletion.

7. **Watch for self-lockout specifically in these common patterns:**
   - Tightening a security group/firewall rule and accidentally blocking the management/SSH/admin port you're connecting through right now
   - Rotating or deleting an API key that the CI/CD pipeline itself uses to deploy — breaking your own ability to deploy the fix
   - Changing file/directory permissions recursively (`chmod -R`, `chown -R`) and catching files needed by the running process or by your own tooling
   - Enforcing MFA or a new auth policy org-wide without first confirming the acting account (human or service account) has MFA/the new credential configured — locking yourself out of the very console you'd use to fix it
   - Revoking a broad IAM/role grant before the narrower replacement grants have been verified to actually cover every action currently performed by automation depending on it
   - Encrypting data with a new key and losing/not saving the old key needed to decrypt existing data, or losing the new key with no backup
   - Disabling a "default"/"legacy" account without checking that nothing (including scheduled jobs, health checks, or the deploy pipeline) still authenticates as that account

8. **Prefer changes that degrade gracefully.** Where a security control could be added in a "log/alert only" or "warn" mode before a hard "block/deny" mode, consider proposing that staged rollout to the user for high-blast-radius changes (org-wide auth policy, broad firewall tightening) rather than flipping straight to enforcement — mention this as an option rather than unilaterally deciding, since the user may have good reason to want it enforced immediately.

9. **When in doubt about blast radius, ask.** If a security-hardening change could plausibly affect access for the user themselves, other legitimate users, or the AI/automation's own ability to continue working on the system, say so explicitly and ask for confirmation before applying it — don't assume it's fine because it's "the secure thing to do." Secure and available are both real requirements; this file exists because sacrificing availability isn't automatically the safe choice.

## BDD scenario patterns for this (write these into the feature file whenever a change touches permissions/access/keys)

```gherkin
@security @lockout-prevention
Scenario: Revoking a role does not remove the last administrator
  Given exactly one active administrator account exists
  When a request attempts to revoke that account's admin role
  Then the operation is rejected or requires explicit override confirmation
  And the system retains at least one functioning admin path

@security @lockout-prevention
Scenario: New least-privilege role is verified before the old broad role is revoked
  Given a user is being migrated from role "admin-broad" to role "least-privilege-x"
  When the migration is performed
  Then the new role's access is verified to succeed for all required actions
  Before the old role is revoked

@security @lockout-prevention
Scenario: API key rotation does not break existing consumers
  Given API key "old-key" is used by the deployment pipeline
  When "old-key" is rotated to "new-key"
  Then the deployment pipeline is updated with "new-key" and verified to authenticate successfully
  Before "old-key" is revoked

@security @lockout-prevention
Scenario: Firewall rule change does not block the current management access path
  Given an administrator is connected via a specific management port
  When a firewall rule tightening is applied
  Then the rule preserves access on the current management path
  Or an alternate verified access path is confirmed before the old path is removed
```
