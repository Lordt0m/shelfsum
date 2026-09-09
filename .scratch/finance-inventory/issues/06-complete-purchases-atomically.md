# 06: Complete Purchases atomically

**What to build:** Let Owners and Staff Members draft and complete multi-line Purchases that increase Stock on Hand, update cost estimates, create Stock Movements, and remain immutable once completed.

**Blocked by:** 03: Create Products with traceable opening stock; 05: Add Staff Members with enforced permissions.

**Status:** ready-for-agent

- [ ] A Purchase captures the approved header fields and one or more valid active-Product lines.
- [ ] The form shows line totals and a document total and handles add/remove line interaction without making JavaScript mandatory.
- [ ] Duplicate Product lines and invalid quantities or costs are rejected clearly.
- [ ] Completion locks affected Products in deterministic order and atomically updates Stock on Hand, current unit-cost estimates, Stock Movements, status, and Audit Event.
- [ ] Completed Purchases and lines cannot be edited or completed twice.
- [ ] Purchase list and detail pages support date and status filtering within the current Business.
- [ ] Service and request tests cover Owner and Staff Member success, invalid forms, rollback, isolation, and repeated completion.
