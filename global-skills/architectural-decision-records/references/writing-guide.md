# Writing guide: what makes an ADR useful

An ADR is only worth the disk it sits on if a future engineer can read it and understand *why*, well enough to either trust the decision or safely change it. Placeholder-grade ADRs ("we chose X because it's better") are worse than none — they imply reasoning happened when it didn't. The quality lives almost entirely in three sections.

## Context and Problem Statement

State the forces as **facts**, value-neutrally, so a reader can later check whether they still hold. Include the constraints that actually bounded the choice: scale numbers, latency budgets, team skills, deadlines, existing systems, compliance requirements. A good context makes the eventual decision feel almost inevitable; a bad one is a vague gesture at "scalability."

- Weak: "We need to store data and want it to scale."
- Strong: "The billing service must record ~4k transactions/sec at peak with strict read-after-write consistency for a customer's own ledger. The team operates Postgres today and has no Cassandra experience. We cannot add a new on-call surface this quarter."

## Decision Drivers

The specific qualities/forces the decision optimizes for, pulled out as a list so the trade-off is legible. These are the criteria you'll judge the options against. If a driver wouldn't change the answer, it's not a real driver — cut it.

## Considered Options and their Pros/Cons

Name **at least two** genuinely-considered options. One option means the decision looks unconsidered — even if the answer was obvious, record the obvious alternative and why it lost. For each option, give the honest goods and bads *against the drivers above*. The reader should be able to see that you understood the option you rejected, not strawmanned it.

## Decision Outcome and Consequences

State the choice plainly and tie the justification back to a driver ("because it's the only option meeting the read-after-write requirement without new ops load"). Then record consequences **including the ones you don't like** — the latency you're accepting, the coupling you're introducing, the migration debt you're taking on. An ADR that lists only benefits is not believed, because every real decision has a cost, and hiding it just means the reader has to rediscover it the hard way.

## Worked example: before → after

**Before (useless):**

> ## Context
> We need a database for the new service.
> ## Decision
> We will use PostgreSQL because it is reliable and well-supported.
> ## Consequences
> The service will have a database.

This records nothing. Any datastore is "reliable and well-supported"; there's no driver, no alternative, no cost — so the next engineer learns nothing and can't tell whether revisiting is safe.

**After (useful, Nygard format):**

> ## Context
> The billing ledger service must guarantee read-after-write consistency for each
> customer's own transactions and sustain ~4k writes/sec at peak. The team runs
> Postgres in three other services and has no operational experience with wide-column
> stores. Adding a new datastore type would mean a new on-call runbook and backup
> strategy, which we've committed not to take on this quarter.
>
> ## Decision
> We will use PostgreSQL (single primary, synchronous replica) for the billing ledger.
> We will revisit if sustained write volume exceeds ~15k/sec, at which point sharding
> or a different store becomes worth the operational cost.
>
> ## Consequences
> Good: reuses existing ops tooling, backups, and team expertise; gives us the strong
> consistency the ledger requires out of the box.
> Bad: a single primary caps write throughput; we are accepting a known ceiling and an
> explicit revisit trigger rather than designing for horizontal write scale now.
> Neutral: couples the billing service to the team's Postgres operational standards.

The second version tells a future engineer exactly what was true, what was chosen, what it costs, and when to reconsider. That's the bar.

## Common failure modes to avoid

- **Placeholder consequences** ("the system will work"). Say what actually changes.
- **One option.** Always show at least one real alternative and why it lost.
- **Only upsides.** Every decision has a cost; name it.
- **Feature-titled ADRs** ("0007-billing-service.md"). Title the *decision*.
- **Restating the code.** The ADR captures *why*, not a description of the implementation.
- **Boiling the ocean.** One decision per ADR. Split bundled choices.
