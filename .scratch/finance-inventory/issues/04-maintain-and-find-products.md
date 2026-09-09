# 04: Maintain and find Products

**What to build:** Let Business users maintain catalogue details, deactivate Products safely, and find Products by search, active state, and low-stock state without damaging historical records.

**Blocked by:** 03: Create Products with traceable opening stock.

**Status:** complete

- [x] Permitted catalogue fields can be updated while Stock on Hand remains protected.
- [x] Deactivation preserves movement history and removes the Product from new stock-affecting choices.
- [x] Product search matches name or SKU within the current Business only.
- [x] Active and low-stock filters are bookmarkable and correctly handle the threshold boundary.
- [x] Empty, no-result, inactive, and low-stock states are clear on small and large screens.
- [x] Tests cover editing, deactivation, filter combinations, Business isolation, and forbidden direct quantity changes.

## Comments

- 2026-09-08: Implementation began after Ticket 03 passed final standards and specification review.
- 2026-09-08: Catalogue update/deactivation services and bookmarkable filters implemented. Thirty-three full-suite tests pass; review pending.
- 2026-09-08: Review requested mandatory Business scope on stock-activity choices, Demo mutation regressions, atomic audit proof, and accurate edit copy. All were addressed; thirty-six tests pass. Fix verification pending.
- 2026-09-09: Fresh standards and specification reviews requested direct service-boundary proof, cross-Business service proof, low-stock-specific empty-state evidence, and an explicit staged stock-choice seam. The regressions and copy were added; both review axes then passed.

## Completion record

- Public refs: feature `3a08b6d`; review repairs `67e8cd4`.
- Delivered: Business-scoped Product editing, safe deactivation, name/SKU search, active/inactive and low-stock filters, protected Stock on Hand, audit records, and clear empty states.
- Invariants and interfaces: INV-01 Business isolation, INV-02 movement-backed Stock on Hand, INV-03 audit rollback, INV-05 Demo write protection, and IF-02/IF-04/IF-05 in `docs/agents/module-map.md`.
- Verification: 39 tests passed; `manage.py check` reported no issues; `makemigrations --check --dry-run` reported no changes; `git diff --check` reported no whitespace errors.
- Review: independent fresh-context standards and specification passes completed after all actionable findings were repaired.
- Staged integration: no Purchase, Sale, or Stock Adjustment choice interface exists yet. Tickets 06, 07, and 09 must consume `Product.objects.available_for_stock_activity(business=...)` so inactive or cross-Business Products cannot enter new stock activity.
- Documentation/demo impact: catalogue behaviour is recorded in the README; no demo-data change yet.
- Reopen triggers: changes to Product mutation, Business access, Demo write policy, stock-activity selection, audit transactions, or catalogue filters.
- Next dependency: Ticket 05. Begin with the Owner request boundary for adding an already registered, unassigned user as a Staff Member.
