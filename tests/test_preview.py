"""Tests for the schematic preview renderers (preview.py). These
assert on structure and content (geometry percentages, colors, text,
fail-soft behavior) -- visual quality was verified by rendering the
output in a real browser."""

import pytest

from deckguard.inventory import build_inventory
from deckguard.preview import (
    archetype_preview_html,
    org_layout_preview_html,
    slide_preview_html,
)
from deckguard.skill_bridge import _skill_dir
from deckguard.slide_import import default_template_path
from tests.helpers import add_rectangle, add_slide, body_run, new_deck, set_run, title_run

needs_skill = pytest.mark.skipif(
    not (_skill_dir() / "kone_deck_creator.py").is_file(), reason="kone-deck-generator skill not installed"
)


def _deck_with_panel():
    prs = new_deck()
    s = add_slide(prs)
    title_run(s).text = "Resolution rate held at 91%"
    body_run(s).text = "Requests doubled"
    box = add_rectangle(s, name="Panel", fill_hex="1450F5", left_in=7, top_in=4.5, width_in=3, height_in=1.5)
    set_run(box.text_frame.paragraphs[0].add_run(), text="Panel text", color_hex="FFFFFF")
    return prs


def test_slide_preview_shows_real_text_and_fill_colors():
    prs = _deck_with_panel()
    inv = build_inventory(prs)

    html = slide_preview_html(inv.slides[0], prs.slide_width / 914400, prs.slide_height / 914400)

    assert "Resolution rate held at 91%" in html
    assert "background:#1450F5" in html  # the panel's real fill
    assert "aspect-ratio:1280/720" in html
    assert "<script" not in html


def test_slide_preview_escapes_hostile_slide_text():
    prs = new_deck()
    s = add_slide(prs)
    title_run(s).text = '<img src=x onerror=alert(1)>'
    inv = build_inventory(prs)

    html = slide_preview_html(inv.slides[0])

    assert "<img" not in html
    assert "&lt;img" in html


def test_slide_preview_is_fail_soft():
    html = slide_preview_html(object())  # nothing SlideRecord-shaped at all
    assert "aspect-ratio:1280/720" in html  # the fallback card, not an exception


@needs_skill
def test_archetype_preview_draws_from_the_skills_own_region_data():
    html = archetype_preview_html("hero_stat", {
        "eyebrow": "Resolution rate", "value": "91.2%", "caption": "cleared", "support": "674 of 739",
    })

    assert "91.2%" in html
    assert "text-transform:uppercase" in html  # eyebrow role styled per kone_engine.ROLE_STYLE


@needs_skill
def test_archetype_preview_shows_picture_slots_as_placeholders():
    html = archetype_preview_html("three_picture_cards", {
        "title": "Three offerings",
        "cards": [{"heading": "Care", "bullets": ["24/7"]}],
    })

    assert "PHOTO" in html
    assert "Care" in html


def test_archetype_preview_is_fail_soft_for_unknown_archetype():
    html = archetype_preview_html("not_a_real_archetype", {})
    assert "not_a_real_archetype" in html  # fallback card names it


def test_org_layout_preview_places_verbatim_content_in_real_placeholders():
    from pptx import Presentation

    tmpl = Presentation(str(default_template_path()))
    layout = next(l for m in tmpl.slide_masters for l in m.slide_layouts if l.name == "Title and content A")

    html = org_layout_preview_html(
        layout, tmpl.slide_width, tmpl.slide_height,
        "My title", [["Point one", "Point two"]], image_count=0,
    )

    assert "My title" in html
    assert "Point one" in html
    assert "border:1px dashed" in html  # placeholder outlines
