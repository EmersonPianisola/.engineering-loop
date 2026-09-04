# Load & Performance Testing

Prove the system meets its performance SLOs *before* users find out it doesn't.

## Types (each answers a different question)
- **Load test** — "Does it meet SLOs at expected traffic?" Run at anticipated peak
  concurrency; assert latency (p95/p99) and throughput stay within target.
- **Stress test** — "Where does it break, and does it break gracefully?" Ramp beyond
  expected load until failure; confirm it sheds load / returns errors cleanly rather than
  corrupting data or falling over.
- **Soak (endurance) test** — "Does it degrade over time?" Sustained load for hours;
  catches memory leaks, connection-pool exhaustion, disk fill, slow GC creep.
- **Spike test** — "Does it survive a sudden surge?" Instant jump in traffic; validates
  autoscaling reaction time and backpressure.
- **Capacity/scalability test** — establish per-unit capacity (req/s per instance) to feed
  capacity planning.

## Method
1. Define the **performance SLOs** first (from `sre-operational-readiness`): target p99
   latency, throughput, error rate at a given concurrency.
2. Use **production-like** environment and data volumes — testing against a tiny dataset
   lies. Beware caches that make the second run unrealistically fast.
3. Model **realistic traffic** — mixed endpoints, think-times, real payload sizes, ramp-up
   — not a single endpoint hammered flat out (unless that's the real pattern).
4. Establish a **baseline**, then track over time so you catch regressions.
5. Measure the **full distribution** (p50/p95/p99/max), not averages. Watch server-side
   resource saturation simultaneously to find the bottleneck.

## Tooling
k6 (JS, CI-friendly), Gatling (JVM), Locust (Python), JMeter, Artillery. Prefer a tool
whose scripts live in the repo and run in CI.

## In CI/CD
- Run a scaled-down load test on PRs or nightly to catch regressions early; full-scale
  before major releases as a gate.
- Fail the build if p99 latency or error rate regresses beyond a threshold vs. baseline.
- Tie into `release-deployment-safety`: a canary can also be watched for latency regression.

## Common findings to look for
- N+1 queries, missing indexes, unbounded result sets (see enterprise DB architecture).
- Connection-pool / thread-pool exhaustion under concurrency.
- Missing timeouts causing cascading slowdowns (see resilience patterns).
- Cache stampedes; lack of pagination; synchronous work that should be async.

## Example k6 gate (concept)
```javascript
export const options = {
  scenarios: { steady: { executor: 'constant-vus', vus: 200, duration: '5m' } },
  thresholds: {
    http_req_duration: ['p(99)<500'],   // p99 latency SLO
    http_req_failed:   ['rate<0.001'],  // <0.1% errors
  },
};
// build fails if thresholds are breached
```
