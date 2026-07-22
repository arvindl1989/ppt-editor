import hashlib

from pptx import Presentation
from pptx.enum.text import PP_ALIGN

from deckguard.config import load_config, default_config_path
from deckguard.fixer import fix_deck
from deckguard.inventory import build_inventory
from deckguard.rules_engine import audit_deck
from tests.helpers import (
    add_rectangle,
    add_shadow_effect,
    add_slide,
    body_run,
    new_deck,
    set_run,
    set_theme_font,
    set_theme_slot,
    title_run,
)
from pptx.oxml.ns import qn

CONFIG = load_config(default_config_path())


def _violating_deck():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(title_run(slide), text="Title", font="Calibri", color_hex="005EB8")
    run = set_run(body_run(slide), text="body copy", font="Inter", color_hex="141414")
    add_shadow_effect(run)
    slide.placeholders[1].text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    set_theme_slot(prs, "accent1", "005EB8")
    set_theme_font(prs, "majorFont", "Calibri")
    set_theme_font(prs, "minorFont", "Calibri")
    return prs


def test_fix_applies_changes_and_reduces_violations(tmp_path):
    prs = _violating_deck()
    before_count = len(audit_deck(build_inventory(prs), CONFIG))

    out_path = tmp_path / "out.pptx"
    report = fix_deck(prs, CONFIG, source_path="in.pptx", output_path=str(out_path), dry_run=False)

    assert len(report.changes) > 0
    assert out_path.exists()

    saved = Presentation(str(out_path))
    after_count = len(audit_deck(build_inventory(saved), CONFIG))
    assert after_count < before_count


def test_fix_dry_run_writes_no_output_file(tmp_path):
    prs = _violating_deck()
    out_path = tmp_path / "out.pptx"

    report = fix_deck(prs, CONFIG, source_path="in.pptx", output_path=str(out_path), dry_run=True)

    assert report.dry_run is True
    assert report.output_path is None
    assert not out_path.exists()
    # dry-run still computes what *would* change, for the preview/changelog
    assert len(report.changes) > 0


def test_fix_never_touches_the_source_file(tmp_path):
    src_path = tmp_path / "source.pptx"
    _violating_deck().save(str(src_path))
    original_bytes = src_path.read_bytes()
    original_hash = hashlib.sha256(original_bytes).hexdigest()

    prs = Presentation(str(src_path))
    out_path = tmp_path / "fixed.pptx"
    fix_deck(prs, CONFIG, source_path=str(src_path), output_path=str(out_path), dry_run=False)

    assert src_path.read_bytes() == original_bytes
    assert hashlib.sha256(src_path.read_bytes()).hexdigest() == original_hash
    assert out_path.exists()
    assert out_path.read_bytes() != original_bytes


def test_fix_is_idempotent_on_a_clean_deck():
    prs = new_deck()
    # python-pptx's default template theme is itself legacy (black
    # dk1, Calibri major/minor font) — bring it up to brand first so this
    # test reflects a deck that's *already* on-brand, not the stock template.
    set_theme_slot(prs, "dk1", "141414")
    set_theme_font(prs, "majorFont", "Inter")
    set_theme_font(prs, "minorFont", "Inter")

    slide = add_slide(prs)
    set_run(title_run(slide), text="Title", font="Inter Semi Bold", color_hex="141414")
    set_run(body_run(slide), text="Body copy", font="Inter", color_hex="141414")
    slide.placeholders[1].text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT

    report = fix_deck(prs, CONFIG, source_path="clean.pptx", output_path=None, dry_run=True)
    # Nothing to fix except the (unfixable) slide-size mismatch and
    # non-KONE layout names inherent to the default python-pptx template.
    assert report.changes == []
    assert all(v.rule in ("slide_size", "non_standard_layout") for v in report.manual_review)


def test_fix_report_summary_counts_match():
    prs = _violating_deck()
    report = fix_deck(prs, CONFIG, source_path="in.pptx", output_path=None, dry_run=True)
    summary = report.summary
    assert summary["changes_applied"] == len(report.changes)
    assert summary["manual_review_required"] == len(report.manual_review)


def _panel_config(min_area_sq_in=8.0):
    """Minimal config isolating just the layout-panel-fill remap, so these
    tests aren't coupled to the real brand_rules.yaml's exact thresholds."""
    return {
        "colors": {
            "approved": ["#1450F5", "#EDEFF0"],
            "remap": {},
            "layout_panel_remap": {"#EDEFF0": "#1450F5"},
            "layout_panel_min_area_sq_in": min_area_sq_in,
        },
        "fonts": {"approved": ["Inter"], "remap": {}},
        "typography_rules": {},
        "logo": {},
        "layout": {},
        "audit": {"fail_on": []},
    }


def _add_rectangle_to_layout(layout, name, fill_hex, left_in, top_in, width_in, height_in):
    """python-pptx's LayoutShapes has no add_shape() -- layout shapes are
    normally inherited from a template, not built via the API. Build the
    rectangle on a scratch slide (where add_shape works) and move its XML
    element into the layout's shape tree instead."""
    from copy import deepcopy

    scratch = Presentation()
    scratch_slide = scratch.slides.add_slide(scratch.slide_layouts[6])
    shape = add_rectangle(
        scratch_slide, name=name, fill_hex=fill_hex,
        left_in=left_in, top_in=top_in, width_in=width_in, height_in=height_in,
    )
    elem = deepcopy(shape._element)
    layout.shapes._spTree.append(elem)
    return layout.shapes[-1]


def _fill_hex(shape):
    spPr = shape._element.find(qn("p:spPr"))
    solid_fill = spPr.find(qn("a:solidFill"))
    srgb = solid_fill.find(qn("a:srgbClr"))
    return srgb.get("val")


def test_fix_remaps_large_background_panel_defined_on_a_layout():
    """Regression test for a real bug: a shape's fill can live entirely on
    the slide LAYOUT it inherits from (e.g. a full-panel background behind
    a picture/content placeholder), never on any slide -- so ordinary
    slide-level color remap never sees or fixes it. This was the actual
    root cause behind a real deck's "grey box that should be blue" report:
    the legacy deck's layout still had the panel as the old gray, while
    the reference deck's equivalent layout had it corrected to KONE Blue."""
    prs = new_deck()
    layout = prs.slide_layouts[1]
    panel = _add_rectangle_to_layout(layout, "Big Panel", "EDEFF0", left_in=1, top_in=1, width_in=4, height_in=3)
    add_slide(prs, layout_idx=1)

    report = fix_deck(prs, _panel_config(), source_path="in.pptx", output_path=None, dry_run=True)

    assert _fill_hex(panel) == "1450F5"
    assert any(c.scope == "layout" and c.shape_name == "Big Panel" for c in report.changes)


def test_fix_leaves_small_layout_shapes_untouched():
    """The exact same literal color is legitimately reused on a layout for
    small accent/placeholder shapes (e.g. unselected tab backgrounds)
    whose color must stay static -- only large background panels should
    ever be treated as the "brand panel" and remapped."""
    prs = new_deck()
    layout = prs.slide_layouts[1]
    small = _add_rectangle_to_layout(layout, "Tab", "EDEFF0", left_in=1, top_in=1, width_in=1, height_in=0.5)
    add_slide(prs, layout_idx=1)

    fix_deck(prs, _panel_config(min_area_sq_in=8.0), source_path="in.pptx", output_path=None, dry_run=True)

    assert _fill_hex(small) == "EDEFF0"


def test_fix_layout_panel_remap_is_a_no_op_when_not_configured():
    prs = new_deck()
    layout = prs.slide_layouts[1]
    panel = _add_rectangle_to_layout(layout, "Big Panel", "EDEFF0", left_in=1, top_in=1, width_in=4, height_in=3)
    add_slide(prs, layout_idx=1)

    config = _panel_config()
    config["colors"]["layout_panel_remap"] = {}

    fix_deck(prs, config, source_path="in.pptx", output_path=None, dry_run=True)

    assert _fill_hex(panel) == "EDEFF0"


def test_fix_corrects_text_color_for_legibility_on_kone_blue():
    """End-to-end: fix_deck must rewrite black-on-blue text to white, not
    leave it for manual review -- this is auto-fixable by construction."""
    prs = new_deck()
    slide = add_slide(prs)
    box = add_rectangle(slide, name="Blue panel", fill_hex="1450F5", left_in=1, top_in=1, width_in=3, height_in=1)
    box.text_frame.text = "Label"
    run = box.text_frame.paragraphs[0].runs[0]
    run.font.name = "Inter"
    from pptx.dml.color import RGBColor

    run.font.color.rgb = RGBColor.from_string("141414")

    report = fix_deck(prs, CONFIG, source_path="in.pptx", output_path=None, dry_run=True)

    assert any(c.rule == "text_contrast" for c in report.changes)
    assert str(run.font.color.rgb) == "FFFFFF"
