# Defects, in the order they should be fixed

Read off the 45 renders in `previews/`. P0 is anything a reader would
blame on KONE rather than on the tool.

## P0

**1 · The classification stamp is wrong on all 45 slides, and illegal on 21 of them.**
Grey `KONE Internal`, top-right, in Inter. Brand mode §3: bottom-left at
`45,640`, role `classification`, KONE Information, 10px, caps, black. On
the External 25 it should not be there at all — every customer-facing
render currently says KONE Internal on it. Fix in the chrome layer, not
per archetype; add the external case to the omit list.

**2 · `cover_a_cut4` prints a raw Python list.**
External 01 renders `['Standardise intake on ServiceNow', 'Automate
repeat request types', 'Publish live queue status']` as its subtitle. A
list is reaching a string slot and being formatted by `repr`. The
template types `context` as a 3-item array for this archetype, so the
renderer is joining it wrongly rather than the caller passing the wrong
shape. Any slot that receives a list where it expects a string should
fail the build, not stringify.

**3 · Icons overlap text.**
Internal 09 `lifecycle_4stage`: icons sit on top of the stage headings and
the bullets collide with them. External 12 `text_picture_a`: the icon row
overlaps the lead line. Both are icon rows positioned from a band top
without reserving the icon's own height. Add a preflight check for
overlapping regions, not just for the y=629 floor — nothing catches this
today.

**4 · The pictogram rotation.**
Cloud / people / clock / wrench / calendar on nine slides, unrelated to
the words beside it every time: `icon_columns_5`, `numbered_icon_row_6`,
`lifecycle_4stage`, `resource_links`, `segment_breakdown`,
`picture_intro`, `text_picture_a`, `text_picture_g`, `statement_links`.
Delete the fallback. See `INSTRUCTIONS.md` §3.

## P1

**5 · Fields do not match the set policy.**
Internal 04 `divider_title_only` should be light-blue and renders sand.
Internal 19 `hero_stat` should be light-blue and renders white. External
06 `statement_a` renders sand where the external policy is white only.
External 19 `kone_numbers` renders a sand band where the policy allows
blue as the only field on that slide. The field is declared in
`slide-sets.json` and is not being read — this is the same lookup the
meter needs, so fix it as part of `audience_for_stop`.

**6 · Two charts draw nothing.**
`chart_commentary` and `segment_breakdown` both declare a chart region and
leave a hole in it. See `NOTES.md` §6 for the ruling.

**7 · Shared archetypes render identically in both sets.**
`how_it_works_3step`, `image_section_divider` and `hero_stat` use the same
photograph and the same copy in both decks, so the two sets read as one
deck shown twice. The internal spec asks for a line illustration in the
`how_it_works_3step` and `lifecycle_4stage` bands rather than a photo;
that alone separates them. `placeholders.json` gives each shared
archetype different copy per audience.

**8 · Photography is not reading the copy.**
External 15 `three_pictures_text` puts three cityscapes against captions
about request routing. Internal 25 `outro` is a stadium crowd. The photo
library is selecting on availability, not on subject. Two options: a
keyword map as with icons, or a per-archetype subject constraint
(`outro` wants people flow, never a crowd at an event). The second is
cheaper and covers the visible cases.

## P2

**9 · Scrims are flat.**
`cover_f_fullbleed` and `image_section_divider` darken the whole frame
instead of running a gradient. Brand mode §4 gives both gradients
verbatim. Covers A/B/C should carry no scrim at all — their titles sit on
white.

**10 · `matrix_2x2` has one axis.**
The render shows `IMPACT →` and no second label, so the 2×2 reads as a
list of four boxes. The template has `xlabel` and `ylabel`; only one is
drawn.

**11 · The em dash in `comparison_table`.**
Six cells use `—` for "not included". Legal in a table, and correct here.
Worth pinning as an exception in the §6 bullet lint so a later rule does
not flag it.

**12 · `two_content_narrow_title` is not narrow.**
External 10 sets body copy in the left column where the archetype's
premise is a narrow title. Either the region is too wide or the contract
is wrong; the render suggests the former.
