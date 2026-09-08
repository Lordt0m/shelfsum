# ShelfSum repository guidance

## Agent skills

- Issue tracker: local Markdown files under `.scratch/`. Read `docs/agents/issue-tracker.md` before creating, updating, or closing tickets.
- Triage labels: use the canonical statuses in `docs/agents/triage-labels.md`.
- Domain documentation: read `CONTEXT.md` and relevant records under `docs/adr/` before changing product behaviour. See `docs/agents/domain.md`.

## Product boundary

ShelfSum is a server-rendered Django application for a small-shop Owner and Staff Members to understand Products, Stock on Hand, Purchases, Sales, Expenses, and operational estimates.

Keep the application focused on the accepted MVP. Payments, payroll, tax, multicurrency, forecasting, barcodes, multiple Businesses per user, and AI-dependent behaviour are outside the product boundary.

## Phase workflow

- Start every phase-based plan with a phase that reads this file and updates it when repository-wide guidance has changed.
- Work in one vertical ticket at a time: understand, inspect, plan, write one failing behaviour test, implement the smallest passing slice, verify, review against standards and the ticket, explain, then commit.
- Keep public claims evidence-backed. A feature is complete only when its behaviour, tests, documentation, and demonstration state agree.
- Use small truthful commits and preserve unrelated work.

## Commands

- Create environment: `py -3.13 -m venv .venv`
- Install: `.venv\Scripts\python -m pip install -r requirements.txt`
- Run: `.venv\Scripts\python manage.py runserver`
- Test: `.venv\Scripts\python manage.py test`
- Check: `.venv\Scripts\python manage.py check`

## Engineering rules

- Target Python 3.13 and the latest Django 5.2 LTS patch recorded in `requirements.txt`.
- Keep SQLite as the lightweight local default. PostgreSQL release verification becomes mandatory before deployment.
- Test the Django request/response boundary for user-visible behaviour. Add a public service seam only for transactional stock operations that need exact invariant tests.
- Scope every Business-owned lookup through the authenticated user's membership before resolving record identifiers.
- Enforce permissions and Demo Business read-only rules on the server.
- Use decimal arithmetic for money and whole numbers for quantities.
- Keep state-changing requests on POST with CSRF protection.
- Prefer explicit services over model signals for multi-record stock and audit behaviour.
- Keep templates usable without JavaScript; use JavaScript as progressive enhancement.
- Never commit secrets, real shop records, local databases, virtual environments, or generated static assets.

## Verification

- Run the focused test after every red-green slice.
- Run `manage.py check` and the complete test suite before review.
- Review changes against this file and the active ticket before committing.
- Document commands only after executing them successfully from a clean-enough local state.
