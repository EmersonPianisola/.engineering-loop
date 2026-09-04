# Zero-Downtime & Reversible Database Migrations

The highest-risk operation in any deploy. The rule: **schema changes and the code that
depends on them are never released together.** Use the expand/contract (a.k.a.
parallel-change) pattern so old and new code both work at every step.

## Expand / Contract pattern

To make a breaking schema change safely, split it into a sequence where each step is
backward-compatible:

1. **Expand** — add the new structure without removing the old. (Add nullable column, new
   table, new index built concurrently.) Old code ignores it; new code isn't live yet.
2. **Migrate/backfill** — populate the new structure from the old, in batches (see below).
   Dual-write from application code if needed so new writes land in both places.
3. **Deploy code** — release code that reads/writes the new structure. Both old and new
   instances coexist safely because the old structure still exists.
4. **Contract** — only after the new code is fully rolled out and verified, remove the old
   column/table/dual-write in a *later* release.

Rolling back is safe at every step because you never destroyed the thing the running code
depends on until nothing depends on it.

## Rules for specific changes
- **Adding a column**: make it nullable or give it a default; never `NOT NULL` without a
  default on a populated table in one step.
- **Renaming a column**: add new → dual-write → backfill → switch reads → drop old. Never a
  direct rename (it breaks the running old code instantly).
- **Changing a type**: add new column of new type → backfill → switch → drop old.
- **Dropping a column/table**: stop writing → stop reading → deploy → drop in a later
  release. Confirm nothing reads it (grep + logs) first.
- **Adding an index**: build concurrently (`CREATE INDEX CONCURRENTLY` in Postgres) to
  avoid locking; watch for long-running builds on huge tables.
- **NOT NULL / constraints**: add as `NOT VALID` then `VALIDATE CONSTRAINT` separately
  (Postgres) to avoid a full-table lock.

## Backfills / large data migrations
- Batch it (e.g. 1–10k rows per batch) with a sleep between batches to protect the DB.
- Make it **idempotent and resumable** — track progress (last-processed id / checkpoint) so
  a failure can restart without redoing or skipping work.
- Throttle based on DB load (replication lag, CPU); back off automatically.
- Run as a background job, not inside the deploy step, for anything large.
- Never do a one-shot `UPDATE` over millions of rows — it locks, bloats, and can't be
  paused.

## Migration tooling
Use a migration framework with up/down (Flyway, Liquibase, Alembic, Rails/Django
migrations, Prisma Migrate, golang-migrate). Migrations must be:
- Version-controlled and ordered.
- Idempotent where possible; safe to re-run.
- Applied by the pipeline, not by hand.
- Reversible (a tested `down`), except deliberate destructive contractions which are
  gated + announced.

## Never
- Never combine expand and contract in one release.
- Never run a destructive migration (drop/truncate/irreversible transform) without an
  explicit backup, a confirmation gate, and calling it out to the user. This ties into the
  lockout/accidental-deletion check in `owasp-secure-coding-bdd`.

## BDD scenario patterns
```gherkin
  @release-safety
  Scenario: Backfill is resumable after interruption
    Given a backfill has processed 50,000 of 200,000 rows
    When the backfill job is interrupted and restarted
    Then it resumes from the last checkpoint without reprocessing completed rows

  @release-safety
  Scenario: Old code tolerates a newly added column
    Given the "expand" migration adds a nullable "preferred_locale" column
    When the previous application version reads and updates a user row
    Then it succeeds and does not error on the unknown column
```
