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
