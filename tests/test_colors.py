import pytest
from pptx.enum.dml import MSO_THEME_COLOR

from deckguard import colors as colors_mod
from tests.helpers import new_deck, set_theme_slot


def test_normalize_hex():
    assert colors_mod.normalize_hex("#1450f5") == "1450F5"
    assert colors_mod.normalize_hex("1450F5") == "1450F5"
    with pytest.raises(ValueError):
        colors_mod.normalize_hex("#ZZZZZZ")
    with pytest.raises(ValueError):
        colors_mod.normalize_hex("#12345")


def test_rgb_distance_and_apply_brightness():
    assert colors_mod.rgb_distance((0, 0, 0), (0, 0, 0)) == 0
    assert colors_mod.rgb_distance((0, 0, 0), (255, 0, 0)) == 255

    lightened = colors_mod.apply_brightness((0, 94, 184), 0.5)
    assert all(lightened[i] > (0, 94, 184)[i] for i in (0, 1, 2) if (0, 94, 184)[i] < 255)

    darkened = colors_mod.apply_brightness((0, 94, 184), -0.5)
    assert darkened == (0, 47, 92)


def test_remap_theme_colors_rewrites_srgb_slot():
    prs = new_deck()
    set_theme_slot(prs, "accent1", "005EB8")

    changes = colors_mod.remap_theme_colors(prs, {"005EB8": "1450F5"})

    assert len(changes) == 1
    assert changes[0]["slot"] == "accent1"
    master = prs.slide_masters[0]
    scheme = colors_mod.get_theme_scheme(master)
    assert scheme.slots["accent1"] == "1450F5"


def test_remap_theme_colors_replaces_syscolor_reference():
    prs = new_deck()
    # dk1 defaults to a <a:sysClr val="windowText" lastClr="000000"/>
    changes = colors_mod.remap_theme_colors(prs, {"000000": "141414"})
    assert changes[0]["slot"] == "dk1"
    scheme = colors_mod.get_theme_scheme(prs.slide_masters[0])
    assert scheme.slots["dk1"] == "141414"


def test_effective_rgb_resolves_theme_tint():
    prs = new_deck()
    set_theme_slot(prs, "accent1", "1450F5")
    scheme = colors_mod.get_theme_scheme(prs.slide_masters[0])

    slide = prs.slides.add_slide(prs.slide_layouts[1])
    run = slide.shapes.title.text_frame.paragraphs[0].add_run()
    run.text = "x"
    run.font.color.theme_color = MSO_THEME_COLOR.ACCENT_1
    run.font.color.brightness = 0.6  # a 60%-tint of accent1, like the brand's tint scale

    eff = colors_mod.effective_rgb(run.font.color, scheme)
    expected = colors_mod.apply_brightness(colors_mod.hex_to_rgb("1450F5"), 0.6)
    assert eff == expected


def test_effective_rgb_none_for_unset_color():
    prs = new_deck()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    run = slide.shapes.title.text_frame.paragraphs[0].add_run()
    run.text = "x"
    assert colors_mod.effective_rgb(run.font.color, None) is None
