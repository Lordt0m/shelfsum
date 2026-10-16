---
name: ShelfSum public landing
description: Shop day, made visible — a welcoming green shopfront with understandable stock facts.
colors:
  green: "#174b39"
  ink: "#183e30"
  paper: "#f7f3e7"
  lime: "#dfed9b"
  apricot: "#f2bd85"
  muted: "#526457"
  line: "#d7ddcb"
  button-hover: "#cddd88"
  preview-paper: "#fffdf5"
  receipt-paper: "#fffcf2"
  warm-section: "#e9e6d8"
  stock-stage: "#dde8b8"
  stock-unit: "#367650"
  ledger-current: "#e5eecb"
  focus: "#aa741b"
typography:
  display:
    fontFamily: "Bricolage, 'Segoe UI', sans-serif"
    fontSize: "clamp(54px,6.5vw,92px)"
    fontWeight: 700
    lineHeight: 1.04
    letterSpacing: "-.035em"
  headline:
    fontFamily: "Bricolage, 'Segoe UI', sans-serif"
    fontSize: "clamp(36px,4.4vw,62px)"
    fontWeight: 700
    lineHeight: 1.04
    letterSpacing: "-.035em"
  title:
    fontFamily: "Bricolage, 'Segoe UI', sans-serif"
    fontSize: "28px"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-.035em"
  body:
    fontFamily: "'Segoe UI', sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.65
  button:
    fontFamily: "'Segoe UI', sans-serif"
    fontSize: "16px"
    fontWeight: 650
    lineHeight: 1.4
  code:
    fontFamily: "monospace"
    fontSize: "14px"
rounded:
  unit: "4px"
  control: "8px"
  summary: "12px"
  surface: "16px"
  pill: "20px"
  seal: "50%"
spacing:
  unit-gap: "8px"
  inline-gap: "12px"
  control-gap: "16px"
  mobile-padding: "28px"
  split-gap: "90px"
components:
  button-lime:
    backgroundColor: "{colors.lime}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "14px 22px 14px 24px"
  button-dark:
    backgroundColor: "{colors.green}"
    textColor: "{colors.paper}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "14px 22px 14px 24px"
  button-hover:
    backgroundColor: "{colors.button-hover}"
    textColor: "{colors.ink}"
  replay:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    padding: "8px 0"
  example-pill:
    backgroundColor: "#edf1df"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "3px 9px"
  preview:
    backgroundColor: "{colors.preview-paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
  receipt:
    backgroundColor: "{colors.receipt-paper}"
    textColor: "{colors.ink}"
    padding: "40px 48px"
  credentials:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    padding: "28px 40px"
  navigation:
    backgroundColor: "{colors.green}"
    textColor: "{colors.paper}"
---

# Design System: ShelfSum public landing

## Overview

**Creative North Star: "Shop day, made visible"**

This system applies only to the public landing page, its dedicated stylesheet and its progressive enhancement. ShelfSum's existing green identity, warm surfaces and welcoming language supply the visual authority. The signed-in application and `static/css/site.css` retain their existing identity; this document does not prescribe a redesign of those screens.

The landing feels like an open shopfront: confident rounded display type, deep green fields, warm paper and practical stock facts. Tonal surfaces distinguish the shelf from its retained receipt. The example is explicitly fictional, and every stock fact remains readable without animation or JavaScript.

**Key Characteristics:**
- Green shopfront with warm paper, lime and apricot accents.
- Large expressive headings paired with quiet system sans text.
- Asymmetric opening and receipt-like stock evidence.
- Finite, interruptible motion with immediate keyboard completion.
- Native links and disclosures; usable static content.

Implementation authority: `static/css/landing.css`, `frontend/landing.ts` and `templates/core/landing.html`. This is an implementation record, not evidence of a completed browser accessibility audit.

## Colors

The palette keeps ShelfSum's green recognisable while making quantities, retained history and invitations easy to distinguish. Frontmatter values are normative; the sidecar adds metadata and illustrative tonal ramps.

### Primary
- **Shopfront Green:** opening, header, demo field and dark actions.
- **Shelf Lime:** headline emphasis, primary invitation, stock summary and demo invitation.

### Secondary
- **Stock Apricot:** the Product initial and high-contrast focus outlines on green fields.

### Neutral
- **Record Ink:** warm dark green text and the receipt total rule.
- **Shop Paper:** page and credentials background.
- **Preview Paper / Receipt Paper:** subtly distinct example surfaces.
- **Quiet Green:** explanatory text.
- **Ledger Line:** separators and disclosure rules.
- **Warm Section:** workday and footer fields.
- **Stock Stage / Stock Unit / Current Ledger:** the shelf explanation and its current row.
- **Amber Focus:** default keyboard outline on light surfaces.

**The Scoped Shopfront Rule.** Landing tokens belong to `.landing-page`; keep signed-in styling independent.

## Typography

Display and headline typography use the self-hosted Bricolage Grotesque font under the CSS family alias `Bricolage`, followed by Segoe UI and sans-serif. Body and actions use Segoe UI with sans-serif fallback. Credentials use the browser's monospace fallback at the recorded code size; there is no separately loaded code font.

The display font is loaded from `static/fonts/bricolage-grotesque.ttf`, with weights (200–800) and `font-display: swap`. Source: [Google Fonts Bricolage Grotesque](https://github.com/google/fonts/tree/main/ofl/bricolagegrotesque). The retained license is `static/fonts/bricolage-OFL.txt`: Copyright 2022 The Bricolage Grotesque Project Authors, [upstream project](https://github.com/ateliertriay/bricolage), SIL Open Font License 1.1. Preserve the font and license together. No raster assets were created or shipped for this visual system; the font is the only new externally sourced visual asset.

### Hierarchy
- **Display:** three-line hero headline; balanced wrapping and the frontmatter display scale. At the intermediate breakpoint it is (64px); on phones it uses `clamp(46px,9vw,66px)`.
- **Headline:** section headings use the frontmatter headline scale. The closing heading is (44px), then (36px) below the intermediate breakpoint.
- **Title:** receipt headings use the recorded title role; role-note headings use (28px/1.2), benefits use (26px/1.15) with tracking (-.02em), and the preview heading uses (37px).
- **Body:** inherited body rhythm; hero supporting copy is (19px), then (17px) at the intermediate breakpoint. Text columns usually stop at (470–490px).
- **Labels:** preview labels and receipt explanations use (12–14px); navigation is (15px, 600), then (13px) on phones. Credential summaries use Bricolage (23px, 700).
- **Quantities:** stock count uses Bricolage (86px/1, 700), then (72px) on phones, with tabular numerals. Ledger quantities also use tabular numerals.

## Layout

The container is `min(1248px,calc(100% - 96px))`. The hero grid uses (1.15fr / 1fr) with a (76px) gap and block padding (68px 98px). Section introductions and supporting sections use equal columns, usually with a (90px) gap. The shelf and receipt form a single split surface rather than separate floating cards.

At `max-width:1000px`, container gutters become (32px), hero gap becomes (38px), split-section gaps become (40px), and stock panels use (30px) padding. At `max-width:720px`, gutters become (20px), content grids stack, panel padding becomes (28px), major section padding becomes (64px), and the close stacks its action beneath the heading. Navigation wraps in place; no menu drawer or hamburger is implemented. Footer columns change from three to two to one.

The demo seal is static at the intermediate breakpoint and becomes absolutely positioned again on phones. At `max-width:400px`, a more specific invitation/seal rule returns it to normal flow with bottom spacing (20px), avoiding overlap with the invitation heading.

## Elevation & Depth

Depth comes mainly from green fields, tonal paper and simple rules. The preview alone uses a structural lifted-paper shadow and a slight (2deg) rotation. The sign-in action uses a one-pixel inset-like outline shadow rather than a floating elevation.

### Shadow Vocabulary
- **Preview lift:** `0 18px 40px -18px #082c28a0,0 3px 8px #082c2840`.
- **Sign-in outline:** `0 0 0 1px #c9dac680`.

## Shapes

Controls have gently curved corners; composed surfaces use the larger surface radius. Small stock rectangles retain the unit radius, summary inset uses the intermediate radius, and status labels use the pill radius. The round demo seal rotates (10deg). Receipt separators are thin single rules, with a (2px) closing-stock rule. Native disclosure markers remain visible.

## Components

### Buttons and links

Primary lime and dark actions share a minimum height (52px), inline icon gap (16px), and the frontmatter padding. Both hover to the same lime hover surface with ink text; background and text changes take (150ms). Icons are inline, stroked SVGs (22px) using current text color. Pointer-down applies `scale(.96)` immediately; pointer release, cancellation, leaving, blur and keydown remove it. Keyboard activation does not wait on a press animation.

Default focus is a (3px) amber outline with (6px) offset. Opening/header focus uses apricot. The skip link becomes visible on focus and targets the main content. Text actions retain underlines; header navigation reveals underlines on hover.

### Example preview and labels

The preview is illustrative product evidence, not a screenshot of the signed-in interface. Its read-only label and stock status label remain plain text. Product identity, movement quantities and the fictional caption are part of the component. Keep the read-only and fictional qualifiers adjacent to the example.

### Shelf and retained receipt

Twenty decorative stock rectangles encode the example count; their grid is hidden from assistive technology because the text states the same information. The server-rendered state shows closing stock (15), opening stock (12), Purchase (+8), Sale (−5) and retained original rows.

Pointer replay shows (12) immediately, (20) after (900ms), then (15) after (2300ms). Twenty fixed shelf slots hold decorative tokens: eight arrive from below for a Purchase; five leave to the right for a Sale. Transform/opacity transitions take (480ms), staggered (45ms), with `cubic-bezier(.2,0,0,1)`; current ledger background takes (150ms). These longer durations explain a fictional shop day, not an operational wait. Replay clears previous timers and CSS retargets from the rendered position. Keyboard or assistive activation (`event.detail === 0`) settles instantly at the final count and writes a complete explanation to a `role="status"` region. Reduced motion and hidden-document changes also settle the sequence. The replay control appears only when JavaScript enhances the page.

### Credentials and evidence disclosures

Use native `details`/`summary` for credentials and footer evidence. Owner credentials begin open; Staff credentials begin closed. Credential code wraps anywhere and uses `user-select: all`. There is no copy button, custom dialog or form input in this landing system.

### Entry and reveal motion

JavaScript adds `lp-motion-ready` only with normal motion enabled. Hero copy enters over (700ms), with semantic groups delayed (100/200/300ms). The preview settles over (850ms), delayed (150ms), from a small lift, rotation and scale (.96); its heading, stock summary, product and retained rows build at (100ms) intervals. Stock introduction enters laterally (650ms); the demo invitation has a small welcoming lift/scale (650ms). Exactly two blocks reveal, once at observer threshold (.15); stock autoplay starts once at (.35). All text begins visible, including during delays, and links remain active. Pointer press scales (.96) over (100ms), releasing instantly; keyboard actions do not scale. Reduced motion disables transitions and animations, removes pointer-press scaling and preview rotation, and settles the stock story. No new dependencies or backend changes.

## Do's and Don'ts

### Do:
- Do keep landing tokens scoped to the public landing page.
- Do preserve the green identity, warm surfaces and understandable language.
- Do retain fictional, read-only labels beside illustrative records.
- Do keep original stock rows visible through every replay state.
- Do give keyboard replay its immediate final state and complete status explanation.
- Do preserve the Bricolage font license with the self-hosted font.

### Don't:
- Don't apply this landing system to signed-in screens without a separate request.
- Don't hide essential facts behind motion or JavaScript.
- Don't invent customers, adoption metrics or commercial outcomes for the examples.
- Don't describe Estimated Profit as accounting, tax or cash profit.
- Don't introduce an input, custom menu or copy-control pattern that this implementation does not have.
