from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

from deckguard.config import load_config, default_config_path
from deckguard.inventory import build_inventory
from deckguard.rules_engine import audit_deck
from tests.helpers import (
    add_rectangle,
    add_shadow_effect,
    add_slide,
    body_run,
    new_deck,
    set_run,
    set_run_theme_color,
    title_run,
)

CONFIG = load_config(default_config_path())


def violations_for(prs):
    return audit_deck(build_inventory(prs), CONFIG)


def by_rule(violations, rule):
    return [v for v in violations if v.rule == rule]


def test_old_kone_blue_in_heading_is_critical_and_fixable():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(title_run(slide), text="Title", font="Inter", color_hex="005EB8")

    viol = by_rule(violations_for(prs), "legacy_color")
    assert len(viol) == 1
    assert viol[0].severity == "critical"
    assert viol[0].auto_fixable is True
    assert viol[0].details["target"] == "#1450F5"


def test_unapproved_font_in_heading_is_critical():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(title_run(slide), text="Title", font="Calibri")

    viol = by_rule(violations_for(prs), "unapproved_font")
    assert len(viol) == 1
    assert viol[0].severity == "critical"
    assert viol[0].auto_fixable is True  # Calibri has a remap target


def test_unapproved_font_in_body_is_major_not_critical():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(body_run(slide), text="Body copy", font="Calibri")

    viol = by_rule(violations_for(prs), "unapproved_font")
    assert len(viol) == 1
    assert viol[0].severity == "major"


def test_unapproved_font_with_no_remap_target_is_not_auto_fixable():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(body_run(slide), text="Body copy", font="Papyrus")

    viol = by_rule(violations_for(prs), "unapproved_font")
    assert viol[0].auto_fixable is False


def test_inherited_unapproved_font_is_flagged_but_not_auto_fixed():
    """A run with no explicit font override still renders with a real
    font -- inherited from the master's txStyles/theme (Calibri, for
    python-pptx's stock template). That's now resolved and checked like
    any other font, but auto-fixing it would mean hardcoding a per-run
    override where the deck relied on inheritance -- the correct fix is
    upstream (theme/master), so this is flagged for review, not silently
    rewritten."""
    prs = new_deck()
    slide = add_slide(prs)
    title_run(slide).text = "Inherits from layout"

    viol = by_rule(violations_for(prs), "unapproved_font")
    assert len(viol) == 1
    assert viol[0].details["current"] == "Calibri"
    assert viol[0].auto_fixable is False
    assert "inherited" in viol[0].message


def test_inherited_approved_font_is_not_flagged():
    """Same shape, but the deck's theme is already on-brand (Inter) --
    inheritance should resolve cleanly with no violation at all."""
    from tests.helpers import set_theme_font

    prs = new_deck()
    set_theme_font(prs, "majorFont", "Inter")
    set_theme_font(prs, "minorFont", "Inter")
    slide = add_slide(prs)
    title_run(slide).text = "Inherits from layout"

    assert by_rule(violations_for(prs), "unapproved_font") == []


def test_inter_in_non_approved_color_is_major():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(body_run(slide), text="Body copy", font="Inter", color_hex="FF00FF")

    viol = by_rule(violations_for(prs), "text_color")
    assert len(viol) == 1
    assert viol[0].severity == "major"
    assert viol[0].details["target"] == "#141414"


def test_all_caps_inter_is_flagged_major_not_auto_fixable():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(body_run(slide), text="SHOUTING TEXT", font="Inter", color_hex="141414")

    viol = by_rule(violations_for(prs), "all_caps")
    assert len(viol) == 1
    assert viol[0].severity == "major"
    assert viol[0].auto_fixable is False


def test_all_caps_allowed_word_kone_is_not_flagged():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(body_run(slide), text="KONE", font="Inter", color_hex="141414")

    assert by_rule(violations_for(prs), "all_caps") == []


def test_kone_information_not_all_caps_is_flagged():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(body_run(slide), text="not shouting", font="KONE Information", color_hex="141414")

    viol = by_rule(violations_for(prs), "all_caps")
    assert len(viol) == 1


def test_kone_information_oversized_is_role_restriction_violation():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(body_run(slide), text="BIG LABEL", font="KONE Information", size_pt=40, color_hex="141414")

    viol = by_rule(violations_for(prs), "role_restriction")
    assert len(viol) == 1
    assert viol[0].auto_fixable is False


def test_forbidden_text_effect_shadow_is_major_and_fixable():
    prs = new_deck()
    slide = add_slide(prs)
    run = set_run(body_run(slide), text="shadowed", font="Inter", color_hex="141414")
    add_shadow_effect(run)

    viol = by_rule(violations_for(prs), "text_effect")
    assert len(viol) == 1
    assert viol[0].severity == "major"
    assert viol[0].auto_fixable is True


def test_alignment_violation_is_minor():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(body_run(slide), text="centered body copy", font="Inter", color_hex="141414")
    slide.placeholders[1].text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

    viol = by_rule(violations_for(prs), "alignment")
    assert len(viol) == 1
    assert viol[0].severity == "minor"


def test_pagination_like_text_is_exempted_from_alignment_rule():
    prs = new_deck()
    slide = add_slide(prs)
    body = slide.placeholders[1]
    body.left, body.top, body.width, body.height = 0, 6350000, 500000, 300000  # bottom-edge, small box
    set_run(body_run(slide), text="12", font="Inter", color_hex="141414")
    body.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

    assert by_rule(violations_for(prs), "alignment") == []


def test_min_body_size_is_minor():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(body_run(slide), text="tiny", font="Inter", size_pt=8, color_hex="141414")

    viol = by_rule(violations_for(prs), "min_size")
    assert len(viol) == 1
    assert viol[0].severity == "minor"


def test_wrong_slide_size_flagged():
    prs = new_deck()  # default python-pptx template is 4:3
    assert by_rule(violations_for(prs), "slide_size")[0].severity == "major"


def test_theme_based_legacy_tint_is_flagged_via_effective_color():
    from pptx.enum.dml import MSO_THEME_COLOR
    from tests.helpers import set_theme_slot

    prs = new_deck()
    set_theme_slot(prs, "accent1", "005EB8")
    slide = add_slide(prs)
    run = title_run(slide)
    run.text = "Themed"
    run.font.name = "Inter"
    set_run_theme_color(run, MSO_THEME_COLOR.ACCENT_1)

    viol = by_rule(violations_for(prs), "legacy_color")
    assert len(viol) == 1
    assert viol[0].severity == "critical"


def test_clean_deck_has_no_violations_besides_template_provenance():
    """python-pptx's stock template is inherently 4:3 and built on generic
    Office layout names, not KONE's -- slide_size and non_standard_layout
    are expected artifacts of the test fixture, not something a real
    KONE-template deck would ever trip. Everything else must be clean."""
    prs = new_deck()
    slide = add_slide(prs)
    set_run(title_run(slide), text="Title", font="Inter Semi Bold", color_hex="141414")
    para = slide.shapes.title.text_frame.paragraphs[0]
    para.alignment = PP_ALIGN.LEFT
    set_run(body_run(slide), text="Body copy", font="Inter", color_hex="141414")
    slide.placeholders[1].text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT

    rules = {v.rule for v in violations_for(prs)}
    assert rules == {"slide_size", "non_standard_layout"}


def test_min_size_uses_the_paragraphs_own_outline_level_not_a_flat_floor():
    """The master's body text has a deliberately different minimum per
    outline level (footnote-tier levels are 11pt by design, not a flat
    number) -- config.min_size_by_level must be consulted per-paragraph,
    not just a single fonts.min_body_size_pt."""
    prs = new_deck()
    slide = add_slide(prs)
    set_run(body_run(slide), text="footnote-tier", font="Inter", size_pt=11, color_hex="141414")
    para = slide.placeholders[1].text_frame.paragraphs[0]
    para.level = 6  # min_size_by_level[6] == 11pt in the real config -- should NOT be flagged

    assert by_rule(violations_for(prs), "min_size") == []


def test_min_size_still_flags_a_level_below_its_own_threshold():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(body_run(slide), text="too small even for level 6", font="Inter", size_pt=8, color_hex="141414")
    para = slide.placeholders[1].text_frame.paragraphs[0]
    para.level = 6  # min_size_by_level[6] == 11pt -- 8pt still violates

    viol = by_rule(violations_for(prs), "min_size")
    assert len(viol) == 1
    assert viol[0].details["min_pt"] == 11


def test_min_size_exempts_plain_text_boxes_with_no_master_defined_floor():
    """Free-form text boxes (footnotes, tab labels, page numbers typed
    into a plain shape rather than a real placeholder) have no
    master-defined size floor -- unlike placeholder body text, they must
    not be flagged just for being small."""
    from pptx.util import Inches, Pt

    from pptx.dml.color import RGBColor

    prs = new_deck()
    slide = add_slide(prs)
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(0.5))
    run = box.text_frame.paragraphs[0].add_run()
    run.text = "tiny footnote"
    run.font.name = "Inter"
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor.from_string("141414")

    assert by_rule(violations_for(prs), "min_size") == []


def test_non_standard_layout_flagged_when_not_in_approved_list():
    prs = new_deck()
    add_slide(prs, layout_idx=1)  # "Title and Content" -- not a KONE template layout name

    config = dict(CONFIG)
    config["layout"] = dict(CONFIG["layout"])
    config["layout"]["approved_layouts"] = ["Some Other Layout"]

    violations = audit_deck(build_inventory(prs), config)
    viol = by_rule(violations, "non_standard_layout")
    assert len(viol) == 1
    assert viol[0].severity == "major"
    assert viol[0].auto_fixable is False


def test_non_standard_layout_not_flagged_when_layout_is_approved():
    prs = new_deck()
    add_slide(prs, layout_idx=1)

    config = dict(CONFIG)
    config["layout"] = dict(CONFIG["layout"])
    config["layout"]["approved_layouts"] = ["Title and Content"]

    violations = audit_deck(build_inventory(prs), config)
    assert by_rule(violations, "non_standard_layout") == []


def test_non_standard_layout_is_a_no_op_when_approved_layouts_not_configured():
    prs = new_deck()
    add_slide(prs, layout_idx=1)

    config = dict(CONFIG)
    config["layout"] = dict(CONFIG["layout"])
    config["layout"].pop("approved_layouts", None)

    violations = audit_deck(build_inventory(prs), config)
    assert by_rule(violations, "non_standard_layout") == []


def test_text_contrast_flags_black_text_on_kone_blue_background():
    """Regression test for General_Branding.docx's legibility rule: black
    text on the KONE Blue background is wrong -- must be white."""
    prs = new_deck()
    slide = add_slide(prs)
    box = add_rectangle(slide, name="Blue panel", fill_hex="1450F5", left_in=1, top_in=1, width_in=3, height_in=1)
    box.text_frame.text = "Label"
    run = box.text_frame.paragraphs[0].runs[0]
    run.font.name = "Inter"
    run.font.color.rgb = RGBColor.from_string("141414")

    violations = violations_for(prs)
    viol = by_rule(violations, "text_contrast")
    assert len(viol) == 1
    assert viol[0].details["target"] == "#FFFFFF"
    assert viol[0].severity == "major"
    assert viol[0].auto_fixable is True

    # the generic allowed-colors-list check must not also fire for the same run
    assert by_rule(violations, "text_color") == []


def test_text_contrast_flags_run_with_no_explicit_color_at_all():
    """Regression test for a real bug report: text with NO explicit color
    (inherits from the theme/master, which color-inheritance resolution
    doesn't attempt to reproduce -- unlike font) was silently skipped by
    the contrast check entirely, so a black-inheriting run sitting on a
    KONE Blue panel just stayed illegible. An unknown inherited color is
    exactly as much in scope as a wrong explicit one."""
    prs = new_deck()
    slide = add_slide(prs)
    box = add_rectangle(slide, name="Blue panel", fill_hex="1450F5", left_in=1, top_in=1, width_in=3, height_in=1)
    box.text_frame.text = "Label"
    run = box.text_frame.paragraphs[0].runs[0]
    run.font.name = "Inter"
    # no run.font.color set at all -- inherits

    viol = by_rule(violations_for(prs), "text_contrast")
    assert len(viol) == 1
    assert viol[0].details["target"] == "#FFFFFF"
    assert viol[0].details["current"] is None
    assert viol[0].auto_fixable is True


def test_text_contrast_passes_when_white_text_on_kone_blue_background():
    prs = new_deck()
    slide = add_slide(prs)
    box = add_rectangle(slide, name="Blue panel", fill_hex="1450F5", left_in=1, top_in=1, width_in=3, height_in=1)
    box.text_frame.text = "Label"
    run = box.text_frame.paragraphs[0].runs[0]
    run.font.name = "Inter"
    run.font.color.rgb = RGBColor.from_string("FFFFFF")

    assert by_rule(violations_for(prs), "text_contrast") == []


def test_text_contrast_flags_white_text_on_light_secondary_background():
    prs = new_deck()
    slide = add_slide(prs)
    box = add_rectangle(slide, name="Pink card", fill_hex="FFCDD7", left_in=1, top_in=1, width_in=3, height_in=1)
    box.text_frame.text = "Label"
    run = box.text_frame.paragraphs[0].runs[0]
    run.font.name = "Inter"
    run.font.color.rgb = RGBColor.from_string("FFFFFF")

    viol = by_rule(violations_for(prs), "text_contrast")
    assert len(viol) == 1
    assert viol[0].details["target"] == "#141414"


def test_text_contrast_always_white_on_kone_blue_60_percent_tint_overriding_wcag():
    """Regression test for an explicit brand-consistency request: KONE
    Blue's 60% tint (#7296F9) is technically light enough that WCAG math
    alone picks black text (higher contrast ratio) -- confirmed via
    colors.expected_contrast_text_hex directly. The brand wants every
    tint in always_light_text_backgrounds treated uniformly as a blue
    panel regardless, so the configured override must win over the math."""
    prs = new_deck()
    slide = add_slide(prs)
    box = add_rectangle(slide, name="Blue tint panel", fill_hex="7296F9", left_in=1, top_in=1, width_in=3, height_in=1)
    box.text_frame.text = "Label"
    run = box.text_frame.paragraphs[0].runs[0]
    run.font.name = "Inter"
    run.font.color.rgb = RGBColor.from_string("141414")

    viol = by_rule(violations_for(prs), "text_contrast")
    assert len(viol) == 1
    assert viol[0].details["target"] == "#FFFFFF"


def test_text_contrast_still_wcag_computed_for_tints_below_the_override_list():
    """The 40% tint (#A1B9FB) is deliberately NOT in
    always_light_text_backgrounds -- white text there would be
    borderline illegible, so it must stay contrast-computed (black)."""
    prs = new_deck()
    slide = add_slide(prs)
    box = add_rectangle(slide, name="Light tint panel", fill_hex="A1B9FB", left_in=1, top_in=1, width_in=3, height_in=1)
    box.text_frame.text = "Label"
    run = box.text_frame.paragraphs[0].runs[0]
    run.font.name = "Inter"
    run.font.color.rgb = RGBColor.from_string("FFFFFF")  # wrong -- should be black

    viol = by_rule(violations_for(prs), "text_contrast")
    assert len(viol) == 1
    assert viol[0].details["target"] == "#141414"


def test_text_contrast_not_checked_without_a_resolved_shape_background():
    """No shape-level solid fill (plain text on the page canvas) -- can't
    compute contrast without full z-order resolution, so it's skipped
    rather than guessed at; the generic allowed-colors check still applies."""
    prs = new_deck()
    slide = add_slide(prs)
    set_run(body_run(slide), text="Body copy", font="Inter", color_hex="FFFFFF")

    assert by_rule(violations_for(prs), "text_contrast") == []
    # white isn't the fallback list's first choice, but it IS an allowed
    # color for Inter (black or white) -- so no text_color violation either
    assert by_rule(violations_for(prs), "text_color") == []
