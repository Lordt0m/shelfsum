# 04: Maintain and find Products

**What to build:** Let Business users maintain catalogue details, deactivate Products safely, and find Products by search, active state, and low-stock state without damaging historical records.

**Blocked by:** 03: Create Products with traceable opening stock.

**Status:** in-progress

- [x] Permitted catalogue fields can be updated while Stock on Hand remains protected.
- [x] Deactivation preserves movement history and removes the Product from new stock-affecting choices.
- [x] Product search matches name or SKU within the current Business only.
- [x] Active and low-stock filters are bookmarkable and correctly handle the threshold boundary.
- [x] Empty, no-result, inactive, and low-stock states are clear on small and large screens.
- [x] Tests cover editing, deactivation, filter combinations, Business isolation, and forbidden direct quantity changes.

## Comments

- 2026-09-08: Implementation began after Ticket 03 passed final standards and specification review.
- 2026-09-08: Catalogue update/deactivation services and bookmarkable filters implemented. Thirty-three full-suite tests pass; review pending.
