# ShelfSum

ShelfSum is a focused stock and daily-business record for a small-shop Owner and Staff Member team. It is being built as a server-rendered Django application with traceable Stock Movements, clear permissions, explainable operational figures, and behaviour-focused tests.

The current foundation provides the product landing page and a deployment health response. Later vertical slices add identity and Business isolation, Products and opening stock, Purchases, Sales, Expenses, Stock Adjustments, reports, Audit Events, fictional demonstration data, and deployment.

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

Tests exercise public behaviour through Django's request/response boundary. Transactional stock workflows will add a separate public service seam when those slices are implemented.

## Demonstration access

A later milestone will provide a read-only Demo Business containing only fictional data. Registration will create isolated writable data; the application will not depend on the developer's computer or an AI model at runtime.

## Working decisions

- Completed stock-affecting records will be immutable and corrected by explicit reversal workflows.
- Stock on Hand will be fast to read while an immutable Stock Movement history explains every change.
- Monetary values will use decimal arithmetic and quantities will use whole units in the first release.
- The deployed application will use PostgreSQL and keep durable data off the web service's filesystem.

See [AGENTS.md](AGENTS.md) for the repository workflow and verification expectations.
