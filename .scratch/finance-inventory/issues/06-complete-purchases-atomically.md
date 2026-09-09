# 06: Complete Purchases atomically

**What to build:** Let Owners and Staff Members draft and complete multi-line Purchases that increase Stock on Hand, update cost estimates, create Stock Movements, and remain immutable once completed.

**Blocked by:** 03: Create Products with traceable opening stock; 05: Add Staff Members with enforced permissions.

**Status:** complete

- [x] A Purchase captures the approved header fields and one or more valid active-Product lines.
- [x] The form shows line totals and a document total and handles add/remove line interaction without making JavaScript mandatory.
- [x] Duplicate Product lines and invalid quantities or costs are rejected clearly.
- [x] Completion locks affected Products in deterministic order and atomically updates Stock on Hand, current unit-cost estimates, Stock Movements, status, and Audit Event.
- [x] Completed Purchases and lines cannot be edited or completed twice.
- [x] Purchase list and detail pages support date and status filtering within the current Business.
- [x] Service and request tests cover Owner and Staff Member success, invalid forms, rollback, isolation, and repeated completion.

## Comments

- Implemented Purchase and PurchaseLine models, server-rendered draft formsets, Business-scoped list/detail/edit routes, and transactional completion. StockMovement supports PurchaseLine origins while retaining adjustment origins.
- Added request and service coverage for Owner and Staff success, no-JavaScript form rows, invalid/duplicate/inactive/cross-Business input, Demo and inactive denial, deterministic Product ordering, provenance, replay, bulk mutation denial, rollback seams, generator-backed bulk writes, and stock reconciliation.
- Independent specification and standards reviews passed after repairs closed cross-Business provenance and one-shot iterable bypasses.

## Completion record

- **Public implementation:** `1aa5267` (`feat: complete purchases atomically`).
- **Delivered behavior:** Owners and active Staff Members can create, edit, list, filter, inspect, and atomically complete Business-scoped multi-line Purchases. Completion updates inventory and cost, writes immutable provenance-linked Stock Movements and an Audit Event, and cannot be replayed.
- **Protected invariants:** Business ownership is enforced for Purchases, lines, Products, and ledger origins; Purchase and PurchaseLine completion state is immutable through instance and bulk ORM paths; movement provenance matches Business, Product, quantity, origin kind, and completed Purchase state.
- **Verification:** 74 tests pass; Django system check is clean; migration drift check reports no changes; diff whitespace check is clean.
- **Review:** independent specification and standards axes both passed after repair.
- **Deferred release evidence:** PostgreSQL-specific concurrent completion behavior remains a release-environment verification item.
- **Next seam:** Ticket 07 begins with failing service tests for atomic Sale completion, stock availability, and unit-cost snapshot behavior.
