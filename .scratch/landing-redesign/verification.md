# Landing redesign verification

Follow-up: the 16 October expressive-motion pass is recorded in issues/02-expressive-motion.md. Both JavaScript-disabled demo sign-in submissions are now verified there; the historical limits below describe the 14 October pass.

14 October 2026. Local-only implementation on `codex/landing-redesign`, based on production documentation ref `aebef64`. No push, merge or deployment.

## Executed checks

- New Django response test failed on the old landing, then passed after replacement. The final test confirms real sign-in/register routes, server-rendered stock facts, fictional preview, separate landing assets and exactly two reveal targets.
- Full local SQLite suite: 288 tests, OK with three PostgreSQL-only concurrency skips. Focused public-view suite: six tests passed again after the final visual/reveal repairs. TypeScript build, Django system check and diff whitespace check passed.
- Browser widths 320, 390, 761/762, 1280 and 1440 CSS pixels: no page-level horizontal overflow, unique IDs, readable headings. Full-page desktop, phone and intermediate screenshots plus normal-motion hero and 320/390 demo repair captures saved in the programme outputs directory.
- Stock story observed opening 12, Purchase 20, Sale 15; all three ledger rows retained. Pointer replay re-enables 250ms unit transitions. Enter replay settles to 15 with zero-duration unit transitions and a status announcement in the accessibility DOM.
- Reduced-motion emulation: headline animation none, unit transitions zero, stock example settles to 15. Normal-motion settled preview checked at opacity 1 with a 2-degree rotation.
- Keyboard: Tab reaches the skip link with a visible outline; Enter follows it to main. Enter opens Demo Staff credentials. Real sign-in and account-creation routes load.
- Both public fictional demo identities signed in locally and reached the dashboard. Staff had no Owner settings navigation. Landing CSS was absent from signed-in workspace; original typography remained.
- JavaScript disabled through browser emulation: native DOM snapshot confirmed server-rendered headline, both demo credential sets and closing stock; sign-in HTML form loaded without scripts. The enhancement-only replay remained hidden. Scripts and media overrides were restored.
- Mechanical Impeccable detector ran once. Its flat-type warning could not resolve Django static template syntax; browser heading/body sizes establish a clear hierarchy. Thick-border warnings point to the tiny shelf brand mark, not rounded cards.
- Narrow-phone seal repair measured and captured with the seal in normal flow above the heading. Repeated section entrances were reduced to stock introduction and demo invitation only.

## Review and limits

Independent Impeccable finish review requested the seal and reveal repairs. The verdict pass scored those repairs and reduced-motion press neutralisation resolved, with disposition ship for local review and no remaining required design fixes from that review. Six final focused tests passed. PRODUCT.md, DESIGN.md and .impeccable/design.json are complete; their scopes preserve CONTEXT.md as domain authority and the existing signed-in interface. The remote Impeccable concept catalog was unavailable; the user's delegated direction was implemented directly.

Not verified: PostgreSQL concurrency on this local-only revision, full JavaScript-disabled authentication submission, physical devices, actual screen-reader speech and animation playback at 10% speed (the available CDP animation inspector rejected that method). Native keyboard disclosure was verified with JavaScript enabled. No claim of a new production release or complete cross-browser audit.

Font: Bricolage Grotesque variable TTF from the Google Fonts repository, self-hosted with its SIL Open Font License in static/fonts. No new shipping raster illustrations.

Preview: http://127.0.0.1:8767/ (autoreloading local Django server retained).
