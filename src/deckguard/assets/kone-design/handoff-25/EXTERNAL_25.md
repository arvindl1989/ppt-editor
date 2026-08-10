# External 25 — the customer-facing set

Twenty-five archetypes out of the 62 kept, chosen to build any customer deck
end to end: pitch, proposal, QBR, launch, site story. Every one is Grade A or B
provenance or an `extra` that earns its place by job. Nothing here needs a
named icon, and nothing here uses a secondary colour as a field — an external
deck is blue, white, black and photography.

Order is deck order, not priority. Build them in this order and the set reads
as one deck.

## Opening — 3

| # | archetype | job | contract |
| --- | --- | --- | --- |
| 1 | `COVER_A_CUT4` | The default cover. Four-pane mask over one photo. | `title:stat_value · context:bullets` |
| 2 | `COVER_F_FULLBLEED` | Cover when one photograph carries the whole idea. Needs photo protection. | `photo:picture · title:stat_value · context:on_panel_body` |
| 3 | `AGENDA_B_NUMBERED` | The running order as a numbered list. | `title:heading · body:body_narrow · body2:body` |

## Structure — 2

| # | archetype | job | contract |
| --- | --- | --- | --- |
| 4 | `DIVIDER_NUMBERING` | Section break with the giant numeral. The spine of a long deck. | `number:display · eyebrow:body · title:display` |
| 5 | `IMAGE_SECTION_DIVIDER` | Section break over a photograph, white type. | `image:image_band · eyebrow:eyebrow_light · title:title_light` |

## Argument — 6

| # | archetype | job | contract |
| --- | --- | --- | --- |
| 6 | `STATEMENT_A` | One sentence, full width, nothing else. The turn in the story. | `title:title` |
| 7 | `TITLE_CONTENT` | The workhorse. Title and a real bulleted list. | `eyebrow:eyebrow · title:title · bullets:bullets` |
| 8 | `TITLE_SUBTITLE_CONTENT_A` | Same, with a qualifying line under the title. | `title:title · subtitle:body · bullets:bullets` |
| 9 | `TWO_CONTENT` | Two bulleted columns. Today/next, us/them, risk/mitigation. | `title:title · items[2]:{label:eyebrow, bullets:bullets}` |
| 10 | `TWO_CONTENT_NARROW_TITLE` | Narrow title left, one wide column right. Long single arguments. | `title:title_narrow · body:body · bullets:bullets` |
| 11 | `THREE_CONTENT` | Three equal text columns. Three pillars, three phases. | `title:title · items[3]:{heading:heading, text:body}` |

## Photography — 5

| # | archetype | job | contract |
| --- | --- | --- | --- |
| 12 | `TEXT_PICTURE_A` | Standard content slide: eyebrow, title, body left; full-height photo right. | `image:picture · eyebrow:eyebrow · title:title · body:body · items[4]:{icon, text:body}` |
| 13 | `TEXT_PICTURE_G` | Banner photo across the top, title and body beneath. | `image:picture · eyebrow:eyebrow_light · title:title · body:body · items[6]:{icon, text:body}` |
| 14 | `TEXT_PICTURE_B` | Full-height photo right, numbered points in the narrow column left. | `image:picture · title:title_narrow · points[3]:{number:number, text:heading}` |
| 15 | `THREE_PICTURES_TEXT` | Three-up pillars, photo over a short list. | `items[3]:{image:picture, text:body}` |
| 16 | `TWO_PICTURES_TEXT_B` | Photo/text against photo/text. Before and after, A and B. | `title:title · items[2]:{image:picture, heading:heading, bullets:bullets}` |

## Proof — 4

| # | archetype | job | contract |
| --- | --- | --- | --- |
| 17 | `HERO_STAT` | One number carrying the slide. | `eyebrow:eyebrow · value:hero_value · caption:heading · support:body` |
| 18 | `STATEMENT_B` | Three to five KONE numbers with context. All figures same size. | `title:title · stats[3]:{label:stat_label, value:stat_value, desc:caption}` |
| 19 | `KONE_NUMBERS` | Credibility band — company scale with a scope line beneath. | `eyebrow:eyebrow · title:title · scope_label:eyebrow · scope:eyebrow · footer:eyebrow · stats[5]:{value:eyebrow, label:eyebrow}` |
| 20 | `QUOTE_A` | Pull quote on a KONE Blue panel, white type. Customer voice. | `title:title_narrow · body:on_panel_body · body2:body_narrow · body3:on_panel_body` |

## Offer — 4

| # | archetype | job | contract |
| --- | --- | --- | --- |
| 21 | `VALUE_PROP_FOUR_POINT` | Product value proposition: photo left, four numbered features right. | `eyebrow:eyebrow · title:title · pictures[4]:{image:picture} · points[4]:{heading:heading, text:body_narrow}` |
| 22 | `HOW_IT_WORKS_3STEP` | Image band over three numbered steps. How delivery works. | `image:image_band · title:title_narrow · steps[3]:{number:number, text:body_narrow}` |
| 23 | `TIMELINE` | Roadmap or history along a horizontal rule. | `title:title · items[4]:{period:stat_label, text:body_narrow}` |
| 24 | `COMPARISON_TABLE` | A ruled comparison table. Options, tiers, scope. | `title:title · table:table` |

## Close — 1

| # | archetype | job | contract |
| --- | --- | --- | --- |
| 25 | `OUTRO` | Close the deck. No footer chrome. | `title:stat_value · text1:body_narrow · text2:body_narrow` |

---

## What is deliberately not here

- **Both remaining covers** (`COVER_B_CUT3`, `COVER_C_CUT4_WIDE`) — one default
  and one full-bleed is enough. The others are internal-set variety.
- **`DIVIDER_TITLE_ONLY`** — a numbered spine plus a photo break covers every
  external break. The title-only divider is where colour-field variants live,
  which belongs to the internal set.
- **`AGENDA_A_TABLE`** — owners and dates are an internal concern.
- **The icon-led archetypes** (`ICON_COLUMNS_5`, `NUMBERED_ICON_ROW_6`,
  `RESOURCE_LINKS`, `LIFECYCLE_4STAGE`, `SEGMENT_BREAKDOWN`) — all five require
  named icons, and per `BRAND_MODE.md §5` an unnamed icon is omitted. They are
  the current renders' most visible defect. Internal set, once the sprite is
  wired by name.
- **The report grids** (`REPORT_*`) — annual-report density, not sales.
- **`MATRIX_2X2`, `QUARTERLY_PLAN_4COL`, `TIMELINE_QUARTER_AXIS`,
  `ORG_FUNCTIONS`, `MILESTONE_SLIDE`, `CREDITS`** — planning and team artefacts.
  Internal.
- **`OFFER_CTA`** — carries a price panel; sales-led rather than brand-led, and
  the only D-grade layout that survived. Ask before using it externally.

## Build rules that apply to all 25

1. Field is white unless the archetype names one. No secondary colour in this
   set except a `panel_sand` inside a component that already specifies it.
2. Footer chrome on every slide except 1, 2, 4, 5 and 25 — date bottom-left
   `x:45 y:658`, page bottom-right `x:1167 y:658`, KONE Information uppercase.
3. Exactly one logo per slide, placed by the layout, never by the archetype.
4. Titles resolve to 32px, `title_narrow` to 28px. The planner never passes a
   size, colour or position.
5. Bullets are real `<ul>` markers, KONE Blue marker on black text, one nested
   level max. No hyphen or dash standing in.
6. White type over a photograph always gets the protection gradient.
7. Content column is 1280px flush at true slide scale; every region's bottom
   ≤ 629.
