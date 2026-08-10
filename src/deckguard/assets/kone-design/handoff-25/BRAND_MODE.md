# Brand mode

The answers to `OPEN_QUESTIONS.md`, in the form the tool consumes.
Everything here is settled — it comes from the KONE brand guidelines, the
master template geometry, and the nine `refined` archetypes that were already
checked in a render. `brand-mode.json` is the same content, machine-readable.

Applied in full, this closes every `derived` and `legacy` gap: **223 of the
tool's 293 regions currently have no type block** and are being guessed at from
a role name. The table in §1 is that missing information.

---

## 1. Type scale per role

The one thing worth having. Every region gets a role; every role gets a line
here. Nothing is inferred from a box size, and nothing changes with the width
of the box it lands in — except the four roles that say so.

### Inter — headlines and body

Sentence case always. Black or white, never blue, **never grey**. Weight 400
everywhere except `heading`, which is the one SemiBold role in the system.

| role | font | px | wt | lead | track | colour | case | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `display` | Inter | 44 | 400 | 1.08 | -0.02em | `#141414` | sentence | Cover title, outro statement. White on a dark cover. |
| `statement` | Inter | 40 | 400 | 1.15 | -0.015em | `#141414` | sentence | One sentence carrying the whole slide (STATEMENT_A). |
| `title` | Inter | 32 | 400 | 1.15 | -0.005em | `#141414` | sentence | The deck title size. Every slide title is 32 — no exceptions, no 24pt variant. |
| `title_narrow` | Inter | 28 | 400 | 1.15 | -0.005em | `#141414` | sentence | Title inside a column ≤374px (TWO_CONTENT_NARROW_TITLE, QUOTE_A/B left column). |
| `title_light` | Inter | 32 | 400 | 1.15 | -0.005em | `#FFFFFF` | sentence | Title on blue, black or a scrimmed photo. |
| `subtitle` | Inter | 20 | 400 | 1.4 | 0 | `#141414` | sentence | Qualifying line under a title. Occupies 195–232, pushing content to 264. |
| `heading` | Inter | 19 | **600** | 1.25 | 0 | `#141414` | sentence | Column, card or stage heading. The ONLY role that is SemiBold. |
| `on_panel_heading` | Inter | 19 | **600** | 1.25 | 0 | `#FFFFFF` | sentence | Heading on a blue or black panel. |
| `body` | Inter | 16 | 400 | 1.5 | 0 | `#141414` | sentence | Paragraph and column text. Never SemiBold, never grey. |
| `body_narrow` | Inter | 15 | 400 | 1.45 | 0 | `#141414` | sentence | Body in a column ≤300px. Below 300px, reduce; never wrap one word per line. |
| `on_panel_body` | Inter | 16 | 400 | 1.5 | 0 | `#FFFFFF` | sentence | Body on a blue or black panel. |
| `bullets` | Inter | 19 | 400 | 1.45 | 0 | `#141414` | sentence | Real disc markers in KONE Blue, text black. 12px between items. Nested: 17px, circle marker, one level max. |
| `caption` | Inter | 14 | 400 | 1.4 | 0 | `#141414` | sentence | Line under a photo tile. Black — never the grey the token file suggests. |
| `quote_lg` | Inter | 30 | 400 | 1.3 | -0.005em | `#141414` | sentence | Quote in a panel ≥600px wide. This is the fix for the quote_b symptom. |
| `quote_sm` | Inter | 24 | 400 | 1.3 | -0.005em | `#141414` | sentence | Quote in a panel <600px wide. |
| `price` | Inter | 34 | 400 | 1.1 | -0.01em | `#141414` | sentence | Offer price figure. |

### KONE Information — labels and chrome

ALL CAPS always. Blue, black or white.

| role | font | px | wt | lead | track | colour | case | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `eyebrow` | KONE Info | 12 | 400 | 1.2 | 0.08em | `#1450F5` | CAPS | Small label above a title. |
| `eyebrow_light` | KONE Info | 12 | 400 | 1.2 | 0.08em | `#FFFFFF` | CAPS | Eyebrow on blue, black or a scrimmed photo. |
| `label` | KONE Info | 12 | 400 | 1.2 | 0.06em | `#1450F5` | CAPS | Section, scope, stat and axis labels. |
| `stat_label` | KONE Info | 12 | 400 | 1.2 | 0.06em | `#141414` | CAPS | The word under a KONE number. Black, so the figure keeps the blue. |
| `attribution` | KONE Info | 12 | 400 | 1.3 | 0.06em | `#141414` | CAPS | Name, title, company under a quote. |
| `axis` | KONE Info | 12 | 400 | 1.2 | 0.06em | `#1450F5` | CAPS | Timeline period markers. |
| `footer` | KONE Info | 11 | 400 | 1 | 0.05em | `#141414` | CAPS | Date x:45 y:658 · page x:1167 y:658. White on dark. |
| `classification` | KONE Info | 10 | 400 | 1 | 0.05em | `#141414` | CAPS | "KONE INTERNAL" etc. Bottom-left above the date, or omitted. Never grey top-right. |

### KONE numbers

Inter, tabular figures, weight 400. The figure is blue; the label under it is
black, so the blue reads as the number rather than the pair.

| role | font | px | wt | lead | track | colour | case | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `hero_value` | Inter | 96 | 400 | 1 | -0.02em | `#141414` | sentence | One figure carrying the slide. |
| `stat_value` | Inter | 64 | 400 | 1 | -0.02em | `#1450F5` | sentence | A row of 3–5 figures — ALL the same size regardless of digit count. A zero renders #141414. |
| `stat_value_md` | Inter | 44 | 400 | 1 | -0.02em | `#1450F5` | sentence | Inline stat beside body copy. |
| `number` | Inter | 28 | 400 | 1 | -0.01em | `#1450F5` | sentence | 01–06 in a numbered list or icon row. |
| `figure` | Inter | 200 | 400 | 0.85 | -0.03em | `#141414` | sentence | The giant section number on DIVIDER_NUMBERING. Black on every secondary field. |

### Roles to retire

Ten role names in the registry encode a rendering rather than an intent —
`gal_i64_141414` means "Inter 64 black", which is an output, not a decision.
They read back into the table above:

| current | becomes |
| --- | --- |
| `body_muted` | body — "muted" is the grey that was banned. Same size, #141414. |
| `title_light` | kept, but only legal on blue/black/scrimmed-photo backgrounds |
| `gal_i64_141414` | hero_value or stat_value — auto-named from the gallery, carries no intent |
| `gal_i19_141414` | bullets or heading — decide per slot, do not auto-map |
| `gal_i43_141414` | stat_value_md |
| `gal_i15_141414` | body_narrow |
| `gal_i16_141414` | body |
| `gal_i64_FFFFFF` | stat_value on dark |
| `gal_i19_FFFFFF` | on_panel_body |
| `gal_i34_FFFFFF` | title_light |
| `gal_k12_FFFFFF_c` | eyebrow_light |

### Two rules that override the box

1. **A title is 32px on every slide in the deck.** There is no 24pt title
   variant; `title_24pt_footers` is a type variant of `TITLE_CONTENT`, not a
   layout. The only reduction is `title_narrow` (28px) in a column ≤374px.
2. **A quote sizes to its panel, not to `body`.** ≥600px wide → 30px.
   Narrower → 24px. This is the `quote_b` symptom in `OPEN_QUESTIONS.md §1`,
   and it is the only place where a box legitimately changes the type.

---

## 2. Vertical rhythm — where content starts

**The rule: a block starts 32px below the bottom of the block above it. A row
of *objects* starts 69px below a title instead of 32.**

That single rule produces both of the numbers `LAYOUTS.md` shows, which is why
neither is the standard on its own:

| above | below | content starts | arithmetic |
| --- | --- | --- | --- |
| title only | paragraph, bullets, text columns | **227** | title band 91 + 104 = 195, + 32 |
| title only | a row of objects — icons, cards, photo tiles, stats | **264** | 195 + 69 |
| title + subtitle | anything | **264** | subtitle occupies 195–232, + 32 |
| eyebrow + title | as above | unchanged | the eyebrow sits at 47 in its own band, above the title |

An object needs more air above it than a line of text does, because its own
top edge is hard. That is the whole reason for the second number.

**Slides are top-weighted.** Content hangs from the top band and the leftover
space collects at the bottom. Never vertically centre, never distribute to
fill, never stretch a row to reach the floor. A KONE slide with air at the
bottom is correct; the 248px hole in the middle of the review slide was not the
white space, it was the row being pinned to the bottom third.

**The floor is y=629.** Nothing but chrome below it. Footer sits at 658.

---

## 3. Chrome

Owned by the layout. An archetype declares the variant it needs and draws
nothing.

- **Logo** — top-left `45,45` on covers, dividers and the outro; top-right
  (right edge at 1235) on every other slide. White variant on blue, black or a
  scrimmed photo. *The current `image_section_divider` render has a logo in
  both corners.*
- **Tagline** — covers and the outro only, bottom-right.
- **Footer** — date `45,658`, page number `1167,658`, role `footer`.
  Mandatory except on covers, dividers, the outro, `fullslide_picture` and
  `blank`. It is missing from most of the current renders.
- **Classification** — bottom-left at `45,640`, role `classification`, black.
  The grey "KONE Internal" sitting top-right in the renders is wrong on
  position, colour and font.

---

## 4. Photo protection

Only when type sits **on** the photo. Covers A/B/C put their titles on white —
they get no scrim, and the one they have today should come off.

- **Bottom-up** (`COVER_F_FULLBLEED`, `TEXT_PICTURE_G` banner, any full-bleed
  with type low): `linear-gradient(180deg, rgba(20,20,20,0) 45%, rgba(20,20,20,0.72) 100%)`
  across the whole frame, type in the bottom 40%.
- **Left-to-right** (`IMAGE_SECTION_DIVIDER`):
  `linear-gradient(90deg, rgba(20,20,20,0.78) 0%, rgba(20,20,20,0) 55%)`.
- **Never** a flat overlay, a globally darkened image, or a solid panel. The
  photograph stays natural-colour everywhere it is visible.

---

## 5. Icons — do not default

**Ruling: if the planner does not name an icon, omit it and reflow.** The
layout must be legal with no icons at all. A cloud beside "briefing quality" is
worse than nothing, and it is worse in a way the reader blames on KONE rather
than on the tool.

When the planner *does* name them, resolve against the 609-name sprite. The
keyword map in `brand-mode.json` (`icons.keyword_map`, 48 entries) covers the
common deck subjects — use it to *suggest* names to the planner, never to fill
a gap silently.

The three shipped pictograms are not a fallback set. Cycling
cloud / people / clock / wrench / calendar is the single most visible tell in
the current renders: it appears on `icon_columns_5`, `numbered_icon_row_6`,
`lifecycle_4stage`, `resource_links` and `segment_breakdown`, and on every one
of them the icons are unrelated to the words beside them.

---

## 6. Bullets

Real list markers. Disc in KONE Blue, text in `#141414`, 19px, 12px between
items, one nested level (circle, 17px).

**A hyphen, dash or em dash standing in for a bullet is a brand violation**, and
it is live right now in `org_functions`, `statement_links`,
`two_picture_compare` and `three_pictures_text`. Worth a lint rule: any text
run beginning `- `, `— ` or `– ` at the start of a line in a bullet region
fails.

---

## 7. Milestone ticks — the ceiling is three

Three is genuinely the ceiling, and the column must not push the sand band.
Labels are role `label` (KONE Information, 12px, caps), one line, ≤45
characters, pitch 34, column top 186, band top 276.

**A fourth tick, or a label that wraps, moves into the sand band as a scope
item.** The band is the overflow, not the column.

---

## 8. The recognition arc

- `AGENDA_B_NUMBERED` **is** the right name — `slideLayout8` is the numbered
  agenda. The registry entry is what's wrong: it reads `{title, body, body2}`
  and cannot hold four numbered sections. Change it to
  `{title, items:[{number, label}]}` and make `agenda_contents` an alias.
- **Cover and outro: correct as built.** The arc should emit neither; the
  master owns Cover F and Thank you. Two covers and three closing slides was
  the right thing to stop.

---

## 9. Which archetypes should not exist

**21 of 83.** `REGISTRY.md` has the full table with a redirect for each. The
shape of it:

| what | count | why |
| --- | --- | --- |
| Master twins | 9 | Geometrically identical to a parent; the master duplicates them only to carry a type variant. Once §1 fixes the type, the twin has no reason to exist. |
| Colour variants of a divider | 4 | `divider_a/b/c/d` differ by field colour. That is a property, not an archetype. |
| Redundant covers and agendas | 4 | `cover_d`, `cover_e`, `agenda_a_bullets`, `agenda_a_text`. |
| Aliases and type variants | 3 | `agenda_contents`, `title_24pt_footers`, `end_logo`. |
| Not for customer decks | 1 | `user_guide` — the master's own instructions page, with an all-caps Inter title. |

Retire them as **aliases, not deletions**: the old key keeps resolving to the
canonical parent so nothing that already builds stops building. The planner's
menu goes from 83 near-neighbours to 62 separable ones, which is the real win —
most mis-routing is a choice between two archetypes that should have been one.

---

## 10. Preflight — the checks worth having in tests

Each of these catches something visible in the current renders:

1. No Inter run in weight 600 outside role `heading` / `on_panel_heading`.
2. No text fill that is not `#141414`, `#FFFFFF` or `#1450F5`; blue only on
   KONE Information runs and KONE numbers.
3. No all-caps Inter run, except the literal word `KONE`.
4. Every slide outside the omit list carries a date and a page number.
5. Exactly one logo per slide.
6. No bullet region whose first characters are `- `, `— ` or `– `.
7. No icon on a slide that did not name it.
8. Every region's bottom ≤ 629.
9. Slide title regions all resolve to 32px (or 28px where `title_narrow`).
10. Two secondary colours maximum per slide; yellow and mint never full-bleed.
11. White type on a photo has a gradient beneath it.
12. Sand normalises to `#F3EEE6` on write.
