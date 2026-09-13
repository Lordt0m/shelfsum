# 09: Record Expenses and Stock Adjustments

**What to build:** Let Owners and Staff Members record operating Expenses and explained stock corrections, preserving financial and stock history through void-and-replace or immutable movements.

**Blocked by:** 03: Create Products with traceable opening stock; 05: Add Staff Members with enforced permissions.

**Status:** complete

- [x] An Expense uses the approved fields, controlled categories, decimal-safe validation, and a recorded or voided state.
- [x] Correcting an Expense uses an explicit void-and-replace flow and preserves Audit Events.
- [x] A Stock Adjustment uses a controlled reason, signed whole-unit change, notes, and a preview of resulting Stock on Hand.
- [x] An adjustment that would make Stock on Hand negative is rejected inside the locked transaction.
- [x] A successful adjustment atomically updates Stock on Hand and creates its Stock Movement and Audit Event.
- [x] Lists and details remain scoped to the current Business and support useful date/status filters.
- [x] Tests cover both roles, categories/reasons, invalid values, rollback, isolation, and historical preservation.

## Comments

- Added scoped Expense recording, detail/history filters, audited voiding, and linked void-and-replace correction. Recorded and voided rows are immutable; new rows cannot begin voided.
- Added write-free manual adjustment preview and atomic recording with fresh Product locking, signed whole-unit validation, negative-stock protection, immutable provenance, and audit history. Opening stock is internal to Product creation, not a manual override.

## Completion record

- **Public implementation:** `707677a` (repairs), following `f4a3b3e` (feature).
- **Delivered behavior:** active Owners and Staff Members can record and inspect operating Expenses and explained manual stock corrections; history remains Business-scoped, with Demo writes denied and POST/CSRF protection.
- **Protected interfaces/invariants:** IF-03 and IF-10 distinguish opening and manual stock; INV-01 through INV-06 remain enforced. Expense correction and stock/audit writes roll back together, and persisted origin records determine provenance.
- **Verification on 2026-09-14:** 42 focused tests passed; coordinator full suite ran 140 tests, OK with one PostgreSQL-only concurrency test skipped on SQLite (139 executed). Django check, migration drift check, and whitespace check passed.
- **Independent review:** Standards and Spec axes passed at `707677a` against base `8a28ef3`, after repairs removed the public opening override and rejected direct voided Expense creation. Optional helper-flag and parameter/dictionary smells were judged non-blocking.
- **Documentation/demo impact:** README capability wording and module map updated; approved Expense/adjustment and future dashboard formulas are explicit in the specification. Stable seeded Demo remains Ticket 12, not a claim of this slice.
- **Remaining release risk:** SQLite does not prove PostgreSQL row-lock interleavings; Ticket 13 must run PostgreSQL concurrency proof, including Purchase lifecycle scenarios. Reopen for new stock, lifecycle, provenance, permission, or migration changes.
- **Next dependency:** Ticket 10, explainable Business dashboard. Begin with request-level tests using known decimal totals, inclusive Africa/Lagos month boundaries, voided exclusions, cost snapshots, and Business isolation.
