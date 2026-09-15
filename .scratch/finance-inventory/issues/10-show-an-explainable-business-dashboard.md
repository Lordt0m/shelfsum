# 10: Show an explainable Business dashboard

**What to build:** Give Owners and Staff Members a current-month operational dashboard showing explainable money summaries, current stock value, low-stock count, and recent activity.

**Blocked by:** 06: Complete Purchases atomically; 07: Complete Sales with availability protection; 09: Record Expenses and Stock Adjustments.

**Status:** complete

- [x] The default period is the current calendar month using the Africa/Lagos Business rule.
- [x] Revenue, recorded Expenses, estimated cost of goods sold, Estimated Profit, and current stock value follow the specification's formulas.
- [x] Estimated Profit is visibly labelled as an estimate and links to its explanation.
- [x] Voided records are excluded and inclusive period boundaries are correct.
- [x] Low-stock count and recent activity link to the records that explain them.
- [x] Empty and populated dashboards remain usable on small screens.
- [x] Tests reconcile representative summary values against underlying records and verify role access and Business isolation.

## Comments

- The dashboard covers the full current Africa/Lagos calendar month. It deliberately includes future-dated records within that month because the records themselves carry the operational date.
- Recent activity selects the newest eight supported, linkable Business audit events. Membership audit events remain available for Ticket 12's complete audit browser rather than appearing without an explanatory destination.

## Completion record

- **Public implementation:** `0628c8e` (traceability repairs), following `f8be947` (feature); this closure record completes the ticket.
- **Delivered behavior:** active Owners and Staff Members, including Demo users on the read path, receive an explainable Business home dashboard with current-month revenue, Expenses, estimated cost of goods sold and Profit, current stock value, low-stock count, and linked recent activity.
- **Protected interfaces/invariants:** IF-11 composes scoped recorded facts without duplicating transaction rules. Voided Sales and Expenses contribute nothing; Sale cost snapshots remain historical; current stock value uses positive current balances and current Product costs for active and inactive Products; cross-Business records remain excluded.
- **Verification on 2026-09-15:** nine focused dashboard tests passed; coordinator full suite ran 149 tests, OK with one PostgreSQL-only concurrency test skipped on SQLite (148 executed). Django check, migration drift check, and whitespace check passed.
- **Independent review:** initial Standards and Spec reviews found an unlinked membership activity case and a non-reconciliable stock-value destination. Repairs filter recent activity to linkable types and render deterministic Product-level stock equations. Fresh re-reviews found no runtime, formula, isolation, security, architecture, or product-behavior defect; both axes required only this tracker closure record.
- **Documentation/demo impact:** README current-capability wording and IF-11 in the module map describe the dashboard. Existing seeded data remains unchanged; a stable seeded Demo and the complete audit browser remain Ticket 12.
- **Remaining release risk:** local SQLite verification does not prove PostgreSQL-specific behavior or deployment. Reopen for changes to dashboard formulas, month-boundary semantics, status rules, Business isolation, or explanatory destinations.
- **Next dependency:** Ticket 11, filtered reports and spreadsheet-safe CSV. Begin with request-level tests for one shared, Business-scoped report query whose HTML and CSV paths preserve identical inclusive filters and neutralize formula-leading text.
