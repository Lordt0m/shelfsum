# Complete the server-rendered shop workflows

Status: complete

## Acceptance

Read repository guidance, context, ADRs and the invariant map first. Preserve the existing local Products heading repair. Work through dashboard, Products/details, Purchases, Sales, Expenses, adjustments/history and reports. Use the existing green/system-type design language, semantic HTML and shared components. Apply better-ui's exact shadow recipe and motion restraint; keyboard and repeated actions stay immediate.

Keep all calculations, authorization, Business isolation, stock transactions, reversals, immutable records, report/CSV definitions and Demo restrictions on the backend. TypeScript enhances submission feedback, error navigation, line-row insertion and preview invalidation only; core workflows remain native links and forms. Compile with strict TypeScript to a Django static asset; no SPA or schema changes.

Verify focused request tests, full existing suite, checks and browser workflows at phone/tablet/desktop widths for writable Owner/Staff and read-only Demo. Check keyboard, reduced motion, form errors and JavaScript-free submissions. No publishing or deployment.

## Completion record

- Closure ref: local commit titled `Polish complete server-rendered shop workflows`; no public release or push. Baseline local HEAD cd2be90; remote main inspected at c546e3a.
- Delivered: consistent Dashboard/Products/details, Purchases/Sales drafts and completion/reversal, Expense entry/correction/voiding, server adjustment preview, immutable history and all five reports. Linked error summaries and inputs, native phone records, focusable report scrollers, consistent currency/status/empty/disabled/Demo states, instant TypeScript row insertion and submit feedback. Backend authorization, services, transactions, stock and money arithmetic and report/export definitions preserved. Expense date-widget formatting repaired after browser reproduction.
- Verification: full SQLite suite 285 tests, OK with three PostgreSQL-only skips. Final focused InterfaceTests 15/15 after confirmation-markup repair (one added regression brings the discoverable suite to 286); earlier relevant 38-test and 28-test selections passed. `npm run check`, `npm run build`, Django system check, migration-drift check, static collection and diff whitespace check passed.
- Browser: 320/390/766/768/1440 px; complete product create/error/search/details, adjustment reject/preview/invalidate/record, purchase and sale draft/complete/void, oversell rejection, Expense error/correction and Staff-created Expense. Staff Owner-settings access 403; Owner/Staff Demo hides or disables write actions. Twelve Staff routes across 320/768/1440 px had zero page-level overflow. Native keyboard menu/add-row/focus/error navigation and horizontal report scrolling checked; reduced motion yielded zero transition duration and automatic scrolling. Blocking only the application's JavaScript verified native purchase add-line/save/complete/void and adjustment preview/record. Downloaded sales CSV agreed with visible revenue 3000, estimated COGS 2000 and margin 1000 in the isolated fictional fixture.
- Review and repairs: independent fresh-context review found malformed void-page title/section boundaries, unpinned Node release environments and tracked generated JS. Repaired and independently rechecked all three; Node 22.23.2 pinned in local/CI/hosting config and generated workspace.js untracked while retained locally. No remaining review findings.
- Documentation/demo: README/spec updated. Preview uses an isolated fictional SQLite fixture under programme `work/`, not production or the existing local database; no real shop records or fixture credentials committed. Existing Products heading repair preserved and measured at shared left edge on phone/tablet/desktop.
- Remaining gates: PostgreSQL concurrency (three local skips), new CI/Render execution, hosted production static behavior, physical phone and assistive-technology testing. Reopen for any material workflow, role, export or responsive regression. No deployment performed.
- Next dependency: a separate authorized publishing ticket must first run PostgreSQL and production gates for this exact local source.
