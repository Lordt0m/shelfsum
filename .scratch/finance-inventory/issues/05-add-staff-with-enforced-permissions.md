# 05: Add Staff Members with enforced permissions

**What to build:** Let an Owner add or deactivate an already registered Staff Member while both roles see only their Business and the server enforces owner-only controls.

**Blocked by:** 02: Register an Owner and create a Business.

**Status:** ready-for-agent

- [ ] An Owner can add an unassigned registered user by unique email as a Staff Member.
- [ ] The flow rejects unknown users, the Owner's own email, duplicate membership, and users already assigned elsewhere.
- [ ] The Owner can list and deactivate Staff Members while historical actor attribution remains intact.
- [ ] Deactivated Staff Members lose Business access immediately.
- [ ] Staff Members cannot manage membership or Business settings through navigation or crafted requests.
- [ ] Tests exercise Owner and Staff Member access plus cross-Business identifiers for every available Business-owned screen.
