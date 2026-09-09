# 10: Show an explainable Business dashboard

**What to build:** Give Owners and Staff Members a current-month operational dashboard showing explainable money summaries, current stock value, low-stock count, and recent activity.

**Blocked by:** 06: Complete Purchases atomically; 07: Complete Sales with availability protection; 09: Record Expenses and Stock Adjustments.

**Status:** ready-for-agent

- [ ] The default period is the current calendar month using the Africa/Lagos Business rule.
- [ ] Revenue, recorded Expenses, estimated cost of goods sold, Estimated Profit, and current stock value follow the specification's formulas.
- [ ] Estimated Profit is visibly labelled as an estimate and links to its explanation.
- [ ] Voided records are excluded and inclusive period boundaries are correct.
- [ ] Low-stock count and recent activity link to the records that explain them.
- [ ] Empty and populated dashboards remain usable on small screens.
- [ ] Tests reconcile representative summary values against underlying records and verify role access and Business isolation.
