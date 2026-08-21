# Two type systems, and the wrong one wins

## The measurement

    62 regions carry a BAKED type block
    204 regions resolve through a brand role
    23% of the library bypasses BRAND_MODE entirely
    15 of the 62 disagree with the brand for a slot of that name

A region either says

    {"role": "title", "box": [...]}                       <- resolved

or

    {"role": "dg_text", "box": [...],
     "dg": {"px": 46, "font": "Inter", "caps": false}}    <- baked

The second form came from porting an HTML archetype gallery: the parser
read the RENDERED type off each element and wrote it down. That was the
right thing to do at the time -- it is how the layouts got built at all
-- but it means those 62 regions are immune to the brand. Change
`TYPE_SCALE` and they do not move. Add a role and they cannot use it.

## Why it showed on the divider first -- and what happened next

`divider_numbering` was baked in all three of its slots and all three
were wrong. It is now the first archetype migrated off baked type, and
the worked example of what the migration costs:

| slot | was baked | now resolves to | measured on the render |
| --- | --- | --- | --- |
| `number` | 190px Inter, black | `section_numeral` | 300px, ink centred on y=360 |
| `eyebrow` | 13px Inter, sentence case | `eyebrow` | 12px KONE Information, CAPS, blue |
| `title` | 46px Inter | `divider_title` | 56px, one line in a 760px column |

Three things that only showed up once it was tried, and that the next
15 archetypes will hit too:

1. **`figure` cannot be used as a region role.** BRAND_MODE's table
   names the section numeral `figure`, but `kone_engine` reads
   `role == "figure"` as an IMAGE and drew the numeral as an empty
   placeholder box. Region roles and type roles share one namespace at
   draw time. The role is `section_numeral` for that reason alone.
2. **The on-dark swap only ever worked for baked regions.** The field's
   ink override was applied in the `dg` branch, so the moment the
   divider resolved through the brand it came out black on KONE Blue,
   with the eyebrow -- blue by role -- invisible against the field.
   Fixed by swapping role-based regions to their light twin in `render`.
3. **A 56px title needs its own role, not an override.** BRAND_MODE says
   "every slide title is 32 -- no exceptions", and that rule is about
   CONTENT slides. Both divider entries in the set specs independently
   ask for 56, which is two witnesses for a distinct role. Naming it
   `divider_title` keeps the 32 rule intact instead of punching a hole
   in it.

## The subtlety that makes this non-trivial

A slot's NAME does not determine its role. `number` on a divider is a
300px display numeral; `number` in `numbered_icon_row_6` is a 28px blue
figure. Both are called `number`. So "look the slot name up in
TYPE_SCALE" is wrong, and that is presumably why the baked blocks were
kept.

The pair `(archetype, slot)` does determine it. That is exactly what
`contracts.py` already knows -- the external contracts name a role per
slot:

    DIVIDER_NUMBERING | number:display . eyebrow:body . title:display

Note that this line is also wrong: `eyebrow:body` is what put body copy
in the eyebrow. The handoff table has the same bug the renderer has.

## The numeral's colour is still open

Three documents disagree and none of them is obviously wrong:

- `INTERNAL_25.md` says "300px blue numeral".
- `BRAND_MODE.md` types it 200px black and gives a reason -- "black on
  every secondary field" -- which matters because this slide ships on
  sand, pink, mint and light blue.
- `brandmode.py` has held 300px BLACK since the type scale was written:
  the spec's size with the brand's colour rule.

It is left black, because the field rule is a rule about fields and the
divider is exactly the slide that lands on them. On a blue field it
reverses to white, which now works. Worth a designer's ruling.

## What remains

1. **62 regions still carry a `dg` block.** Same treatment:
   name the role, delete the block, look at the render.
2. **15 disagreements are a migration, not a rewrite.**
   Listed in `type-audit.json` with both values, so each is a decision
   rather than a guess.

The risk is real, and the divider proved it: two defects that had
never fired -- the `figure` name collision and the missing on-dark swap
-- both surfaced on the very first archetype moved. Every one of these
regions was measured off a render that looked right. A staged migration
with the renders in front of you is the only honest way to do it.
