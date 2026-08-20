# What landed, what I corrected, and what is still blocked

Written back against `NOTES.md`, `DEFECTS.md` and `INSTRUCTIONS.md`.

## Landed

**`placeholders.json`, all 45 slides.** Validated against the contracts
on the way in — every key is one the renderer reads, every required slot
is filled, every list is within its declared range, and all 25 icon
names resolve against the sprite. Zero violations. It is now the source
for every preview, and `tests/test_contracts.py` holds it there.

The previews are rendered **per set** rather than per archetype, so the
six shared archetypes no longer show the same slide twice (`DEFECTS.md`
§7). `hero_stat` previews at 90% for the programme and 99% for the
portfolio.

**P0-2, the raw Python list.** Confirmed and fixed. `cover_a_cut4`
printed `['Maintenance and modernisation', ...]` because the contract
types `context` as `bullets` and the region is a plain text box.

I did not take the advice to fail the build. A deck that refuses to
build is worse than one with a joined line, and the caller was right —
only the shape was wrong. A list in a text region is now joined with
line breaks. The three lines render as three lines.

**P1-5, the declared field.** Confirmed and fixed. `slide-sets.json`
declares a field per `(archetype, audience)` and nothing read it, so
every slide fell back to its layout's own background. The audience now
travels with the deck spec and the set's declaration wins.

Two things came out of that worth knowing:

- Painting a field **buried the logo**, because the logo lives on the
  layout and every slide shape draws above every layout shape. The
  dividers had been shipping with no logo at all for this reason and it
  read as the layout's design. The logo is now re-placed above the
  field, in white on a dark one. This would have spread to the 39 slides
  that declare white the moment the fix landed.
- The white field initially forced black ink over everything and turned
  `kone_numbers`' blue figures black. A field the SET declares now
  carries no ink override; only a divider, which picks its own colour,
  reverses type.

**P0-3, overlapping regions.** Confirmed — `lifecycle_4stage` has 8
overlapping pairs and `text_picture_a` 9 — and preflight now checks for
it, as asked. It measures **ink, not boxes**: comparing boxes reported a
divider's one-line eyebrow as colliding with the title below it, on
every numbered divider in the library. The geometry fix itself is
blocked, see below.

**`comparison_table` as a string.** Your guess was right and is now
supported: rows on `;`, columns on `|`, first row the header, a leading
empty cell for the row-label column. It crashed the build before —
`AttributeError` on the whole deck, not just that slide.

## Corrected

**P0-1, the classification stamp — the diagnosis, not the finding.**
You are right that it is on all 45 and wrong on the 21 external ones.
It is not in the chrome layer, so adding an external case to the omit
list would have done nothing.

It is a plain **Arial 8pt text box on the slide master**, at x:1204 y:7,
inherited by all fifty layouts. `stamp_chrome` never drew it and already
places a real classification correctly (bottom-left, KONE Information,
only when a deck declares one). The fix was to remove the master's box.
Worth noting it was off-brand three ways: Arial is not an approved face,
the position is wrong, and it appeared on customer decks.

**Contract problem 1 — nested list slots.** This was my bug, not a
contract defect. The renderer has always accepted an array for
`two_content.items[].bullets` and the other five; my template generator
special-cased `bullets` only at the top level and emitted `""` inside a
list. You wrote single clauses because I asked for strings.

The template is fixed. **Those six slots are worth a second pass** —
`two_content`, `matrix_2x2`, `statement_links`, `lifecycle_4stage`,
`segment_breakdown`, `quarterly_plan_4col` — and they will now come
through as arrays. Your copy is legal in the meantime; it just reads as
one line where three belong.

## Still blocked

**The two drawings did not arrive.** `Internal Layout Specs.dc.html` and
`Slide Review Board.dc.html` are referenced in `INSTRUCTIONS.md` §4 as
living "in the design project", and the zip contains only the five
markdown files and `placeholders.json`. This blocks:

- the five unbuilt layouts (§4), including `value_prop_four_point`,
  which you specifically said not to guess at;
- the geometry fix for the two overlapping icon rows. `lifecycle_4stage`
  gives each stage cell 73px between the axis at 548 and the floor at
  629 — an icon at 40px plus a heading at 21px leaves 12px for the
  bullets, so the cell needs re-proportioning rather than nudging, and
  that is a design decision.

Both are quarantined by name in the test suite so nothing new can hide
behind them.

**`kone_numbers` external needs a colour ruling.** The slide field is
now white per the set, but the sand band across the figures is a panel
the archetype draws, not the field, so it survives. `DEFECTS.md` §5 says
"the policy allows blue as the only field on that slide". Should the
band be blue externally and sand internally — i.e. does panel colour
follow the `(archetype, audience)` pair the same way the field does?

## Not yet decided: the meter

`meter.json`, `TIER_MAP.md` and §1–2 of your `INSTRUCTIONS.md` are read
and understood, and the shape is right — collapsing the audience switch
into the deviation axis removes exactly the combinations nobody should
be able to express. It is also a real change to how the tool is driven,
so it is with the owner rather than half-built.

Two things I would want settled before building it:

1. **Stop 1 is short three layouts today** and stop 2 two more, because
   all five unbuilt archetypes are tier 1 or 2. Until the drawings
   arrive, stop 1 offers 17 of its 20. Ship the meter with a short stop
   1, or build the five first?
2. **`pool_for_stop` reads `meter.json` rather than hard-coding tiers** —
   agreed, and that means the file is vendored into the package and
   becomes a build input. Is `meter.json` yours to edit from here on, the
   way `slide-sets.json` is?

The icon ruling in §3 is independent of the meter and I would rather do
it next: deleting the rotation is a two-line change, but "every icon
layout must render legally with zero icons" needs the reflow, and that
is the same reflow the two overlapping rows need. One job, once the
drawings are here.
