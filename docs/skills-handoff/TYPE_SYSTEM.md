# Two type systems, and the wrong one wins

## The measurement

    83 regions carry a BAKED type block
    200 regions resolve through a brand role
    29% of the library bypasses BRAND_MODE entirely
    25 of the 83 disagree with the brand for a slot of that name

A region either says

    {"role": "title", "box": [...]}                       <- resolved

or

    {"role": "dg_text", "box": [...],
     "dg": {"px": 46, "font": "Inter", "caps": false}}    <- baked

The second form came from porting an HTML archetype gallery: the parser
read the RENDERED type off each element and wrote it down. That was the
right thing to do at the time -- it is how the layouts got built at all
-- but it means those 83 regions are immune to the brand. Change
`TYPE_SCALE` and they do not move. Add a role and they cannot use it.

## Why it shows on the divider first

`divider_numbering` is baked in all three of its slots, and all three
are wrong:

| slot | baked | the brand says | the spec says |
| --- | --- | --- | --- |
| `number` | 190px Inter | — | 300px |
| `eyebrow` | 13px Inter, sentence case | 12px KONE Information, CAPS | "section label" |
| `title` | 46px Inter | 32px Inter | 56px |

The eyebrow is the one that reads as broken: it is body copy where the
brand wants a small-caps label, so a section marker looks like a stray
sentence above the title.

## The subtlety that makes this non-trivial

A slot's NAME does not determine its role. `number` on a divider is a
300px display numeral; `number` in `numbered_icon_row_6` is a 28px blue
figure. Both are called `number`. So "look the slot name up in
TYPE_SCALE" is wrong, and that is presumably why the baked blocks were
kept.

The pair `(archetype, slot)` does determine it. That is exactly what
`contracts.py` already knows -- the external contracts name a role per
slot:

    DIVIDER_NUMBERING | number:display · eyebrow:body · title:display

Note that this line is also wrong: `eyebrow:body` is what put body copy
in the eyebrow. The handoff table has the same bug the renderer has.

## What I think should happen, and want challenged

1. **The contract names the role; the region stops carrying type.**
   Delete every `dg` block and resolve `(archetype, slot) -> role ->
   TYPE_SCALE` at draw time. One system.
2. **The contracts need a display tier.** `display` is 44px in the
   scale; the divider wants 300px for its numeral and 56px for its
   title. Either add roles (`divider_numeral`, `divider_title`) or let a
   contract override a size, which reopens the same hole.
3. **The 25 disagreements are a migration, not a rewrite.** They are
   listed in `type-audit.json` with both values, so each can be decided
   rather than guessed.

The risk is real: 83 regions were measured off renders that
looked right. Resolving them through the brand will change
25 slides, and some of those changes will be worse before
they are better. A staged migration with the renders in front of you is
the only honest way to do it.
