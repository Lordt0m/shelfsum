# ShelfSum

ShelfSum is a focused stock and daily-business record for a small-shop Owner and Staff Member team. It is being built as a server-rendered Django application with traceable Stock Movements, clear permissions, explainable operational figures, and behaviour-focused tests.

The current application provides the product landing page, a deployment health response, email-based registration and authentication, one-Business membership enforcement, an authenticated Business home, Owner-only Business settings, Staff Member management, Product creation with traceable opening stock, and draft-to-completed Purchases. Later vertical slices add Sales, Expenses, general Stock Adjustments, reports, an Audit Event browser, fictional demonstration data, and deployment.

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
- Completed Purchases and their lines reject edits, deletion, bulk ORM mutation, new-line insertion, and repeated completion; corrections remain reserved for a later explicit reversal workflow.

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

Tests exercise public behaviour through Django's request/response boundary. Transactional stock workflows use focused public service seams, including Product creation and Purchase completion, for exact atomicity and ledger-invariant tests.

The active specification and vertical tickets are kept in [`.scratch/finance-inventory/`](.scratch/finance-inventory/). Product vocabulary and invariants are defined in [`CONTEXT.md`](CONTEXT.md), with consequential technical choices recorded under [`docs/adr/`](docs/adr/).

## Demonstration access

A later milestone will provide a read-only Demo Business containing only fictional data. Registration will create isolated writable data; the application will not depend on the developer's computer or an AI model at runtime.

## Working decisions

- Completed stock-affecting records will be immutable and corrected by explicit reversal workflows.
- Stock on Hand will be fast to read while an immutable Stock Movement history explains every change.
- Monetary values will use decimal arithmetic and quantities will use whole units in the first release.
- The deployed application will use PostgreSQL and keep durable data off the web service's filesystem.

## Module boundaries

- `businesses` owns membership-based access and the shared Demo Business write rule.
- `catalogue` owns Products, their forms and pages, and Product-creation orchestration.
- `inventory` owns Stock Adjustments, immutable Stock Movements, and locked stock changes.
- `auditing` owns append-only Audit Events.
- `purchases` owns draft Purchase entry and the transactional `complete_purchase` seam; Purchase-origin Stock Movements remain in `inventory`.

The public Product-creation service coordinates these modules inside one database transaction, which keeps the code a deployable Django monolith while making rollback behaviour directly testable.

See [AGENTS.md](AGENTS.md) for the repository workflow and verification expectations.
