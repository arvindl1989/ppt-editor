# Handoff: deckguard type system — one authority, resolved at draw time

## Overview

deckguard draws KONE slides with python-pptx onto KONE's own master. It has
**two type systems**, and for 29% of its layout library the wrong one wins. This
handoff is the work order to collapse them into one, and to trim the library
while it is open.

The reported symptom was that the divider slide's "fonts and everything look
whack". That is true and it is not a divider bug — `divider_numbering` is simply
the archetype where the fault is most visible, because all three of its slots
are baked and all three are wrong.

**Repo:** `arvindl1989/ppt-editor`, branch `claude/github-token-gpgvrk`
**Package:** `src/deckguard/`

## About the design files

`Deckguard Type Review.dc.html` in this bundle is a **design reference** — an
HTML prototype of the review deck, showing the intended look of a corrected
`divider_numbering` and the argument for the fix. It is not production code and
nothing in it should be lifted into the Python package.

Its value to you is §5: **the four section dividers in that deck are
`divider_numbering` drawn to its own spec.** They are the target state. Open the
file, go to slide 3, and compare it with slide 4, which shows the current render
beside it.

The work itself is Python, in the existing package, following its established
patterns.

## Fidelity

**High fidelity.** Every px value, hex code and role name below is taken from
the built files, `brandmode.py`, `type-audit.json` or measured off the renders.
Do not re-derive spacing or sizes.

---

## 1 · The library, and what is actually reachable

Three different counts are all true, and the difference between them is the
first piece of work.

| | Count |
| --- | --- |
| Archetype definitions carrying regions | **51** |
| Declared in `meter.json` — what the planner can choose | **44** |
| Built and drawable by the renderer | **39** |
| **Unreachable** — regions exist, `meter.json` does not list them | **7** |
| Declared in the meter but not built | 5 |

### The 7 unreachable archetypes

`agenda_a_table` · `card_grid` · `text_picture_h` · `three_content_b` ·
`title_content_b` · `two_content_b` · `two_content_narrow_title_b`

They carry baked type regions but are absent from `meter.json`, so
`pool_for_stop()` can never return them and no plan can select them. Four of the
seven are `_b` variants of archetypes that are already built.

**This matters to the migration.** Of the 83 baked regions and 25
disagreements, these seven hold **20 regions and 6 disagreements** — 24% of the
work, on slides that cannot be produced.

Delete them first. It is the only step with no risk of a visual regression,
and it reduces the real job to:

| | Before | After deleting the orphans |
| --- | --- | --- |
| Baked regions | 83 | **63** |
| Disagreements | 25 | **19** |
| Archetypes needing attention | 22 | **15** |

### The 5 declared but not built

`statement_b`, `text_picture_b`, `two_pictures_text_b` (tier 1), `quote_e`,
`value_prop_four_point` (tier 2). All three tier-1 holes are external, so the
most conservative meter stop is missing the most layouts. See §6 — the
recommendation is not to build them.

### Where the remaining work is concentrated

29 of the 44 declared archetypes have **no baked regions at all** — they already
resolve fully through the brand. The problem is 15 archetypes, and six of them
hold 14 of the 19 real disagreements:

| Archetype | Baked | Disagree |
| --- | --- | --- |
| `agenda_c_split` | 4 | 3 |
| `divider_numbering` | 3 | 3 |
| `timeline_quarter_axis` | 5 | 2 |
| `agenda_b_numbered` | 3 | 2 |
| `title_subtitle_content_a` | 3 | 2 |
| `two_content_narrow_title` | 3 | 2 |
| `milestone_slide` | 12 | 1 |

Migrate in that order. `milestone_slide` is the largest single conversion at 12
regions but only one of them disagrees, so it is volume without controversy —
do it when you want an easy win, not first.

## 2 · The meter: one control, four stops

Context you need before touching the library, because the meter decides what a
deck may contain.

There is **one axis — layout geometry — with four stops, and no separate
audience switch.** The argument for that, from `meter.py`, is worth keeping: an
audience switch plus a freedom slider is two controls for one decision, and the
corners of that matrix are decks nobody should be able to make — a customer deck
with a pink panel, an all-hands with no icons. Collapsing them means the illegal
combinations cannot be expressed at all.

| Stop | Key | What it is | Audience | Promised | Built |
| --- | --- | --- | --- | --- | --- |
| **1** | `master` | On template. The master's own layouts, drawn as the master draws them. | external | 20 | 17 |
| **2** | `slight` | Slight deviation. Master geometry plus layouts that re-divide the master's own bands — stat rows, quote panels, step rows, tables. | external | 30 | 25 |
| **3** | `moderate` | Moderate deviation. Compositions the master does not contain, built on the master's grid: split panels, quadrants, axes, icon rows, chart-plus-commentary. | internal | 41 | 36 |
| **4** | `internal` | Internal slide types. Everything above plus the programme artefacts: the milestone announcement, the org view, the credits grid. | internal | 44 | 39 |

Pools are **cumulative** — stop 4 contains stop 1. Audience is **inferred** from
the stop: 1–2 external, 3–4 internal.

### Tier definitions

| Tier | Meaning |
| --- | --- |
| 1 | Master layout, unmodified geometry. The slide exists in `master_ppt.pptx` and the archetype draws into its regions. |
| 2 | Master bands, re-divided. Same top band, floor and margins; the content area is split differently. |
| 3 | Off-master composition on the master grid. New panels, quadrants or axes. Reads as KONE because grid, type and colour rules are untouched. |
| 4 | Programme artefact. Restructures the slide around information a customer deck never carries: owners, names, dated commitments, internal scope. |

### Invariants — do not break these

- **The meter changes the layout pool and nothing else.** It does not loosen
  colour, type, icons or chrome as it moves right. Those are properties of the
  archetype and the set, not of the stop.
- **Tier is a property of the archetype** (its geometry). **Field colour is a
  property of the `(archetype, audience)` pair**, read from `slide-sets.json`.
  This invariant is the basis for two of the merges in §6.
- An archetype whose declared field is a secondary colour cannot be tier 1 or 2,
  because tiers 1–2 are external and the external field policy is white plus
  blue.
- Every stop must be able to build a complete deck: opening, at least one
  divider, argument slides, and a close.

**The filter is the enforcement.** The planner cannot choose a layout it was
never shown, so nothing downstream has to re-validate the choice against the
meter. Keep it that way — do not add a second validation pass.

`meter.py :: summary()` already renders the promised-vs-built gap as "N not
built yet". Leave it; after §6 that string should read zero everywhere.

## 3 · The fault, precisely

A region takes one of two forms.

**Resolved** — 200 regions. The region says *where*; `brandmode` says what it
looks like, resolving the role against `TYPE_SCALE` at draw time.

```json
{"role": "title", "box": [453, 304, 578, 150]}
```

**Baked** — 83 regions. The region says both. The brand cannot reach it and
nothing downstream knows the difference.

```json
{"role": "dg_text", "box": [453, 304, 578, 150],
 "dg": {"px": 46, "font": "Inter", "caps": false}}
```

The baked form came from porting an HTML archetype gallery: the parser read the
rendered type off each element and wrote it down. That was the right call at the
time — it is how the layouts got built at all — but those 83 regions are now
immune to the brand. Change `TYPE_SCALE` and they do not move. Add a role and
they cannot use it.

### Why the divider shows it first

All three slots of `divider_numbering` are baked, and all three disagree:

| Slot | Baked today | `brandmode` for that slot name | The spec asks for |
| --- | --- | --- | --- |
| `number` | 190px Inter, `#141414` | — | **300px, `#1450F5`** |
| `eyebrow` | 13px Inter, sentence case | 12px KONE Information, caps | A section label, uppercase |
| `title` | 46px Inter | 32px Inter | **56px** |

**Read the title row carefully.** All three authorities disagree, and resolving
the region through the brand moves it from 46px to 32px — *further* from the 56
the spec wants. Deleting the `dg` block is necessary and not sufficient; see §7,
blocker 1.

### The four faults a reader actually sees

Measured off `renders/divider-2.jpg`, not read off the spec:

1. **The numeral is black.** At 142px of cap height in the title's own ink, it
   reads as a large dark shape the eye must get past, not a section index.
2. **The eyebrow is body copy.** 11px of x-height in sentence case is what a
   paragraph gets. This is the one that reads as "whack" — a section marker
   looking like a stray sentence.
3. **Nothing separates the eyebrow from the title.** 26px between the eyebrow's
   baseline and the title's cap, on a slide with 460px of empty field below.
4. **The block rides high.** Ink spans y=258–400 on a 720px canvas; its centre
   is at 329 against a canvas centre of 360.

The numeral is **not** clipped — its ink stops at y=400 inside a box running to
y=510. The flat edge under the `2` is the glyph. Do not "fix" this.

### The subtlety that makes it non-trivial

**A slot's name does not determine its role.** `number` on a divider is a 300px
display numeral; `number` in `numbered_icon_row_6` is a 28px blue figure. Both
are called `number`. So "look the slot name up in `TYPE_SCALE`" is wrong — which
is presumably why the baked blocks were kept.

The pair **`(archetype, slot)`** does determine it, and that is exactly what
`contracts.py` already knows. The external contracts name a role per slot, and
`gaps()` holds the contracts and the renderer to each other in both directions,
currently at zero.

## 4 · The fix, in order of work

0. **Delete the 7 unreachable archetypes.** 20 baked regions and 6
   disagreements gone, with no possible visual regression. Do this first so the
   remaining numbers mean something.
1. **The contract names the role; the region stops carrying type.** Delete every
   remaining `dg` block. Resolve `(archetype, slot) → role → TYPE_SCALE` at draw
   time in `layouts.py :: render`. One system.
2. **Add the display tier the contracts need** — see blocker 1, which must be
   answered before this step.
3. **Migrate the 19 remaining disagreements one at a time**, in the order given
   in §1. Both values are recorded per region in `type-audit.json`, so each is a
   decision rather than a guess. Regenerate the render after each and look at it.
4. **Consolidate the library** — §6. Independent of the type fix; do it after,
   or in parallel by someone else.

`layouts.py :: render` is the only place the two systems meet, and the only place
that needs to change structurally. Do not touch `meter.py`, and do not weaken
`preflight` — it is the only thing in the pipeline that has caught its own
author, twice.

### Where each decision is made, for orientation

| Stage | Owner | Note |
| --- | --- | --- |
| 1 · Input | `web.py :: generate` | The meter's stop decides the audience; there is no separate audience control. |
| 2 · Plan | `assemble.py :: plan` | One model call chooses the archetypes **and** writes the copy. Known weakness — see blocker 4. Out of scope here. |
| 3 · Build | `layouts.py :: render` | **The fix goes here.** |
| 4 · Check | `assemble.py :: preflight` | Reports, does not block. Strengthen, don't replace. |

## 5 · Target state: `DIVIDER_NUMBERING`, corrected

Exact geometry, 1280×720 canvas. This is what the four dividers in the bundled
deck are drawn to.

| | Value |
| --- | --- |
| Field | Sand `#F3EEEA` (internal), white or blue (external) |
| Logo | `kone-logo.svg`, `top:45 left:45`, height 31px. Left, because dividers are cover-kind chrome. |
| Footer chrome | **None.** `brandmode.wants_footer()` returns False for `divider`. |
| Numeral | `left:38`, vertically centred on the canvas. Inter Regular **300px**, line-height 0.8, tracking -0.04em, `#1450F5`. |
| Numeral on a blue field | `#FFFFFF`. The on-dark swap already works — it resolves through the brand. |
| Text column | `left:620`, width 615, vertically centred. |
| Eyebrow | KONE Information **12px**, uppercase, tracking 0.08em, `#1450F5`. `margin-bottom: 26px`. |
| Title | Inter Regular **56px**, line-height 1.0, tracking -0.025em, `#141414`. |

Each line maps to one of the four faults: numeral colour → fault 1, eyebrow font
and casing → fault 2, the 26px gap → fault 3, vertical centring → fault 4.

## 6 · Consolidation: fewer archetypes, same coverage

Yes, the library is larger than the work it does. 51 definitions is too many for
39 built layouts and two 25-slide sets, and the excess is not variety — it is
duplication under different names. Every merge below is available **because the
system already supports the parameter**; none of them needs new machinery.

| Move | Why it is safe | Net |
| --- | --- | --- |
| **Delete the 7 unreachable** — `agenda_a_table`, `card_grid`, `text_picture_h`, `three_content_b`, `title_content_b`, `two_content_b`, `two_content_narrow_title_b` | Absent from `meter.json`; no plan can select them. Zero output change. | −7 definitions |
| **Do not build the 5 declared-unbuilt.** Retire them from `meter.json` instead. | Each is a near-duplicate of something built: `text_picture_b` is `text_picture_a` mirrored; `two_pictures_text_b` is `three_pictures_text` at count 2; `statement_b` (3 stats) is a subset of `kone_numbers` (3–5 stats); `value_prop_four_point` is `text_picture_a` with numbered points; `quote_e` is a quote with a split column. | −5 |
| **`quote_a` + `quote_b` → one quote panel**, field from `slide-sets.json` | `quote_a` is blue-field external, `quote_b` pink-field internal. Same geometry. The meter's own invariant says field is a property of the `(archetype, audience)` pair — two archetypes for one geometry violates it. | −1 |
| **`cover_a_cut4` + `cover_b_cut3` → one cut cover**, `panes: 3\|4` | Identical archetype, different pane count. And the cut cover is a mask over one photo, so pane count is a mask parameter, not a layout. | −1 |
| **`icon_columns_5` + `numbered_icon_row_6` → one icon row**, count 3–6, optional numeral | The contracts already declare overlapping ranges: 3–5 and 4–6. The only real difference is whether a cell carries a numeral. | −1 |
| **`two_content` + `two_content_narrow_title` → one two-column**, title column width a parameter | `brandmode.resolve()` **already** swaps `title` → `title_narrow` at width ≤ 374px. The narrow variant is a box change the brand handles unprompted. | −1 |

**Result: 51 definitions → 35.** Every one built, every one reachable, every one
with a distinct job in `brandmode.jobs()`.

That last clause is the real prize. `brandmode` already carries per-archetype job
descriptions because a planner given a bare list of names cannot choose between
`matrix_2x2` and `segment_breakdown` on merit — a name is not a reason, so it
falls back to the order it was given. **Duplicate archetypes make that worse in a
way no prompt fixes:** when two entries do the same job, the menu is teaching the
planner that the choice does not matter. Cutting 51 to 35 makes every remaining
entry a real decision.

### What not to cut

Do not consolidate on visual similarity alone. `matrix_2x2`, `segment_breakdown`
and `chart_commentary` look related and are not — they answer different
questions and carry different contracts. The test for a merge is whether the
difference is **a parameter the system already reads** (count, field, box width,
pane number). If it is a different job, keep it.

## 7 · Blockers — do not start without answers

These are open by design. Two of them gate the work.

**1. How should a display size be expressed?** *(gates step 2)*
`display` is 44px in `TYPE_SCALE`. The divider wants 300px for its numeral and
56px for its title. Three options, all costly:
- **More roles** (`divider_numeral`, `divider_title`, …) — verbose, and the list
  grows with every archetype wanting an exception.
- **A size override on the contract** — reopens the hole just closed. A contract
  that can set px is a baked block with a different name.
- **A per-archetype scale factor** — compact, and magic. Nobody reading a render
  can work out where 300 came from.

**2. Do the baked blocks go, or get blessed?** *(gates step 1)*
Removing all of them makes the brand the single authority and changes 25 slides.
Keeping them makes `BRAND_MODE.md` advisory for a third of the library, which
makes the contract layer a half-truth. Note that step 0 answers a quarter of
this question for free.

**3. Is the contract table wrong, or is a divider's label not an eyebrow?**
`EXTERNAL_25.md` types the divider's section label as `body`. That is what put
sentence-case body copy where a small-caps label belongs — **the handoff table
has the same bug the renderer has.** Fix both or neither.

**4. Is one model call defensible?** Out of scope for the type fix, tracked here
so it is not lost. Splitting extraction from selection doubles the calls;
prompt caching keeps cost near flat, but it is two places to go wrong.

**5. What should `preflight` refuse?** Today it reports everything and returns
the file. Should anything be fatal, or is a deck you can see the faults in
always better than no deck?

## 8 · Acceptance criteria

- The 7 unreachable archetypes are gone, and `meter.json` plus the region tables
  name the same set.
- No region in the library carries a `dg` block.
- Every `(archetype, slot)` resolves to a role, and `gaps()` is still at zero in
  both directions.
- `renders/divider-2.jpg` regenerated: numeral 300px `#1450F5`, eyebrow 12px
  KONE Information caps, title 56px, ink centred on y=360 ±6px.
- The 19 remaining disagreements each have a recorded decision, not a default.
- `meter.py :: summary()` reports no "not built yet" at any stop.
- `preflight` reports no type outside black / white / KONE Blue, no dash standing
  in for a bullet, nothing below the floor at y=629, no overlapping text, exactly
  one logo per slide.
- **Changing one number in `TYPE_SCALE` visibly moves every region that claims
  that role.** This is the whole point; test it explicitly.

**Expect regressions.** Those 83 regions were measured off renders that looked
right. Resolving them through the brand will change 25 slides and some will look
worse before they look better. A staged migration with the renders in front of
you is the only honest way to do it.

---

## Design tokens

### Colour

| Token | Hex | Use |
| --- | --- | --- |
| KONE Blue | `#1450F5` | Primary. Present on every slide as field or spot colour. |
| Black | `#141414` | All body and headline type. Never grey. |
| White | `#FFFFFF` | Field, and all type on blue. |
| Sand | `#F3EEEA` | Secondary field. **Note the collision** — `F3EEE6` and `F3EEEA` were both in circulation and both shipped, on adjacent slides of the same deck. The real KONE deck measures `F3EEEA`; `brandmode.py` is correct. |
| Light blue | `#D2F5FF` | Secondary field |
| Pink | `#FFCDD7` | Secondary field |
| Mint | `#AAE1C8` | Block inside a layout, **never** a slide field |
| Yellow | `#FFE141` | Block inside a layout, **never** a slide field |
| Hairline | `#E6E6E6` | Rules and table borders |
| Blue tints | `#4373F7` `#7296F9` `#A1B9FB` `#D0DCFD` | Chart series only. Never a background. |

Rules that are not matters of taste: max two secondary colours per slide (charts
excepted); blue field → white type, any secondary field → black type; accents
(`#FF5F28` `#FFA023` `#1ED273`) are UI states and illustration only.

### Typography

**Inter** for everything except labels — Regular 400 for headlines and body,
SemiBold 600 only where emphasis is genuinely intended. **Inter is never bold,
never blue, never grey, and always sentence case.** The only uppercase word is
"KONE".

**KONE Information** for labels, eyebrows, page numbers, attribution. Always ALL
CAPS. May be blue, black or white.

| Role | Size | Line-height | Tracking |
| --- | --- | --- | --- |
| Cover title | 76px | 0.98 | -0.03em |
| Outro title | 120px | 0.95 | -0.04em |
| Section numeral (divider) | 300px | 0.8 | -0.04em |
| Hero stat figure | 280px | 0.86 | -0.04em |
| Divider title | 56–64px | 1.0–1.02 | -0.025em |
| Statement / large quote | 40–56px | 1.05–1.2 | -0.02em |
| Slide title | 40px | 1.1 | -0.015em |
| Stat figure (band) | 52–64px | 1.0 | -0.025em |
| Card heading | 24–26px | 1.15–1.2 | -0.01em |
| Numeral (step / workstream) | 28px | 1.0 | -0.01em |
| Lead paragraph | 19px | 1.4–1.5 | — |
| Body | 15–18px | 1.45–1.5 | — |
| Eyebrow (KONE Information) | 12px | — | 0.08em |
| Label / scope (KONE Information) | 12px | 1.3–1.6 | 0.06em |
| Footer (KONE Information) | 11px | — | 0.05em |

Nothing on a 1280×720 slide is set below 15px, and no label below 11px.

### Geometry

- Canvas 1280×720. Safe margin 45px left and top. Content column runs to x:1235.
- Logo 31px tall at top:45 — left on covers, dividers and the outro; right
  otherwise. **Exactly one per slide.**
- Footer chrome: date `left:45 top:658`, page number `right:45 top:658`, both
  KONE Information 11px uppercase. On content slides only.
- Vertical rhythm: title band bottom 195, text content starts 227, object rows
  start 264, floor at 629, footer at 658.
- **Corner radius 0 everywhere.** Rules and underlines 4px or 6px solid KONE
  Blue. No shadows, no gradients except photo protection, no textures, no blur.

### Bullets

Real `<ul style="list-style:disc">` markers — marker in KONE Blue (`color` on
the `ul`), text in `#141414` (a `span` inside the `li`). One nested level max
(`list-style:circle`). A hyphen, dash or em dash standing in for a bullet is not
acceptable, and `preflight` already checks for it.

---

## Assets

| Path | Contents |
| --- | --- |
| `assets/logo/` | `kone-logo.svg`, `kone-logo-white.svg`, `kone-tagline.svg`, `kone-tagline-white.svg`. Keep RGBA end to end — never flatten onto black. The `.pptx` embed path needs the PNG variants; PowerPoint cannot take SVG. |
| `assets/photos/` | `escalator-station.jpg` — used for the cut cover in the reference deck. |
| `renders/` | `divider-1..4.jpg` — the reported archetype on all four fields it ships against. `dividers.pptx` is the source file. |

Fonts: Inter from Google Fonts (400 and 600). KONE Information is proprietary,
self-hosted from `fonts/KONE_Information.ttf`.

**Production caveat carried over from the source handoff:** the pictogram set in
the repo was extracted and recoloured from the master template. The full official
library lives at brandbook.kone.com and resolves by name — wire that sprite in
production and drop the extracted copies. Only `arrow`, `cloud` and `connect`
are genuine master pictograms.

---

## Files in this bundle

| File | What it is |
| --- | --- |
| `README.md` | This document. Self-sufficient — implement from this alone. |
| `Deckguard Type Review.dc.html` | The review deck. 21 slides; its four dividers are the target state. Design reference only. |
| `deck-stage.js` | Slide runtime for the deck HTML — scaling, nav, notes, print. Not part of the fix. |
| `type-audit.json` | Every baked region with both values. **This is your migration checklist.** |
| `contracts.json` | What each archetype needs, per slot, with cardinality and role. |
| `meter.json` | The deviation meter: four stops, tier per archetype, field per (archetype, audience). |
| `state.json` | The four headline counts, machine-readable. |
| `renders/` | The four divider renders and the source `.pptx`. |
| `assets/` | Logo, tagline and the cover photograph used by the deck. |

The deck HTML needs `assets/` and `deck-stage.js` alongside it to render. Its
design-system stylesheets are not bundled — open it in the original project if
you need it pixel-accurate, or read the geometry out of this README, which is
the authority either way.
