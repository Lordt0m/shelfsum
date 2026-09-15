# 11: Filter reports and export safe CSV

**What to build:** Let Business users inspect date-filtered Sales, Purchases, Expenses, stock position, and Product movement reports and export exactly the active result set as spreadsheet-safe CSV.

**Blocked by:** 06: Complete Purchases atomically; 07: Complete Sales with availability protection; 09: Record Expenses and Stock Adjustments.

**Status:** ready-for-agent

- [ ] Each report has a clear purpose, useful columns, totals where meaningful, and inclusive start/end filters preserved in the URL.
- [ ] Completed, voided, and active-state rules match the specification and dashboard formulas.
- [ ] CSV exports reuse the report query and filters and expose explicit stable headings.
- [ ] Exported text beginning with `=`, `+`, `-`, or `@` is neutralized against spreadsheet formula execution.
- [ ] Naira and decimal values remain machine-readable without losing precision.
- [ ] Empty, invalid-range, and cross-Business requests behave safely and clearly.
- [ ] Tests cover filters, boundaries, totals, headers, encoding, injection protection, permissions, and isolation.

## Comments

- Sales report slice accepted at `5de1c1d`, following `acb4416`. One Business-scoped result feeds the HTML and UTF-8 CSV presenters, defaults to the full current Africa/Lagos calendar month, preserves explicit one-sided or inclusive date filters, and exposes completed or voided history without including voided rows in active totals.
- Sales CSV uses stable headings, ISO dates, two-place machine-readable decimals, and apostrophe-prefixes formula-leading text. Twelve focused tests and the 161-test suite passed with one PostgreSQL-only concurrency test skipped on SQLite; fresh Standards and Spec reviews passed after default-period and malformed-date repairs.
- Ticket 11 remains open. Purchases, Expenses, stock position, and Product movement reports must reuse the proven filter/export boundary before completion.
- **Next slice contract - Purchases:** default to completed Purchases in the full current Africa/Lagos calendar month; allow explicit completed or voided inspection and explicit one-sided or inclusive date filters. Show Purchase date, immutable Purchase reference/ID link, supplier, status, and quantity-by-unit-cost total. Sum only displayed completed Purchase cost into the active total; retain voided row amounts for explanation while labelling them excluded from active totals. The CSV must use the identical scoped result, stable text and decimal columns, and the same formula-leading-text defence for supplier and reference values.
- The Purchase slice may extract only already-proven cross-report mechanics, especially CSV text neutralization and date-range parsing. Keep status rules, row meaning, and totals owned by each report so a generic abstraction cannot blur Sale revenue/COGS with Purchase cost. Prove Lagos defaults and UTC boundary, inclusive and one-sided dates, malformed/reversed filters, completed/voided behavior, HTML/CSV parity, formula safety, both roles, Demo reads, inactive/anonymous denial, Business isolation, and empty results before review.
