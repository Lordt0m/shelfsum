# Issue tracker: Local Markdown

ShelfSum specifications and tickets live under `.scratch/` so the repository remains usable without a particular hosting service or model.

## Conventions

- One effort per directory: `.scratch/<feature-slug>/`.
- Keep the specification at `.scratch/<feature-slug>/spec.md`.
- Keep each ticket in `.scratch/<feature-slug>/issues/<NN>-<slug>.md`.
- Record triage state in a `Status:` line near the top of each ticket.
- Change a ticket to `complete` only after its acceptance checks, tests, documentation, and review agree.
- Append implementation notes under `## Comments`; do not erase useful decision history.
- Treat these tickets as the sole mutable ShelfSum delivery tracker. Do not rely on a private mirror for status or acceptance criteria.

## Completion record

Before setting a ticket to `complete`, append a compact `## Completion record` with:

- the closure commit or public ref;
- the delivered behaviour and affected interfaces or invariants;
- focused and full verification actually run, with exact outcomes;
- independent review findings and repairs;
- documentation or demo-data impact;
- unresolved risks or explicit reopen triggers;
- the next dependent ticket and its first safe action.

Preserve durable evidence and meaningful repairs, not raw command transcripts or tool narration.

The public tracker contains product work only. Interview-defence notes, application plans, and personal coordination material belong outside this repository.
