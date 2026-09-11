# 08: Void completed stock documents

**What to build:** Let Business users correct completed Purchases and Sales through explicit voiding that creates reversing Stock Movements and preserves the original record.

**Blocked by:** 06: Complete Purchases atomically; 07: Complete Sales with availability protection.

**Status:** complete

- [x] A confirmation page explains the stock effect before voiding.
- [x] Voiding a Purchase is rejected when reversing it would make any Product's Stock on Hand negative.
- [x] Voiding a Sale restores its quantities.
- [x] Each successful void locks affected Products, creates one reversal per original movement, updates Stock on Hand, changes status, and records an Audit Event atomically.
- [x] A completed record can be voided only once and a voided record remains read-only.
- [x] Tests cover success, insufficient-stock rejection, repeated requests, rollback, permissions, and reconciliation.

## Comments

- Added Business-scoped confirmation and POST-only void routes for completed Purchases and Sales. Purchase voids explain and validate stock removal; Sale voids explain stock restoration.
- Each void persists the protected VOIDED transition inside the transaction, creates one immutable reversal tied to each exact original movement, updates stock, and records an Audit Event. Purchase unit cost and Sale cost snapshots remain historical evidence.
- Independent specification and standards reviews passed after repairs blocked forged reversals, serialized Purchase draft edits with terminal transitions, hardened queryset/bulk mutation seams, and added enforced-CSRF and isolation coverage.

## Completion record

- **Public implementation:** `5f77f8e` (`feat: void stock documents with reversals`).
- **Delivered behavior:** Owners and active Staff Members can inspect the exact stock effect and void an eligible completed Purchase or Sale once; original documents and movements remain immutable and the correction is an explicit linked reversal.
- **Protected invariants:** reversal creation requires the originating document's persisted VOIDED state; origin Business/Product/quantity must match; one original has at most one reversal; Purchase negative stock is rejected; all status, stock, reversal, and audit effects roll back together.
- **Verification:** 110 tests pass with one existing PostgreSQL-only concurrency test skipped on SQLite; Django system check, migration drift/plan, and diff whitespace checks pass.
- **Review:** independent specification and standards axes both passed after repair.
- **Deferred release evidence:** run the PostgreSQL row-lock interleaving suite, including the equivalent Purchase edit/completion/void scenarios, before deployment.
- **Next seam:** Ticket 09 begins with failing service and request tests for auditable Expenses and additional manual Stock Adjustments.
