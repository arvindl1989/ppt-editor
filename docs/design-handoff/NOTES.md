# Notes

Answers to `OPEN_QUESTIONS.md`, then what I changed my mind about, then
the contract problems I found while writing the copy.

## Answers

**1 · Where the numbered divider's parts sit.** Take the measured
positions — numeral `x:45`, title `x:453` — over the prose. The prose was
written from one deck; you measured five uses of the layout in a real
deck, and five uses beat one description. Keep the vertical centring of
the pair. The 200px figure is black on every secondary field and white on
blue, per brand mode §1.

**2 · How big a cover title actually is.** 40px is right, and the prose
is wrong. A cover title is `display` (44px), not a size of its own; 76px
is an artefact of measuring a two-word cover in the master where the box
autofitted up. Set `display` at 44 and let the budget follow. Keep the
`fits` figures computed from the measurement — a budget derived from a
size nobody renders at is worse than a tight one.

**3 · `picture_intro` — you changed the slide.** Confirmed, keep your
version. A banner photo with a title and one line is `text_picture_g`
with less in it; the photo-right layout with three reasons is the slide
the set needs at position 2. Register the banner variant as an alias of
`text_picture_g` rather than leaving two archetypes that differ by a
photo's aspect.

**4 · The fifth agenda row.** Let all five be sand. Per-item colour is
not worth adding to the group model for one row, and the inversion was
decoration — the row numbers already carry the sequence. If you want the
last row to read as the destination, that is a job for the section
divider that follows it.

**5 · How tall the pink panel on `TIMELINE_QUARTER_AXIS` is.** Shorter.
End the panel 32px under the last bullet, which is what the vertical
rhythm rule in brand mode §2 gives you everywhere else. Slides are
top-weighted; a panel run to the floor to fill space is the same mistake
as a row pinned to the bottom third.

**6 · Two charts do not draw.** Make it a fixed illustration driven by
the numbers the caller already supplies, not a chart engine. Both slides
have a chart-shaped hole because they are asking for something the
contract has no way to express, and adding series data to the contract
makes the planner responsible for data design — which is how you get a
five-series stacked bar in a slide that needed three numbers.

- `segment_breakdown`: the contract already carries three categories with
  headings and items. Draw the bars from those, one bar per category,
  blue-tint ramp, and drop the separate `chart` key.
- `chart_commentary`: take `chart` as a list of `{label, value}` pairs,
  maximum eight, and draw paired bars. If the caller supplies fewer than
  three the slide is the wrong choice — put that in the contract's
  `needs` so the planner does not pick it.

**7 · `stat_value` on things that are not statistics.** Add a display
role and move them to it. `stat_value` means "one of a row of figures,
64px blue, all the same size" — that is a rendering decision *and* a
semantic claim, and a cover headline satisfies neither. Suppressing the
hint hides the symptom; the planner still sees a cover slot typed as a
figure. Covers and outros want `display`.

## What I changed my mind about

**The meter is not a freedom dial.** My first shape had each stop relax
one more constraint — layouts, then colour, then icons, then geometry.
That is wrong: it makes brand compliance a slider, and stop 4 becomes a
place where the rules are optional. The meter moves the layout pool only.
Every stop is fully on-brand; the stops differ in which shapes are
available, not in how strictly the shapes are drawn. An internal deck
deviates from the *slide structure*, never from the brand.

**Tier is geometry, but colour sets the floor.** `agenda_c_split` is a
modest geometric deviation and would sit at tier 2 on shape alone. Its
mint panel is not external-safe, and tiers 1–2 are external, so it is
tier 3. Same for `timeline_quarter_axis` (pink) and `quarterly_plan_4col`
(sand). Stated as a rule in `meter.json`.

## Contract problems found while writing the copy

Rather than bending the copy to fit, per your note:

**1 · Nested list slots are typed as strings.** `two_content.items[].bullets`,
`matrix_2x2.quadrants[].items`, `statement_links.columns[].links`,
`lifecycle_4stage.stages[].bullets`, `segment_breakdown.categories[].items`
and `quarterly_plan_4col.quarters[].items` are all `""` in the template.
Every one of them is semantically a list, and rule 3 says a list is an
array of strings — so today the only way to put three items in one of
these is to smuggle them into one string with separators, which rule 3
forbids. I have written a single clause into each, which is legal and
reads poorly. **These should be arrays.** It is the single change that
would most improve the previews.

**2 · `comparison_table.table` is one string** for a four-row,
three-column table. External 24 renders a real table, so the renderer is
parsing structure out of that string. Whatever it parses is the contract;
the contract should say so. I have written it as rows separated by
semicolons and columns by pipes, and flagged it here because I am
guessing.

**3 · `org_functions` carries both `functions` and `diagram`.** The render
draws a single column of seven names and nothing that resembles a
diagram. Either the archetype is a list — in which case drop `diagram`
and rename it — or it is an org chart, in which case `functions` as a
flat array of strings cannot express one, and it needs parent/child.
Tier 4 either way.

**4 · `credits.names` is twelve slots** and the render repeats four names
three times to fill them. Twelve is the ceiling, not the target; the list
should be allowed to run short without previewing as a hole. Filled to
twelve in `placeholders.json` as instructed.

**5 · `resource_links.tiles` is four slots** in what renders as a
six-slot grid. Either the grid is 2×2 and the render is drawing an empty
row, or the contract is short by two.

**6 · Copy is written to conservative ceilings.** I wrote to the role's
intent — an eyebrow is two to five words, a bullet is one line, a stat
label is one or two words — rather than to the `fits` budget, so nothing
should autofit down. Where a slot's budget is much larger than its
intent, treat my copy as the intent.
