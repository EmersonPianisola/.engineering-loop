# CI/CD Delivery Pipeline (build → promote → deploy)

The `bdd-comprehensive-testing` skill covers the *test* stages. This covers the *delivery*
stages that come after tests pass.

## Build once, promote the same artifact
- Produce **one immutable artifact** (container image, jar, zip) per commit, identified by
  git SHA.
- Promote that *exact* artifact through environments — never rebuild per environment
  ("build once, deploy many"). Rebuilding introduces "works in staging, breaks in prod"
  drift.
- Store artifacts in a registry with retention so you can redeploy any recent version.

## Environment progression with gates
```
commit → CI (build + all tests) → deploy to dev → automated checks
       → deploy to staging → smoke + integration + canary analysis
       → manual approval (if required) → progressive prod rollout → verify → done
```
- Each stage is a gate: failing checks block promotion.
- Staging should mirror prod as closely as feasible (config, data shape, scale profile).
- Production rollout uses the progressive strategy from `deployment-strategies.md`.

## Migrations in the pipeline
- Run migrations as an explicit, ordered pipeline step (expand step before code deploy;
  contract step in a later pipeline run) — never ad hoc by hand.
- Migrations must be idempotent and safe to re-run if a stage retries.

## Configuration & secrets
- Config per environment via env vars / config service, not baked into the artifact.
- Secrets from a vault / secret manager injected at deploy time — never in the image or
  repo (see `owasp-secure-coding-bdd` secrets guidance).

## GitOps
- Declarative desired state (k8s manifests, Helm, Terraform) in git; Argo CD / Flux
  reconciles. Rollback = `git revert`. Every change is reviewed and audited.

## Deployment record / traceability
Keep an automatic record of every production deploy: git SHA, artifact version, who
triggered it, when, which flags changed, and the migration steps applied. This is
essential for incident forensics ("what changed right before this broke?").

## Pipeline security (delegates to owasp-secure-coding-bdd)
- Least-privilege runners; pin CI actions to SHAs; protect prod credentials from PR/fork
  contexts; sign artifacts; prefer OIDC over long-lived cloud keys. See that skill's
  `third-party-dependency-container.md`.

## Minimal example (GitHub Actions delivery job, after tests pass)
```yaml
deploy-prod:
  needs: [build, test]           # test job is defined by bdd-comprehensive-testing
  if: github.ref == 'refs/heads/main'
  runs-on: ubuntu-latest
  permissions:
    id-token: write              # OIDC, no long-lived secrets
    contents: read
  steps:
    - uses: actions/checkout@<pinned-sha>
    - name: Download built artifact
      uses: actions/download-artifact@<pinned-sha>   # same artifact built in CI
    - name: Run expand migrations
      run: ./scripts/migrate.sh expand
    - name: Progressive deploy (canary → 100%)
      run: ./scripts/deploy.sh --strategy canary --artifact ${{ github.sha }}
    - name: Verify canary health
      run: ./scripts/verify_canary.sh || ./scripts/rollback.sh
    - name: Record deployment
      run: ./scripts/record_deploy.sh --sha ${{ github.sha }} --actor ${{ github.actor }}
```
