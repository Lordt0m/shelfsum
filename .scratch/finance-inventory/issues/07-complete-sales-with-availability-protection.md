# 07: Complete Sales with availability protection

**What to build:** Let Owners and Staff Members draft and complete multi-line Sales while preventing overselling, snapshotting costs, and recording the complete stock and audit effect atomically.

**Blocked by:** 03: Create Products with traceable opening stock; 05: Add Staff Members with enforced permissions.

**Status:** complete

- [x] A Sale captures the approved header fields and one or more valid active-Product lines.
- [x] The form shows line totals and a document total and handles add/remove line interaction without making JavaScript mandatory.
- [x] Duplicate Products, invalid quantities or prices, and quantities above Stock on Hand produce useful errors.
- [x] Completion locks affected Products in deterministic order and rechecks availability inside the transaction.
- [x] Completion atomically decreases Stock on Hand, snapshots unit cost, creates Stock Movements, changes status, and creates an Audit Event.
- [x] Completed Sales and lines cannot be edited or completed twice.
- [x] Sale list and detail pages support date and status filtering within the current Business.
- [x] Service and request tests cover Owner and Staff Member success, unavailable stock, rollback, isolation, and repeated completion.

## Comments

- Implemented a server-rendered Sale workflow with Business-scoped draft, edit, list, filter, detail, and completion routes for Owners and active Staff Members.
- Sale completion and draft editing serialize on the Sale and ordered lines; completion then locks Products deterministically, rechecks availability, snapshots costs, decrements stock, writes exact immutable Sale-origin movements, changes status, and records the Audit Event in one transaction.
- Independent specification and standards reviews passed after repairs closed the stale-edit race, status-expression bypass, generator exhaustion, over-broad deletion, cached-origin provenance, and lock-order deadlock risks.

## Completion record

- **Public implementation:** `ee74a73` (`feat: complete sales with stock protection`).
- **Delivered behavior:** Owners and active Staff Members can create, edit, list, filter, inspect, and atomically complete Business-scoped multi-line Sales with useful stock-availability errors and no-JavaScript form controls.
- **Protected invariants:** completion is service-only and replay-safe; stock, cost snapshots, ledger movements, status, and audit succeed or roll back together; completed records are immutable; persisted SaleLine provenance matches Business, Product, and negative quantity; line queryset/bulk updates are deliberately instance-save-only.
- **Verification:** 91 tests pass with one PostgreSQL-only concurrency test skipped on SQLite; Django system check is clean; migration drift check reports no changes; migration plan and diff whitespace check are clean.
- **Review:** independent specification and standards axes both passed after repair.
- **Deferred release evidence:** execute the real edit/completion interleaving test on PostgreSQL before deployment.
- **Next seam:** Ticket 08 begins with failing service tests for explicit, atomic reversal of completed Purchases and Sales without mutating their original ledger history.
