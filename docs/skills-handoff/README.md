# deckguard — how it makes a deck, and where that is wrong

## The ask

The report was "the fonts and everything on the divider slide looks
whack". It is true, and the cause is not the divider. **The tool has two
type systems and the wrong one wins.**

Since the first version of this handoff, one archetype has been moved
across and the library has been trimmed. What that cost, and what it
turned up, is the most useful part of the document now -- the same two
defects are waiting for the next 15 archetypes.

Read `TYPE_SYSTEM.md` first; it is the whole handoff. `DIVIDER.md` is the
worked example. `PIPELINE.md` says where a deck's decisions get made, so
a fix can be put in the right place.

    TYPE_SYSTEM.md     two type systems, and which one wins
    DIVIDER.md         the reported slide, measured against its own spec
    PIPELINE.md        where each decision is made, in order
    OPEN_QUESTIONS.md  what I could not decide alone
    type-audit.json    every baked region, machine-readable
    contracts.json     what each archetype needs
    meter.json         the deviation meter's tiers
    renders/           the divider on all four fields, and the .pptx

## What the tool is

One page, one button. A brief, a set of picked slides, an uploaded
.pptx, or any combination, becomes a finished KONE deck plus an editable
list of what it built. Slides are drawn with python-pptx onto KONE's own
master. There are 39 built archetypes across two curated sets of 25.

Three layers were added recently and they work:

- **`brandmode.py`** — the brand as data. 42 type roles, the colour
  palette, the vertical rhythm, which slides take a footer.
- **`contracts.py`** — what each archetype NEEDS before it is worth
  choosing, with cardinality. `gaps()` holds the contracts and the
  renderer to each other in both directions and is currently at zero.
- **`meter.py`** — one control, four stops, filtering which layouts are
  eligible. The filter is the enforcement: the planner cannot choose a
  layout it was never shown.

The problem is underneath all three.

## What has already been done

- **`divider_numbering` is migrated.** Three baked slots became three
  brand roles. Two new roles were needed (`section_numeral`,
  `divider_title`) and two latent defects fired -- see `TYPE_SYSTEM.md`.
- **Five duplicate archetypes are no longer installed.** Four `_b`
  twins and a `text_picture` variant: absent from `meter.json` and from
  `slide-sets.json`, so no plan and no manual pick could ever reach
  them. A test holds them to that.
- **Two that were also unreachable are now reachable instead.**
  `card_grid` (slide 8 of the reference deck) and `agenda_a_table` were
  built and refined but had no tier; they were given one rather than
  dropped.

Net: 83 baked regions to 62, 29% of the library to 23%,
25 disagreements to 15.
