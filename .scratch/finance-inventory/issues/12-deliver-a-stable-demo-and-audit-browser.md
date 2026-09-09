# 12: Deliver a stable demo and Audit Event browser

**What to build:** Provide a deterministic fictional Demo Business, enforce read-only demo access, and let authorized Business users inspect the Audit Events produced by every consequential workflow.

**Blocked by:** 04: Maintain and find Products; 05: Add Staff Members with enforced permissions; 08: Void completed stock documents; 09: Record Expenses and Stock Adjustments; 10: Show an explainable Business dashboard; 11: Filter reports and export safe CSV.

**Status:** ready-for-agent

- [ ] A deterministic command recreates a fictional Business with Owner and Staff Member demo users, several weeks of records, and at least one low-stock Product.
- [ ] Demo credentials are documented and visible from the landing page without exposing real personal or Business data.
- [ ] Demo users can inspect every major workflow and report.
- [ ] Every write attempt against the Demo Business is rejected by shared server-side policy with a clear response.
- [ ] Audit Events exist for every consequential action named in the specification and remain append-only through the application.
- [ ] The Audit Event browser filters by actor, action, and date and remains scoped to the current Business.
- [ ] Tests cover deterministic seeding, idempotent recreation, read-only enforcement at request and service seams, audit attribution, and isolation.
