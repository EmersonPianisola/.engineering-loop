# Deployment Strategies

## Rolling deployment
Replace instances a few at a time with the new version behind a load balancer.
- Pros: no extra capacity needed; simple. Cons: old+new run together (needs backward
  compatibility); rollback = roll forward with old version, slower.
- Use `maxUnavailable`/`maxSurge` (k8s) to control blast radius. Add readiness probes so
  traffic only hits instances that are actually up.

## Blue-green deployment
Stand up a full parallel environment (green) with the new version; cut traffic over from
blue when green is verified; keep blue warm for instant rollback.
- Pros: instant cutover and instant rollback (flip the router back). Cons: 2x capacity
  during the switch; database is shared, so schema still must be backward-compatible.
- Cut over at the load balancer / DNS / service mesh, not by redeploying.

## Canary deployment
Route a small slice of real traffic (1–5%) to the new version, compare against the stable
baseline, then progressively widen.
- Stages: 1% → 5% → 25% → 50% → 100%, with a "bake time" at each stage.
- Canary analysis compares canary vs. baseline on: error rate, p50/p95/p99 latency, CPU/
  memory saturation, and key business metrics. Automate the promote/abort decision.
- Abort criteria (auto-rollback): error rate exceeds baseline by X%, latency regresses
  beyond threshold, or error-budget burn rate spikes.
- Tools: Argo Rollouts, Flagger, Spinnaker, or cloud-native (AWS CodeDeploy, GCP).

## Progressive delivery
Canary + feature flags + automated analysis combined: ship dormant, enable for a cohort,
measure, widen. This is the modern default at scale — it decouples deploy from release and
makes every rollout a measured experiment.

## Shadow / mirror traffic
Send a copy of production traffic to the new version without serving its responses. Great
for validating performance and correctness of risky changes with zero user impact. Be
careful with side effects (don't double-write to the DB or send duplicate emails).

## GitOps (declarative delivery)
Desired production state (manifests, Helm charts, Terraform) lives in git; an operator
(Argo CD, Flux) continuously reconciles the cluster to match. Benefits: git is the single
source of truth, every change is reviewed + audited, and rollback is `git revert`.

## Choosing
- Default to **rolling + canary** for stateless services.
- Use **blue-green** when you need instant, guaranteed rollback and can afford 2x capacity.
- Always layer **feature flags** on top for user-visible behavior.
- Whatever you choose, the shared database means backward-compatible schema is mandatory.
