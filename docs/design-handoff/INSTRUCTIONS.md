# deckguard — the deviation meter, and what to change to publish it

Answers to `INSTRUCTIONS.md` and `OPEN_QUESTIONS.md`, plus the one new
thing: the meter.

Read in this order. `meter.json` is the spec; this file is the reasoning
and the work.

    meter.json          the meter, machine-readable — the authority
    TIER_MAP.md         every archetype with its tier, in set order
    placeholders.json   the main ask: copy for all 45 built slides
    NOTES.md            answers to the seven open questions
    DEFECTS.md          what the renders get wrong, prioritised

Two things live in the design project rather than in this folder, because
they are drawings:

    Internal Layout Specs.dc.html   geometry for the five unbuilt layouts
    Slide Review Board.dc.html      all 45 renders with the defects marked

---

## 1. The meter

One control, four stops, one axis. **The meter decides which layouts are
eligible and nothing else.**

    1  On template            master layouts, drawn as the master draws them      20 layouts
    2  Slight deviation       master bands, re-divided                            30 layouts
    3  Moderate deviation     off-master composition on the master grid           41 layouts
    4  Internal slide types   plus the programme artefacts                        44 layouts

Pools are cumulative. Stop 4 contains stop 1.

**Audience is inferred from the stop.** Stops 1–2 are external-safe;
stops 3–4 are internal. There is no second switch. A user who wants a
customer deck moves the meter left, and that is the whole interaction.

### What the meter does not do

This is the part worth getting right, because the obvious implementation
is wrong. The meter does **not** loosen colour, type, icons or chrome as
it moves right. Those are fixed at every stop:

- **Colour** is a property of the `(archetype, audience)` pair, read from
  `brand/slide-sets.json`. `kone_numbers` has a white field for a
  customer and a sand band internally. The meter never changes a field.
- **Type** never moves. A title is 32px at stop 1 and 32px at stop 4.
- **Icons** are a property of the archetype: internal column, step and
  row layouts declare icon slots, external layouts declare none.
- **Chrome** — logo, footer, classification — is owned by the layout at
  every stop.

The consequence worth stating, because it is the tiering rule: **an
archetype whose declared field is a secondary colour cannot sit at tier 1
or 2.** Tiers 1–2 are external, and the external field policy is white
plus blue. That is why `agenda_c_split` is tier 3 and not tier 2 — its
geometry is a modest deviation, but its mint panel is not external-safe.
Tier follows geometry; the colour constraint sets the floor.

### Why this shape

An audience switch plus a freedom slider is two controls for one
decision, and every combination in the corner of that matrix is a deck
nobody should send: a customer deck with a pink panel, an all-hands with
no icons. Collapsing them means the illegal combinations cannot be
expressed.

## 2. Where it goes in the code

The meter is a filter, so it belongs at the two places the layout set is
read — and nowhere else.

**`registry.py`** — add the pool filter. One function:

    def pool_for_stop(stop: int) -> set[str]:
        """Archetype names eligible at this stop. Cumulative."""

Read the tiers from `meter.json`; do not hard-code them in Python. The
file is the artefact a designer edits.

Add `audience_for_stop(stop) -> "external" | "internal"` beside it, and
have the field lookup take the audience rather than a set name, so
`(archetype, audience)` resolves the field in one place.

**`planner.py`** — `_kone_archetype_guide()` currently walks every key in
`_load_archetypes()`. Take a `stop` argument and walk `pool_for_stop(stop)`
instead. This is the whole behavioural change: the model cannot choose a
layout it was never shown, so the meter needs no post-validation pass.
`_validate_kone_spec` should still check membership — a plan that names an
out-of-pool archetype is a bug, not a preference — with the stop in the
error text.

Add the stop to the system prompt as one line of context, not as a rule
to obey: *"This deck is being built at stop 3 (moderate deviation,
internal audience)."* The pool already enforces it.

**`screens.py` / `ui.py`** — the meter is the first control on the page,
above the brief. Four stops, `.seg` styling that already exists, stop 1
default. Below it, one line of live consequence: *"30 layouts ·
customer-safe"*. The picker tiles then show the pool for the current stop
and nothing else — not greyed-out tiles for higher stops, which invites
the user to argue with the control they just set.

**Do not** put the stop in `brand_rules.yaml`. That file is what is
legal; the meter is what is chosen.

## 3. Icons — the internal set needs them named

Ruling, replacing the rotation: **every internal column, step and row
layout carries a named-icon slot, resolved against the 609-name sprite,
and nothing is ever filled to avoid a hole.**

    planner names it        -> resolve, or reject the plan for that slot
    slot empty             -> suggest from the keyword map, to the planner
    nothing resolves       -> omit the icon and reflow the row

Three changes in `icons.py`:

1. **Delete the rotation.** Cycling cloud / people / clock / wrench /
   calendar is the single most visible tell in the current renders — it is
   on nine slides and relates to the words beside it on none of them.
2. **An unknown name is an error.** Today a typo falls back to the
   rotation, so it fails quietly and the deck ships with a pictogram
   nobody chose. Report it against the slot.
3. **Every icon layout must render legally with zero icons.** Test it:
   build the internal 25 with every `icon` key empty and run the
   preflight. Nothing may overlap and nothing may cross y=629.

`placeholders.json` names a real icon in every internal icon slot, from
the sprite. Those names are also the fixture for the keyword map: they are
what "queue", "dispatch", "training", "reporting" should resolve to.

Illustrations stay where they are for now. `lifecycle_4stage` and
`how_it_works_3step` are specified with an illustration band rather than a
photo band and neither draws one; that is in `DEFECTS.md` as a fix, not as
a new capability.

## 4. The five that are not built

Build all five. They are the reason two stops have gaps: `statement_b`,
`text_picture_b` and `two_pictures_text_b` are tier 1, so **stop 1 is
missing three of its twenty layouts today**, and `value_prop_four_point`
and `quote_e` are tier 2.

Geometry for all five is drawn to scale in `Internal Layout Specs.dc.html`
alongside the five you redrew, with px positions on each region. Build
from that rather than from the prose — `value_prop_four_point` in
particular should not be guessed at.

## 5. Acceptance

The build is publishable when:

1. Each of the four stops builds a complete deck from the same brief, and
   the four decks differ only in which layouts appear.
2. Stop 1 and stop 2 contain no secondary colour field anywhere.
3. The internal 25 builds with every icon slot empty, and passes preflight.
4. No slide carries the grey `KONE INTERNAL` stamp; classification is
   bottom-left, 10px, KONE Information, black, and absent from external
   decks entirely.
5. The `DEFECTS.md` P0 list is empty.
6. Every preview in the picker uses the copy in `placeholders.json`.
