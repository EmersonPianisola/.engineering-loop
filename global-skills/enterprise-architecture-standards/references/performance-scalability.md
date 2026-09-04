# Performance & Scalability Architecture

Covers: Caching strategies, load balancing algorithms, async/queue processing, horizontal vs. vertical scaling, query optimization, connection pooling, the N+1 problem.

## Measure before optimizing
- Profile and measure the actual bottleneck (database query time, network latency, CPU-bound computation, memory pressure) before optimizing — optimizing the wrong layer is wasted effort and can add complexity for zero real-world benefit. "Premature optimization" cuts both ways: don't add caching/async/sharding speculatively either, without evidence of the actual bottleneck.
- Establish a performance budget/target tied to a real requirement (e.g., "p95 API latency under 300ms," "supports 500 concurrent users") before deciding what architecture is needed to hit it — designing for an unspecified "fast" and "scalable" leads to over-engineering in the wrong places.

## Caching strategies
- **Cache-aside (lazy loading)** — application checks cache first, falls back to the data store on miss and populates the cache; simplest and most common pattern. Risk: cache stampede on a popular key's expiry (many concurrent requests all miss simultaneously and hit the database at once) — mitigate with a lock/single-flight pattern or staggered expiry.
- **Write-through** — writes go to the cache and the data store together, keeping them always in sync; adds write latency but avoids stale-cache windows.
- **Write-behind (write-back)** — writes go to the cache immediately and are asynchronously flushed to the data store; lowest write latency but risks data loss if the cache fails before flushing — only acceptable where that risk is explicitly tolerable.
- Set explicit TTLs matched to how stale the data can acceptably be — never cache indefinitely without an invalidation strategy, since "the cache never updates" is a recurring, hard-to-diagnose bug class.
- Explicitly invalidate on write where correctness requires fresh reads (don't rely on TTL alone for data where staleness has real business impact, e.g., inventory counts near zero).
- Use a CDN for static/cacheable content and cacheable API responses close to the user, reducing both latency and origin load.
- Cache at the right layer for the access pattern: CDN (static assets, cacheable public responses), application-level cache (Redis/Memcached, for computed results and session data), and database query cache/materialized views (for expensive aggregate queries) are different tools for different problems — don't rely on one layer to solve all of them.

## Load balancing
- **Round robin** — simplest, distributes requests evenly by count; doesn't account for uneven request cost or instance health beyond basic up/down.
- **Least connections** — routes to the instance with the fewest active connections; better for workloads with variable request duration.
- **Weighted** (round robin or least-connections) — accounts for heterogeneous instance capacity (e.g., some instances are larger).
- **Consistent hashing** — routes based on a hash of a request attribute (e.g., user ID or session ID) so the same client consistently reaches the same backend instance — useful for session affinity or cache locality, at the cost of uneven distribution if the hash key distribution is skewed.
- Combine load balancing with health checks that actually exercise the service's real dependencies (not just "is the process running") so an instance that's up but can't reach its database gets taken out of rotation rather than continuing to receive and fail requests.

## Horizontal vs. vertical scaling
- **Vertical scaling** (bigger instance) is simpler operationally and has no distributed-systems complexity, but has a hard ceiling and doesn't improve availability (still one instance to fail).
- **Horizontal scaling** (more instances) improves both capacity and availability but requires the application to be stateless (or externalize state to a shared store — session data in Redis, not in-process memory) so any instance can serve any request.
- Design for horizontal scalability from the start for anything expected to need real capacity growth (externalize session state, avoid in-memory-only state that only one instance knows about, make background jobs safe to run from multiple instances concurrently) — retrofitting statelessness into an app built assuming a single instance is a much larger undertaking later.

## Asynchronous / queue-based processing
- Move genuinely slow or bursty work (report generation, image/video processing, sending bulk emails, any operation whose latency the user doesn't need to wait on synchronously) off the synchronous request path into a background queue — this keeps request-serving capacity available for actual user-facing latency-sensitive work.
- Size worker concurrency deliberately against the downstream dependency's real capacity (don't spin up unlimited workers that overwhelm a database or third-party API just because the queue has a backlog — apply the rate-limiting/bulkhead patterns from `resilience-reliability-patterns.md`).
- Monitor queue depth and consumer lag as first-class metrics — a growing, un-alerted backlog is a common way async processing quietly falls behind for hours before anyone notices.

## Query optimization & the N+1 problem
- The N+1 query problem: fetching a list of N parent records, then executing one additional query per parent to fetch related data (N additional queries), instead of one query (or a small constant number) that fetches everything needed. This is one of the most common, most impactful, and most preventable performance bugs in ORM-based codebases — watch for it any time a loop makes a database/ORM call per iteration.
- Fix with eager loading (`JOIN` / ORM "include"/"select related" features) or batching (fetch all needed IDs, then one query with `WHERE id IN (...)`) instead of per-item queries.
- Select only the columns actually needed rather than `SELECT *` on wide tables, especially in hot paths and list endpoints, to reduce I/O and network transfer.
- Paginate any endpoint returning a list, with a sane default and maximum page size (this is also a DoS-prevention control — see `owasp-secure-coding-bdd`'s logging/DoS reference).

## Connection pooling
- Use a connection pool for database and other network resource connections rather than opening a new connection per request — connection establishment (especially TLS handshakes) has real latency and resource cost that a pool amortizes.
- Size the pool based on the actual downstream capacity and the application's concurrency, not an arbitrary large number — an oversized pool can overwhelm the database with more concurrent connections than it can efficiently handle; an undersized pool causes request queuing/timeouts under load. Monitor pool utilization and adjust based on real data.
- Set a pool checkout timeout so a request that can't get a connection fails fast with a clear error rather than hanging indefinitely (ties back to the timeout principle in `resilience-reliability-patterns.md`).

## BDD / performance scenario patterns

```gherkin
Scenario: List endpoint does not trigger N+1 queries
  Given a request fetches 50 orders with their line items
  When the endpoint executes
  Then the total number of database queries is a small constant, not proportional to the number of orders

Scenario: Cache-aside prevents a stampede on popular key expiry
  Given a popular cached value has just expired
  When 100 concurrent requests request that value simultaneously
  Then only one request queries the underlying data store
  And the rest receive the value once it's repopulated

Scenario: List endpoint enforces a maximum page size
  When a client requests a page size of 1,000,000
  Then the server caps the response to the configured maximum

Scenario: Service remains responsive when horizontally scaled behind a load balancer
  Given the service is running as 3 stateless instances behind a load balancer
  When a user's session spans requests routed to different instances
  Then the user's session state is correctly available regardless of which instance handles the request
```
