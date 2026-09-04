# SLIs, SLOs, SLAs & Error Budgets

## Definitions (keep them straight)
- **SLI** (Indicator): a *measured* number reflecting user experience, e.g. "proportion of
  HTTP requests that succeed" or "proportion of requests served under 300 ms."
- **SLO** (Objective): the *target* for an SLI over a window, e.g. "99.9% of requests
  succeed over 28 days." Internal.
- **SLA** (Agreement): a *contractual* promise to customers with consequences (credits) if
  missed. Always set the SLA looser than the SLO so you have margin before breaching it.
- **Error budget**: `100% − SLO`. At 99.9% over 30 days, the budget is ~43 minutes of
  unavailability. It's the amount of failure you're *allowed* to spend.

## Choosing good SLIs
- Measure as close to the user as possible (at the load balancer / API edge, not deep
  inside).
- Common SLI types: **availability** (good requests / valid requests), **latency**
  (fraction under a threshold — use a threshold, not an average), **quality/correctness**,
  **freshness/staleness** (for data pipelines), **throughput/coverage**.
- Define "good" precisely: which status codes count as failures? which endpoints? Exclude
  invalid client requests (4xx from bad input) from availability where appropriate.
- Use percentiles, never averages, for latency: track p50/p95/p99. Averages hide the tail
  that actually hurts users.

## Setting SLOs
- Base the target on what users actually need, not on the maximum achievable. 99.9% and
  99.99% differ by 10x in cost and effort — don't buy nines you don't need.
- Start from current measured performance; set an SLO slightly tighter as a goal, iterate.
- Measure over a rolling window (commonly 28–30 days) so a single bad day doesn't
  permanently doom the quarter.

## Error budget policy (the point of all this)
The budget converts reliability into a decision rule agreed *in advance*:
- **Budget remaining** → ship features; take reasonable risks; velocity is fine.
- **Budget exhausted** → feature freeze; all effort shifts to reliability until you're back
  in budget. No debate in the moment — the policy decided it earlier.
- This aligns dev and ops: reliability isn't "as much as possible" (which fights features),
  it's "meet the SLO," which is a shared, finite target.

## Burn rate
How fast you're consuming the budget. A burn rate of 1 means you'll exactly exhaust the
budget by the window's end; a burn rate of 14.4 means you'll exhaust a 30-day budget in ~2
days. Burn rate drives alerting (see `alerting-and-oncall.md`): fast burn pages
immediately, slow burn opens a ticket.

## Anti-patterns
- Aiming for 100% (impossible, and it makes every deploy terrifying).
- SLIs that measure the machine (CPU) instead of the user (success rate).
- SLA tighter than or equal to SLO (no margin — you breach the contract the moment you miss
  internal target).
- An error-budget policy nobody enforces (then it's just a chart).
