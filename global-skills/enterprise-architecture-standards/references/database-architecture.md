# Database Architecture

Covers: relational design/normalization, NoSQL data model fit, sharding/partitioning, replication, CAP/PACELC tradeoffs, indexing, transactions/ACID, polyglot persistence, migrations.

## Relational schema design
- Normalize to at least 3NF by default for transactional (OLTP) data — every non-key attribute depends on the key, the whole key, and nothing but the key. This prevents update/insert/delete anomalies and keeps a single source of truth for each fact.
- Denormalize deliberately, not accidentally, and only where a measured read-performance need justifies it (a reporting/read-model table, a materialized view, a cache) — document why the denormalized copy exists and how it stays in sync, since an undocumented denormalized copy is a future data-integrity bug waiting to happen.
- Choose primary keys deliberately: surrogate keys (auto-increment or UUID) are usually right for internal references; be intentional about UUID v4 (no ordering, can hurt index locality on high-insert tables — consider UUID v7/ULID for time-ordered inserts) vs. sequential IDs (simpler, but leak information about record count/order if exposed externally).
- Define foreign keys and constraints (NOT NULL, UNIQUE, CHECK) at the database level, not only in application code — the database is the last line of defense against data integrity violations, including from future code that doesn't go through today's validation path.
- Use explicit, meaningful column and table names (`customer_id` not `cid`); avoid reserved words; keep a consistent naming convention across the schema (snake_case vs. camelCase) rather than mixing per-table.

## NoSQL data model fit
- Choose the data store type based on the actual access pattern, not popularity:
  - **Document stores** (MongoDB, DynamoDB, CosmosDB) — good fit for aggregate-oriented data accessed mostly by a known key, with a naturally nested/document-shaped structure and a need for schema flexibility across records. Poor fit for data with heavy ad-hoc relational querying/joining needs.
  - **Key-value stores** (Redis, DynamoDB, Memcached) — best for simple lookups by key, caching, session storage, counters/rate-limiting. Not a substitute for a system needing rich querying.
  - **Wide-column stores** (Cassandra, HBase, Bigtable) — strong fit for very high write throughput, time-series data, and workloads where you can design around known query patterns up front (Cassandra in particular requires designing the table around the queries you'll run, not around the entity model).
  - **Graph databases** (Neo4j, Amazon Neptune) — fit for data whose primary value is in relationships/traversals (social graphs, fraud-detection networks, recommendation engines) where relational joins would become deeply nested and slow.
  - **Search engines** (Elasticsearch, OpenSearch) — for full-text search and complex faceted/aggregated queries over large document sets; not a system of record — treat it as a derived index kept in sync from the actual source of truth, not the primary data store.
- Don't default to NoSQL "for scale" without a concrete driver — a well-indexed relational database handles the overwhelming majority of real-world transactional workloads at enterprise scale; reach for NoSQL when the access pattern or scale genuinely doesn't fit the relational model, not by default.

## Polyglot persistence
- It's normal and often correct for a system (especially microservices) to use different data stores for different services/subsystems based on their actual access patterns (e.g., Postgres for the order service, Redis for session/cache, Elasticsearch for product search, a time-series DB for metrics) — the discipline required is keeping each store as the authoritative system of record for only its own data, with clear, documented sync mechanisms for any derived copies.

## Transactions & consistency (ACID, CAP, PACELC)
- **ACID** (Atomicity, Consistency, Isolation, Durability) — the guarantee a traditional relational transaction gives; understand and choose the right isolation level (Read Committed is a common safe default; Serializable is stronger but costs throughput; Read Uncommitted is rarely justified) rather than accepting a framework's default without understanding what anomalies it does or doesn't prevent (dirty reads, non-repeatable reads, phantom reads).
- **CAP theorem** — in the presence of a network partition, a distributed system must choose between Consistency (every read gets the latest write) and Availability (every request gets a response, possibly stale). This is a real tradeoff only during partitions; **PACELC** extends it usefully: even without a partition, you still trade off Latency vs. Consistency in normal operation. Be explicit about which side of this tradeoff a given data store/service needs — a payment ledger usually needs strong consistency; a "likes count" or a recommendation feed usually tolerates eventual consistency in exchange for lower latency and higher availability.
- Don't assume "the database handles it" for cross-service consistency in a microservices system — see the Saga pattern in `microservices-patterns.md` for consistency across service boundaries.

## Indexing strategy
- Index columns used in `WHERE`, `JOIN`, and `ORDER BY` clauses for queries that actually run in production — don't index speculatively for queries that don't exist yet, since every index adds write overhead and storage cost.
- Use composite indexes matching the actual query's column order (leftmost-prefix rule) rather than several single-column indexes when queries filter on multiple columns together.
- Watch for indexes that silently stop being used (e.g., a function or type-cast applied to an indexed column in the query, breaking index usage) — verify with the database's query planner (`EXPLAIN ANALYZE` or equivalent) rather than assuming an index is working because it exists.
- Periodically review for unused indexes (they still cost write performance and storage with zero read benefit) as part of routine maintenance, not just when adding new ones.

## Sharding & partitioning
- Partition (splitting one logical table into pieces on the same instance, e.g., by date range) before sharding (splitting across separate database instances) — partitioning solves table-size/maintenance problems without the distributed-systems complexity sharding adds.
- When sharding is genuinely necessary (data/throughput exceeds what a single instance can handle even after vertical scaling and read replicas), choose a shard key that distributes load evenly and matches the dominant query pattern (most queries should be able to target a single shard using the shard key; cross-shard queries/joins are expensive and should be rare by design, not routine).
- Understand the operational cost up front: resharding an unevenly-grown dataset later is a major undertaking — pick a shard key with room to grow evenly, and don't shard until the actual measured need (not a hypothetical future one) justifies the added complexity.

## Replication
- Use read replicas to scale read throughput and provide failover, understanding replication lag: reads from a replica can be stale by some interval — route anything requiring read-your-own-write consistency (e.g., a user immediately viewing data they just submitted) to the primary, or use a consistency mechanism the datastore provides for this, rather than assuming replica reads are always fresh.
- Have an explicit, tested failover plan (automatic or manual promotion of a replica to primary) rather than discovering the failover process for the first time during an actual outage.

## Migrations
- Every schema change ships as a versioned, reversible migration script (Flyway, Liquibase, Alembic, Rails migrations, EF Core migrations, etc.) checked into version control alongside the code that depends on it — never a manual, undocumented change applied directly to a production database.
- For any migration that could lock a large table or take significant time in production (adding a column with a default on a huge table, adding an index), use the database's online/non-blocking migration mechanism where available, and test migration timing against a production-scale copy of the data before running it live.
- Destructive migrations (dropping a column or table) require the same lockout-prevention discipline as any other destructive change — see `owasp-secure-coding-bdd`'s `lockout-prevention-safe-changes.md`: verify nothing still reads the column/table, deploy code that stops using it first, deploy and verify, then drop it in a separate, later migration — never in the same deploy that removes the last code path using it, so there's a rollback window if something was missed.

## BDD scenario patterns

```gherkin
Scenario: Database rejects a write that violates a foreign key constraint
  Given an order references a non-existent customer ID
  When the insert is attempted
  Then the database rejects it, not just the application layer

Scenario: Replica read does not break read-your-own-write for the acting user
  Given a user has just submitted a profile update
  When the same user immediately requests their profile
  Then the response reflects their own update, not stale replica data

Scenario: Destructive schema migration is applied only after code no longer references the column
  Given a column is being removed from a table
  When the migration plan is reviewed
  Then no currently deployed code path reads or writes that column before the drop migration runs
```
