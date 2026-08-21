# Deck review: `deck (12).pptx`

12 slides, 960×540pt (= the 1280×720 grid at 1:1.333). Measured off the OOXML,
not eyeballed. Every coordinate below is converted to the px grid the brand
spec uses.

## What it got right — do not let anyone "fix" these

Worth stating first, because a blanket rewrite would break them:

- 34pt left margin (= 45px) on every slide. Correct.
- Footer baseline at y=494pt (= 658px), date bottom-left, page bottom-right,
  KONE Information uppercase. Correct.
- Logo top-left on covers and dividers, top-right on content slides. Exactly
  one logo per slide. Correct.
- Slide 4's divider numeral is 225pt = **300px**. That is the spec value, and it
  is the one place the deck gets the display tier right.
- KONE Information used only for labels/eyebrows/chrome, always caps. Inter for
  everything else. No grey type anywhere.
- Content titles consistently 30pt (= 40px).

## P0 — fix before this is shown to anyone

### 1. The cover title is a truncated sentence from the email

Slide 1, `TextBox 2`, 57pt (= 76px, correct size), reads:

> "I would like to share our plan of ONE Week MOD deployment with you reg"

It is cut mid-word at 69 characters. The generator used the email's opening
line as the cover headline and hard-truncated it to the box. The contract for
`cover_a_cut4` declares `title fits_chars: 16` — the copy was never written for
the slot, it was inherited from the source and clipped.

**Instruction:** never truncate to fit a slot. If the extracted string exceeds
the contract's `fits_chars`, that is a signal to *write* a title, not to cut
one. A cover title here is three or four words: "ONE Week MOD deployment".

### 2. The cut cover is not cut

Slide 1 has a single `Picture 1` at x0 y0, 960×317pt — one unbroken band. There
are no mask rectangles in the slide XML.

The archetype is a **mask, not a photo band**: one picture frame plus
background-coloured mask rectangles, so dropping in a single photograph
produces the chopped effect. Slide 11 has the same problem — one 960×287pt
band.

**Instruction:** implement `cover_a_cut4` / `cover_b_cut3` as one picture frame
plus 3 or 4 background-coloured rectangles that mask it into staggered panes of
different heights. Never a single band, never a pre-sliced photo.

### 3. The outro carries stale chrome and a footer it should not have

Slide 12 is the master's own "Thank you", kept verbatim, and it brought its
placeholder values with it:

- Page number reads **"11"** on slide **12**.
- Date reads **"23 July 2026"**. Every other slide reads "21 August 2026".
- It has a date *and* a page number at all — the outro takes **no footer
  chrome**.
- Its `Picture Placeholder 21` is empty.

**Instruction:** when the master's Thank-you slide is kept, re-stamp or strip
its chrome like any other slide. `brandmode.wants_footer()` returns False for
the outro, so the footer must be removed, not inherited. A hard-coded date
anywhere in output is a bug.

### 4. Inter is set in blue

Slide 10, `TextBox 2` carries both `1450F5` and `141414` — the owner names are
blue Inter.

**Inter is only ever black or white, never blue.** Only KONE Information may be
blue. This is a hard rule, and `preflight` should be catching it.

### 5. A bold flag on Inter SemiBold

Slide 5, `TextBox 3`: `sz="1650"`, `b="1"`, `typeface="Inter SemiBold"`.

Weight comes from the SemiBold *family*, never from a bold flag. This sets
both, so the renderer synthesises weight on top of a already-semibold face.

**Instruction:** `b="1"` must never be emitted on any Inter run. Assert it.

## P1 — layout faults

### 6. Slide 10 puts five owners in one text box in a 270pt column

`TextBox 2` at x34 y128, 270×300pt, 14.25pt, containing all five lines as one
run: Ajith, Aino, Omnicom, Frontlines/Global Comms, DACH. The result is a wall
of wrapped text in the left third with **656pt of empty slide to its right.**

This is the slide that most needs to be a structure — five owners against five
responsibilities. `org_functions` exists for exactly this.

**Instruction:** when a slot's content is a list of N labelled items, it must
map to a repeating region with cardinality N, not be joined into one paragraph.
If no contract matches, that is a planning failure to report, not a paragraph to
concatenate.

### 7. A 40px title in a 272px column

Slide 11, `TextBox 2`: "Practicalities: how the work reaches you" at 30pt
(= 40px) in a box 204pt wide (= 272px). At that width the title wraps to four
lines in a narrow column.

`brandmode.resolve()` **already** swaps `title` → `title_narrow` (28px) at width
≤ 374px. It did not fire, because this region is baked — it carries its own
`dg` block and never asks the brand.

**This slide is a live demonstration of the type-system fault in README §3.**
Use it as the regression test: once regions resolve through the brand, this
title should become 28px with no other change.

### 8. Three indented sentences with no bullet markers

Slide 2, `TextBox 9/10/11` at x79 — indented 45pt past the x34 margin, 14.25pt,
one sentence each, with **no marker of any kind** in the XML. They read as
floating fragments that were meant to be a list.

**Instruction:** an indent is not a bullet. Either emit a real list with KONE
Blue disc markers and black text, or set the lines flush at x34 as separate
statements. Never indent without a marker.

### 9. Three different divider treatments, one of them by accident

- Slide 4: numeral divider, 300px white numeral, eyebrow, 42pt title. Correct.
- Slide 6: photo divider, full-bleed, white type. Correct.
- Slide 9: a single 30pt line of black text on white at y218, a logo, and
  nothing else.

Slide 9 has no numeral, no eyebrow, no field colour and no rule. It carries no
footer, so the renderer *does* classify it as a divider — it is just an empty
one. Next to slide 4 it reads as a slide that failed to render.

**Instruction:** a divider must draw its full archetype or not be chosen. If
`divider_title_only` is selected, it needs its field colour, its chip and its
6px blue rule. Pick one divider archetype per deck and repeat it; three
treatments in twelve slides has no rhythm.

## P2 — weaker choices

### 10. The hero figure is a bare date at a third of its size

Slide 5: "21" at 90pt (= 120px). The `hero_value` role is **280px**. And "21"
alone carries no meaning — it needs its caption read first, which defeats the
archetype. The number that would actually work here is **6** (EUR frontlines)
or **7** (markets), with September 21 as the caption.

### 11. Overlapping boxes on slide 4

Eyebrow box: y238, height 90pt → occupies to y328. Title box starts at y257.
They overlap by 71pt. It probably renders acceptably because both are
top-aligned, but the geometry is wrong and `preflight`'s overlap check should
flag it.

### 12. Numbering a parallel list

Slide 7 numbers the six channels 01–06 at 30pt (= 40px; the `number` role is
28px). These are parallel channels, not a sequence — numbering them implies an
order that does not exist. Same on slide 11's three practicalities.

### 13. No speaker notes anywhere

There is no `notesSlide` part in the package at all. For a deck handing scope to
an agency team, the notes are where the non-negotiable date, the AME caveat and
the "no preview tool" consequence should live.

### 14. Inconsistent right edge

Slide 3's agenda labels are 458pt wide from x446, ending at x904. Everything
else runs to x926 (= the 1235px content edge). Slide 2's title is 33pt where
every other content title is 30pt.

---

## Paste-ready instruction for Claude Code

> Fix the following in the deck generator, in this order. Do not change the
> margin grid, the footer geometry, the logo placement rules, or slide 4's 300px
> divider numeral — those are correct.
>
> **1.** Never truncate copy to fit a slot. If extracted text exceeds a
> contract's `fits_chars`, write copy for the slot instead. The cover title on
> slide 1 is currently a mid-word truncation of the source email's first
> sentence.
>
> **2.** Implement the cut cover as a mask: one picture frame plus 3–4
> background-coloured rectangles producing staggered panes of unequal height.
> Slides 1 and 11 are currently single unbroken photo bands.
>
> **3.** Re-stamp chrome on the master's kept "Thank you" slide: the page number
> reads 11 on slide 12, the date reads 23 July 2026 against 21 August 2026
> everywhere else, and the outro should carry no footer at all. Remove every
> hard-coded date from output.
>
> **4.** Assert that Inter is never blue. Slide 10 sets owner names in
> `#1450F5`. Only KONE Information may be blue.
>
> **5.** Assert that `b="1"` is never emitted on an Inter run. Slide 5 sets a
> bold flag on top of Inter SemiBold.
>
> **6.** When a slot's content is a list of N labelled items, map it to a
> repeating region with cardinality N. Slide 10 joins five owner lines into one
> paragraph in a 270pt column with 656pt of empty slide beside it.
>
> **7.** Resolve region type through the brand so `title` becomes `title_narrow`
> at box width ≤ 374px. Slide 11 sets a 40px title in a 272px column because the
> region is baked. Use that slide as the regression test.
>
> **8.** Never indent a line without a marker. Slide 2 has three sentences
> indented 45pt with no bullet glyph. Emit real disc markers in KONE Blue with
> black text, or set them flush.
>
> **9.** A divider must draw its full archetype. Slide 9 is a bare 30pt title on
> white with no numeral, eyebrow, field colour or rule. Use one divider
> archetype consistently.
>
> **10.** Give `hero_stat` a figure that means something on its own, at the
> role's 280px. Slide 5 sets a bare "21" at 120px.
>
> **11.** Fix the overlapping eyebrow and title boxes on slide 4, and make
> `preflight`'s overlap check fatal in tests.
>
> **12.** Do not number parallel lists. Slides 7 and 11 number items that have
> no sequence.
>
> **13.** Emit speaker notes for every slide. The package currently contains no
> `notesSlide` part.
>
> **14.** Run every content region to the x=926pt content edge. Slide 3 stops at
> 904, and slide 2's title is 33pt where every other content title is 30pt.
