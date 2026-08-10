# Handoff: KONE 25+25 — internal and external slide sets

## Overview

Two 25-slide KONE-branded presentation sets, built from the KONE brand
guidelines and the master PowerPoint template.

- **Internal 25** — town halls, all-hands, programme updates, planning. Built
  and complete: `Internal 25 v2.dc.html` (25 slides, 1280×720).
- **External 25** — customer-facing pitch, proposal, QBR, launch. Built and
  complete: `External 25.dc.html` (25 slides, 1280×720). A second worked
  example, `Patient Flow in Healthcare.dc.html` (11 slides), applies the same
  treatment to a healthcare narrative.

Both sets share one archetype vocabulary and one 1280×720 grid. The difference
between them is dressing, not geometry.

## About the design files

The HTML files in this project are **design references**. They are prototypes
showing intended look and behaviour — not production code to lift. The task is
to recreate them in the target codebase's own environment (React, Vue, a
python-pptx generator, whatever the deck pipeline is) using its established
patterns. Where no environment exists yet, pick the framework that fits the
delivery format and implement the designs there.

The decks render through a small slide-stage web component (`deck-stage.js`)
that handles scaling, navigation, the thumbnail rail, speaker notes and
print-to-PDF. If the target pipeline already has a deck runtime, replace it;
only the slide markup is the design.

## Fidelity

**High fidelity.** Every colour, type size, position and measurement below is
final and taken from the built files. Positions are absolute pixels on a
1280×720 canvas. Recreate pixel-perfectly; do not re-derive spacing.

---

## Design tokens

### Colour

| Token | Hex | Use |
| --- | --- | --- |
| KONE Blue | `#1450F5` | Primary. Present on every slide as field or spot colour. |
| Black | `#141414` | All body and headline type. Never grey. |
| White | `#FFFFFF` | Field, and all type on blue. |
| Sand | `#F3EEE6` | Secondary field |
| Light blue | `#D2F5FF` | Secondary field |
| Pink | `#FFCDD7` | Secondary field |
| Mint | `#AAE1C8` | Secondary block (never a full background) |
| Yellow | `#FFE141` | Secondary block (never a full background) |
| Blue tints | `#4373F7` `#7296F9` `#A1B9FB` `#D0DCFD` | Charts and infographics only |

Rules that are not matters of taste:

1. Max **two** secondary colours in one slide. Charts excepted.
2. Yellow and mint are **blocks inside a layout, never the slide field**.
3. Blue field → white type and white icons. Any secondary field → black type
   and black or blue icons.
4. Tints are chart series only. Never a background.
5. Accent colours (`#FF5F28`, `#FFA023`, `#1ED273`) are UI states and
   illustration only. They do not appear in either deck.
6. Type is black, white, or — for KONE Information labels only — KONE Blue.
   Inter is **never** blue and **never** grey.

### Typography

**Inter** for everything except labels. Regular 400 for headlines and body;
SemiBold 600 only where emphasis is genuinely intended — Inter is never bold.
Inter is always **sentence case**; the only uppercase word is "KONE".

**KONE Information** for labels, eyebrows, page numbers, scope lines,
attribution. Always ALL CAPS. May be blue, black or white.

| Role | Size | Line-height | Tracking | Weight |
| --- | --- | --- | --- | --- |
| Cover title | 76px | 0.98 | -0.03em | 400 |
| Outro title | 120px | 0.95 | -0.04em | 400 |
| Section numeral (divider) | 300px | 0.8 | -0.04em | 400 |
| Hero stat figure | 280px | 0.86 | -0.04em | 400 |
| Divider title | 56–64px | 1.0–1.02 | -0.025em | 400 |
| Statement / large quote | 40–56px | 1.05–1.2 | -0.02em | 400 |
| Slide title (h2) | 40px | 1.1 | -0.015em | 400 |
| Stat figure (band) | 52–64px | 1.0 | -0.025em | 400 |
| Card heading | 24–26px | 1.15–1.2 | -0.01em | 400 |
| Numeral (step / workstream) | 28px | 1.0 | — | 400, KONE Blue |
| Lead paragraph | 19px | 1.4–1.5 | — | 400 |
| Body | 15–18px | 1.45–1.5 | — | 400 |
| Eyebrow (KONE Information) | 12px | — | 0.08em | uppercase |
| Label / scope (KONE Information) | 12px | 1.3–1.6 | 0.06em | uppercase |
| Footer (KONE Information) | 11px | — | 0.05em | uppercase |

Nothing on a 1280×720 slide is set below 15px, and no label below 11px.

### Geometry and spacing

- Canvas 1280×720. Safe margin **45px** left, 45px top.
- Content column runs to x:1235 (1190px wide).
- Logo: top 45px, 31px tall — left on covers and blue-column slides, right
  otherwise. **Exactly one logo per slide.**
- Footer chrome on every slide except 1, 4, 5, 6 and 25: date bottom-left at
  `left:45 top:658`, KONE Information 11px uppercase.
- Corner radius **0 everywhere**. KONE is a square brand; the logo is four hard
  squares.
- No shadows, no gradients except photo protection, no textures, no blur.
- Rules and underlines: 4px or 6px solid KONE Blue.
- Icon chips: 44px, 48px, 56px, 64px or 72px squares, solid fill, icon at
  roughly half the chip.
- Grid gaps: 20–32px between cards, 14px between list rows.

### Bullets

Real `<ul style="list-style:disc">` markers. Marker in KONE Blue (set
`color:#1450F5` on the `ul`), text in black (`<span style="color:#141414">`
inside the `li`). One nested level maximum. A hyphen, dash or em dash standing
in for a bullet is not acceptable.

### Photography

Bright, high-key, natural light, real people moving through buildings.
Full-bleed, sharp corners, natural colour — no duotone, no filters. White type
over a photograph always gets a protection gradient beneath it (internal slide
06 uses `linear-gradient(105deg, rgba(20,20,20,.78) 0%, rgba(20,20,20,.46) 40%,
rgba(20,20,20,0) 74%)`).

The cut cover (slide 01) is **one photo behind background-coloured mask
rectangles**, not a photo pre-sliced into panes. Dropping in a single new image
must reproduce the chopped effect.

---

## Internal 25 — as built

File: `Internal 25 v2.dc.html`. Subject: a fictional regional programme,
"People Flow Intelligence". Replace the copy; the structure is the deliverable.

Field rotation follows content type, not a fixed cadence: white is the default,
sand carries process, light blue carries structure, pink carries voice and
people, mint carries plan and function, yellow carries the ask.

| # | Archetype | Slide | Field / blocks |
| --- | --- | --- | --- |
| 01 | `COVER_B_CUT3` | Cover | White field, three photo panes cut across the top, blue icon chip, black 76px title |
| 02 | `PICTURE_INTRO` | Why we're here | White, full-height photo right (574px), three blue icon chips left |
| 03 | `AGENDA_C_SPLIT` | Today | Mint column left (420px), sand agenda rows, final row blue |
| 04 | `DIVIDER_TITLE_ONLY` | Section break, plain | Light-blue field, blue chip, 64px title, 6px blue rule |
| 05 | `DIVIDER_NUMBERING` | Section break, numbered | Sand field, 300px blue numeral, title right |
| 06 | `IMAGE_SECTION_DIVIDER` | Section break, photo | Full-bleed photo, black protection scrim, white type |
| 07 | `ICON_COLUMNS_5` | Five things | Five cards: four light blue, fifth blue with white type |
| 08 | `NUMBERED_ICON_ROW_6` | Six workstreams | White, 3×2 grid, 4px blue top rule per cell, blue numerals |
| 09 | `LIFECYCLE_4STAGE` | Lifecycle | White, four illustrations each on a 120px sand block, blue stage rules |
| 10 | `HOW_IT_WORKS_3STEP` | How it works | Three sand panels, illustration over numbered step |
| 11 | `QUARTERLY_PLAN_4COL` | Year by quarter | Blue quarter headers; bodies mint Q1–Q3, pink Q4 |
| 12 | `TIMELINE_QUARTER_AXIS` | Milestones | Pink panel left (340px), 6px blue axis right with four stems |
| 13 | `MATRIX_2X2` | Effort and impact | Blue / yellow / light blue / black-outline quadrants |
| 14 | `MILESTONE_SLIDE` | Announcement | White, full-width blue stat band (150px, five figures) |
| 15 | `ORG_FUNCTIONS` | Who does what | Sand list panel left, blue owner box, three mint function boxes |
| 16 | `KONE_NUMBERS` | Where we stand | Full KONE Blue field, five 64px white figures, white rules |
| 17 | `SEGMENT_BREAKDOWN` | By segment | Blue highlight panel, blue-tint bars on sand tracks, light-blue commentary |
| 18 | `CHART_COMMENTARY` | Callout volume | White chart, mint "what it shows", pink "what it does not" |
| 19 | `HERO_STAT` | The one number | Light-blue field, 280px blue figure |
| 20 | `QUOTE_B` | Voice of the team | Pink field, 44px black quote, blue rule |
| 21 | `QUOTE_E` | Voice with context | Blue column left (420px, white type), quote black on white |
| 22 | `CREDITS` | Who did the work | Sand field, twelve names in a 4-column grid, blue rule per name |
| 23 | `STATEMENT_LINKS` | What we need | 56px statement, three yellow cards with blue icon chips |
| 24 | `RESOURCE_LINKS` | Where to find more | Four tiles: pink, pink, mint, blue |
| 25 | `OUTRO` | Thank you | Full KONE Blue field, 120px white title, tagline bottom right, no footer |

Charts on slides 17 and 18 carry `data-om-raster="true"` so PowerPoint export
embeds them as images rather than attempting shape conversion.

Every slide carries `data-screen-label`, `data-label` and
`data-speaker-notes`. The notes travel with the slide on reorder and are read
by both the notes panel and the PPTX exporter.

## External 25 — as built

File: `External 25.dc.html`. Region contracts per archetype are in
`EXTERNAL_25.md`. Subject: a fictional portfolio modernisation proposal,
"Northgate Estates". Replace the copy; the structure is the deliverable.

The external treatment is stricter than the internal one: **blue, white, black
and photography only**. No secondary colour anywhere — no sand, light blue,
pink, mint or yellow. No named-icon archetypes; every icon-led layout was
pushed to the internal set, because an unnamed icon is omitted and the row
reflows. Blue appears as spot colour (rules, numerals, labels, the numbered
chips) on white slides, and as a full field on exactly two: the stat band on 19
and the quote on 20.

| # | Archetype | Slide | Field / treatment |
| --- | --- | --- | --- |
| 01 | `COVER_A_CUT4` | Cover | White field, four photo panes cut across the top, 76px black title |
| 02 | `COVER_F_FULLBLEED` | Cover, alternate | Full-bleed photo, protection gradient, white type, white mark and tagline |
| 03 | `AGENDA_B_NUMBERED` | What we will cover | White, five rows on hairlines, 28px blue numerals |
| 04 | `DIVIDER_NUMBERING` | Section break, numbered | White field, 300px blue numeral, title and 6px rule right |
| 05 | `IMAGE_SECTION_DIVIDER` | Section break, photo | Full-bleed photo, protection scrim, white type |
| 06 | `STATEMENT_A` | The turn in the story | White, 6px blue rule, 56px sentence, one supporting paragraph |
| 07 | `TITLE_CONTENT` | Survey findings | White, real disc bullets, one nested level |
| 08 | `TITLE_SUBTITLE_CONTENT_A` | Where the risk sits | White, subtitle under title, four 4px-ruled bullet blocks |
| 09 | `TWO_CONTENT` | Repair or modernise | Two bulleted columns; grey rule left, blue rule right |
| 10 | `TWO_CONTENT_NARROW_TITLE` | Why replace | 330px title column left, 765px argument right |
| 11 | `THREE_CONTENT` | Three parts | Three columns, 4px blue top rule, KONE Information tail line |
| 12 | `TEXT_PICTURE_A` | The equipment | Full-height photo right (574px), four 12px blue markers left |
| 13 | `TEXT_PICTURE_G` | Service | 280–300px banner photo top with top scrim, three-column tail |
| 14 | `TEXT_PICTURE_B` | On an occupied site | Photo right, three numbered points left |
| 15 | `THREE_PICTURES_TEXT` | Reference projects | Three 250px photos over label, heading and caption |
| 16 | `TWO_PICTURES_TEXT_B` | Before and after | Two 236px photos, each over a heading and bullets |
| 17 | `HERO_STAT` | The one number | White field, 280px blue figure, method note right |
| 18 | `STATEMENT_B` | Three numbers | Three 64px figures, all the same size, blue top rules |
| 19 | `KONE_NUMBERS` | KONE at scale | White field, full-bleed 190px blue band, five white figures |
| 20 | `QUOTE_A` | Customer voice | Full KONE Blue field, 48px white quote, white footer chrome |
| 21 | `VALUE_PROP_FOUR_POINT` | Four commitments | 2×2 photo grid left, four numbered points on hairlines right |
| 22 | `HOW_IT_WORKS_3STEP` | How each building runs | 280px photo band, narrow title left, three steps right |
| 23 | `TIMELINE` | Phasing | 6px blue rule, four 30px markers, four period columns |
| 24 | `COMPARISON_TABLE` | Scope comparison | Hairline table, no fills; recommended column headed in blue |
| 25 | `OUTRO` | Thank you | White field, 120px black title, contact block, tagline |

Footer chrome runs on slides 3 and 6–24: date bottom-left at `left:45 top:658`,
page number bottom-right at `right:45 top:658`, both KONE Information 11px
uppercase. Slides 1, 2, 4, 5 and 25 carry none. The chrome is set white where
it falls on a dark ground: slide 20 (blue field) and slide 14, where the page
number sits over a dark photograph. On slide 12 the photograph is light in that
corner, so the number stays black — set the colour against the image, not
against the archetype.

Both decks also carry a **centred archetype name** at `top:658` in KONE
Information 10px. It is a reference marker for this exercise, not deck chrome —
strip it in production.

`Patient Flow in Healthcare.dc.html` (11 slides) applies the same treatment to
a healthcare narrative and is worth reading as a second sample of the same
rules under different content.

---

## Interactions and behaviour

The decks are presentation artefacts, not applications. Behaviour is limited to
the stage:

- **Navigation** — arrow keys, click, or `deckStage.goTo(n)` (0-indexed).
- **Thumbnail rail** — click to select and jump, shift/cmd-click to multi-select,
  Delete to remove, drag to reorder, right-click for skip/move/duplicate.
- **Speaker notes** — read from each section's `data-speaker-notes`.
- **Print** — one page per slide.

No hover states, no transitions, no animation. If the target environment adds
motion, keep it quiet: ~140ms ease, colour shifts only, never scale or bounce.
Transparency and blur are not KONE motifs.

## State management

None. Both decks are static markup. The only state is the current slide index,
owned by the stage component.

## Assets

All paths are relative to the project root.

| Path | Contents |
| --- | --- |
| `assets/logo/` | `kone-logo.svg`, `kone-logo-white.svg`, `kone-tagline.svg`, `kone-tagline-white.svg`. Keep RGBA end to end — never flatten onto black. |
| `assets/pict/blue/`, `/white/`, `/black/` | 26 solid-fill KONE pictograms in each colour: alert, arrow, bars, building, calendar, check, clock, cloud, connect, document, elevator, gauge, gear, globe, growth, link, lock, mobile, nut, people, search, shield, target, train, trend, van. |
| `assets/illus/` | 14 line illustrations: buildings, cloud, elevator-tech, escalator, office, phone, rocket, technician-tools, technician, tool, train, van, walkway, wheelchair. Black line art with a single blue accent. |
| `assets/photos/` | 15 photographs, natural colour, full-bleed use. |
| `assets/sea-map.png` | Regional map used in the external deck. |

**Production caveat.** The pictograms here were extracted and recoloured from
the master template. The full official library lives at brandbook.kone.com and
resolves by name; wire that sprite in production and drop these. The three
genuine master pictograms are arrow, cloud and connect.

Nine of the illustrations have no written description, so a content planner
cannot select them by meaning. Either describe them or restrict slide-building
to the described set.

**Fonts.** Inter (Google Fonts, weights 400 and 600) and KONE Information
(proprietary, self-hosted from `fonts/KONE_Information.ttf`). Noto Sans for
non-Latin scripts, Arial as the system fallback in email and signatures.

## Files

| File | What it is |
| --- | --- |
| `Internal 25 v2.dc.html` | The internal 25, complete. |
| `External 25.dc.html` | The external 25, complete. |
| `Patient Flow in Healthcare.dc.html` | The external treatment on a second subject, 11 slides. |
| `Internal 25.dc.html` | First internal pass, kept for reference. Superseded by v2. |
| `deck-stage.js` | Slide stage: scaling, nav, rail, notes, print. |
| `design_handoff_kone_25/README.md` | This document. |
| `design_handoff_kone_25/CLAUDE_CODE.md` | Build instructions and order of work. |
| `design_handoff_kone_25/INTERNAL_25.md` | Internal set, as-built spec. |
| `design_handoff_kone_25/EXTERNAL_25.md` | External set, archetype spec with region contracts. |
| `design_handoff_kone_25/BRAND_MODE.md` | The brand-rule source these sets were checked against. |
| `design_handoff_kone_25/slide-sets.json` | Machine-readable set definitions. |

The deck HTML files stay at the project root because they load `assets/` and
`deck-stage.js` by relative path. Download the whole project if you need them
to render locally.
