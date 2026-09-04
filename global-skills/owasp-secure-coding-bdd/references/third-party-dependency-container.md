# Third-Party Dependencies, Container & Supply Chain Security

Covers: Vulnerable Dependency Management (OWASP Top 10 "Vulnerable and Outdated Components"), Docker Security, Kubernetes Security basics, Software Supply Chain Security, Infrastructure as Code Security, Secure Cloud Architecture, Virtual Patching.

## Dependency management
- Run automated dependency vulnerability scanning in CI on every build: `npm audit` / `yarn audit` (Node), `pip-audit` or `safety` (Python), `dotnet list package --vulnerable` (.NET), OWASP Dependency-Check or `mvn versions:display-dependency-updates` (Java), `bundle-audit` (Ruby), or GitHub's built-in Dependabot alerts. Fail the build (or at least alert loudly) on newly introduced critical/high vulnerabilities.
- Pin dependency versions (lockfiles: `package-lock.json`/`yarn.lock`, `Pipfile.lock`/`poetry.lock`, `packages.lock.json`) so builds are reproducible and a compromised upstream publish can't silently flow into a build via a loose version range.
- Regularly update dependencies rather than letting them drift for years — an old, unpatched version of a widely used library is one of the most common real-world breach vectors precisely because the fix already exists and wasn't applied.
- Review new dependencies before adding them for basic hygiene: actively maintained, reasonable download/usage numbers, no known unresolved critical CVEs, license compatible with the project.
- Avoid pulling dependencies from untrusted/unofficial registries; verify package integrity where the ecosystem supports it (npm's provenance/signatures, pip's hash-checking mode).

## Container (Docker) security
- Don't run the application process as root inside the container — create and switch to an unprivileged user (`USER appuser` in the Dockerfile).
- Use minimal base images (distroless, `-slim`, or Alpine variants) to reduce attack surface and image size — fewer installed packages means fewer things that can carry a vulnerability.
- Pin base image versions/digests rather than `latest`, so builds are reproducible and you control exactly when an update is pulled in.
- Never bake secrets (API keys, credentials, private keys) into image layers — even a later "removed" file in a subsequent layer still exists in the image history. Inject secrets at runtime via environment variables from a secrets manager or orchestrator secret store.
- Scan images for known vulnerabilities in CI (Trivy, Grype, or the registry's built-in scanning) before deploying.
- Set resource limits (CPU/memory) on containers so a single compromised or runaway container can't exhaust the host's/node's resources.
- Use multi-stage builds so build-time tools/dependencies (compilers, dev packages) don't end up in the final runtime image.
- Mount the container filesystem read-only where the app doesn't need to write, and drop unnecessary Linux capabilities (`--cap-drop=ALL`, add back only what's needed).

## Kubernetes basics (if applicable)
- Apply Network Policies to restrict pod-to-pod traffic to only what's needed, rather than a flat network where any pod can reach any other.
- Store secrets in Kubernetes Secrets (or better, an external secrets manager integration) rather than in plain ConfigMaps or environment variables baked into manifests committed to git.
- Set `securityContext` to run as non-root, disallow privilege escalation, and use a restrictive Pod Security Standard (`restricted` profile) rather than the permissive default.
- Apply resource requests/limits per pod for the same DoS-prevention reason as container-level limits above.

## Infrastructure as Code (Terraform, CloudFormation, Pulumi, ARM/Bicep)
- Scan IaC templates in CI for misconfigurations before apply (`tfsec`, `checkov`, `terrascan`, or cloud-native equivalents) — catching an overly permissive security group or a publicly exposed storage bucket at plan time is far cheaper than after it's live.
- Never commit state files (`terraform.tfstate`) to version control — they can contain secrets and sensitive resource details; use a remote backend with access controls and encryption at rest instead.
- Apply the same least-privilege principle to the IaC tool's own execution credentials (the CI job applying Terraform should have only the permissions its templates actually need, not blanket account admin).
- Review diffs (`terraform plan` output) for unexpected deletions or permission widenings before every apply — this is also a lockout-prevention control, see `lockout-prevention-safe-changes.md`.

## Secure cloud architecture
- Follow least-privilege for every cloud IAM role/service account — scope permissions to specific resources and actions rather than broad wildcard grants (`*:*` or `s3:*` on all buckets).
- Segregate environments (dev/staging/prod) into separate accounts/projects/subscriptions where the cloud provider supports it, rather than relying on naming conventions within one shared account, so a mistake in dev can't reach production resources.
- Enable and centralize audit logging for the cloud account itself (CloudTrail, Azure Activity Log, GCP Audit Logs) — this is what lets you reconstruct what happened after an incident, including who changed a permission.
- Encrypt data at rest by default at the storage-service level (S3/Blob/GCS default encryption) in addition to any application-level encryption, and restrict public access at the storage level explicitly (block public access settings) rather than relying on bucket policy alone.

## Virtual patching
- When a vulnerability is discovered in a dependency or the application itself and an immediate code fix isn't ready to ship, a WAF rule or reverse-proxy filter blocking the specific known-malicious request pattern is a reasonable **temporary** mitigation — but track it explicitly as temporary and still ship the real fix; don't let a virtual patch quietly become the permanent "fix."

## Supply chain / CI-CD pipeline itself
- Treat the CI/CD pipeline as part of the attack surface: restrict who can modify pipeline config, use least-privilege tokens/credentials for CI jobs (scoped to only what that job needs, not a broad admin token), and avoid running untrusted PR code (e.g., from forks) with access to repository secrets.
- Verify the integrity of build tools/scripts pulled into the pipeline (pin action/plugin versions by commit SHA in GitHub Actions rather than a mutable tag like `@v1` for third-party actions handling secrets).

## BDD / CI check patterns

These are mostly automated CI gates rather than Gherkin scenarios, but where relevant, express them as scenarios too:

```gherkin
@security
Scenario: Build fails when a critical dependency vulnerability is introduced
  Given a new dependency with a known critical CVE is added to the lockfile
  When the CI pipeline runs the dependency audit step
  Then the build fails and reports the vulnerable package and CVE

@security
Scenario: Container image does not run as root
  Given the application's Docker image is built
  When the container is inspected
  Then the running process user is not root
```

Complementary CI step (not a Gherkin scenario, an actual pipeline job) to add alongside the BDD suite from `bdd-comprehensive-testing`:

```yaml
# Example: dependency + image scanning job, add to the same pipeline
security-scan:
  steps:
    - run: npm audit --audit-level=high   # or pip-audit / dotnet list package --vulnerable
    - run: trivy image myapp:latest --severity HIGH,CRITICAL --exit-code 1
```
