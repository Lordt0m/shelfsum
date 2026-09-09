# 07: Complete Sales with availability protection

**What to build:** Let Owners and Staff Members draft and complete multi-line Sales while preventing overselling, snapshotting costs, and recording the complete stock and audit effect atomically.

**Blocked by:** 03: Create Products with traceable opening stock; 05: Add Staff Members with enforced permissions.

**Status:** ready-for-agent

- [ ] A Sale captures the approved header fields and one or more valid active-Product lines.
- [ ] The form shows line totals and a document total and handles add/remove line interaction without making JavaScript mandatory.
- [ ] Duplicate Products, invalid quantities or prices, and quantities above Stock on Hand produce useful errors.
- [ ] Completion locks affected Products in deterministic order and rechecks availability inside the transaction.
- [ ] Completion atomically decreases Stock on Hand, snapshots unit cost, creates Stock Movements, changes status, and creates an Audit Event.
- [ ] Completed Sales and lines cannot be edited or completed twice.
- [ ] Sale list and detail pages support date and status filtering within the current Business.
- [ ] Service and request tests cover Owner and Staff Member success, unavailable stock, rollback, isolation, and repeated completion.
