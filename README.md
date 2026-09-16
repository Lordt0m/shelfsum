# ShelfSum

ShelfSum is a focused stock and daily-business record for a small-shop Owner and Staff Member team. It is being built as a server-rendered Django application with traceable Stock Movements, clear permissions, explainable operational figures, and behaviour-focused tests.

The current application provides the product landing page, a deployment health response, email-based registration and authentication, one-Business membership enforcement, Owner-only Business settings, Staff Member management, Product and stock workflows, Purchase and Sale lifecycles, Expense correction, an explainable operational dashboard, a dedicated Audit Event browser, and filterable Sales, Purchase, Expense, current stock-position, and Product-movement reports with spreadsheet-safe CSV exports. Later vertical slices add fictional demonstration data and deployment.

## Current behaviour

- A visitor can register and sign in using a unique email address.
- Email storage and sign-in are case-insensitive.
- A newly registered person creates one Business and becomes its Owner.
- The database and request boundary prevent one person from belonging to a second Business.
- Business settings are available only to the Owner; Staff Member requests are rejected on the server.
- An Owner can add an already registered, unassigned person as a Staff Member by email, then list or deactivate Staff Members.
- Membership changes are Owner-only, Business-scoped, audited, and unavailable for the read-only Demo Business.
- Deactivation retains the person and their Audit Event attribution while immediately blocking their Business access.
- Password changes and POST-only sign-out use Django's authenticated session flow.
- Product names and non-empty SKUs are case-insensitively unique inside one Business and reusable by another Business.
- A positive opening quantity creates a Stock Adjustment and immutable Stock Movement in the same transaction as the Product and Audit Event.
- A zero opening quantity creates no meaningless zero movement; the Product begins at zero and its creation remains recorded by an Audit Event.
- Product pages are resolved inside the current membership's Business and never expose Stock on Hand as an editable field.
- Approved catalogue details can be edited without changing Stock on Hand or movement history.
- Deactivated Products keep their history and are excluded from new stock-activity choices.
- Product search and active/low-stock filters are combined in bookmarkable query parameters; the low-stock boundary is inclusive.
- Owners and active Staff Members can draft, edit, filter, and complete multi-line Purchases using server-rendered forms that remain usable without JavaScript.
- Completing a Purchase deterministically locks its Products, updates Stock on Hand and current unit costs, writes one immutable Purchase-origin Stock Movement per line, and records an Audit Event in one transaction.
- Completed and voided Purchases and their lines reject edits, deletion, bulk ORM mutation, new-line insertion, and repeated completion or voiding. A one-time void confirmation applies one immutable reversal Stock Movement per original movement, rejects a negative resulting Stock on Hand, and leaves current Product unit cost unchanged.
- Owners and active Staff Members can draft, edit, list, filter, inspect, and complete multi-line Sales using server-rendered forms that remain usable without JavaScript.
- Completing a Sale deterministically locks its Products, rechecks Stock on Hand, snapshots each Product cost on its Sale line, decreases stock, writes one immutable Sale-origin Stock Movement per line, and records an Audit Event in one transaction.
- Owners and active Staff Members can record, list, filter, inspect, void, and correct Expenses with controlled categories, positive decimal amounts, immutable history, linked replacements, and audited lifecycle changes.
- Owners and active Staff Members can preview and record explained manual Stock Adjustments; locked validation prevents negative Stock on Hand and preserves an immutable movement and audit trail.
- Completed and voided Sales and their lines reject edits, deletion, bulk ORM mutation, new-line insertion, and repeated completion or voiding. A one-time void confirmation applies one immutable reversal Stock Movement per original movement and restores the sold quantities while preserving Sale cost snapshots.
- The Business home explains the full current Africa/Lagos calendar month with completed Sale revenue and cost snapshots, recorded Expenses, Estimated Profit, current stock value, active low-stock count, and recent scoped Audit Events linked back to their records.
- Owners and active Staff Members can inspect completed or voided Sales through inclusive date filters. The report shows completion-time cost estimates, excludes voided Sales from active totals, and exports exactly its active result set as UTF-8 CSV with formula-leading text neutralized.
- Owners and active Staff Members can inspect completed or voided Purchases through inclusive date filters. The report shows quantity-by-unit-cost totals, excludes voided Purchases from active totals, and exports exactly its active result set as UTF-8 CSV with formula-leading text neutralized.
- Owners and active Staff Members can inspect recorded or voided Expenses through inclusive date filters. The report shows recorded Expense totals, excludes voided originals from active totals while counting a recorded replacement once, and exports exactly its active result set as UTF-8 CSV with formula-leading text neutralized.
- Owners and active Staff Members can inspect a current stock-position snapshot for active, inactive, or all Products and positive, low, zero, or all stock states. It sums exactly the displayed quantity-by-current-unit-cost rows, includes inactive positive stock in its default total, and exports the identical result as UTF-8 CSV with formula-leading text neutralized. Current costs do not reconstruct historical inventory value.
- Owners and active Staff Members can inspect Product movements for a full or explicitly bounded Africa/Lagos local period, filter by movement kind and current-Business Product, see linked origins and voided-document reversals, and export the identical signed result as UTF-8 CSV with explicit Lagos offsets and formula-leading text neutralized.
- Owners and active Staff Members can inspect current-Business Audit Events, including deactivated actors, newest first; actor, action, and one-sided or inclusive Africa/Lagos date filters preserve invalid values without exposing records or choices from another Business. The browser is also available to read-only Demo Business members.

## Product boundary

ShelfSum will help a Business:

- keep a Product catalogue and explain Stock on Hand;
- record Purchases, Sales, Expenses, and Stock Adjustments;
- warn about low stock;
- inspect date-filtered reports and safe CSV exports;
- separate Owner controls from Staff Member work;
- preserve consequential actions in an Audit Event history.

It is not payment, payroll, tax, invoicing, forecasting, barcode, multicurrency, or AI software.

## Technical foundation

- Python 3.13
- Django 5.2 LTS
- Server-rendered HTML and CSS
- SQLite for the lightweight local loop
- PostgreSQL required for release verification and deployment
- Django's built-in test runner

## Local setup on Windows

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver
```

Open `http://127.0.0.1:8000/` for the landing page. The health response is available at `http://127.0.0.1:8000/health/`.

## Verification

```powershell
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py test
```

Tests exercise public behaviour through Django's request/response boundary. Transactional stock workflows use focused public service seams, including Product creation, Purchase and Sale completion, and Purchase and Sale voiding, for exact atomicity and ledger-invariant tests.

The active specification and vertical tickets are kept in [`.scratch/finance-inventory/`](.scratch/finance-inventory/). Product vocabulary and invariants are defined in [`CONTEXT.md`](CONTEXT.md), with consequential technical choices recorded under [`docs/adr/`](docs/adr/).

## Demonstration access

A later milestone will provide a read-only Demo Business containing only fictional data. Registration will create isolated writable data; the application will not depend on the developer's computer or an AI model at runtime.

## Working decisions

- Completed and voided stock-affecting records are immutable and corrected only by explicit one-time reversal workflows.
- Stock on Hand will be fast to read while an immutable Stock Movement history explains every change.
- Monetary values will use decimal arithmetic and quantities will use whole units in the first release.
- The deployed application will use PostgreSQL and keep durable data off the web service's filesystem.

## Module boundaries

- `businesses` owns membership-based access and the shared Demo Business write rule.
- `businesses` also owns the authenticated dashboard composition and its read-only, Business-scoped summary query.
- `catalogue` owns Products, their forms and pages, and Product-creation orchestration.
- `inventory` owns Stock Adjustments, immutable Stock Movements, and locked stock changes.
- `auditing` owns append-only Audit Events and the read-only, Business-scoped Audit Event browser.
- `purchases` owns draft Purchase entry and the transactional `complete_purchase` and `void_purchase` seams; Purchase-origin and reversal Stock Movements remain in `inventory`.
- `sales` owns draft Sale entry and the transactional `complete_sale` and `void_sale` seams; Sale-origin and reversal Stock Movements remain in `inventory`.
- `expenses` owns immutable Expense records, request forms, date/status filters, and audited void-and-replace correction workflows.
- `reports` owns read-only, Business-scoped report queries and their HTML and CSV presenters; Sales, Purchase, Expense, current stock-position, and Product-movement report modules own their filters, rows, and totals while shared date-range and CSV response mechanics live in `reports.filters` and `reports.csv`.

The public Product-creation service coordinates these modules inside one database transaction, which keeps the code a deployable Django monolith while making rollback behaviour directly testable.

See [AGENTS.md](AGENTS.md) for the repository workflow and verification expectations.
