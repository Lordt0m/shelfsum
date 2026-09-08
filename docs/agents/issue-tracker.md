# Issue tracker: Local Markdown

ShelfSum specifications and tickets live under `.scratch/` so the repository remains usable without a particular hosting service or model.

## Conventions

- One effort per directory: `.scratch/<feature-slug>/`.
- Keep the specification at `.scratch/<feature-slug>/spec.md`.
- Keep each ticket in `.scratch/<feature-slug>/issues/<NN>-<slug>.md`.
- Record triage state in a `Status:` line near the top of each ticket.
- Change a ticket to `complete` only after its acceptance checks, tests, documentation, and review agree.
- Append implementation notes under `## Comments`; do not erase useful decision history.

The public tracker contains product work only. Interview-defence notes, application plans, and personal coordination material belong outside this repository.
