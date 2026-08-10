# Instructions for Claude Code

Read `README.md` first — it carries every colour, size and position. This file
is the order of work and the rules that fail review.

## What you are being asked to do

Recreate two KONE slide sets in the target codebase's own environment. The HTML
in this project is the design reference, not the shipping artefact. If the
codebase already has a deck pipeline (python-pptx, a React deck runtime, a
Markdown-to-slides build), implement into it. If it has none, choose one and
say why in your first message.

## Order of work

1. **Tokens first.** Encode the colour, type and spacing tables from
   `README.md` as the codebase's own tokens. Do not hardcode hex values in
   slide components.
2. **Chrome second.** Logo placement, footer chrome, page numbering and the
   protection gradient belong to the layout layer, not to individual slides. An
   archetype that draws its own logo produces two logos once the layout is
   correct.
3. **Archetypes third.** Build the twenty-five internal archetypes as
   parameterised components against `INTERNAL_25.md`. Six of them
   (`DIVIDER_NUMBERING`, `IMAGE_SECTION_DIVIDER`, `HOW_IT_WORKS_3STEP`,
   `KONE_NUMBERS`, `HERO_STAT`, `OUTRO`) also serve the external set —
   build once, parameterise the field.
4. **External set fourth.** `EXTERNAL_25.md` gives each archetype's region
   contract; `External 25.dc.html` is all twenty-five drawn. Six archetypes
   (`DIVIDER_NUMBERING`, `IMAGE_SECTION_DIVIDER`, `HOW_IT_WORKS_3STEP`,
   `KONE_NUMBERS`, `HERO_STAT`, `OUTRO`) appear in both sets — build once,
   parameterise the field and the on-field type colour. The external set adds a
   page number to the footer; the internal set does not.
5. **Export last.** Both sets must survive PowerPoint and PDF export. Charts
   are marked to rasterise; text must stay native.

## Rules that fail review

These are not style preferences. Output that breaks one is wrong.

1. **Inter is never bold.** Weight comes from Inter SemiBold as a separate
   family, never a bold flag on Inter Regular.
2. **Type is never grey.** Black `#141414`, white, or KONE Blue for KONE
   Information labels. Hierarchy comes from size and position, never opacity.
3. **Inter is never blue, and never uppercase** — except the word "KONE".
   KONE Information is always uppercase.
4. **Max two secondary colours per slide**, charts excepted.
5. **Yellow and mint are never a full background.** Blocks only.
6. **Blue field → white type. Secondary field → black type.** Note that the
   master's "Title and text" layout carries its blue in the slide background
   rather than in a shape, so any generator that only inspects shapes will place
   black type on blue. Use a background shape.
7. **Bullets are real list markers**, blue marker on black text, one nested
   level. No hyphens standing in.
8. **Exactly one logo per slide**, placed by the layout.
9. **Footer chrome on every slide** except covers, dividers and the outro.
   python-pptx does not clone the master's latent DATE / FOOTER / SLIDE_NUMBER
   placeholders — stamp them explicitly.
10. **Corner radius 0. No shadows. No gradients** except photo protection.
11. **Keep RGBA end to end.** Logos, taglines and illustrations are
    transparent. If a flatten is unavoidable, composite onto the slide's own
    background colour, never onto black.
12. **Name every icon or accept none.** An unnamed icon is omitted and the row
    reflows — the layout must still render legally with no icons at all.

## Known gaps to resolve before production

- **Pictogram sprite.** Swap the extracted `assets/pict/` set for the official
  brandbook.kone.com library, resolved by name.
- **Illustration inventory.** Nine of the illustrations have no description; a
  content planner cannot pick them by meaning.
- **Archetype markers.** Both decks print the archetype name centred at
  `top:658` for reference. Strip it from anything customer-facing.
- **Placeholder copy.** Both sets carry fictional content — a regional
  programme internally, a portfolio modernisation proposal externally. Slot
  real copy before use; region contracts are in `INTERNAL_25.md` and
  `EXTERNAL_25.md`.
- **Confidentiality label.** Internal decks often need one. Only
  `MILESTONE_SLIDE` has a region for it today. Decide whether it goes into the
  footer for the whole internal set.

## Verifying your output

Check every generated slide against these, in this order: two-secondary limit;
blue present somewhere; on-colour type correctness; footer chrome present or
correctly absent; one logo; no bold Inter; no grey type; bottom of every region
at or above y:629; content column flush to 1280px at true slide scale.
