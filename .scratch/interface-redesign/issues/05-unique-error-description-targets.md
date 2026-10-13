# Unique validation error description targets

Status: complete

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

## Completion record

- Public repair ref: bd734e1d3c207c6b0fa407a18554b5d8fb646c24, on codex/interface-verification. Main and production are unchanged.
- Delivered one ErrorList description target per invalid field in shared forms and Business settings. No business-rule, data or authorization changes.
- Proof: both regressions failed before repair; all 16 interface tests pass; Django check and diff check pass. Repaired ref passed 287 PostgreSQL tests with zero skips and all release gates in GitHub Actions run 38471782585.
- Hosted proof: separate free staging deploy of bd734e1 at https://shelfsum-ui-verification.onrender.com; 56 HTTP workflow checks passed, including unique invalid-Amount ID/reference. Hosted stock HTML/CSV values and six retained movement rows agree after completion and reversals.
- Review: inspected the minimal template/test diff against repository standards; original browser audit found the duplicate-ID cause; removed only wrapper IDs and retained Django's native ErrorList IDs. No independent review was run because the change does not alter release configuration or protected backend invariants.
- Documentation/demo impact: this ticket records the repair; canonical read-only demo data remains unchanged. Fictional writable test records exist only in the authorised staging database.
- Remaining verification limits: actual invalid-form/row-change speech was not observed. Final writable Owner browser audit was interrupted by browser permission denial; user instructed completion with existing results. Request/response regressions and hosted HTTP error checks pass. Reopen if a field description loses its native ErrorList target or a screen-reader regression is observed.
- Next dependency: any future production release should use the repaired ref and complete the remaining screen-reader checks and a staging restart/persistence cycle first.

## Final verification disposition

The user authorised committing the accurate record despite the unresolved final browser permission block. See [verification record](../verification.md) for the completed gates and explicit remaining limits. The validation repair is complete; the final browser audit and production release are not claimed as complete. No runtime files changed in this documentation closure.
