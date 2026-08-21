# Where a deck's decisions are made

In order, with the file that owns each.

## 1 · Input — `web.py :: generate`

Reads the brief, the meter's stop, the ticked sections, any picked
slides, and an uploaded .pptx. The stop decides the audience; there is
no separate audience control.

## 2 · Plan — `assemble.py :: plan` / `_from_brief`

Builds the instruction and calls the model ONCE. The menu is filtered to
the meter's stop, and every entry carries what the archetype needs:

    three_content — Three equal text columns. Three pillars, three phases.
        needs: title · items (3 × {heading, text})

**The known weakness.** That single call chooses the archetypes AND
writes the copy. Structure therefore gets decided as a side effect of
writing, and whatever the model has just written for is the cheapest
next choice — which is the mechanical cause of a deck reusing one
layout. The intended fix is two passes: extract typed material from the
brief with no layouts mentioned, then match material to contracts in
code and let the model only write copy. Neither pass is built.

## 3 · Build — `layouts.py :: build_deck` / `render`

Prepends the four-pane cut cover unless the spec names one, draws each
archetype onto its own master layout, stamps chrome, keeps the master's
"Thank you".

`render` is where the two type systems meet: a region with a `dg` block
is drawn from that block; a region with a role goes through the engine's
`ROLE_STYLE`, which `brandmode` now fully populates.

## 4 · Check — `assemble.py :: preflight`

Reads the built .pptx back and reports: type outside black/white/KONE
Blue, a dash standing in for a bullet, content below the floor at y=629,
overlapping text, more than one logo. It reports rather than blocks —
the file is always returned.

Preflight is the only thing in the pipeline that has caught its own
author, twice. It is worth strengthening rather than replacing.
