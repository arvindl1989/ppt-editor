"""Tests for layouts.py -- the master's geometry read as data.

The parsing tests run on inline fixtures so the rules are pinned
regardless of which spec revision is installed. The tests that read the
shipped `LAYOUTS.md` / `ARCHETYPES.md` are there to catch a spec update
that silently stops parsing -- the failure mode this module exists to
prevent is not a crash, it is quietly generating nothing.
"""

import pytest

from deckguard import layouts as L

LAYOUTS_FIXTURE = """\
# geometry

## Covers

### Cover A
`slideLayout1`

- **Picture** — 0, 0, 1280 × 421 · white · image
- **Logo** — 45, 45, 81 × 31
- **Title** — 45, 429, 578 × 155
- **Footer** — 215, 658, 408 × 19

### Three content A
`slideLayout24`

- **Text/body** — 45, 227, 374 × 403
- **Text/body** — 453, 227, 374 × 403
- **Text/body** — 861, 227, 374 × 403
- **Logo** — 1153, 45, 81 × 31 · image

### Quote A
`slideLayout40`

- **Background** — 453, 136, 782 × 493
- **Title** — 45, 136, 272 × 104
- **Text/body** — 510, 212, 657 × 349 · white
"""

ARCHETYPES_FIXTURE = """\
# glossary

## Grade A — most used

| Archetype | What it's for | Master | Status |
| --- | --- | --- | --- |
| `COVER_A_CUT4` | Title slide. Alias: `cover_cut` | `slideLayout1` | built · 01 |
| `THREE_CONTENT` | Three columns. | `slideLayout24` | built · 09 |
| `TIMELINE` | Roadmap. | no master | built · 10 |

## Grade D — good to have

| Archetype | What it's for | Master | Status |
| --- | --- | --- | --- |
| `THREE_CONTENT_B` | Twin of `THREE_CONTENT`. | `slideLayout25` | twin |
"""


@pytest.fixture
def spec(monkeypatch, tmp_path):
    (tmp_path / "LAYOUTS.md").write_text(LAYOUTS_FIXTURE)
    (tmp_path / "ARCHETYPES.md").write_text(ARCHETYPES_FIXTURE)
    monkeypatch.setattr(L, "spec_dir", lambda: tmp_path)
    return tmp_path


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------


def test_geometry_parses_into_boxes():
    layouts = L.parse_layouts(LAYOUTS_FIXTURE)
    assert set(layouts) == {"slideLayout1", "slideLayout24", "slideLayout40"}
    cover = layouts["slideLayout1"]
    assert cover.name == "Cover A"
    picture = next(b for b in cover.boxes if b.role == "Picture")
    assert (picture.x, picture.y, picture.w, picture.h) == (0, 0, 1280, 421)
    assert "image" in picture.mods


def test_chrome_is_recognised_and_excluded_from_content():
    """An archetype that places its own logo produces two of them once
    the master's own frames are repaired. Chrome belongs to the layout."""
    cover = L.parse_layouts(LAYOUTS_FIXTURE)["slideLayout1"]
    assert [b.role for b in cover.content_boxes()] == ["Picture", "Title"]


def test_archetype_rows_carry_their_grade_and_binding():
    archetypes = L.parse_archetypes(ARCHETYPES_FIXTURE)
    cover = archetypes["COVER_A_CUT4"]
    assert cover.grade == "A"
    assert cover.master == "slideLayout1"
    assert cover.aliases == ("cover_cut",)
    assert cover.is_built and cover.engine_key == "cover_a_cut4"
    assert archetypes["TIMELINE"].master is None
    assert archetypes["THREE_CONTENT_B"].twin_of == "THREE_CONTENT"


def test_an_ungraded_archetypes_file_yields_nothing_rather_than_guessing():
    assert L.parse_archetypes("| `FOO` | bar | `slideLayout1` | built · 01 |") == {}


# --------------------------------------------------------------------------
# role binding
# --------------------------------------------------------------------------


def test_a_simple_layout_becomes_regions(spec):
    built = L.build_archetypes()
    cover = built["cover_a_cut4"]
    assert [r["role"] for r in cover["regions"]] == ["picture", "title"]
    assert cover["regions"][0]["content"] == "image"
    assert "groups" not in cover


def test_equal_boxes_at_one_y_become_one_repeating_group():
    """Three 374x403 boxes at y=227 are not three regions -- they are
    one group of three, which is the only form the engine can expand
    over a content list of a different length.

    Tested on `_bind_roles` rather than `build_archetypes` because
    THREE_CONTENT carries a reference refinement that replaces this
    binding; the binding still has to be right underneath it."""
    layouts = L.parse_layouts(LAYOUTS_FIXTURE)
    three = L._bind_roles(layouts["slideLayout24"])
    assert three["regions"] == []
    (group,) = three["groups"]
    assert group["origins"] == [[45, 227], [453, 227], [861, 227]]
    assert [r["box"] for r in group["regions"]] == [[0, 0, 374, 403]]


def test_a_background_box_becomes_a_panel_not_a_region(spec):
    """The engine's own `panel` role is hardcoded to KONE Blue and these
    come in five colours, so panels are carried separately and painted
    by `render` before the engine draws anything."""
    layouts = L.parse_layouts(LAYOUTS_FIXTURE)
    quote = L._bind_roles(layouts["slideLayout40"])
    assert quote["panels"] == [{"box": [453, 136, 782, 493], "fill": "1450F5"}]
    assert not any(r["role"] == "panel" for r in quote["regions"])


def test_white_marks_ink_on_a_text_box_and_fill_on_a_panel():
    """The same modifier means different things either side of the
    role: `white` text on Quote A's blue panel, a white FILL on Title
    and Text's field."""
    layouts = L.parse_layouts(LAYOUTS_FIXTURE)
    quote = L._bind_roles(layouts["slideLayout40"])
    on_panel = next(r for r in quote["regions"] if r["box"][0] == 510)
    assert on_panel["role"] == "on_panel_body"


def test_a_twin_renders_as_its_parent(spec):
    """`ARCHETYPES.md` says to prefer the parent -- but a brief that
    names the twin still has to render, and a twin is by definition
    geometrically identical."""
    built = L.build_archetypes()
    assert built["three_content_b"] == built["three_content"]


def test_timeline_has_geometry_despite_having_no_master(spec):
    built = L.build_archetypes()
    assert "timeline" in built
    assert any(r["role"] == "axis" for r in built["timeline"]["regions"])


# --------------------------------------------------------------------------
# installing
# --------------------------------------------------------------------------


class _Registry:
    def __init__(self, existing=None):
        self.ARCHETYPES = dict(existing or {})


def test_install_never_overwrites_a_hand_built_archetype(spec):
    """Hand-built archetypes were tuned against a real rendering; these
    are derived from a coarser description and must lose."""
    hand = {"regions": [{"role": "title", "box": [1, 2, 3, 4], "content": "title"}]}
    module = _Registry({"three_content": hand})
    added = L.install(module)
    assert "three_content" not in added
    assert module.ARCHETYPES["three_content"] is hand


def test_install_defers_to_an_alias_too(spec):
    """`COVER_A_CUT4` aliases `cover_cut`; implementing either means the
    archetype is covered and must not be regenerated under the other
    name."""
    module = _Registry({"cover_cut": {"regions": []}})
    assert "cover_a_cut4" not in L.install(module)


def test_install_is_idempotent(spec):
    module = _Registry()
    first = L.install(module)
    assert first and L.install(module) == []


def test_coverage_counts_aliases_as_covered(spec):
    module = _Registry({"cover_cut": {"regions": []}})
    assert L.coverage(module)["A"] == (1, 3)


# --------------------------------------------------------------------------
# against the shipped spec
# --------------------------------------------------------------------------


def test_the_shipped_spec_parses_completely():
    """The failure mode this guards is silence: a spec revision that
    stops matching the regex generates nothing and reports nothing.
    Every geometry line in the file must turn into a box."""
    text = (L.spec_dir() / "LAYOUTS.md").read_text()
    # `- **Grade A** — most used...` is prose in the preamble; a
    # geometry line is the one carrying a `w × h`.
    geometry_lines = [ln for ln in text.splitlines() if ln.startswith("- **") and " × " in ln]
    parsed = sum(len(v.boxes) for v in L.parse_layouts(text).values())
    assert parsed == len(geometry_lines) > 300


def test_every_canonical_archetype_is_renderable():
    """The whole point of the module. If a spec update adds archetypes
    faster than this can bind them, this is where it shows up."""
    import sys

    from deckguard import gallery
    from deckguard.skill_bridge import _ensure_skill_on_path

    _ensure_skill_on_path()
    archetypes = __import__("archetypes")
    try:
        gallery.install(archetypes)
    except Exception:  # noqa: BLE001 -- the gallery is optional
        pass
    L.install(archetypes)

    _, meta = L.load_spec()
    missing = sorted(
        a.name for a in meta.values()
        if a.engine_key not in archetypes.ARCHETYPES
        and not any(x in archetypes.ARCHETYPES for x in a.aliases)
    )
    assert missing == [], f"no geometry for: {missing}"


def test_the_pictogram_set_is_rasterised():
    """A .pptx cannot embed an SVG directly, so the icons have to exist
    as raster beside their vector source."""
    marks = L.pictograms()
    assert len(marks) >= 3
    assert all(m.endswith(".png") for m in marks)


def test_the_two_most_used_layouts_carry_an_icon_grid():
    """Measured, not assumed: across two on-brand KONE decks
    `Text and picture A` is used 18 times and `Text and picture G` 8 --
    more than every other layout combined -- and both carry a grid of
    icon-plus-short-text cells that the placeholder map has no form for.
    Slides using them average 7-10 text blocks against 3 bound regions.
    """
    for key in ("text_picture_a", "text_picture_g"):
        refinement = L._REFINEMENTS[key]
        group = refinement["groups"][0]
        assert any(r.get("role") == "icon" for r in group["regions"]), key
        assert len(group["origins"]) >= 4, key


def test_an_archetype_serves_both_its_plain_and_grid_forms():
    """One spec, two shapes. The engine skips a region whose content key
    is absent, so supplying `body` gives the paragraph version and
    supplying `items` gives the grid -- which is how the real decks use
    this layout, sometimes one way and sometimes the other."""
    regions = L._REFINEMENTS["text_picture_a"]["regions"]
    assert any(r.get("content") == "body" for r in regions)
    assert L._REFINEMENTS["text_picture_a"]["groups"][0]["content"] == "items"


def test_a_photo_banner_declares_protection_for_its_reversed_type():
    """White type on a pale photo is unreadable, and the brand specifies
    a gradient for exactly this. Declared only when there IS a photo --
    a scrim over white is just a grey band."""
    scrims = L._REFINEMENTS["text_picture_g"]["scrims"]
    assert scrims and scrims[0]["content"] == "image"
    assert scrims[0]["box"] == [0, 0, 1280, 440]


def test_the_scrim_is_a_gradient_that_spares_the_middle_of_the_picture():
    """A flat tint greys out the subject, which is why the spec calls
    for a gradient: dark at the edges where the type sits, clear through
    the middle where the photograph does its work."""
    import sys

    from pptx import Presentation
    from pptx.util import Emu

    sys.path.insert(0, "/root/.claude/skills/kone-deck-generator")
    try:
        import kone_engine as engine
    except Exception:  # pragma: no cover
        pytest.skip("archetype engine not available")

    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    shape = L._draw_scrim(slide, engine, [0, 0, 1280, 440])

    A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    grad = shape._element.spPr.find(f"{{{A}}}gradFill")
    assert grad is not None, "a flat fill would grey out the photograph"
    stops = [(int(gs.get("pos")), int(a.get("val")))
             for gs in grad.iter(f"{{{A}}}gs")
             for a in gs.iter(f"{{{A}}}alpha")]
    assert stops == sorted(stops), "gradient stops must run in order"
    by_pos = dict(stops)
    assert by_pos[0] > 0 and by_pos[100000] > 0, "the edges carry the type"
    middle = [alpha for pos, alpha in stops if 30000 <= pos <= 70000]
    assert middle and max(middle) == 0, "the subject of the photograph is spared"


def test_icons_are_counted_against_content_not_geometry():
    """An archetype serving both a plain and a grid form declares the
    grid's origins either way. Counting those drew a full set of icons
    onto the plain form -- four of them, two straddling the body
    paragraph, on a slide that asked for none."""
    spec = {
        "regions": [{"role": "body", "box": [0, 0, 10, 10], "content": "body"}],
        "groups": [{
            "content": "items",
            "origins": [[0, 0], [1, 0], [2, 0], [3, 0]],
            "regions": [{"role": "icon", "box": [0, 0, 60, 60]}],
        }],
    }
    assert L._icon_slots(spec, {"body": "just a paragraph"}) == 0
    assert L._icon_slots(spec, {"items": [{}, {}]}) == 2
    assert L._icon_slots(spec, {"items": [{}] * 9}) == 4   # never past the origins
    assert L._icon_slots(spec) == 4                        # geometry, when asked


def test_the_six_up_row_stays_inside_the_right_margin():
    """The grid puts the last column at x=1065 and the page margin is
    45, so a cell wider than 170 runs off the edge -- it was 187."""
    group = L._REFINEMENTS["text_picture_g"]["groups"][0]
    last_x = max(x for x, _ in group["origins"])
    widest = max(r["box"][2] for r in group["regions"])
    assert last_x + widest <= 1280 - 45


def test_a_theme_referenced_background_resolves_to_a_colour():
    """Four KONE layouts set their background by reference --
    `<p:bgRef><a:schemeClr val="bg2"/>` -- which names a theme slot, not
    a colour. Reading only a literal srgbClr reported them as having no
    background, so archetypes drew onto them blind."""
    import posixpath

    from pptx import Presentation

    from deckguard.logo import _page_background_hex

    master = (L._VENDORED_SKILL_DIR / "uploads" / "master_ppt-1784774200983.pptx")
    if not master.is_file():
        pytest.skip("master template not available")
    prs = Presentation(str(master))
    by_key = {posixpath.basename(l.part.partname).replace(".xml", ""): l
              for l in prs.slide_layouts}

    divider = by_key["slideLayout10"]
    assert _page_background_hex(divider.element) is None      # no literal colour
    assert _page_background_hex(divider.element, divider) == "F3EEEA"   # resolved

    # a layout stating a literal colour still reads directly
    assert _page_background_hex(by_key["slideLayout39"].element) == "1450F5"


def test_the_divider_puts_the_number_left_and_the_title_right():
    """Corrected against a real deck that uses this layout five times.
    The gallery port and the HTML reference both had it the other way;
    the master's own boxes agree with the real slides."""
    regions = {r["content"]: r["box"] for r in L._REFINEMENTS["divider_numbering"]["regions"]}
    assert regions["number"][0] == 45
    assert regions["title"][0] == 453
    assert regions["number"][0] < regions["title"][0]


def test_a_named_colour_floods_the_divider_and_carries_its_own_ink():
    """Every divider in sand made a deck monotonous, and the brand puts
    the secondary palette on exactly this slide. The ink follows the
    brand's own rule -- white out of blue, black out of a secondary."""
    assert L._field_for({"field": True}, {"colour": "blue"}) == ("1450F5", "FFFFFF")
    assert L._field_for({"field": True}, {"colour": "light-blue"}) == ("D2F5FF", "141414")
    assert L._field_for({"field": True}, {"color": "pink"}) == ("FFCDD7", "141414")
    # unnamed falls back to KONE Blue rather than to nothing
    assert L._field_for({"field": True}, {}) == L.BRAND_FIELDS[L.DEFAULT_FIELD]
    # an archetype that does not declare a field never takes one
    assert L._field_for({}, {"colour": "pink"}) is None
    for fill, ink in L.BRAND_FIELDS.values():
        assert ink in ("FFFFFF", "141414") and len(fill) == 6


def test_the_colour_field_replaces_the_engines_background_rather_than_hiding_under_it():
    """`render_archetype` opens by flooding the slide with the
    archetype's default fill. A field inserted at the bottom of the
    shape tree is covered by that sand, and only the ink survives --
    which is how a blue divider rendered as white type on sand."""
    import sys

    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Emu

    sys.path.insert(0, "/root/.claude/skills/kone-deck-generator")
    try:
        import kone_engine as engine
    except Exception:  # pragma: no cover
        pytest.skip("archetype engine not available")

    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    engine._rect(slide, [0, 0, 1280, 720], engine._hex("F3EEEA"))   # the engine's own
    L._paint_field(slide, engine, "1450F5")

    fills = [s for s in slide.shapes if s.name == "Colour field"]
    assert len(fills) == 1
    assert str(fills[0].fill.fore_color.rgb) == "1450F5"
    # and nothing full-slide is left painted over it
    assert len(L._full_slide_fills(slide, engine)) == 1

    # a shape that merely happens to be large is not mistaken for one
    slide.shapes.add_shape(MSO_SHAPE.OVAL, 0, 0, Emu(12192000), Emu(6858000))
    assert len(L._full_slide_fills(slide, engine)) == 1


def test_the_scrim_darkens_where_the_white_type_actually_sits():
    """A fixed dark-at-the-edges ramp guessed wrong on TEXT_PICTURE_G,
    whose headline starts 60% of the way down its banner -- exactly
    where a ramp clearing at the midpoint has recovered almost nothing.
    The bands come from the archetype's own reversed-out boxes."""
    spec = {"regions": [
        {"box": [45, 39, 917, 36], "content": "eyebrow",
         "dg": {"kind": "text", "color": "FFFFFF"}},
        {"box": [45, 262, 697, 125], "content": "title",
         "dg": {"kind": "text", "color": "FFFFFF"}},
        {"box": [45, 470, 1190, 40], "content": "body",     # below the banner
         "dg": {"kind": "text", "color": "141414"}},
    ]}
    content = {"eyebrow": "WHAT TENANTS EXPECT", "title": "Six expectations", "body": "x"}
    bands = L._reversed_bands(spec, content, [0, 0, 1280, 440])
    assert bands == [(39, 75), (262, 387)]

    stops = dict(L._scrim_ramp([0, 0, 1280, 440], bands, 78))
    # the headline band is fully protected, the middle of the picture is not
    assert stops[65000] == 78 and stops[80000] == 78
    # and clears completely between the eyebrow and the headline
    assert max(stops[pos] for pos in (30000, 35000, 40000, 45000)) == 0

    # an empty block is not protected: nothing is written there
    assert L._reversed_bands(spec, {"title": "Six expectations"}, [0, 0, 1280, 440]) \
        == [(262, 387)]


def test_the_cut_cover_banner_crops_its_photograph_instead_of_stretching_it():
    """`add_picture` given both a width and a height scales each axis
    independently. Every photo in the set is between 1.3 and 1.9 wide and
    the banner is 2.25, so the cover came out squashed by half again."""
    import sys

    from pptx import Presentation
    from pptx.util import Emu

    sys.path.insert(0, "/root/.claude/skills/kone-deck-generator")
    try:
        import kone_engine as engine
    except Exception:  # pragma: no cover
        pytest.skip("archetype engine not available")

    from deckguard import photos

    tall = next((p for p in photos.load_photos().values()
                 if photos.crop_severity(p, 950 / 422) > 0.1), None)
    if tall is None:  # pragma: no cover
        pytest.skip("no photo narrower than the banner")

    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    picture = photos.place_cover(slide, engine, (330, 0, 950, 422), tall.path)

    assert (picture.width, picture.height) == (engine.X(950), engine.X(422))
    # narrower than the slot, so a centre BAND is kept and nothing is
    # taken off the sides
    assert picture.crop_top > 0 and picture.crop_top == pytest.approx(picture.crop_bottom)
    assert picture.crop_left == 0 and picture.crop_right == 0

    kept = (1 - picture.crop_top - picture.crop_bottom)
    from PIL import Image
    with Image.open(str(tall.path)) as image:
        width, height = image.size
    assert (width / (height * kept)) == pytest.approx(950 / 422, rel=1e-3)


def test_the_slot_shape_breaks_ties_between_equally_matching_photos():
    """The cut-cover banner is 2.25:1 and the set holds photographs at
    exactly that ratio. Handing it a 3:2 portrait threw away a third of
    the frame while one that fitted sat unused."""
    from deckguard import photos

    wide = photos.choose("elevator women people", slot_aspect=950 / 422)
    assert wide is not None
    assert photos.crop_severity(wide, 950 / 422) < 0.15

    # the subject still outranks the shape: a query with no aspect given
    # is unchanged by the new argument
    assert photos.choose("skyline city") == photos.choose("skyline city", slot_aspect=None)


def test_a_picture_carrying_white_type_gets_a_scrim_nobody_declared():
    """`LAYOUTS.md` marks the type white and leaves the protection to
    the designer, so the derived archetypes shipped without any -- the
    full-bleed cover put a white headline onto a sunlit treeline."""
    regions = [
        {"role": "picture", "box": [0, 0, 1280, 720], "content": "photo"},
        {"role": "title_light", "box": [45, 136, 578, 448], "content": "title"},
    ]
    assert L._implied_scrims(regions) == [
        {"box": [0, 0, 1280, 720], "content": "photo"}]

    # gallery ports carry the ink in the role name instead
    assert L._is_light_role("gal_i64_FFFFFF") and L._is_light_role("title_light")
    assert not L._is_light_role("gal_i19_141414")

    # black type over a picture needs no protection, and neither does a
    # white block that misses the picture entirely
    assert L._implied_scrims([
        regions[0], {"role": "body", "box": [45, 136, 578, 40], "content": "body"}]) == []
    assert L._implied_scrims([
        {"role": "picture", "box": [0, 0, 640, 300], "content": "photo"},
        {"role": "title_light", "box": [700, 400, 400, 60], "content": "title"}]) == []


def test_the_scrim_protects_the_type_not_the_frame_it_was_given():
    """The full-bleed cover's title frame is 448px tall for three lines
    of type. Protecting the frame darkened the picture end to end and
    the cover came back a uniform grey."""
    region = {"role": "gal_i64_FFFFFF", "box": [45, 136, 578, 448], "content": "title"}
    height = L._typeset_height(region, "The lift is the last thing you decarbonise")
    assert 150 < height < 300, height
    assert height < region["box"][3]

    # a long enough string still fills the frame and never overruns it
    assert L._typeset_height(region, "word " * 400) == region["box"][3]


def test_the_scrim_sits_above_the_photograph_and_below_the_type():
    """A cover carries its logo and tagline as pictures too, and they
    are added after the type. Seating the scrim above the LAST picture
    put it over the headline and dimmed the words it exists to make
    readable."""
    import sys

    from pptx import Presentation
    from pptx.util import Emu

    sys.path.insert(0, "/root/.claude/skills/kone-deck-generator")
    try:
        import kone_engine as engine
    except Exception:  # pragma: no cover
        pytest.skip("archetype engine not available")

    from deckguard import photos

    any_photo = next(iter(photos.load_photos().values()), None)
    if any_photo is None:  # pragma: no cover
        pytest.skip("no photographs installed")

    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_picture(str(any_photo.path), 0, 0,
                             Emu(1280 * 9525), Emu(720 * 9525))          # the photograph
    slide.shapes.add_textbox(0, Emu(136 * 9525), Emu(578 * 9525), Emu(200 * 9525))
    slide.shapes.add_picture(str(any_photo.path), Emu(1102 * 9525), Emu(633 * 9525),
                             Emu(133 * 9525), Emu(45 * 9525))            # the tagline

    L._draw_scrim(slide, engine, [0, 0, 1280, 720], protect=[(136, 300)])
    order = [s.shape_type for s in slide.shapes]
    names = [s.name for s in slide.shapes]
    assert names.index("Photo protection") == 1, order
    assert names.index("Photo protection") < names.index("TextBox 2")


def test_the_engines_caption_grey_is_corrected_to_black_at_install():
    """The brand allows three inks for type -- black, white and, for
    KONE Information only, blue. The engine sets captions, muted body
    and quote attributions in a #727272 that is in no palette, and it
    shows on any deck carrying a quote or a captioned statistic."""
    import sys

    sys.path.insert(0, "/root/.claude/skills/kone-deck-generator")
    try:
        import archetypes as module
        import kone_engine as engine
    except Exception:  # pragma: no cover
        pytest.skip("archetype engine not available")

    # restore the engine's shipped greys first: another test in the
    # session may already have installed and corrected them
    greyed = {}
    for role in ("caption", "body_muted", "attribution"):
        style = engine.ROLE_STYLE[role]
        greyed[role] = style
        engine.ROLE_STYLE[role] = tuple(
            engine.GREY if i == 2 else v for i, v in enumerate(style))

    corrected = L._correct_grey_ink(module)
    assert {"caption", "body_muted", "attribution"} <= set(corrected)
    for role in corrected:
        assert engine.ROLE_STYLE[role][2] == engine.BLACK
    # and nothing anywhere is left painting type in the caption grey
    assert not [r for r, s in engine.ROLE_STYLE.items()
                if len(s) > 2 and s[2] == engine.GREY]
    # idempotent: a second pass finds nothing left to correct
    assert L._correct_grey_ink(module) == []
    # everything else about the role is untouched -- font, size, caps
    for role, before in greyed.items():
        after = engine.ROLE_STYLE[role]
        assert [v for i, v in enumerate(after) if i != 2] \
            == [v for i, v in enumerate(before) if i != 2]


def _skill_modules():
    import sys

    sys.path.insert(0, "/root/.claude/skills/kone-deck-generator")
    try:
        import archetypes
        import kone_engine  # noqa: F401
    except Exception:  # pragma: no cover
        pytest.skip("archetype engine not available")
    from deckguard import gallery

    L.install(archetypes)
    gallery.install(archetypes)
    return archetypes


def test_a_deck_built_from_a_brief_puts_each_archetype_on_its_own_layout(tmp_path):
    """The skill's own `build_deck` puts every archetype on BLANK and
    calls `archetypes.render` directly, which bypasses this module
    entirely. The first deck a user built through the web tool came back
    with the engine's rasterised PNGs and blue placeholder chips instead
    of KONE pictograms, and no scrim on the cover."""
    archetypes = _skill_modules()
    out = tmp_path / "brief.pptx"

    L.build_deck({"title": "Service review", "slides": [
        {"archetype": "icon_columns_5", "title": "What we need", "items": [
            {"icon": "clock", "text": "Confirm the forecast"},
            {"icon": "people", "text": "Name an owner"},
            {"icon": "wrench", "text": "Apply the pricing"},
        ]},
    ]}, str(out), archetypes)

    from pptx import Presentation

    prs = Presentation(str(out))
    assert len(prs.slides._sldIdLst) == 3      # master cover, body, master outro

    body = prs.slides[1]
    kinds = [str(s.shape_type).split(" ")[0] for s in body.shapes]
    # native editable pictograms, not rasters and not the engine's chips
    assert kinds.count("FREEFORM") >= 3
    assert "PICTURE" not in kinds
    assert not [s for s in body.shapes if "Rounded Rectangle" in s.name]


def test_the_retained_master_cover_gets_the_scrim_the_master_never_had(tmp_path):
    """Cover F reverses its title out of a full-bleed photograph and
    ships no gradient -- the layout assumes a designer picks a
    photograph with a quiet corner. A deck built from a brief picks one
    automatically, and a half-year review came back with a white
    headline lost in a sunlit atrium."""
    archetypes = _skill_modules()
    out = tmp_path / "cover.pptx"
    L.build_deck({"title": "Service business review — first half of the year",
                  "slides": []}, str(out), archetypes)

    from pptx import Presentation

    cover = Presentation(str(out)).slides[0]
    names = [s.name for s in cover.shapes]
    assert "Photo protection" in names
    # directly above the photograph and below every piece of type
    assert names.index("Photo protection") == 1
    title = next(i for i, s in enumerate(cover.shapes)
                 if getattr(s, "has_text_frame", False) and "Service business" in s.text_frame.text)
    assert names.index("Photo protection") < title


def test_a_chart_slot_nobody_filled_is_dropped_not_invented(tmp_path):
    """The engine keeps sample artwork and stamps it onto every slide of
    certain archetypes whether or not anyone asked. `segment_breakdown`
    gets a donut reading 53% against satisfaction bands -- invented data
    in the company's own chart styling, and it went out in a business
    review."""
    archetypes = _skill_modules()
    assert "chart" in archetypes.FIGURES["segment_breakdown"], "guard is about this map"

    region = {"content": "chart", "role": "figure"}
    assert L._is_unsupplied_figure(region, {}, "segment_breakdown", archetypes)
    # supplied by the author, it is theirs and must be drawn
    assert not L._is_unsupplied_figure(
        region, {"chart": "/tmp/mine.png"}, "segment_breakdown", archetypes)
    # a slot that is not a figure is never touched by this rule
    assert not L._is_unsupplied_figure(
        {"content": "title"}, {}, "segment_breakdown", archetypes)

    out = tmp_path / "nochart.pptx"
    L.build_deck({"title": "Review", "slides": [
        {"archetype": "segment_breakdown", "title": "Where we stand",
         "highlight_value": "88%", "highlight_caption": "first-time fix"},
    ]}, str(out), archetypes)

    from pptx import Presentation

    body = Presentation(str(out)).slides[1]
    assert not [s for s in body.shapes if str(s.shape_type).startswith("PICTURE")]
    assert any("88%" in s.text_frame.text
               for s in body.shapes if getattr(s, "has_text_frame", False))


def test_build_deck_takes_the_registry_from_the_loader_not_a_bare_import(tmp_path):
    """`gallery.install` OVERWRITES what it finds; `layouts.install`
    defers to it except for a short override list. So the gallery has to
    be installed first and this module second, and only
    `skill_bridge._load_archetypes` guarantees that order.

    Getting it backwards is silent and expensive: the refined agenda
    reverted to a port with no bullets, and the divider to one with no
    number and no colour field. Both looked like rendering bugs."""
    _skill_modules()
    from deckguard.skill_bridge import _load_archetypes

    registry = _load_archetypes().ARCHETYPES

    agenda = registry["agenda_a_table"]
    assert [r.get("content") for r in agenda["regions"]] == [
        "photo", "eyebrow", "title", "items"]
    assert any(r.get("role") == "dg_bullets" for r in agenda["regions"])

    divider = registry["divider_numbering"]
    assert divider.get("field") is True
    assert {r.get("content") for r in divider["regions"]} == {"number", "eyebrow", "title"}
    # the number sits left of the title, as five real KONE slides do
    boxes = {r["content"]: r["box"] for r in divider["regions"]}
    assert boxes["number"][0] < boxes["title"][0]

    # and a deck built without naming a module picks up exactly that
    out = tmp_path / "ordered.pptx"
    L.build_deck({"title": "T", "slides": [
        {"archetype": "divider_numbering", "number": "2", "eyebrow": "Section 02",
         "title": "What's working", "colour": "light-blue"},
    ]}, str(out))

    from pptx import Presentation

    body = Presentation(str(out)).slides[1]
    field = next(s for s in body.shapes if s.name == "Colour field")
    assert str(field.fill.fore_color.rgb) == "D2F5FF"
    assert any("2" == s.text_frame.text.strip()
               for s in body.shapes if getattr(s, "has_text_frame", False))


def test_the_planner_is_told_the_keys_the_renderer_actually_reads():
    """`catalog.json` describes 22 of 80 archetypes and `SAMPLES` 41, so
    most were named and nothing more. The keys come off the live
    registry instead, and cannot drift from it."""
    _skill_modules()
    from deckguard.skill_bridge import _derived_content_keys, _load_archetypes

    registry = _load_archetypes().ARCHETYPES
    described = [n for n in registry if _derived_content_keys(n)]
    assert len(described) >= len(registry) - 2, "nearly every archetype must describe itself"

    agenda = dict(k.split(" (")[0:1] + [k] for k in
                  L.content_keys(registry["agenda_a_table"]))
    assert set(agenda) == {"photo", "eyebrow", "title", "items"}
    assert "list of strings" in agenda["items"]
    assert "do not supply" in agenda["photo"]

    # a repeating group states its capacity and its per-item fields,
    # including the icon, which carries no content key of its own
    (items,) = [k for k in L.content_keys(registry["text_picture_g"])
                if k.startswith("items ")]
    assert "up to 6" in items and "icon" in items and "text" in items


def test_a_worked_example_that_no_longer_matches_is_not_shown():
    """The model follows a concrete example over an abstract slot list.
    `agenda_a_table`'s advertised `text1..text4` long after the renderer
    was rebuilt to read `items` -- so a planner emitted four keys nothing
    reads and the agenda came back as a title on an empty half."""
    _skill_modules()
    from deckguard.skill_bridge import _kone_archetype_guide, _load_archetypes, _sample_agrees

    archetypes = _load_archetypes()
    stale = {"title": "x", "text1": "a", "text2": "b"}
    assert not _sample_agrees("agenda_a_table", stale)
    assert _sample_agrees("agenda_a_table", {"title": "x", "items": ["a"]})
    # an archetype we cannot describe keeps its example rather than losing both
    assert _sample_agrees("nothing_we_know_about", {"anything": 1})

    guide = _kone_archetype_guide()
    section = guide[guide.index("### agenda_a_table"):]
    section = section[:section.index("\n\n")]
    assert "Content keys (authoritative" in section
    assert "text1" not in section
    assert archetypes.SAMPLES["agenda_a_table"].get("text1"), "guard is about this sample"


def test_content_the_archetype_cannot_hold_is_reported_rather_than_dropped(tmp_path):
    """Silent loss is the failure this catches. The deck came back with
    less in it than the brief had, and nothing said so -- not the build,
    not the review page, not the audit."""
    archetypes = _skill_modules()
    agenda = archetypes.ARCHETYPES["agenda_a_table"]

    assert L.unread_keys(agenda, {"title": "x", "text1": "a", "text2": "b"}) == ["text1", "text2"]
    assert L.unread_keys(agenda, {"title": "x", "items": ["a"]}) == []
    # an empty field was never content, and `colour` is read by the
    # renderer rather than by the archetype's regions
    assert L.unread_keys(agenda, {"title": "x", "text1": "", "colour": "blue"}) == []

    report: dict = {}
    L.build_deck({"title": "T", "slides": [
        {"archetype": "agenda_a_table", "title": "Agenda",
         "text1": "one", "text2": "two"},
    ]}, str(tmp_path / "d.pptx"), archetypes, report=report)
    assert report["dropped"] == {1: ("agenda_a_table", ["text1", "text2"])}
