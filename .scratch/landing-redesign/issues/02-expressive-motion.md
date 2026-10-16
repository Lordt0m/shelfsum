# Expressive shop-day motion

Status: complete

Scope: preserve the landing copy, green identity, page composition, Django rendering and backend invariants. Improve the hero choreography, explanatory stock movement, selected story entrances and interruptible replay. No merge or deployment.

## Acceptance evidence

- Hero copy, actions and preview build in semantic groups without hiding content or disabling links.
- Eight decorative units arrive for Purchase; five leave for Sale. Fixed slots and all original ledger rows remain visible. Replay cancels prior phase timers and transitions retarget their rendered positions.
- Story introduction enters laterally; demo heading uses a restrained lift/scale. No looping or scroll interception.
- Keyboard and reduced-motion replay settle immediately. Pointer press takes 100ms and releases immediately. No animation dependency added.
- Native browser form submissions with JavaScript disabled succeeded for both local demo roles, including Enter submission for Staff. Native demo disclosure and anchor navigation also worked on a phone-width viewport.

## Completion record

Closure ref: the local commit containing this record on codex/landing-redesign, parent d78368a. No new public ref or production release.

Full SQLite suite: 288 tests, OK with three PostgreSQL-only concurrency skips. Final focused public-view suite: six tests passed. TypeScript build/check, Django system check and whitespace check passed. Extended the response test to protect the complete 15-unit, five-empty-slot, replay-hidden server-rendered fallback.

Browser checks covered normal and reduced motion at desktop 1440px and phone 390px, plus 320px overflow. Rapid pointer replay was tested both repeatedly from opening and during Purchase; it returned to opening and then settled at 15 with three retained rows. Keyboard replay returned 15 with zero-duration transitions. Skip link focus/activation and Staff credential disclosure passed. Final CSS loaded through an updated asset revision query to invalidate a stale browser copy. Temporary script, media, cache and viewport overrides were restored.

Review-animations repairs: fixed empty-marker drift with stationary slots; removed obsolete competing entrance rules; made pointer press/release asymmetric. Verdict: Approve for this local landing scope. Marketing/explanatory durations above 300ms are deliberate; navigation and keyboard actions remain immediate. DESIGN.md and the Impeccable motion metadata reflect the implementation. Copy and demo records unchanged.

Limits: no new PostgreSQL run, physical touch-device test, cross-browser audit or slow-motion playback measurement. Screenshot artifacts and standalone verification are in programme outputs/shelfsum-landing. Next dependency: user review of the local motion before any separately requested merge/release.
