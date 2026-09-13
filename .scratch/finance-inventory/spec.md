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

## Expense and adjustment record contract

- Expenses capture date, controlled category, description, positive decimal amount, notes, Business, and actor. First-release categories are Rent, Utilities, Transport, Maintenance, Supplies, and Other; no category administration is included.
- An Expense is recorded or voided. Correction preserves the original financial meaning and its audit history and creates a linked replacement rather than editing or deleting the original.
- Manual Stock Adjustments capture Product, signed nonzero whole-unit quantity change, controlled reason, notes, Business, and actor. Reasons use the existing Damage, Missing, Found, and Count correction choices; Opening stock remains the Product-creation workflow.
- Adjustment forms preview resulting Stock on Hand. The stock service rechecks the locked balance and rejects negative stock, then atomically writes the adjustment, movement, stock update, and Audit Event.

## Explainable summary contract

- The default reporting period is the current calendar month in Africa/Lagos. Date boundaries are inclusive and apply to the recorded Sale or Expense date.
- Sales revenue is the sum of quantity multiplied by selling price for lines belonging to completed, non-void Sales in the period.
- Recorded Expenses are the sum of amounts for recorded, non-void Expenses in the period; a correction contributes only its recorded replacement.
- Estimated cost of goods sold is the sum of Sale-line quantity multiplied by its completion-time unit-cost snapshot for completed, non-void Sales in the period. Later Product cost changes do not rewrite this estimate.
- Estimated Profit is Sales revenue minus estimated cost of goods sold minus recorded Expenses. Label it as an operational estimate, not accounting, tax, or cash profit.
- Current stock value is the sum of current Stock on Hand multiplied by the current Product unit-cost estimate for active and inactive Products with positive stock. It is a current balance, not a historical period valuation.
- Dashboard summaries link to explanatory records or reports; voided history remains inspectable but contributes nothing to period totals.

## Quality rules

- Implement one vertical ticket at a time with a failing behaviour test first.
- Cover ownership isolation, role permissions, Demo Business protection, invalid input, and transactional failure paths.
- Keep core workflows usable without JavaScript and accessible at mobile widths.
- Require PostgreSQL verification before deployment while retaining SQLite for the local loop.
- Keep runtime behaviour independent of an AI model and paid API.

## Out of scope

Payments, invoicing, payroll, tax accounting, multicurrency, fractional quantities, multiple Businesses per user, forecasting, barcodes, external catalogue integrations, and AI-dependent features.

## Tickets

Numbered implementation tickets live in `.scratch/finance-inventory/issues/` and are the sole mutable delivery plan. They are executed in dependency order unless a ticket explicitly states otherwise. Every completed ticket retains the concise proof and handoff record required by `docs/agents/issue-tracker.md` so the repository can be resumed without private programme context.
