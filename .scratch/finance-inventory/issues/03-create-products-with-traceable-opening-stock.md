# 03: Create Products with traceable opening stock

**What to build:** Let an Owner create, list, and inspect Products while any opening quantity flows through a Stock Adjustment and immutable Stock Movement so Stock on Hand is explainable from the first record.

**Blocked by:** 02: Register an Owner and create a Business.

**Status:** in-progress

- [x] A Product records the approved catalogue fields, decimal prices, whole-unit Stock on Hand, low-stock threshold, and active state.
- [x] Product names and non-empty SKUs are unique within a Business but reusable by another Business.
- [x] Creating a Product with opening quantity atomically creates the opening Stock Adjustment, Stock Movement, Stock on Hand value, and Audit Event.
- [x] Negative money, negative opening stock, and ambiguous duplicate identifiers produce useful form errors.
- [x] Product list and detail pages expose current values and movement history without permitting direct Stock on Hand edits.
- [x] Request and service tests cover the successful tracer path, zero opening quantity, invalid data, isolation, and atomic rollback.

## Comments

- 2026-09-08: Implementation began after Ticket 02 passed its repaired standards and specification gates.
- 2026-09-08: Implementation and documentation complete. Twenty-six full-suite tests pass; standards and specification review pending.
- 2026-09-08: Review found bypassable ORM immutability, editable Stock Adjustments, premature origin states, and incomplete late-failure rollback coverage. The ORM mutation boundary, ledger schema, migration, and tests were tightened; all twenty-eight tests now pass. Fix verification pending.
- 2026-09-08: Follow-up review rejected a destructive transitional migration and requested direct bulk-update evidence. Because the product is unreleased, the correct required-origin schema now lives in the initial migration; the destructive migration was removed and bulk update is covered.
