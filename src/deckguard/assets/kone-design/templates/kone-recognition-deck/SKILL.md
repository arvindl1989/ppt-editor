---
name: kone-recognition-deck
description: Turn an internal announcement email (a launch, migration, programme win, transformation milestone) into a 12-slide on-brand KONE deck with intro, sections, dividers and outro. Use when a milestone needs a walkthrough for a call or town hall rather than one shareable slide.
license: Proprietary — KONE brand assets. Internal / authorized use only.
---

# KONE Recognition Deck — skill

The deck-length counterpart to `kone-milestone-slide`. Same input — one announcement email — but paced across four sections so it can be presented rather than forwarded.

Requires the `kone-design` skill for tokens, fonts and assets. Start from `MarketingHubServiceNow.dc.html` in this folder; it is a worked 12-slide example, not a blank.

## Which one to build

| Signal | Build |
|---|---|
| "One slide I can share", posted to a channel, read not presented | `kone-milestone-slide` |
| Slot on a call, a town hall, an all-hands, "walk us through it" | this deck |
| The email has three or more distinct beats (what changed / how / what's next / who) | this deck |
| The email is one claim and a thank-you | the single slide |

Do not build a 12-slide deck out of an email with four facts in it. If the extraction below yields fewer than three sections' worth of material, fall back to the single slide.

## The arc

Four sections, twelve slides. The sections are the spine — everything from the email lands in exactly one of them.

```
01  COVER_A_CUT4          intro · claim + the groups who delivered it
02  AGENDA_B_NUMBERED     the four sections, numbered, photo panel right
—— Section 01 · What changed
03  DIVIDER_NUMBERING     KONE Blue field, white numeral
04  TEXT_PICTURE_A        the context paragraph + data-continuity line
05  KONE NUMBERS          sand stat band + the scope row
06  TWO_CONTENT           delivered / data continuity, as two bulleted columns
—— Section 02 · How it was delivered
07  DIVIDER_NUMBERING     KONE Blue field, white numeral
08  THREE_CONTENT         the scope groups — frontlines / regions / global teams
—— Section 03 · What's next
09  QUOTE_B               pink panel, the email's own benchmark line
10  TIMELINE              three milestones: Now / a date / a quarter
—— Section 04 · Thank you
11  CREDITS               names in a four-column ruled grid
12  OUTRO                 cut-image, closing line, tagline
```

Drop slides rather than pad them. A deck of nine that all carry weight beats twelve with three filler slides. The cover, a divider per section, credits and outro are the only mandatory slides.

## Reading the email

Same six-item extraction as `kone-milestone-slide` — claim, proof numbers, completion states, scope names, what's next, credits — with three additions the longer form allows:

7. **The context paragraph** — the sentence explaining what actually moved, verbatim where possible. Slide 04.
8. **The quotable line** — the email's own framing phrase ("a benchmark in easy to work with, easy to work for"). Slide 09, in quotation marks, attributed to the groups rather than a person when the email has no named speaker.
9. **The closing sentiment** — the "this demonstrates what we can achieve" paragraph. Compress to one line on the outro, or cut it. Never render the paragraph.

Numbers appear **once**, on slide 05. If a number is repeating on slides 06 or 08, the slide is restating rather than adding.

## Dividers — approved treatments only

A section divider is one of two things:

1. **`DIVIDER_NUMBERING` on KONE Blue** — `--kone-blue` field, white logo (`kone-logo-white.svg`), white eyebrow and title left, white numeral 420px KONE Information at `right:90px`, vertically centred. The default.
2. **`DIVIDER_TITLE_ONLY`** — title on white, nothing else.

Do **not** use a secondary-colour field (light blue, sand, pink, mint) as a divider background in this deck, and do not use a photo divider with a gradient scrim. Keep every divider in a deck on the same treatment — mixing a photo divider with a colour-field divider makes the section breaks read as different kinds of break.

Dividers carry no footer chrome. Logo goes **top-left** on covers, dividers and the outro; top-right everywhere else.

## The cut cover — get the aspect ratio right

The cut cover is one photo revealed through three windows of different heights, never three photos and never a pre-chopped image. The windows sit flush to the top edge at `left:330/660/990`, widths `289/290/290`, heights `322/419/370`.

Each window paints the *same* background image with a shared `background-size` and an offset `background-position`. **Compute the size from the photo's real dimensions** — hardcoding `950px 419px` stretches anything that is not 2.267:1:

```
scale   = 950 / natural_width
height  = round(natural_height × scale)      // must be ≥ 419
offsetY = -round((height - 419) / 2)         // centre the vertical crop
background-size: 950px {height}px
background-position: {0 | -330 | -660}px {offsetY}px
```

For a 2000×1126 photo that gives `950px 535px` at `-58px`. Check every cover image; the failure is silent and looks like a bad crop rather than an obvious bug.

## Slide-level rules

- Footer chrome on every slide except cover, dividers and outro: context + date bottom-left at y≈677, page number bottom-right, KONE Information 11px uppercase.
- One secondary colour per slide. Sand carries the stat band, pink carries the quote panel — never both on one slide.
- **Never grey type.** No `--black-60`, no opacity. Separate by size, weight and position.
- Real bullets: `<ul style="list-style:disc">`, marker blue via `color` on the `<li>`, text in a black `<span>`. One nested level max.
- Titles 32px minimum, never grey, never blue.
- The zero-stat renders black while the others are blue.
- Credits are verbatim and in the email's order. Group names ("and the Hub specialists") get their own line under the grid, not squeezed into a cell.
- If the slide sits in a `display:flex` wrapper, give each `<section>` `flex:0 0 auto` — `flex-shrink` defaults to 1 and silently clips the right third.

## Worked example

`MarketingHubServiceNow.dc.html` — a Marketing Hub email announcing a Monday.com → ServiceNow migration in six weeks. Note what was cut: the regional and global-team *names* on slide 05 (already counted in the band, listed on slide 08 instead), and the closing paragraph about speed and accountability, compressed to the outro line. Note what was kept verbatim: the completion states, the data-continuity sentence, the benchmark quote, and all eight names.

## Using it in Claude Code

Place this folder at `~/.claude/skills/kone-recognition-deck/` or `<repo>/.claude/skills/kone-recognition-deck/` alongside the `kone-design` and `kone-milestone-slide` skills. Keep `ds-base.js` next to the deck file and point its `base` line at wherever the KONE design system tree lives relative to the page.
