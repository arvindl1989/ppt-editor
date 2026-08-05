# KONE deck archetypes — graded glossary

The single vocabulary for KONE slide archetypes. One canonical name per archetype, one casing convention (`UPPER_SNAKE`), one grade. `LAYOUTS.md` holds the px geometry; this file holds the names, the grades and what each archetype is for.

**Grades**

| Grade | Meaning | Use |
| --- | --- | --- |
| **A** | Most used, referred to commonly | Reach for these first. Built and maintained in `KoneDeck.dc.html`. |
| **B** | Important | Real jobs to be done, just less often. Build from `LAYOUTS.md` geometry on demand. |
| **C** | Somewhat important | Occasional need, or a colour/mirror variant of a higher grade. |
| **D** | Good to have | Specialist, or a master twin that duplicates an A/B layout for a type variant only. Prefer the parent. |

**Status column**

- `built · NN` — present at slide `NN` in `templates/kone-deck/KoneDeck.dc.html` (Grade A), `templates/archetype-library-b/ArchetypeLibraryB.dc.html` (Grade B), `templates/archetype-library-c/ArchetypeLibraryC.dc.html` (Grade C), or `templates/archetype-library-d/ArchetypeLibraryD.dc.html` (Grade D). Each grade file numbers its own slides starting at 01.
- `twin` — geometry duplicates a built parent; see the twin table at the end of `ArchetypeLibraryD.dc.html` rather than a slide of its own.
- `no master` — an archetype the brand uses that has no master layout behind it, built anyway where valuable.

Grades B–D are a **curated 44-slide gallery split across three files** (one per grade, so no single file gets slow to render), not a 1:1 transcription of all 63 master layouts — near-duplicate colour/geometry variants (extra quote-panel colours, extra divider colours, a redundant wide cover, etc.) were consolidated into one representative slide with a note, and slides that added no real value beyond an existing one were cut. `LAYOUTS.md` still has the full 63-layout px geometry if you need a variant that didn't make the cut.

**Naming rule.** Canonical names are `UPPER_SNAKE`. Where a deck engine uses a `lower_snake` key for the same thing, it is listed as an alias — resolve aliases case-insensitively, and when a name is unknown, fail with the nearest match rather than substituting a generic layout.

---

## Grade A — most used

The core twelve. Between them they carry the overwhelming majority of real KONE decks.

| Archetype | What it's for | Master | Status |
| --- | --- | --- | --- |
| `COVER_A_CUT4` | Title slide. **One** photo frame with background-coloured mask rectangles over it, cutting it into staggered banners flush to the top and right edges. Drop in one image and the cut happens. | `slideLayout1` | built · 01 |
| `AGENDA_A_TABLE` | Agenda as a ruled table (item · owner · from · to), photo panel right. Alias: `agenda_contents` | `slideLayout7` | built · 02 |
| `DIVIDER_NUMBERING` | Section divider. Secondary-colour field, giant section number right, title left. | `slideLayout10` | built · 03 |
| `TITLE_CONTENT` | The workhorse. Title plus a real bulleted list, one nested level. | `slideLayout16` | built · 04 |
| `TEXT_PICTURE_A` | Standard content slide: eyebrow, title and body left, full-height photo right. | `slideLayout33` | built · 05 |
| `TWO_CONTENT` | Two bulleted columns on the 578px halves. Comparison, today/next, us/them. | `slideLayout20` | built · 06 |
| `VALUE_PROP_FOUR_POINT` | Product value proposition: full-height photo left, numbered features right. Alias: `four_point_value` | `slideLayout34` (mirrored) | built · 07 |
| `THREE_PICTURES_TEXT` | Three-up pillars, photo over a short bulleted list. | `slideLayout31` | built · 08 |
| `STATEMENT_B` | The numbers slide. Big KONE Information figures over three columns of context. Alias: `three_stats` | `slideLayout49` | built · 09 |
| `TIMELINE` | Roadmap or history along a horizontal rule, one node per period. | no master | built · 10 |
| `QUOTE_E` | Pull quote on a light-blue panel, black type, attribution below. Alias: `quote_context` | `slideLayout44` | built · 11 |
| `OUTRO` | Thank-you / close. Same masked cut treatment as the cover, big statement lower-left, tagline. | `slideLayout55` | built · 12 |

## Grade B — important

| Archetype | What it's for | Master | Status |
| --- | --- | --- | --- |
| `COVER_B_CUT3` | Cover with the image field inset from the left: **one photo** shown through four staggered windows (a short one at far left carrying the logo, then three of increasing/varying height) — never four different photos. | `slideLayout2` | built · 02 |
| `COVER_F_FULLBLEED` | Full-bleed photo cover, white type, bottom-up photo-protection gradient for legibility. | `slideLayout6` | built · 03 |
| `AGENDA_B_NUMBERED` | Agenda as a numbered list, number column split from the label column. | `slideLayout8` | built · 04 |
| `DIVIDER_TITLE_ONLY` | Section divider, title and nothing else. | `slideLayout15` | built · 05 |
| `IMAGE_SECTION_DIVIDER` | Section divider over a photo instead of a colour field, left-side gradient (not a flat overlay) for legibility. Alias: `image_section_divider` | no master | built · 06 |
| `TITLE_SUBTITLE_CONTENT_A` | Title, subtitle, then body. For slides that need a qualifying line. | `slideLayout18` | built · 07 |
| `TWO_CONTENT_NARROW_TITLE` | Narrow title column left, wide 781px content right. | `slideLayout22` | built · 08 |
| `THREE_CONTENT` | Title, then three equal 374px text columns, no pictures. | `slideLayout24` | built · 09 |
| `TWO_PICTURES_TEXT_A` | Two stacked photo/text pairs right, title and body left. | `slideLayout28` | built · 10 |
| `TEXT_PICTURE_B` | Full-height photo right (861×720), title and body in the narrow 272px column left. The un-mirrored twin of `VALUE_PROP_FOUR_POINT`'s geometry. Alias: `numbered_summary_picture` | `slideLayout34` | built · 11 |
| `TEXT_PICTURE_F` | Two text columns left, photo right. Denser than `TEXT_PICTURE_A`. | `slideLayout36` | built · 12 |
| `TEXT_PICTURE_G` | Banner photo across the top, title and body beneath. | `slideLayout37` | built · 13 |
| `TEXT_STATS_PICTURE_RIGHT` | Body copy with inline stats, photo right. Alias: `text_stats_picture_right` | no master | built · 14 |
| `TITLE_TEXT_SPLIT` | Blue title column left, white content panel right. | `slideLayout39` | built · 15 |
| `QUOTE_A` | Pull quote on a KONE Blue panel, white type; the left-column label is 32px, matching every other title in the deck. | `slideLayout40` | built · 16 |
| `STATEMENT_A` | One sentence, full width, nothing else. Logo stays in its standard top-right spot; only the statement text centres when there's no other content. | `slideLayout48` | built · 17 |
| `FULLSLIDE_PICTURE` | Photo, edge to edge, logo only. | `slideLayout46` | built · 18 |
| `BLANK` | Logo and nothing else. For bespoke content. | `slideLayout61` | built · 19 |
| `TIMELINE_PHOTO_4COL` | Four equal photo tiles over a year/period + short body, blue divider rules beneath. | `slideLayout45` (shared) | built · 20 |

Removed as redundant during review: `DIVIDER_A`/`DIVIDER_D` (covered by `DIVIDER_TITLE_ONLY` + the Grade A/C dividers), `STATEMENT_C`/`STATEMENT_E` (covered by `STATEMENT_A` and the Grade A statement beats), `END_LOGO` (covered by `BLANK`).

## Grade C — somewhat important

| Archetype | What it's for | Master | Status |
| --- | --- | --- | --- |
| `COVER_C_CUT4_WIDE` | Cover spanning the full width in four staggered windows onto **one photo** — no colour tint, logo plain on white above the band. | `slideLayout3` | built · 22 |
| `AGENDA_C_SPLIT` | Short title left, agenda body in the right 578px column. | `slideLayout9` | built · 23 |
| `TITLE_SUBTITLE_CONTENT_B` | Eyebrow above the title in KONE Blue, then body. | `slideLayout19` | built · 24 |
| `TWO_PICTURES_TEXT_B` | Photo/text, photo/text across four bands. Alias: `two_picture_compare` | `slideLayout29` | built · 25 |
| `FOUR_PICTURES_TEXT` | Four 272px photos, each with a caption and a one-line description. | `slideLayout32` | built · 26 |
| `QUOTE_B` | Quote panel, pink. The same panel also ships in yellow (`QUOTE_C`, `slideLayout42`) and mint (`QUOTE_D`, `slideLayout43`) — swap `--pink` for `--yellow`/`--green-mint` rather than building a separate slide. | `slideLayout41` | built · 27 |
| `STATEMENT_LINKS` | Statement with a list of links or next steps, no decorative icon. Alias: `statement_links` | no master | built · 28 |
| `TITLE_24PT_FOOTERS` | Small title with footer chrome, for dense or tabular content. | `slideLayout45` | built · 29 |
| `NUMBERED_ICON_ROW_6` | Six icon-led items, three over three — number, icon, short label. Alias: `numbered_icon_row_6` | no master | built · 30 |
| `REPORT_TWO_CONTENT` | Report grid: title column plus two content columns, full height. | `slideLayout57` | built · 31 |
| `REPORT_THREE_CONTENT` | Report grid: title plus three 272px columns. | `slideLayout58` | built · 32 |
| `ICON_COLUMNS_5` | Five icon-led columns. **Needs the KONE pictogram set** — cycles the three shipped icons as placeholders today. | no master | built · 33 |
| `LIFECYCLE_4STAGE` | Four-stage lifecycle or process. Needs icons; cycles the three shipped icons as placeholders. | no master | built · 34 |
| `SEGMENT_BREAKDOWN` | Chart or diagram placeholder — a dashed empty box, never a phantom sample chart. Also represents `CHART_COMMENTARY` and `ORG_FUNCTIONS`, which use the same treatment. | no master | built · 35 |
| `TIMELINE_QUARTER_AXIS` | Bullet list left, quarter/month roadmap axis with alternating up/down milestone stems right. | `slideLayout22` (shared) | built · 36 |

Removed as redundant during review: `COVER_D_CUT3_WIDE` (near-duplicate of `COVER_B_CUT3`/`COVER_C_CUT4_WIDE`), `COVER_E_SIDE` (little beyond the other covers), `DIVIDER_B`/`DIVIDER_C` (colour repeats of the Grade A/B dividers), `THREE_CONTENT_WIDE_RIGHT` (near-duplicate of `THREE_CONTENT`), `STATEMENT_F`/`STATEMENT_OR_QUOTE` (covered by `STATEMENT_A` and `QUOTE_A`/`QUOTE_B`).

## Grade D — good to have

Specialist layouts, and the master twins. A twin is geometrically identical to its parent — the master duplicates it only to carry a different type treatment. Use the parent.

| Archetype | What it's for | Master | Status |
| --- | --- | --- | --- |
| `TITLE_CONTENT_B` | Twin of `TITLE_CONTENT`. | `slideLayout17` | twin |
| `TWO_CONTENT_B` | Twin of `TWO_CONTENT`. | `slideLayout21` | twin |
| `TWO_CONTENT_NARROW_TITLE_B` | Twin of `TWO_CONTENT_NARROW_TITLE`. | `slideLayout23` | twin |
| `THREE_CONTENT_B` | Twin of `THREE_CONTENT`. | `slideLayout25` | twin |
| `THREE_CONTENT_WIDE_RIGHT_B` | Twin of `THREE_CONTENT_WIDE_RIGHT`. | `slideLayout27` | twin |
| `TWO_PICTURES_TEXT_C` | Twin of `TWO_PICTURES_TEXT_B`. | `slideLayout30` | twin |
| `TEXT_PICTURE_C` | Twin of `TEXT_PICTURE_B`. | `slideLayout35` | twin |
| `TEXT_PICTURE_H` | Twin of `TEXT_PICTURE_G`. | `slideLayout38` | twin |
| `STATEMENT_D` | Twin of `STATEMENT_C`. | `slideLayout51` | twin |
| `REPORT_FIVE_CONTENT` | Six-cell report grid. Dense annual-report use only. | `slideLayout59` | spec |
| `REPORT_SEVEN_CONTENT` | Eight-cell report grid. Dense annual-report use only. | `slideLayout60` | spec |
| `FULLSLIDE_VIDEO` | Video fills the slide. | `slideLayout47` | spec |
| `USER_GUIDE` | The master template's own instructions page. Not for customer decks. | `slideLayout62` | spec |
| `RESOURCE_LINKS` | Link list with icons. Needs the pictogram set. | no master | spec |
| `OFFER_CTA` | Offer with a call to action. Needs the pictogram set. | no master | spec |

---

## Glossary of terms

Shared vocabulary for the parts of a KONE slide, so the skill, the generator and review tooling all mean the same thing.

| Term | Meaning |
| --- | --- |
| **Archetype** | A named slide pattern: geometry plus its content roles. What a user asks for by name ("use `TITLE_CONTENT` for slide 4"). |
| **Master layout** | The corresponding layout in `master_ppt`, identified as `slideLayoutN`. The source of the geometry. |
| **Twin** | A master layout with geometry identical to another, duplicated only for a type variant. Always prefer the parent. |
| **Chrome** | The repeating furniture: logo, tagline, date, page number. **Owned by the layout, never the archetype** — an archetype that draws its own logo produces two once the master frames are repaired. Archetypes declare which variant they need (white on dark); they do not place the mark. |
| **Footer chrome** | Date bottom-left (x:45 y:658), page number bottom-right (x:1167 y:658), KONE Information uppercase. Mandatory on every slide except covers, dividers and the outro. Must be stamped explicitly when building programmatically. |
| **Eyebrow** | The small KONE Information label above a title. ALL CAPS, KONE Blue or black. |
| **Cut cover** | The staggered-banner cover treatment. **One picture frame plus background-coloured mask rectangles** — never a photo pre-chopped into panes, so a user can drop in one image and get the effect. |
| **Mask rectangle** | A background-coloured rectangle sitting over a photo to cut it into banners. |
| **Image field** | The rectangle a cover photo fills, e.g. 1280×421 on `COVER_A_CUT4`. |
| **Photo protection** | The gradient placed under white type on a photo so it stays legible. Required on `COVER_F_FULLBLEED`. |
| **Primary type** | Inter. Headlines and body. Sentence case, black or white, never blue. **Never bold** — weight comes from the separate Inter SemiBold family, not a bold flag on Inter. |
| **Secondary type** | KONE Information. ALL CAPS labels, page numbers, technical text and big figures. Blue, black or white. |
| **Never grey type** | All text is solid black `#141414`, white, or KONE Blue for KONE Information labels. Hierarchy comes from size, weight and position. The `--black-60` / `--black-40` tints are for hairlines and fills only. |
| **Secondary colour** | Sand, yellow, light blue, pink, mint. Support, never dominate. Max two per layout, never yellow or green as a full background. |
| **Tint** | A percentage of KONE Blue or black. Charts, infographics and callout blocks only, never a full-page background. |
| **Hairline** | The 1px rule separating table rows and columns. |
| **Grid** | 1280 × 720 px, 45px margins. Columns land on 45 / 351 / 453 / 555 / 657 / 759 / 861 / 963; common widths 272 / 374 / 476 / 578 / 679 / 781 / 917 / 1189. |
| **Bullet** | A real list marker: `<ul style="list-style:disc">` with the marker in KONE Blue and the text in black. Never a hyphen, dash or em dash standing in for a bullet. One nested level max (`list-style:circle`). |

---

## Known gaps

Carried over from tooling review — these limit which archetypes can actually be built today.

1. ~~The master's picture frames are empty.~~ **Fixed** — `uploads/All Slides.pptx` is the current master: 63 layouts, **63/63 picture frames embedded, 0 broken**, white logo variants on the dark layouts, 31 content picture *placeholders*, latent `DATE`/`FOOTER`/`SLIDE_NUMBER` on every layout, prompt text intact. Build against this file, not `master_ppt-1784774200983.pptx`.
2. ~~Logo assets are SVG only.~~ **Done** — `assets/logo/` now ships transparent PNG at 2x beside each SVG (`kone-logo` 2387×924, `kone-tagline` 2085×711, plus both white variants) for `.pptx` embedding. Alpha preserved; never flatten onto black.
4. **Two production-deck variants without canonical names yet.** The engine's `three_picture_cards` (own title bar, 213px-tall photos at y:224) and `how_it_works_3step` (image band + 3 numbered steps) are close cousins of `THREE_PICTURES_TEXT` and `TEXT_PICTURE_G` respectively but not geometric matches — left unaliased pending a look at batch 3.

3. **Only three pictograms ship.** `arrow`, `cloud`, `connect`. Six archetypes need up to five icons each — the seven `no master` entries flagged above are blocked on this. The generator now loads real pictograms from `assets/icons/` by name as soon as they exist.

5. **One dark `<p:bg>` layout.** `Title and Text` (`slideLayout39`) carries `#1450F5` in the slide background rather than a shape, so shape-only contrast checks will place black type on blue. The generator knows about it (`DARK_BG_LAYOUTS`); moving the colour into a full-bleed rectangle would remove the special case.

6. **Sand drift.** The master theme’s `lt2` is `#F3EEEA`; `tokens/colors.css` says `#F3EEE6`. Four units on one channel, invisible in practice, but worth reconciling so decks and web agree.
4. **Galleries 2–4 are unreworked** and the archetype geometry in them is not machine-readable. A `data-archetype` / `data-role` attribute pair per block would make them a spec rather than a rendering.
