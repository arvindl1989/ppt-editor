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
    alphas = [int(a.get("val")) for a in grad.iter(f"{{{A}}}alpha")]
    assert alphas[0] > 0 and alphas[1] == 0 and alphas[2] > 0
