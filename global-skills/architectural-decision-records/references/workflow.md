# Workflow: locating the log, numbering, and setup

## 1. Detect the existing decision log

Never invent a location when the repo already has one. Search in this priority order and stop at the first hit:

1. A `.adr-dir` file at the repo root — its contents name the ADR directory (this is the `adr-tools` convention). Honor it.
2. `docs/adr/`
3. `docs/decisions/` (MADR's own default)
4. `doc/adr/`
5. `adr/`
6. `architecture/decisions/` or `docs/architecture/decisions/`
7. Any directory containing files matching `NNNN-*.md` where NNNN is 3–4 digits — grep the tree for the pattern before concluding there's nothing.

If you find a log, **conform to it exactly**: same directory, same filename pattern, same numbering width, same template flavor (if their existing ADRs are Nygard-style, keep writing Nygard-style even though MADR is the skill default — local consistency wins). Read one or two existing records to match tone and depth.

## 2. If no log exists, establish one

- Create `docs/adr/`.
- Copy `assets/adr-readme.md` to `docs/adr/README.md` so the next person understands the convention.
- Optionally seed `0001-record-architecture-decisions.md` — a tiny ADR (Nygard format) whose decision is "we will use ADRs, stored here, numbered sequentially." This is a well-known idiom and makes the log self-documenting. Then the feature's own ADR becomes `0002`.
- If the repo root is a sensible place for a marker, you may write `docs/adr` into a `.adr-dir` file so tooling and future runs detect it instantly.

## 3. Compute the next number

The next id is `max(existing ids) + 1`, zero-padded to four digits — **not** the count of files. Superseded or deleted records still burned their number; reusing it breaks every existing cross-reference. `scripts/new_adr.sh` does this correctly; prefer it over manual counting.

Numbers are global to a single log and monotonic. Two ADRs authored in the same PR take consecutive numbers.

## 4. Filename

`NNNN-kebab-case-title.md`. The title is short, lowercase, hyphenated, and describes the *decision*, not the feature: `0007-use-postgres-for-billing.md`, `0012-async-order-events-over-sync-calls.md`. Avoid vague titles like `0007-database.md`.

## Edge cases

**Monorepo with multiple independent services.** A per-service log (`services/billing/docs/adr/`) is appropriate when services are independently owned and deployed; number each log independently. Keep a root `docs/adr/` for cross-cutting decisions that affect the whole repo. Decide based on the blast radius of the decision: repo-wide force → root log; single-service force → that service's log.

**Existing log with a non-standard scheme** (e.g. three-digit numbers, a custom template, dated filenames). Match it. Do not "fix" their convention as a side effect of adding one record — that's its own decision (and arguably its own ADR).

**Retrofitting a repo that has none.** Don't back-fill the entire history. Establish the log now and start recording decisions from this change forward. If a few foundational past decisions are still load-bearing and undocumented, you can offer to capture them as ADRs dated to today with a note that they record a prior decision — but only if the user wants that; don't balloon the task.

**Non-code repos / infra-as-code / data platforms.** ADRs apply anywhere significant technical decisions are made — Terraform layouts, data models, ML pipeline architecture. Same rules.
