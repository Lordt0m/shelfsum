# A welcoming shop identity

Status: complete

## Acceptance

Second visual pass on the verified e385f27 interface. Keep green identity, all routes, Django/native forms, TypeScript enhancements, exact backend values, roles and Demo protection. Add warm backgrounds, stronger sans-serif typography, a distinctive shop overview, expressive labelled stock states and consistent surfaces across catalogue, details, documents, adjustments, history, reports and account screens. Frequent/keyboard actions stay immediate; respect reduced motion. Local only.

## Design plan

Palette: paper #f7f6ed, surface #fffefa, forest #174b39, green #287456, lime #e0edac, honey #f1bd61. Ink #203b30 and muted #58685d; danger retains readable red. Trebuchet MS display lettering draws on rounded shop signage, Segoe UI/system body preserves compact tables and forms. No remote font dependency.

Dashboard: one lime shop-sign composition with a striped awning edge, daily links and three directly labelled stock counts; quiet asymmetric attention/history panels below. Product balance is a forest-green anchor with explicit state and quantity. Warm inset form lines and paper table headings extend the same identity. Meaningful labels and backend data carry the design; no invented charts or stock ratios.

Plan critique: rejected cream-plus-serif and identical dashboard cards. Spend visual boldness on the storefront overview and stock balance; keep repeated data and controls disciplined. Surface shadows retain better-ui's explicit recipe. Motion budget: 100ms colour feedback only; keyboard and reduced-motion feedback snap. No page entrances or delayed row insertion.

## Verification plan

Desktop before/after dashboard captures, plus a final 390x844 phone capture. Existing focused interface/document/report checks and full suite. Browser representative workflows, mobile/desktop overflow, add-row keyboard, linked validation errors, no-JavaScript fallback, reduced motion and selected contrast pairs. Roles/Demo rules remain covered by backend tests; do not interrupt the user's signed-in session to switch roles. Preserve the user's existing untracked ticket 02.

## Completion record

- Closure ref: local commit `Give ShelfSum a welcoming shop identity`, based on e385f27; no public ref, push or deployment.
- Delivered: warm paper and forest/lime green identity; local rounded display typography; striped shop-sign dashboard with grouped stock totals, asymmetric attention/history composition, visible signed movement chips, dark Product balance panel, warm form lines, stronger field outlines and consistent reports/navigation/account surfaces. Labels and backend figures preserved. No Python, permissions, services, money/stock arithmetic, TypeScript behavior or schema changed.
- Proof: 37 focused interface/purchase/report tests passed; full SQLite suite 286 tests OK, three PostgreSQL-only skips. TypeScript check, Django check, static collection and whitespace diff check passed. Reversible visual changes do not add implementation-mirroring tests.
- Browser: 17 Owner routes at phone widths (first five at 320, remaining twelve at 390), and all 17 at 1440, zero page-level overflow. Dashboard, Purchase form, Product details and report screenshot review; complete dashboard includes operational-estimate qualifications, stock-value contributions and Audit Events. Keyboard add-row instantly focused its Product selector; invalid submission focused linked server summary; native add-row POST worked with only application JavaScript blocked. Reduced motion yielded transition 0s and no animation. Existing frequent actions keep colour-only 100ms feedback; keyboard focus snaps.
- Contrast: ink/surface 12.03, muted/paper 5.45, forest/lime 8.03, navigation/forest 8.15, warning text/background 6.43. Darkened input outline after its initial 2.16 contrast result. Review repaired cache-stale preview captures and the light navigation divider. Final screenshots use real rendered UI.
- Documentation/demo: specification and README design description updated; fictional browser fixture reused without stock changes. Screenshots and local result note live outside repository, under programme outputs. Existing user ticket 02 remains untracked and untouched.
- Not verified: physical phone, screen-reader output, 10% animation-panel replay, fresh browser role-switch flows, PostgreSQL concurrency, hosted CI/static/runtime. Role/Demo/invariant coverage comes from the full existing tests. This remains a local design pass.
- Next dependency: user review of this local design; publishing requires a separate request and PostgreSQL/production gates.
