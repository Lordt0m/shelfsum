# 05: Add Staff Members with enforced permissions

**What to build:** Let an Owner add or deactivate an already registered Staff Member while both roles see only their Business and the server enforces owner-only controls.

**Blocked by:** 02: Register an Owner and create a Business.

**Status:** complete

- [x] An Owner can add an unassigned registered user by unique email as a Staff Member.
- [x] The flow rejects unknown users, the Owner's own email, duplicate membership, and users already assigned elsewhere.
- [x] The Owner can list and deactivate Staff Members while historical actor attribution remains intact.
- [x] Deactivated Staff Members lose Business access immediately.
- [x] Staff Members cannot manage membership or Business settings through navigation or crafted requests.
- [x] Tests exercise Owner and Staff Member access plus cross-Business identifiers for every available Business-owned screen.

## Comments

- 2026-09-09: Implementation added Owner-only, Business-scoped Staff Member list, add, and deactivate request paths plus an audited service seam. Focused access and catalogue isolation tests pass; full verification and coordinator review remain pending.
- 2026-09-09: Independent review identified a missing direct-service Demo denial proof for adding Staff Members. The regression now verifies both membership writes leave no membership or Audit Event side effects for the Demo Business; final coordinator review remains pending.
- 2026-09-09: Final two-axis review requested audit-failure rollback proof and Staff coverage across every Product endpoint. Both gaps were repaired; standards and specification re-reviews passed.

## Completion record

- Public ref: implementation `1fcd8a2`.
- Delivered: Owner-only Staff Member list, add-by-registered-email, and deactivation flows; transactional audited services; immediate inactive-access handling; Owner-only navigation and request enforcement.
- Invariants and interfaces: INV-01 Business isolation, INV-03 atomic audit behaviour, INV-05 Demo write protection, and IF-01/IF-02/IF-06 in `docs/agents/module-map.md`.
- Verification: 52 tests passed; `manage.py check` reported no issues; `makemigrations --check --dry-run` reported no changes; `git diff --check` reported no whitespace errors.
- Review: independent fresh-context standards and specification passes completed after rollback and complete Product-route access evidence were added.
- Historical integrity: deactivation retains the Membership and user identity for existing Audit Event actor attribution.
- Documentation/demo impact: README and Owner navigation describe Staff management; Demo Business mutation remains blocked at request and service boundaries.
- Reopen triggers: membership cardinality, invitation design, role model, inactive-access response, Demo policy, or any new Business-owned endpoint.
- Next dependency: Ticket 06. Begin with a failing service test for atomically completing a one-line Purchase and creating its Stock Movement and Audit Event.
- 2026-09-09: Follow-up review repairs added audit-failure rollback proof for both membership writes and request coverage for active and deactivated Staff Members across every current Product endpoint, including cross-Business Product identifiers. Email normalization remains at the service boundary; form normalization is presentation cleanup and was not merged into a new helper to avoid widening this ticket.
