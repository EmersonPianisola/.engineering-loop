# Architecture Decision Records

This directory holds the project's Architecture Decision Records (ADRs): one file per
architecturally-significant decision, capturing the context, the options considered,
the choice made, and the consequences accepted.

See <https://adr.github.io/> for background.

## Conventions

- **Filename**: `NNNN-kebab-case-title.md`, e.g. `0007-use-postgres-for-billing.md`.
- **Numbering**: zero-padded, sequential, never reused — even for superseded records.
- **Format**: [MADR](https://adr.github.io/madr/) by default; the lighter Nygard format
  is fine for small-but-real decisions.
- **Status**: `proposed` → `accepted` → (`deprecated` | `superseded by ADR-NNNN`).
- **Immutable**: accepted ADRs are not rewritten to change a decision. A new decision
  gets a new ADR that supersedes the old one; the old one's status is updated to point
  at it.

## Adding one

Copy the newest ADR or a template, take the next number, fill in every section with
specifics (not placeholders), and commit it in the same change as the code it explains.
