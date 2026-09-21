# 0002: Use an immutable Stock Movement ledger

Status: Accepted

## Context

A displayed stock number is weak evidence unless a user can explain where it came from. Directly editing one balance also makes failures and corrections difficult to trace.

## Decision

Keep a current Stock on Hand value for efficient reads and create an immutable Stock Movement for every change. Complete multi-record stock operations inside database transactions. Correct completed records through explicit reversals instead of destructive edits.

## Consequences

- The current value can be reconciled with its history.
- Purchase, Sale, adjustment, and reversal services must enforce atomic invariants.
- The application stores more rows and requires deliberate reversal workflows.

### Canonical Demo Seeding Exception

The fictional Demo Business requires a fixed, historical demonstration period (August 2026) so that public evaluators can inspect coherent multi-week reports and CSV exports regardless of deployment date.

During `seed_demo_business()`, runtime services generate movements via standard domain logic, after which `core.demo` normalizes their `created_at` timestamps to the canonical August 2026 schedule using a private helper.

This exception:
- Is strictly owned by the canonical Demo seeding contract (`core.demo`) and executes atomically within the seed transaction.
- Scopes all updates explicitly to `business=business` for the named fictional Demo Business.
- Is strictly prohibited from application views, public domain services, and non-demo records.
- Does not weaken normal application Stock Movement immutability or runtime invariants (INV-02, INV-04), because normal application paths cannot update them and the private Demo normalization helper is explicitly scoped to the named Demo Business.
