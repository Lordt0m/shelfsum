# Interface verification record

Recorded 13 October 2026. Application ref: `bd734e1d3c207c6b0fa407a18554b5d8fb646c24` on `codex/interface-verification`.

## Completed checks

| Check | Result and scope |
| --- | --- |
| PostgreSQL release CI | 287 tests passed with zero skips, including all three concurrency tests. Migration drift, migrations, repeat demo seed, TypeScript check/build, static collection and production configuration checks passed. |
| Local PostgreSQL | Initial design ref a3aabb5 passed 286 tests with zero skips against an isolated PostgreSQL 17 Alpine container. |
| Focused repair tests | Both duplicate-error-ID regressions failed before repair. All 16 interface tests passed after removing duplicate wrapper IDs. Django check and diff check passed. |
| Hosted smoke tests | 56 checks passed on the isolated staging service using fictional records. Covered Owner/Staff access, foreign Business isolation, purchase/sale drafts and completions, stock adjustments, reversals, retained movement history, expense correction/void, reports and all five CSV exports. |
| Report consistency | Product HTML and stock CSV agreed at each balance: 10, 15, 12, 15, 13, 8. Six original/reversal movement rows remained, with net quantity 8. |
| Demo protection | Both demo roles rejected writes; their movement exports remained unchanged. |
| Validation descriptions | Hosted HTTP response exposes exactly one invalid-Amount error ID and the matching aria-describedby reference. |
| Browser accessibility | Inspected computed names, roles, headings, landmarks, error-summary focus and keyboard error links. axe-core 4.11.0 found no WCAG A/AA violations or incomplete results on hosted Demo Owner movement history at the available browser width and the 390px catalogue. |
| Phone reflow | Hosted catalogue at 390 CSS pixels had no page-level overflow. This was a browser emulation check, not physical-phone verification. |
| Narrator | User confirmed that staging Demo Owner navigation and table headers read correctly. Agent did not observe speech directly. |

CI: https://github.com/Lordt0m/shelfsum/actions/runs/38471782585

Staging: https://shelfsum-ui-verification.onrender.com

Staging deployment `dep-db7aas59fdbs73df7eng` is live at the application ref above. It is a separate free web service and PostgreSQL database; automatic deployment is off. The free database expires on 12 November 2026. No paid upgrade was selected. Fictional writable smoke-test records are confined to staging; the canonical demo was unchanged. Local PostgreSQL testing was stopped and Docker Desktop returned to its original stopped state.

## Explicit remaining limits

- Final writable Owner browser audit is blocked by a saved browser permission denial. Repeated retries after the user's settings changes were rejected. No alternate surface or indirect execution was used to bypass that block. This audit is not claimed as complete.
- Actual screen-reader announcements for invalid forms and dynamic product rows were not verified. The earlier user confirmation covers navigation and table headers only.
- Physical-phone hardware and broader browser/screen-reader combinations were not tested.
- Provider log inspection was unavailable with a 504 response; no log-cleanliness claim is made.
- Staging restart/persistence verification was not performed.

The user authorised committing this accurate record with those limits retained. The documentation commit does not change runtime behaviour or resolve the remaining release checks.

## Production status

At the final status check, https://shelfsum.onrender.com still served `c546e3a38694bbde1dec96af090fe8488f7b5b23`. The production service tracks `main` with automatic deployment enabled. No production merge or deployment was performed. Production release requires a separate authorised release decision, including disposition of the remaining checks above.
