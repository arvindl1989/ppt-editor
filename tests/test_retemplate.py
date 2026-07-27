"""Tests for deckguard's content-preserving re-layout (retemplate):
classifying an old deck's slides, matching each to an org-template
layout, and rebuilding accepted slides on it while carrying over
title/body text and images.
"""

import io
import zipfile

import pytest
from lxml import etree
from pptx import Presentation
from pptx.enum.shapes import PROG_ID
from pptx.util import Inches

from deckguard.retemplate import (
    CONTENT_LAYOUT_CANDIDATES,
    LayoutProfile,
    SlideProfile,
    apply_rebrand,
    apply_retemplate,
    classify_slide,
    match_layout,
    propose_retemplate,
)
from deckguard.slide_import import default_template_path
from tests.helpers import add_picture, add_rectangle, add_slide, body_run, make_pattern_png, new_deck, title_run

TEMPLATE_PATH = default_template_path()
pytestmark = pytest.mark.skipif(not TEMPLATE_PATH.exists(), reason="bundled template asset not present")


def _no_duplicate_zip_entries(path) -> bool:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    return len(names) == len(set(names))


def _no_malformed_xml(path) -> list:
    bad = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith((".xml", ".rels")):
                try:
                    etree.fromstring(z.read(name))
                except Exception as exc:  # noqa: BLE001
                    bad.append((name, str(exc)))
    return bad


# --------------------------------------------------------------------------
# classify_slide
# --------------------------------------------------------------------------


def test_classify_slide_extracts_title_and_body_text():
    prs = new_deck()
    slide = add_slide(prs)
    title_run(slide).text = "My Title"
    body_run(slide).text = "First line"

    profile = classify_slide(slide)

    assert profile.eligible
    assert profile.title == "My Title"
    assert profile.text_blocks == [[(0, "First line")]]
    assert profile.images == []


def test_classify_slide_extracts_images(tmp_path):
    prs = new_deck()
    slide = add_slide(prs, layout_idx=6)
    img_path = make_pattern_png(tmp_path / "img.png", seed=1)
    add_picture(slide, str(img_path))

    profile = classify_slide(slide)

    assert profile.eligible
    assert len(profile.images) == 1
    assert profile.images[0] == img_path.read_bytes()


def test_classify_slide_ignores_small_footer_text_near_slide_edge():
    """A "Confidential | (c) KONE Corporation"-style footer must not be
    treated as real body content -- it isn't something a human wants
    migrated, and would otherwise crowd out real content against the
    max-text-blocks cap and pollute the preview text."""
    prs = new_deck()
    slide = add_slide(prs, layout_idx=6)
    footer = slide.shapes.add_textbox(Inches(0.3), Inches(7.0), Inches(4), Inches(0.3))
    footer.text_frame.text = "Confidential | © KONE Corporation"

    profile = classify_slide(slide, slide_height_in=7.5)

    assert profile.text_blocks == []
    assert not profile.eligible
    assert profile.reason == "no title, text, or images to migrate"


def test_classify_slide_keeps_a_similarly_small_textbox_away_from_the_edge():
    prs = new_deck()
    slide = add_slide(prs, layout_idx=6)
    box = slide.shapes.add_textbox(Inches(1), Inches(3), Inches(3), Inches(0.4))
    box.text_frame.text = "Real short content"

    profile = classify_slide(slide, slide_height_in=7.5)

    assert profile.eligible
    assert profile.text_blocks == [[(0, "Real short content")]]


@pytest.mark.parametrize(
    "build,expected_reason",
    [
        (lambda slide: slide.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(3), Inches(2)), "contains a table"),
        (lambda slide: slide.shapes.add_group_shape(), "contains a group"),
        (
            lambda slide: slide.shapes.add_ole_object(
                io.BytesIO(b"fake xlsx bytes"), PROG_ID.XLSX, Inches(1), Inches(1)
            ),
            "contains an embedded OLE object",
        ),
    ],
)
def test_classify_slide_disqualifies_unsafe_shape_types(build, expected_reason):
    prs = new_deck()
    slide = add_slide(prs, layout_idx=6)
    build(slide)

    profile = classify_slide(slide)

    assert not profile.eligible
    assert profile.reason == expected_reason


def test_classify_slide_disqualifies_too_many_decorative_shapes():
    prs = new_deck()
    slide = add_slide(prs, layout_idx=6)
    for i in range(6):
        add_rectangle(slide, left_in=i, top_in=0, width_in=0.5, height_in=0.5)

    profile = classify_slide(slide)

    assert not profile.eligible
    assert profile.reason == "too many free-form shapes to safely reflow"


def test_classify_slide_disqualifies_more_text_blocks_than_any_layout_holds():
    prs = new_deck()
    slide = add_slide(prs, layout_idx=6)
    for i in range(5):
        box = slide.shapes.add_textbox(Inches(1), Inches(1 + i), Inches(3), Inches(0.5))
        box.text_frame.text = f"Block {i}"

    profile = classify_slide(slide)

    assert not profile.eligible
    assert profile.reason == "more body text blocks than any template layout can hold"


def test_classify_slide_empty_slide_is_ineligible():
    prs = new_deck()
    slide = add_slide(prs, layout_idx=6)

    profile = classify_slide(slide)

    assert not profile.eligible
    assert profile.reason == "no title, text, or images to migrate"


# --------------------------------------------------------------------------
# match_layout
# --------------------------------------------------------------------------


def test_match_layout_picks_the_tightest_fitting_candidate():
    profiles = [
        LayoutProfile(name="Loose", has_title=True, n_body=3, n_picture=2),
        LayoutProfile(name="Tight", has_title=True, n_body=1, n_picture=0),
        LayoutProfile(name="TooSmall", has_title=True, n_body=0, n_picture=0),
    ]
    profile = SlideProfile(title="T", text_blocks=[[(0, "x")]], images=[], eligible=True)

    match = match_layout(profile, profiles)

    assert match is not None
    assert match.layout_name == "Tight"


def test_match_layout_requires_a_title_placeholder_when_slide_has_a_title():
    profiles = [LayoutProfile(name="NoTitle", has_title=False, n_body=5, n_picture=5)]
    profile = SlideProfile(title="T", text_blocks=[], images=[], eligible=True)

    assert match_layout(profile, profiles) is None


def test_match_layout_returns_none_when_nothing_fits():
    profiles = [LayoutProfile(name="Small", has_title=True, n_body=1, n_picture=0)]
    profile = SlideProfile(title="T", text_blocks=[[(0, "a")], [(0, "b")], [(0, "c")]], images=[], eligible=True)

    assert match_layout(profile, profiles) is None


def test_match_layout_usage_counts_only_break_ties_never_override_a_better_fit():
    """usage_counts is an anti-repeat tie-break for apply_rebrand's layout
    variety, not a second scoring signal that can outrank actual fit: a
    heavily-reused Tight layout must still beat a fresh, but wasteful,
    Loose one."""
    profiles = [
        LayoutProfile(name="Loose", has_title=True, n_body=3, n_picture=2),
        LayoutProfile(name="Tight", has_title=True, n_body=1, n_picture=0),
    ]
    profile = SlideProfile(title="T", text_blocks=[[(0, "x")]], images=[], eligible=True)

    match = match_layout(profile, profiles, usage_counts={"Tight": 10, "Loose": 0})

    assert match.layout_name == "Tight"


def test_match_layout_usage_counts_break_ties_among_equally_good_fits():
    profiles = [
        LayoutProfile(name="A", has_title=True, n_body=1, n_picture=0),
        LayoutProfile(name="B", has_title=True, n_body=1, n_picture=0),
    ]
    profile = SlideProfile(title="T", text_blocks=[[(0, "x")]], images=[], eligible=True)

    match_no_usage = match_layout(profile, profiles)
    assert match_no_usage.layout_name == "A"  # ties resolve by candidate-list order, unchanged from before

    match_with_usage = match_layout(profile, profiles, usage_counts={"A": 3, "B": 0})
    assert match_with_usage.layout_name == "B"  # least-used wins the tie


def test_candidate_layouts_all_exist_in_the_bundled_template():
    tmpl_prs = Presentation(str(TEMPLATE_PATH))
    names = {layout.name for master in tmpl_prs.slide_masters for layout in master.slide_layouts}
    missing = [n for n in CONTENT_LAYOUT_CANDIDATES if n not in names]
    assert missing == []


# --------------------------------------------------------------------------
# propose_retemplate / apply_retemplate (end to end)
# --------------------------------------------------------------------------


def _simple_deck(tmp_path):
    prs = new_deck()
    slide1 = add_slide(prs)
    title_run(slide1).text = "First Slide"
    body_run(slide1).text = "Some content"

    slide2 = add_slide(prs)
    title_run(slide2).text = "Second Slide"
    body_run(slide2).text = "More content"

    slide3 = add_slide(prs, layout_idx=6)  # ineligible: has a table
    slide3.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(3), Inches(2))

    path = tmp_path / "src.pptx"
    prs.save(str(path))
    return path


def test_propose_retemplate_classifies_every_slide(tmp_path):
    path = _simple_deck(tmp_path)
    prs = Presentation(str(path))

    proposals = propose_retemplate(prs, template_path=TEMPLATE_PATH)

    assert [p.slide_index for p in proposals] == [1, 2, 3]
    assert proposals[0].eligible and proposals[0].layout_name
    assert proposals[1].eligible and proposals[1].layout_name
    assert not proposals[2].eligible
    assert proposals[2].reason == "contains a table"


def test_apply_retemplate_defaults_to_every_eligible_slide(tmp_path):
    path = _simple_deck(tmp_path)
    out_path = tmp_path / "out.pptx"

    result = apply_retemplate(str(path), str(out_path), template_path=TEMPLATE_PATH)

    assert result.transformed == [1, 2]
    assert result.skipped == [3]
    assert _no_duplicate_zip_entries(out_path)
    assert _no_malformed_xml(out_path) == []

    prs = Presentation(str(out_path))
    assert len(prs.slides) == 3
    assert prs.slides[0].shapes.title.text_frame.text == "First Slide"
    assert prs.slides[1].shapes.title.text_frame.text == "Second Slide"
    assert any(s.shape_type is not None and s.shape_type.name == "TABLE" for s in prs.slides[2].shapes)  # slide 3 untouched


def test_apply_retemplate_honors_accepted_indexes_subset(tmp_path):
    path = _simple_deck(tmp_path)
    out_path = tmp_path / "out.pptx"

    result = apply_retemplate(str(path), str(out_path), accepted_indexes={1}, template_path=TEMPLATE_PATH)

    assert result.transformed == [1]
    assert result.skipped == [2, 3]

    prs = Presentation(str(out_path))
    assert prs.slides[0].shapes.title.text_frame.text == "First Slide"
    assert prs.slides[1].shapes.title.text_frame.text == "Second Slide"  # untouched original, not rebuilt


def test_apply_retemplate_is_a_no_op_when_nothing_is_eligible(tmp_path):
    prs = new_deck()
    slide = add_slide(prs, layout_idx=6)
    slide.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(3), Inches(2))
    path = tmp_path / "src.pptx"
    prs.save(str(path))
    out_path = tmp_path / "out.pptx"

    result = apply_retemplate(str(path), str(out_path), template_path=TEMPLATE_PATH)

    assert result.transformed == []
    assert result.skipped == [1]
    reopened = Presentation(str(out_path))
    assert any(s.shape_type is not None and s.shape_type.name == "TABLE" for s in reopened.slides[0].shapes)


def test_apply_retemplate_replacing_three_or_more_slides_does_not_collide_partnames(tmp_path):
    """Regression test for a real bug: python-pptx's own add_slide()
    computes each new slide's partname as just "current slide count + 1"
    (not a scan for a free name -- see PresentationPart._next_slide_partname).
    Interleaving a delete between two add_slide() calls shrinks that count
    and can make a LATER add_slide() reuse a partname a PRIOR new slide
    from the same run is still using, silently merging two slides onto one
    XML part (a real zipfile "Duplicate name" corruption on save, not just
    clutter). Needs >= 3 replaced slides to actually exercise the shrink/
    reuse cycle a single replacement can't trigger."""
    import warnings

    prs = new_deck()
    titles = ["Alpha", "Bravo", "Charlie", "Delta"]
    for t in titles:
        slide = add_slide(prs)
        title_run(slide).text = t
        body_run(slide).text = f"{t} body"
    path = tmp_path / "src.pptx"
    prs.save(str(path))
    out_path = tmp_path / "out.pptx"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = apply_retemplate(str(path), str(out_path), template_path=TEMPLATE_PATH)
        dupes = [str(w.message) for w in caught if "Duplicate name" in str(w.message)]

    assert dupes == []
    assert result.transformed == [1, 2, 3, 4]
    assert _no_duplicate_zip_entries(out_path)
    assert _no_malformed_xml(out_path) == []

    prs2 = Presentation(str(out_path))
    assert len(prs2.slides) == 4
    assert [s.shapes.title.text_frame.text for s in prs2.slides] == titles


def test_apply_retemplate_carries_images_into_the_new_layouts_picture_placeholder(tmp_path):
    prs = new_deck()
    slide = add_slide(prs, layout_idx=6)
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(8), Inches(0.8))
    title_box.text_frame.text = "irrelevant"  # not a real TITLE placeholder -- just body-like text
    img_path = make_pattern_png(tmp_path / "img.png", seed=2)
    add_picture(slide, str(img_path), left_in=1, top_in=2)
    path = tmp_path / "src.pptx"
    prs.save(str(path))
    out_path = tmp_path / "out.pptx"

    result = apply_retemplate(str(path), str(out_path), template_path=TEMPLATE_PATH)

    assert result.transformed == [1]
    prs2 = Presentation(str(out_path))
    # A filled picture placeholder reports shape_type PLACEHOLDER, not
    # PICTURE (python-pptx's PlaceholderPicture) -- check by trying to
    # read an image blob from every shape rather than filtering by type.
    blobs = []
    for s in prs2.slides[0].shapes:
        try:
            blobs.append(s.image.blob)
        except (AttributeError, ValueError):
            continue
    assert img_path.read_bytes() in blobs


# --------------------------------------------------------------------------
# apply_rebrand -- verbatim carryover + layout variety + cover/end swap
# --------------------------------------------------------------------------


def _cover_content_end_deck(tmp_path):
    prs = new_deck()
    cover = add_slide(prs)
    title_run(cover).text = "Annual Review"

    content1 = add_slide(prs)
    title_run(content1).text = "Highlights"
    body_run(content1).text = "Grew nicely"

    content2 = add_slide(prs)
    title_run(content2).text = "Next Steps"
    body_run(content2).text = "Keep going"

    end = add_slide(prs)
    title_run(end).text = "Thank You"

    path = tmp_path / "src.pptx"
    prs.save(str(path))
    return path


def test_apply_rebrand_swaps_cover_and_end_slides_onto_current_brand_layout(tmp_path):
    path = _cover_content_end_deck(tmp_path)
    out_path = tmp_path / "out.pptx"

    result = apply_rebrand(str(path), str(out_path), template_path=TEMPLATE_PATH)

    assert result.transformed == [1, 2, 3, 4]
    by_index = {p.slide_index: p for p in result.proposals}
    assert by_index[1].layout_name == "Cover B"
    assert by_index[4].layout_name == "Outro"

    prs2 = Presentation(str(out_path))
    texts = [s.shapes.title.text_frame.text for s in prs2.slides]
    assert texts == ["Annual Review", "Highlights", "Next Steps", "Thank You"]


def test_apply_rebrand_never_changes_wording(tmp_path):
    """The whole point of brand mode: title/body text survives character
    for character -- no condensing, no rewording, regardless of what
    match_layout or the cover/end override picks."""
    path = _cover_content_end_deck(tmp_path)
    out_path = tmp_path / "out.pptx"

    apply_rebrand(str(path), str(out_path), template_path=TEMPLATE_PATH)

    prs2 = Presentation(str(out_path))
    body_texts = {
        shp.text_frame.text for slide in prs2.slides for shp in slide.shapes
        if shp.has_text_frame and shp.text_frame.text.strip()
    }
    assert "Grew nicely" in body_texts
    assert "Keep going" in body_texts


def test_apply_rebrand_picks_varied_layouts_instead_of_repeating_one(tmp_path):
    """Several ordinary content slides, identically shaped (title + one
    body block, no images) -- without anti-repeat scoring they'd all pick
    the same single tightest-fitting layout; with it, match_layout should
    spread them across the tied candidates instead."""
    prs = new_deck()
    for i in range(4):
        slide = add_slide(prs)
        title_run(slide).text = f"Slide {i}"
        body_run(slide).text = f"Body {i}"
    path = tmp_path / "src.pptx"
    prs.save(str(path))
    out_path = tmp_path / "out.pptx"

    result = apply_rebrand(str(path), str(out_path), template_path=TEMPLATE_PATH)

    layouts_used = [p.layout_name for p in result.proposals if p.eligible]
    assert len(set(layouts_used)) > 1


def test_apply_rebrand_still_hard_skips_a_table_and_leaves_it_untouched(tmp_path):
    prs = new_deck()
    cover = add_slide(prs)
    title_run(cover).text = "Deck"
    table_slide = add_slide(prs)
    table_slide.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(3), Inches(2))
    path = tmp_path / "src.pptx"
    prs.save(str(path))
    out_path = tmp_path / "out.pptx"

    result = apply_rebrand(str(path), str(out_path), template_path=TEMPLATE_PATH)

    assert result.skipped == [2]
    proposal = next(p for p in result.proposals if p.slide_index == 2)
    assert proposal.reason == "contains a table"


def test_apply_rebrand_runs_fix_deck_for_color_and_font_compliance(tmp_path):
    """Brand mode's whole promise is 'follow the color/font guidelines' --
    `apply_retemplate` alone never runs `fix_deck`, so a rebuilt slide's
    freshly-written text (no explicit run color, by design -- see
    compose.py's own module docstring) is left as an inherited, therefore
    audit-unresolvable color. `apply_rebrand` finishes that off, the same
    way `deckguard fix` would."""
    from deckguard.config import default_config_path, load_config
    from deckguard.inventory import build_inventory
    from deckguard.rules_engine import audit_deck

    path = _cover_content_end_deck(tmp_path)
    retemplate_only = tmp_path / "retemplate_only.pptx"
    apply_retemplate(str(path), str(retemplate_only), template_path=TEMPLATE_PATH)
    rebrand_out = tmp_path / "rebrand.pptx"
    apply_rebrand(str(path), str(rebrand_out), template_path=TEMPLATE_PATH)

    config = load_config(default_config_path())
    retemplate_contrast = [
        v for v in audit_deck(build_inventory(Presentation(str(retemplate_only))), config) if v.rule == "text_contrast"
    ]
    rebrand_contrast = [
        v for v in audit_deck(build_inventory(Presentation(str(rebrand_out))), config) if v.rule == "text_contrast"
    ]

    assert retemplate_contrast  # confirms the premise: retemplate alone leaves this unresolved
    assert not rebrand_contrast  # apply_rebrand's fix_deck pass resolves it
