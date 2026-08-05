# Feedback for the `kone-design` skill (and `kone-deck-generator`)

Everything below was found by running the skill's own assets through deckguard
against real production decks, then measuring the output. Each item names the
file, the measurement, and what deckguard had to do to work around it. Anything
marked **workaround** is currently patched on deckguard's side — if the skill
fixes it upstream, the workaround can be deleted.

Measurements are reproducible against:

- `~/.claude/skills/kone-design/uploads/master_ppt-1784774200983.pptx`
- `~/.claude/skills/kone-design/templates/kone-deck/ArchetypeGallery{1..4}-*.dc.html`
- `~/.claude/skills/kone-deck-generator/{archetypes.py,kone_engine.py,assets/}`

---

> **Update after the design handoff (`Gradient_Design_System_1.zip` + `All Slides.pptx`).**
> The reworked spec landed and most of this document is now actionable rather
> than open. Current state on deckguard's side: **all 61 canonical archetypes
> render** (A 12/12, B 19/19, C 15/15, D 15/15), generated from `LAYOUTS.md`
> geometry rather than ported by hand. Still open upstream, verified against
> the files as shipped:
>
> - **§1.1 is NOT fixed.** `All Slides.pptx` has the same 54 empty frames
>   (47 `Logo`, 7 `Tagline`); `ARCHETYPES.md`'s "63/63 embedded, 0 broken"
>   does not match the file. Re-exporting did not re-link them.
> - `ARCHETYPES.md` claims the generator "loads real pictograms from
>   `assets/icons/`" and "knows about it (`DARK_BG_LAYOUTS`)". Neither is
>   true of the generator in the bundle — its four `.py` files are
>   byte-identical to the installed skill, and `DARK_BG_LAYOUTS` exists
>   nowhere.
> - The counts in `INSTRUCTIONS.md` (12+20+16+8=56) don't match the tables
>   (12+19+15+15=61, of which 46 built / 9 twins / 6 spec).
> - §1.2 (alpha), §1.3 (`FIGURES`), the em-dash bullets in
>   `_dash_bullets`, the grey `caption`/`body_muted`/`attribution` roles,
>   and `COVER_F_FULLBLEED`'s photo-protection gradient are all still
>   live in `kone_engine.py`.

## 1. Blockers — these produce visibly broken slides

### 1.1 The master template ships 54 empty picture frames

`master_ppt-1784774200983.pptx` contains 63 pictures. **9 carry an embedded
image. 54 do not** — their `<p:pic>` has an `<a:blip>` with no relationship, so
python-pptx raises `ValueError: no embedded image` and **PowerPoint draws them as
an empty dotted rectangle**.

```
pictures ok:        9
pictures broken:   54   ->  Logo x47, Tagline x7
layouts affected:  49 of 63
```

This is the single most visible defect: every deck built on the master shows a
dotted box where the logo should be, on 49 of 63 layouts. It is not a rendering
bug — the image parts are genuinely absent from the .pptx.

**Fix:** re-export the master with the logo/tagline images actually embedded,
including the white variants for dark layouts.

**Workaround:** `deckguard/logo.py :: repair_empty_logo_frames()` finds frames
named `Logo`/`Tagline` with no blip and injects the correct raster mark, picking
the white variant when the page background is dark. Verified 52 → 0 on a
rebuilt deck.

### 1.2 `kone_engine._image()` destroys alpha

`kone_engine.py:91`:

```python
im = Image.open(path).convert("RGB")
```

Every logo, tagline and illustration in `kone-deck-generator/assets/` is RGBA.
`convert("RGB")` composites transparency onto **black**, so a mostly-transparent
mark lands on the slide as a black rectangle:

```
logo-white.png     RGBA  73% opaque
tagline-blue.png   RGBA  24% opaque   <- renders as a near-solid black block
```

This is what the user saw and reported as *"the KONE logo has a black
background"* on the divider slide.

**Fix:** keep RGBA end-to-end — save resized results as PNG, and if a flatten is
unavoidable, composite onto the slide's background colour, never onto black.

### 1.3 `archetypes.FIGURES` force-injects bundled chart art

`archetypes.py:27-38`:

```python
FIGURES = {
 "segment_breakdown": {"chart":  "seg_chart.png"},
 "chart_commentary":  {"chart":  "cc_chart.png"},
 "org_functions":     {"diagram":"org_diagram.png"},
}

def render(slide, name, content):
    c = dict(content)
    for key, fn in FIGURES.get(name, {}).items():
        c[key] = os.path.join(_icondir, fn)   # overwrites caller content
```

The caller's content is overwritten unconditionally, so any deck using one of
those three archetypes gets a **sample pie chart it never asked for**. The user
reported exactly this: *"why is there a pie chart there randomly?"*

**Fix:** only fall back to the bundled figure when the caller supplied nothing
for that key (`c.setdefault(...)`), and ideally only in gallery/demo mode.

### 1.4 Icon-driven archetypes need more icons than the skill ships

`archetypes.ICONS` maps 6 archetypes to icon sets needing **up to 5 icons each**
(`icon_columns_5`, `lifecycle_4stage`, `resource_links`, `segment_breakdown`,
`statement_links`, `offer_cta`). `kone-design/assets/icons/` ships **3 SVGs**
(`arrow`, `cloud`, `connect`). The generator therefore falls back to its own
`ic0..ic4.png` placeholder chips, which are flat RGB and off-brand.

**Fix:** ship the real KONE pictogram set (a dozen or so covers the archetypes),
as transparent PNG alongside the SVG.

### 1.5 Vector-only assets can't go into a .pptx

`kone-design/assets/logo/` and `assets/icons/` are **SVG only**. PowerPoint
cannot embed SVG through python-pptx, so every pipeline that builds a real deck
has to rasterise first.

**Fix:** ship PNG (transparent, ≥2x) next to each SVG — at minimum
`kone-logo`, `kone-logo-white`, `kone-tagline`, `kone-tagline-white`. Note
`kone-tagline-white.svg` exists but the generator's raster assets have no
white tagline at all (`assets/` has `tagline-blue.png` only).

**Workaround:** deckguard vendors 10 rasterised marks under
`src/deckguard/assets/kone-design/logo/`.

---

## 2. Two archetype vocabularies that don't overlap

The gallery and the generator name the same design language differently:

| source | count |
| --- | --- |
| `ArchetypeGallery1..4` HTML (documented) | **56** |
| `kone_deck_generator.ARCHETYPES` (implemented) | **23** |
| shared (case-insensitively) | **17** |
| documented but not implemented | **39** |
| implemented but not documented | **6** |

Implemented-only: `agenda_contents`, `four_point_value`, `image_section_divider`,
`quote_context`, `statement_links`, `text_stats_picture_right`.

Documented-only includes everything a user actually asks for by name from the
gallery: `COVER_A_CUT4`, `COVER_B_CUT3`, `COVER_C_CUT4_WIDE`, `COVER_D_CUT3_WIDE`,
`COVER_E_SIDE`, `COVER_F_FULLBLEED`, `DIVIDER_A..D`, `DIVIDER_NUMBERING`,
`END_LOGO`, `TITLE_TEXT_SPLIT`, `TITLE_CONTENT`, `TWO_CONTENT`, `THREE_CONTENT`,
`STATEMENT_*`, `REPORT_*`, `QUOTE_*`, `AGENDA_A_*` …

The practical consequence: a user writes *"use COVER_A_CUT4 for the title slide,
DIVIDER_D for dividers, END_LOGO for the outro, TITLE_TEXT_SPLIT for slide 2"* —
which is a perfectly reasonable reading of the gallery — and **none of those four
names exist in the engine**, so the deck comes back with generic layouts and no
error explaining why.

Also note the casing difference: gallery names are `UPPER_SNAKE`, engine keys are
`lower_snake`. Whatever the merged vocabulary is, one casing convention would
prevent silent misses.

**Fix (in priority order):**
1. Make the two vocabularies one list. Either implement the gallery names or mark
   the unimplemented ones clearly as "documented, not yet buildable".
2. When an archetype name is unknown, **fail loudly with the nearest match**
   rather than silently substituting.

**Workaround:** deckguard parses the gallery HTML into engine archetypes
(`deckguard/gallery.py`) — registry 23 → 41, shared vocabulary 17 → 35 — and
`skill_bridge.check_brief_archetypes()` reports unknown names back to the user.

---

## 3. The gallery HTML resists parsing

Porting gallery 1 surfaced four markup patterns that each silently dropped
elements. If the galleries are meant to be machine-readable (they are the only
spec for 39 archetypes), these are worth normalising:

1. **Unitless zero** — `left:0` instead of `left:0px`. A strict `(-?[\d.]+)px`
   parse rejects it, which dropped every cut banner on the cover archetypes.
2. **Geometry on the wrapper, role on the child** — the positioned box is the
   `<div>`, but the thing that says "this is a title" is the `<h2>` inside it.
   Parsing per-element found no titles at all.
3. **Multiple roles in one wrapper** — eyebrow and title share a wrapper on
   several archetypes, so a one-role-per-box parse kept the eyebrow and lost
   the title.
4. **Stacked lines with no per-line box** — several boxes hold 3-4 separately
   styled lines. Given a flat 1.5x line-height in a 539px column, shrink-to-fit
   crushed 19px type to 8.5pt.

A `data-archetype` / `data-role` attribute pair on each block would make the
galleries a real spec instead of a rendering.

Galleries 2-4 are still marked "pending rework" — that's ~40 of the 56 names.

---

## 4. Brand rules the tool now enforces (please confirm they're right)

These came out of review and are now hard rules in deckguard's
`brand_rules.yaml`. Worth writing into `readme.md` so both the skill and the
tool agree:

- **Inter is never bold.** Weight comes from the separate *Inter SemiBold*
  family, not from `bold=true` on Inter. If source content is bold Inter, it
  should be re-set as regular Inter (or SemiBold where emphasis is intended) —
  never bold Inter. Measured 67 bold-Inter runs → 0 after the rule landed.
- **Blue background → white text; secondary background → black text.** Already
  in `readme.md`, but the master's "Title and text" layout carries a solid
  `#1450F5` in `<p:bg>` rather than a shape, so any tool that only inspects
  shapes will happily place black text on it. Consider using a background shape,
  or documenting the `<p:bg>` layouts.
- **The cut cover is a mask, not four pre-cropped panes.** `COVER_A_CUT4` should
  be *one picture frame plus background-coloured mask rectangles*, so a user can
  drop in a single photo and get the chopped effect. The gallery currently reads
  as four separate panes, which is how the first port implemented it — and the
  user immediately flagged it: *"it's a template where when we add a picture,
  adds that chopped effect, instead of it being chopped into 4 sections
  already."*
- **Footer chrome is mandatory.** Date bottom-left, page number bottom-right, on
  every slide except covers/dividers/outro. Note python-pptx never clones the
  master's latent `DATE`/`FOOTER`/`SLIDE_NUMBER` placeholders, so any generator
  building slides programmatically has to stamp them explicitly — the user
  reported missing footers on two separate decks.
- **`COVER_F_FULLBLEED`'s photo-protection gradient** is specified in the
  gallery but not implemented anywhere. White type over an unprotected photo is
  a contrast failure waiting to happen.

---

## 5. Smaller things

- `LAYOUTS.md` documents 63 master layouts; several duplicate each other after a
  logo/tagline swap. Deckguard drops redundant masters
  (`gallery.drop_redundant_master_slides()`); collapsing them upstream would
  make layout matching more predictable.
- Archetype chrome vs. template frames now double up: once the master's empty
  logo frames are repaired, archetypes that draw their own logo produce **two**
  logos on the same slide. Worth deciding once, in the skill: does the archetype
  own the chrome, or the layout?
- `kone_engine._image()` writes temp files to `/tmp/_img_<hash>.png` with a
  collision-prone `abs(hash(...)) % 99999` key — two different images can share a
  filename within a run.
- `_icon()` is still a blue rounded-rectangle placeholder with a `# swap for real
  KONE icons` comment.

---

## 6. What deckguard is doing in the meantime

So the skill knows what's already covered on this side and doesn't need to
duplicate it:

| area | module |
| --- | --- |
| repair empty `Logo`/`Tagline` frames, dark/light variant | `logo.py` |
| parse gallery HTML into engine archetypes | `gallery.py` |
| mine a reference .pptx into archetypes | `mine.py` |
| structural archetype matching + vocabulary check | `skill_bridge.py` |
| headless-Chromium visual measurement (overflow, contrast, tiny type, off-slide) | `visual.py` |
| stamp date/page-number footers python-pptx won't clone | `transform.py` |
| never-bold-Inter, background-aware contrast | `rules_engine.py` |

Measured effect on real decks: no-option slides 10/12 → 0/12 and 5/8 → 0/8;
bold Inter 67 → 0; empty logo frames 52 → 0; visual findings on the DX deck
116 major → 19.
