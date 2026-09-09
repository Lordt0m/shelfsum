# 08: Void completed stock documents

**What to build:** Let Business users correct completed Purchases and Sales through explicit voiding that creates reversing Stock Movements and preserves the original record.

**Blocked by:** 06: Complete Purchases atomically; 07: Complete Sales with availability protection.

**Status:** ready-for-agent

- [ ] A confirmation page explains the stock effect before voiding.
- [ ] Voiding a Purchase is rejected when reversing it would make any Product's Stock on Hand negative.
- [ ] Voiding a Sale restores its quantities.
- [ ] Each successful void locks affected Products, creates one reversal per original movement, updates Stock on Hand, changes status, and records an Audit Event atomically.
- [ ] A completed record can be voided only once and a voided record remains read-only.
- [ ] Tests cover success, insufficient-stock rejection, repeated requests, rollback, permissions, and reconciliation.
