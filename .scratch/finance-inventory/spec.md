# ShelfSum implementation specification

Status: ready-for-agent

## Outcome

Deliver a publicly accessible, server-rendered Django product that lets a small-shop Owner and Staff Members maintain Products, trace Stock on Hand, record Purchases, Sales, Expenses and Stock Adjustments, inspect explainable summaries, and safely explore a fictional read-only Demo Business.

## Release slices

1. Establish the project foundation.
2. Register an Owner and Business with isolated data.
3. Create Products with traceable opening stock.
4. Maintain and find Products.
5. Add Staff Members with enforced permissions.
6. Complete Purchases atomically.
7. Complete Sales with cost snapshots and stock protection.
8. Void completed stock records through reversals.
9. Record Expenses and Stock Adjustments.
10. Show an explainable dashboard.
11. Filter reports and export safe CSV files.
12. Deliver a stable Demo Business and useful audit history.
13. Deploy and publish truthful technical evidence.

## Product rules

- Manual record creation is the core workflow; no external API is required.
- One user owns at most one Business in the first release.
- Every Business-owned lookup is membership-scoped before object resolution.
- Owner-only permissions and Demo Business read-only behaviour are enforced on the server.
- Quantities are whole numbers. Money is decimal and uses one configured currency.
- Stock on Hand is fast to display and reconciles with immutable Stock Movements.
- Purchase and Sale completion, their lines, Stock Movements, and Audit Events succeed or fail atomically.
- Completed stock-affecting records are corrected with explicit reversals, not destructive edits.
- Estimated Profit is labelled as an operational estimate and is calculated from recorded revenue, cost snapshots, and Expenses.
- CSV exports prevent spreadsheet formula injection and respect active filters.

## Quality rules

- Implement one vertical ticket at a time with a failing behaviour test first.
- Cover ownership isolation, role permissions, Demo Business protection, invalid input, and transactional failure paths.
- Keep core workflows usable without JavaScript and accessible at mobile widths.
- Require PostgreSQL verification before deployment while retaining SQLite for the local loop.
- Keep runtime behaviour independent of an AI model and paid API.

## Out of scope

Payments, invoicing, payroll, tax accounting, multicurrency, fractional quantities, multiple Businesses per user, forecasting, barcodes, external catalogue integrations, and AI-dependent features.

## Tickets

Numbered implementation tickets live in `.scratch/finance-inventory/issues/`. They are executed in dependency order unless a ticket explicitly states otherwise.
