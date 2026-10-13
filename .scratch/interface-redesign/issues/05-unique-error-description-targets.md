# Unique validation error description targets

Status: in-progress

## Problem

An automated accessibility audit of the Purchase error state found duplicate field-error IDs. The wrapper and Django's ErrorList both render the same ID, making aria-describedby references ambiguous. The shared field partial and Business settings use this pattern.

## Acceptance

- Keep exactly one error description target per invalid field.
- Preserve server-rendered errors, linked error summaries and keyboard recovery.
- Verify the request/response boundary for shared forms and Business settings.
- Run the focused tests and full PostgreSQL release checks before closure.

## Comments

Discovered during the user's authorised extended verification. No authorization, calculations, stock logic or database data changes are required.

Both request-boundary regressions failed with two matching error IDs before the repair. Removed the wrapper ID in both templates, retaining Django's ErrorList ID and aria-describedby reference. All 16 interface tests now pass. The original a3aabb5 passed 286 PostgreSQL tests locally with zero skips and GitHub release CI; the repaired ref will receive the same CI checks before staging acceptance.
