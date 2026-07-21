from pptx.enum.text import PP_ALIGN

from deckguard.config import load_config, default_config_path
from deckguard.inventory import build_inventory
from deckguard.rules_engine import audit_deck
from tests.helpers import (
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


def test_run_with_no_explicit_font_is_not_flagged():
    prs = new_deck()
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


def test_clean_deck_has_no_violations_besides_slide_size():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(title_run(slide), text="Title", font="Inter Semi Bold", color_hex="141414")
    para = slide.shapes.title.text_frame.paragraphs[0]
    para.alignment = PP_ALIGN.LEFT
    set_run(body_run(slide), text="Body copy", font="Inter", color_hex="141414")
    slide.placeholders[1].text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT

    rules = [v.rule for v in violations_for(prs)]
    assert rules == ["slide_size"]
