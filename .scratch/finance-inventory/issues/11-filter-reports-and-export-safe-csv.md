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
