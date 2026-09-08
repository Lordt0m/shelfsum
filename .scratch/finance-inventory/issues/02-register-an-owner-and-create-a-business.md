# 02: Register an Owner and create a Business

**What to build:** Let a visitor register with a unique email, sign in, create one Business, and reach an authenticated Business home page while unauthenticated and unassigned users remain correctly constrained.

**Blocked by:** 01: Establish the project foundation.

**Status:** complete

- [x] Registration uses a custom user model with unique email as the login identifier.
- [x] Registration, sign-in, sign-out, and authenticated password change work through accessible server-rendered forms.
- [x] A newly registered user can create exactly one Business and becomes its Owner.
- [x] A user without a membership is guided to Business creation and cannot access Business-owned pages.
- [x] A user with a membership cannot create or join a second Business through the interface or a crafted request.
- [x] Business settings are visible and editable only to the Owner.
- [x] Request tests cover success, validation failures, authentication redirects, and the one-membership boundary.

## Comments

- 2026-09-08: Implementation started after Ticket 01 passed standards and specification review.
- 2026-09-08: Thirteen application tests pass, including registration validation, case-insensitive email sign-in, password change, unauthenticated redirects, one-membership enforcement, and Owner-only settings. Review pending.
- 2026-09-08: Review found an inactive-membership redirect loop and a missing Demo Business write guard. Both received failing regression tests and centralized server-side fixes; all fifteen tests now pass. Fix verification pending.
- 2026-09-08: Follow-up standards and specification reviews confirmed both fixes and found no remaining actionable gaps.
