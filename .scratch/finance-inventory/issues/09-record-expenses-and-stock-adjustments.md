# 09: Record Expenses and Stock Adjustments

**What to build:** Let Owners and Staff Members record operating Expenses and explained stock corrections, preserving financial and stock history through void-and-replace or immutable movements.

**Blocked by:** 03: Create Products with traceable opening stock; 05: Add Staff Members with enforced permissions.

**Status:** ready-for-agent

- [ ] An Expense uses the approved fields, controlled categories, decimal-safe validation, and a recorded or voided state.
- [ ] Correcting an Expense uses an explicit void-and-replace flow and preserves Audit Events.
- [ ] A Stock Adjustment uses a controlled reason, signed whole-unit change, notes, and a preview of resulting Stock on Hand.
- [ ] An adjustment that would make Stock on Hand negative is rejected inside the locked transaction.
- [ ] A successful adjustment atomically updates Stock on Hand and creates its Stock Movement and Audit Event.
- [ ] Lists and details remain scoped to the current Business and support useful date/status filters.
- [ ] Tests cover both roles, categories/reasons, invalid values, rollback, isolation, and historical preservation.
