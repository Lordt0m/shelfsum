# 13: Ship the public evidence

**What to build:** Release a secure, documented, publicly inspectable application on free hosting, with PostgreSQL verification, continuous tests, demonstration access, and concise technical evidence suitable for applications and interviews.

**Blocked by:** 12: Deliver a stable demo and Audit Event browser.

**Status:** in-progress

- [x] The phase begins by reviewing and updating `AGENTS.md` for final build, security, deployment, documentation, and explanation requirements.
- [ ] The complete release suite passes against PostgreSQL and the fast local suite remains documented separately.
- [ ] Continuous integration runs the appropriate automated checks on proposed changes.
- [ ] Production configuration uses environment-held secrets, HTTPS-safe settings, static-file handling, safe logs, and a working health check.
- [ ] The application is deployed to a free Render web service connected to Neon PostgreSQL after current provider terms are rechecked.
- [ ] Migrations, static collection, and deterministic demo seeding succeed from a clean deployment.
- [ ] Public documentation explains the problem, target users, live demo, setup, tests, architecture, data model, permissions, key workflows, trade-offs, explicit exclusions, deployment, and known limitations.
- [ ] The live landing page, demo login, protected pages, major reports, and mobile layout pass a final smoke review.

Private interview-defence work is coordinated outside this public repository and is not a release acceptance item here.

## Comments

- **2026-09-17 phase start:** reviewed `AGENTS.md` and added durable release-evidence rules for PostgreSQL, environment-held production configuration, HTTPS/host/CSRF safety, static collection, safe logs, explicit migration/demo seeding, CI ownership, and public evidence. Current provider terms are being rechecked against first-party documentation before implementation; no deployment claim or external account action has been made.
- **Next safe action:** choose the current free Render/Neon-compatible route from primary-source evidence, then add production configuration and PostgreSQL CI test-first without changing the lightweight SQLite development loop.
