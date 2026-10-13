# ShelfSum interface redesign

Date: 4 October 2026. Baseline: c546e3a, authoritative repository Lordt0m/shelfsum.

## Phase 0: guidance and current workflows

Read AGENTS.md, CONTEXT.md, module map and the three accepted ADRs. Repository-wide guidance remains applicable without changes. Use frontend-design; retain server-rendered Django, POST/CSRF, whole quantities, existing permissions, Demo protection, transaction services and immutable history.

## Design plan

An everyday shop workspace: the important visual element is the stock balance and its explainable changes. Products, adjustments, movement history and low-stock decisions lead; operational financial estimates keep their existing qualifications.

- Palette: canvas #f5f7f9; surface #ffffff; ink #18252b; secondary text #52616b; divider #dbe2e7; accent #176b4d. Green is the single interaction accent. Amber and red are reserved for explicitly labelled stock warnings and errors.
- Typography: locally available Segoe UI and system sans-serif, tabular numerals for quantities/money. Page titles 30–36 px; section titles 20 px; body 15–16 px. Sentence case, left alignment, no decorative uppercase labels.
- Layout: desktop navigation rail, compact workspace header, generous white tables. Below 960 px navigation becomes a native disclosure; below 640 px products and movements become compact stacked records. No page-level horizontal scrolling.
- Components: 44 px minimum controls, visible focus, quiet outlined secondary buttons, one primary action per task, linked summaries, semantic tables, labels on all inputs, live feedback, concise error and empty states.

```text
Navigation | Business / role                Account
           | Products                       Add product
           | Search name or SKU | Status | Stock | Filter
           | Product / SKU | Stock | Status | Price | Actions
           | Results count                          Pagination
```

The reference patterns are adapted to supported features: no invented orders pending, warehouse availability, product photographs, barcode tools or growth charts. Historical balances are explicitly calculated from the complete ledger, with stable created-at/ID ordering, before applying report filters. Stored stock and movements are never changed to produce presentation data.

## Implementation stages

1. Shared responsive shell and components; products search/status filters/pagination; product balances and detail history.
2. Adjustment input and server preview, readable history with reasons/actors/reversal links, actionable dashboard.
3. Focused regression tests, complete suite, system/migration checks, browser workflows at desktop/tablet/phone/320 px, independent presentation review, repairs and local completion record.

## Acceptance

Products: combine search, active-state and stock-state filters; preserve filters through pagination. Details show quantity, threshold, price and history. Adjustment preview shows current/signed/new balance before the existing record action. No-JavaScript server preview remains usable. Movements show real reason, actor, change and ledger-derived balance; reversal links identify original movement even when outside report dates. Demo is visibly read-only; Staff have no Owner navigation. Dashboard leads with low stock and recent stock movements, retaining exact financial definitions. No new framework or schema changes.

## Reference evidence

Checked 4 October 2026:
- https://www.zoho.com/inventory/help/getting-started/dashboard.html — linked summaries, recent activities, actionable inventory overview.
- https://www.zoho.com/us/inventory/help/items/item-details.html — stock balance, essential product details, history.
- https://help.sortly.com/sortly-mobile-app — Items, Search and Workflows screenshots; compact phone browsing and stock actions.
- https://help.shopify.com/en/manual/products/inventory/adjusting-inventory/adjustment-history — timestamp, change, reason, new quantity and actor.
- https://ui.shadcn.com/examples/dashboard — spacing, rail navigation, restrained summary surfaces, table controls and pagination.

Deployment is outside this request. PostgreSQL remains a release gate before publishing.

## Complete-workflow extension, 13 October 2026

Ticket 03 extends the same visual system through Purchases, Sales, Expenses, report filters and reversal confirmations. Apply better-ui's exact surface shadows and consistent outline icons; use emil-design-eng's immediate keyboard/repeated actions, clear feedback and restrained motion. No new motion is needed for frequent operations. Strict TypeScript enhances native Django forms only. Keep money/stock calculations and write authorization on the server. Include linked error summaries, preserved inputs, native add-line fallback, submit progress, empty states, disabled Demo actions and immutable/reversal explanations. Build generated JavaScript before static collection; keep it out of source control.

Local acceptance includes writable Owner/Staff and read-only Demo checks, phone/tablet/desktop layouts, keyboard input, reduced motion, JavaScript-free purchase and adjustment workflows, report/CSV agreement, focused regressions and the existing suite. This extension does not change the previously deployed site.

## Welcoming shop identity, 13 October 2026

Ticket 04 supersedes the neutral visual palette with warm paper, forest green, lime shop signage and honey warning surfaces. Use local Trebuchet MS display lettering and the existing Segoe/system body; no remote type dependency. A striped shop overview replaces identical summary cards, while the Product balance becomes a dark green anchor. Extend warm surfaces, clear outlines, labelled stock states and tabular values through all existing screens. Keep the exact operational definitions, native forms and current enhancement behavior. No page entrances, motion delay or backend changes. Visual and test evidence is recorded in ticket 04; hosting remains separate.
