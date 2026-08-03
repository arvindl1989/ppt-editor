# KONE slide archetypes — generation spec

A catalogue of **57 reusable KONE slide layouts**. Gallery 1 (covers, agendas, dividers, closers) is rebuilt **1:1 against the KONE master template** — geometry, chrome and photo masks are exact replicas. Galleries 2–4 derive from the master's 62 layouts with near-duplicates collapsed and are pending the same rework. Claude Code uses this file to turn a prompt into finished KONE slides: pick the archetype whose shape fits the content, copy its markup, fill the named slots.

Every archetype is one `<section>` sized **1280×720** on the KONE grid (45px margin). Copy the markup straight out of its gallery file — each block is preceded by an HTML comment `<!-- NN NAME -->`. **Archetype names are the canonical IDs**: numbering restarts at 01 in gallery 1, while galleries 2–4 keep their historical 15–54 numbers.

## Gallery files

| File | Archetypes | Covers |
|---|---|---|
| `archetypes-1-covers-dividers.html` | 01–17 | Covers, dividers, picture intro, agendas, outro, end — same 17 presentable as a deck |
| `archetypes-2-content.html` | 15–28 | Title/two/three-up columns, icon rows, process, matrix |
| `archetypes-3-pictures-statements.html` | 29–43 | Picture grids, text+image splits, statements, quotes |
| `archetypes-4-data-reports.html` | 44–54 | Stats, charts, tables, REPORT grids, resources, email |

## How to use
1. Read the prompt and choose the archetype whose **shape** matches (counts of items, presence of image/quote/stat/table).
2. Copy that section's markup from the gallery file above.
3. Replace the placeholder copy in each slot. Keep the geometry, type sizes, colours and chrome.
4. Swap photos by replacing the `<img src>` **inside** the mask wrapper — never edit the `clip-path`. Pick the right subject from `assets/photos/`.
5. Renumber the footer page number and set the footer date.
6. Mix layouts for rhythm — never repeat one archetype back to back. Use a divider between parts and a `HERO_STAT` or `STATEMENT_FULL` as a pace change.

## Chrome rules — differ by slide type (match the master exactly)

| Slide type | Logo | Footer |
|---|---|---|
| Covers 01–06 | top-left x45 y45 (81×31; white version on photo) | date bottom-left · tagline bottom-right (x1102 y633, 133×45) · **no page number** |
| Dividers 07–10 | top-left | date bottom-left · page number bottom-right (left:1167px) |
| `DIVIDER_D` 11 | top-left | page number + date together bottom-left · tagline bottom-right |
| `PICTURE_INTRO` 12 · agendas 13–15 | top-**right** x1153 y45 (white — it sits on the photo) | date bottom-left · page number bottom-right (white when it lands on the photo column) |
| Content / data slides (15–54) | top-right | date bottom-left · page number bottom-right |
| `OUTRO` 16 | top-left | name + email at y629 · tagline bottom-right · no date, no page number |
| `END_LOGO` 17 | giant centred white logo | none |

Footer text is KONE Information 11px, +.05em tracking, ALL CAPS, 43px from the bottom edge. Use `assets/logo/kone-logo-white.svg` + `kone-tagline-white.svg` whenever the corner sits on a photo or dark fill.

## Cut-image masks — fixed templates, image-swappable
The signature staggered photo blocks are a single `<div data-om-raster>` wrapper carrying a fixed `clip-path: path('…')` with a full-cover `<img>` inside. To change the picture, swap the `<img>` only — the mask geometry never changes. `data-om-raster` makes PPTX export rasterise the block so the cut survives PowerPoint.

- **CUT4** — full-width banner, wrapper x0 y0 1280×422: `path('M0 0 H288.9 V249.1 H0 Z M330.2 0 H619.1 V322.3 H330.2 Z M660.4 0 H949.4 V421.3 H660.4 Z M991.2 0 H1280 V371.8 H991.2 Z')`
- **CUT3** — offset banner, wrapper x330 y0 950×422: `path('M0 0 H288.9 V322.3 H0 Z M330.2 0 H619.2 V421.3 H330.2 Z M661 0 H949.9 V371.8 H661 Z')`
- **CUT2 side** — wrapper x661 y0 619×488: `path('M0 0 H288.5 V371.3 H0 Z M330.1 0 H619.1 V487.5 H330.1 Z')`

## Non-negotiable brand rules (apply to every slide)
- **Colour:** KONE Blue `#1450F5` (`--kone-blue`), White, Black `#141414` (`--black`) lead. Section dividers may use **one** solid secondary background straight from the master — light blue `#D2F5FF`, pink `#FFCDD7` or sand `#F3EEEA`. Never yellow or green as a background; never stack secondaries. Blue tints (`--blue-20/40/60`) are for **charts only**.
- **Type:** **Inter** (`--font-primary`) for titles and body — always sentence case, **only black or white, never blue**. Cover and divider titles: Inter 400 **64px**, -.8px tracking. Content-band titles: 43px. **KONE Information** (`--font-secondary`) for eyebrows, numerals, footers — **ALWAYS CAPS**, may be blue/black/white. "KONE" is the only all-caps word allowed in Inter.
- **Subtitle** (`Presenter name · Occasion`): Inter 19px, **black** on every cover except `COVER_F_FULLBLEED` (white).
- **Bullets:** real `<ul>/<li>` markup — 38px hanging indent, a KONE-Blue `•` (Arial) pseudo-marker, items 27px / 110% line height on agenda slides. Dense layouts in galleries 2–4 use the 7px blue dot span at 16px/1.5. Never em dashes or squares.
- **Big figures ("KONE numbers"):** KONE Information, **black**, with a **blue** KONE-Information eyebrow above.
- **Corners:** sharp everywhere. **No shadows, no gradients** except the photo-protection gradient under white text. Left-aligned everything.
- **Icons:** KONE pictograms via CSS mask so they render in `--kone-blue`; divider artwork ships in `assets/illustrations/`.
- **No emoji.**

## Slot type key
`title` Inter 400 slide title · `eyebrow` KONE-Info caps blue label · `subhead` Inter 600 · `body` Inter 400 · `context` Inter 400 `--black-60` · `stat` big KONE-Info figure (black) · `bullets` blue-dot list · `photo` full-cover image · `number` KONE-Info numeral · `chart` blue-tint CSS chart.

---

# 1 · Covers & dividers — 01–17, 1:1 master replicas

### 01 · COVER_A_CUT4
The standard opener: CUT4 banner across the top, title bottom-aligned below it. Slots: `photo` · `title` (502 box, last line at y584) · `context` presenter · occasion.

### 02 · COVER_B_CUT3
Quieter opener: CUT3 banner offset to x330 leaves a white margin at left. Slots: as 01 (title box 509).

### 03 · COVER_C_CUT4_WIDE
Cover A with a wide title box (948) — for longer titles on one wide line.

### 04 · COVER_D_CUT3_WIDE
Cover B with the widest title box (1067).

### 05 · COVER_E_SIDE
CUT2 side image at right; title vertically centred at left (578×448 at y136) — for titles over several lines.

### 06 · COVER_F_FULLBLEED
Full-bleed photo with a 460px bottom protection gradient; logo, title, subtitle, tagline and date all white. The only cover with a white subtitle.

### 07 · DIVIDER_NUMBERING
Sand bg. Huge KONE-Info section numeral (240px, black) centred in the left 374 column, section title at x453 (578). Use when parts are numbered.

### 08 · DIVIDER_A
Light-blue bg. Title at left (578, vertically centred); blue arrow pictogram at x861 y220 (336×324).

### 09 · DIVIDER_B
Pink bg. Title at left; KONE numeral artwork at x861 y220 (238×324).

### 10 · DIVIDER_C
Sand bg. Same frame as 09 — the quiet default divider.

### 11 · DIVIDER_D
White bg. Narrow title (374, vertically centred); black line illustration at x684 y136 (422×448); tagline bottom-right; page number and date share the bottom-left.

### 12 · PICTURE_INTRO
Full-width photo band (1280×382), white logo top-right; 43px title at y435 with a 19px lead line at y551. Opens a part with imagery plus one framing sentence.

### 13 · AGENDA_A_BULLETS
Full-height photo column at x759 (521×720), white logo top-right. "Agenda" 43px at y91; blue-dot `<ul>` from y182, items 27px. Up to ~7 short items.

### 14 · AGENDA_A_TEXT
Same frame as 13, for fewer, longer points that wrap on the 38px hanging indent.

### 15 · AGENDA_A_TABLE
Same frame; hairline agenda table (grid 250/170/96/96, 16px rows): subject, responsible person, two time columns.

### 16 · OUTRO
CUT3 banner + "Thank you" (64px). Presenter name at x45 and email at x249, 15px at y629; tagline bottom-right; no date or page number.

### 17 · END_LOGO
Full-bleed photo with the giant white logo centred (x215 y195, 850×329). Nothing else — the brand sign-off.

---

# 2 · Content

### 15 · TITLE_CONTENT
Title + one body block (917 wide). **Use when:** a single topic with a lead sentence and a few points.
Slots: `title` · `body` lead · `bullets`.

### 16 · TITLE_SUB_CONTENT
Blue eyebrow above the title, then a subtitle and content. **Use when:** the slide needs labelling within a section.
Slots: `eyebrow` · `title` · `context` subtitle · `bullets`.

### 17 · TWO_CONTENT
Two equal columns (578 each) under one title. **Use when:** two parallel sets of points.
Slots: `title` · 2 × { `subhead` · `bullets` }.

### 18 · TWO_CONTENT_ASYM
Narrow summary column (374) beside a wide 2×2 detail grid (781). **Use when:** a framing paragraph plus four sub-areas.
Slots: `title` · `context` summary · 4 × { `subhead` · `context` }.

### 19 · THREE_CONTENT
Three equal columns (374 each). **Use when:** three parallel themes with real explanation each.
Slots: `title` · 3 × { `subhead` · `body` · `bullets` }.

### 20 · THREE_CONTENT_ASYM
Two text columns beside a full-height sand takeaway panel (x759, 476×539). **Use when:** detail should build to a pulled-out conclusion.
Slots: `title` · 2 × { `subhead` · `context` · `bullets` } · panel { `eyebrow` · `body` · `bullets` }.

### 21 · TITLE_TEXT_SPLIT
Blue title panel at left (to x419), text on white at x555. **Use when:** you want a colour-blocked, high-contrast content slide.
Slots: `eyebrow` (white) · `title` (white) · `body` · `bullets`.

### 22 · ICON_COLUMNS_5
Five short points, each led by a pictogram. **Use when:** 5 parallel ideas/shifts/features.
Slots: `eyebrow` · `title` · `body` intro · 5 × { icon · `subhead` · `context` }.

### 23 · NUMBERED_ICON_ROW_6
Six numbered items with icons in one row. **Use when:** 6 short parallel items.
Slots: `title` · 6 × { icon · `number` · short label }.

### 24 · HOW_IT_WORKS_3STEP
Banner image (1280×382) over three numbered steps. **Use when:** explaining how something works in 3 steps.
Slots: `photo` · `title` · 3 × { `number` · `subhead` · `context` }.

### 25 · LIFECYCLE_4STAGE
Banner image over four sequential stages with icons. **Use when:** a 4-phase lifecycle with sub-points.
Slots: `photo` · `eyebrow` · `title` · 4 × { icon · `subhead` · `bullets` }.

### 26 · QUARTERLY_PLAN_4COL
Four workstreams sequenced by quarter. **Use when:** a roadmap, one column per workstream.
Slots: `eyebrow` · `title` · `body` intro · 4 × { `eyebrow` Q-label · `subhead` · `context` · `bullets` }. Sand bg.

### 27 · ORG_FUNCTIONS
Function list at left beside a 2×2 sand structure grid. **Use when:** describing how a team/org is organised.
Slots: `title` · `bullets` functions · 4 × sand box { `subhead` · `context` }.

### 28 · MATRIX_2X2
Two-by-two matrix with axis labels. **Use when:** plotting items on two axes (impact × effort).
Slots: `title` · vertical + horizontal `eyebrow` axes · 4 × sand quadrant { `subhead` · `bullets` }.

---

# 3 · Pictures & statements

### 29 · TWO_PICTURE_COMPARE
Two images (272×448) each with a heading and points. **Use when:** contrasting two options.
Slots: `title` · 2 × { `photo` · `subhead` · `bullets` }.

### 30 · THREE_PICTURE_CARDS
Three image cards (374×272) with headings and points. **Use when:** 3 parallel offerings with imagery.
Slots: `title` · 3 × { `photo` · `subhead` · `bullets` }.

### 31 · FOUR_PICTURE_CARDS
Four square image cards (272×272) with short captions. **Use when:** 4 benefits/value drivers with imagery.
Slots: `eyebrow` · `title` · 4 × { `photo` · `subhead` "1. …" · `context` }.

### 32 · TWO_PICTURES_STACKED
Summary at left, two stacked text+picture rows at right (374×230 each). **Use when:** two cases/examples with images.
Slots: `title` · `context` summary · 2 × { `subhead` · `context` · `photo` }.

### 33 · TEXT_PICTURE_RIGHT
Text with a tall image bleeding off the right (x759, 521×720). **Use when:** a narrative slide that needs one strong image.
Slots: `title` · `body` · `bullets` · `photo`.

### 34 · TEXT_STATS_PICTURE
Intro text + a stack of labelled figures, image at x725 (555 wide). **Use when:** narrative + 2–3 figures + image. Sand bg.
Slots: `title` · `context` · 3 × { `eyebrow` · `stat` · label } · `photo`.

### 35 · NUMBERED_SUMMARY_PICTURE
Numbered takeaways beside a wide image (x419, 861×720). **Use when:** 3 summary points with a dominant image.
Slots: `title` · 3 × { `number` · `subhead` } · `photo`.

### 36 · STATEMENT_FULL
One statement filling the slide (52px). **Use when:** a single idea deserves the whole slide.
Slots: `title` statement. Blue brand bar under the logo.

### 37 · STATEMENT_THREE_COL
A statement (985 wide) above three supporting columns at y364. **Use when:** a claim plus three reasons.
Slots: `title` · 3 × { `subhead` · `context` }.

### 38 · STATEMENT_TWO_COL
A statement above a wide explanation (544) and a narrow implications list (374). **Use when:** a claim needing reasoning plus consequences. Sand bg.
Slots: `title` · `body` · `eyebrow` · `bullets`.

### 39 · STATEMENT_ON_PICTURE
Statement over a full-bleed photo with a left-to-right protection gradient. **Use when:** an emotive claim.
Slots: `photo` · `eyebrow` (white) · `title` (white).

### 40 · STATEMENT_PICTURE_NOTE
Statement at the left edge over a dimmed photo, notes column at x963. **Use when:** a claim plus caveats over imagery.
Slots: `photo` · `title` (white) · `eyebrow` + `bullets` (white).

### 41 · QUOTE_PANEL
Quote in a KONE Blue panel (x453, 782×493) with a context column at left. **Use when:** a customer/leader quote is the centrepiece.
Slots: `subhead` context · `context` · `quote` (white) · `eyebrow` attribution (white).

### 42 · QUOTE_PLAIN
The quietest quote — no panel, 32px on white. **Use when:** a quote inside a text-led section.
Slots: `eyebrow` · `context` · `quote` · `eyebrow` attribution.

### 43 · OFFER_CTA
Banner image, offer + price at left, blue call-to-action block at right. **Use when:** presenting a priced offer with a next step.
Slots: `photo` · `title` · `eyebrow` "From" · `stat` price · `context` fine print · CTA { `subhead` · `body` · action line }.

---

# 4 · Data & reports

### 44 · HERO_STAT
One dominant figure (~200px) carrying the slide. **Use when:** a single number is the message.
Slots: `eyebrow` · `stat` · `subhead` meaning · `context`.

### 45 · THREE_STATS
Three headline figures with context. **Use when:** 3 comparable metrics.
Slots: `title` framing sentence · 3 × { `eyebrow` · `stat` · `context` }.

### 46 · CHART_COMMENTARY
Bar chart at left with two columns of commentary. **Use when:** interpreting a chart or survey result.
Slots: `eyebrow` · `title` · `chart` · 2 × { `subhead` · `bullets` }.

### 47 · SEGMENT_BREAKDOWN
Three donut breakdowns at left, bar chart + headline figure at right. **Use when:** splitting an audience several ways plus one hero number.
Slots: `title` · 3 × { donut `chart` · `subhead` · `bullets` % } · `chart` bars · `eyebrow` · `stat` · `context`.

### 48 · COMPARISON_TABLE
Tiered feature-comparison table (row labels × three tiers). **Use when:** comparing tiers/plans.
Slots: `title` · 3 column headers · 5 rows { feature · value/—/Yes per tier }.

### 49 · REPORT_3COL
Three full-height report columns (374×493), no title band, each ending in a figure. **Use when:** a dense read-not-present page.
Slots: 3 × { `eyebrow` · `subhead` heading · `body` · `bullets` · `stat` + label }.

### 50 · REPORT_4COL
Four full-height report columns (272×493). **Use when:** four dense parallel sections.
Slots: 4 × { `eyebrow` · `subhead` · `body` · `stat` + label }.

### 51 · REPORT_6CELL
Six cells — three across, two down (374×201). **Use when:** six short report items.
Slots: 6 × { `eyebrow` · `subhead` · `context` }.

### 52 · REPORT_8CELL
Eight cells — four across, two down (272×201). The densest master grid. **Use when:** eight short numbered items.
Slots: 8 × { `number` · `subhead` · `context` }.

### 53 · RESOURCE_LINKS
A 2×2 list of links with icons, plus a contact block. **Use when:** a "find out more" slide.
Slots: `title` · `body` intro · 4 × { icon · link label } · `eyebrow` + contact line.

### 54 · EMAIL_SPEC
An email's body in a sand panel beside its four linked content cards. **Use when:** documenting or reviewing email templates (not a general presentation layout).
Slots: `eyebrow` persona · email type · `title` subject · body panel { greeting · paragraphs · `bullets` · sign-off } · 4 × card { thumb · `subhead` · `context` · link label }.
Note: body text here is intentionally 11px — it is a *preview of an email*, not presented slide text.

---

## Assets referenced
- **Logo:** `assets/logo/kone-logo.svg` (blue), `kone-logo-white.svg` (on dark/photo).
- **Tagline:** `assets/logo/kone-tagline.svg`, `kone-tagline-white.svg` — bottom-right on covers/dividers/closers.
- **Divider artwork:** `assets/illustrations/kone-pictogram-arrow.svg`, `kone-numeral-3.svg`, `kone-illustration-technician.png`.
- **Pictograms:** `assets/icons/arrow.svg`, `cloud.svg`, `connect.svg` — recolour via CSS mask.
- **Photos (9):** `assets/photos/` — `elevator-bike.jpg`, `elevator-women.jpg`, `escalator-station.jpg`, `handrail-hands.jpg`, `product-signalization.jpg`, `stairs-bag.jpg`, `stairs-phone.jpg`, `technician-van.jpg`, `technician-van-branded.jpg`. Mix them; avoid repeating one photo twice on a slide.
- **Tokens/fonts:** load the `tokens/*.css` + `styles.css` bundle for `--kone-blue`, `--sand`, `--black`, `--black-60`, `--hairline`, `--blue-20/40/60`, `--font-primary`, `--font-secondary`.
