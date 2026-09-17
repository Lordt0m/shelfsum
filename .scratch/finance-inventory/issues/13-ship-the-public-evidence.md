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
- **2026-09-17 provider decision:** first-party evidence in [the free-deployment comparison](../research/free-deployment-options.md) confirms Render Free Web Service plus Neon Free PostgreSQL as the primary route, preferably Frankfurt for both. Render supplies public HTTPS and a free 512 MB web runtime but sleeps after inactivity; Neon supplies durable scale-to-zero PostgreSQL without an advertised card requirement. Render Free PostgreSQL is rejected because it expires, and Koyeb plus Neon is the fallback because Koyeb requires card validation.

### Ordered release slices

1. **Production configuration:** add testable environment parsing, PostgreSQL/SSL configuration, secret and host validation, HTTPS/proxy/CSRF security, WhiteNoise static handling, Gunicorn, a reproducible build/release script, and deployment metadata. Preserve SQLite and `runserver` as the default local loop. Fail closed in production and prove both development and production settings through public checks or subprocess tests.
2. **PostgreSQL CI and release suite:** add a GitHub Actions workflow with Python 3.13 and PostgreSQL, install pinned dependencies, run checks, migration drift, the complete suite with zero skips, and collect static files. The workflow is evidence only after a real run on a published repository.
3. **Public technical evidence:** rewrite the README around problem, users, live-demo contract, setup, test modes, architecture, data model, permissions, workflows, trade-offs, exclusions, deployment, and limitations. Add only diagrams or screenshots that materially clarify the system and only after the deployed surface exists.
4. **External release and smoke:** publish the exact reviewed ref, provision Neon and Render through user-owned accounts, set secrets, migrate/collect/seed from clean state, verify restart persistence, run both Demo roles through landing, authentication, workflows, reports, Audit browser, health, and mobile layout, then perform fresh release review.

- **Next safe action:** implement slice 1 test-first, beginning with a failing subprocess settings test that proves production refuses a missing secret and accepts an SSL PostgreSQL URL without changing the default SQLite development configuration.
