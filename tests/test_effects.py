from deckguard import effects as effects_mod
from tests.helpers import (
    add_shadow_effect,
    add_shape_3d,
    add_text_outline,
    new_deck,
)


def _run_with_text(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    run = slide.shapes.title.text_frame.paragraphs[0].add_run()
    run.text = "hello"
    return slide, run


def test_detect_run_effects_none_by_default():
    prs = new_deck()
    _, run = _run_with_text(prs)
    assert effects_mod.detect_run_effects(run) == set()


def test_detect_and_remove_shadow():
    prs = new_deck()
    _, run = _run_with_text(prs)
    add_shadow_effect(run)

    assert effects_mod.detect_run_effects(run) == {"shadow"}
    removed = effects_mod.remove_run_effects(run)
    assert removed == {"shadow"}
    assert effects_mod.detect_run_effects(run) == set()


def test_detect_and_remove_text_outline():
    prs = new_deck()
    _, run = _run_with_text(prs)
    add_text_outline(run)

    assert effects_mod.detect_run_effects(run) == {"outline"}
    removed = effects_mod.remove_run_effects(run)
    assert removed == {"outline"}
    assert effects_mod.detect_run_effects(run) == set()


def test_detect_read_only_does_not_mutate_tree():
    prs = new_deck()
    _, run = _run_with_text(prs)
    before = run._r.find(effects_mod.a_qn("rPr"))
    assert before is None
    effects_mod.detect_run_effects(run)
    after = run._r.find(effects_mod.a_qn("rPr"))
    assert after is None  # detection must never get_or_add the rPr element


def test_detect_and_remove_shape_3d():
    prs = new_deck()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    shape = slide.shapes.add_shape(1, 0, 0, 914400, 914400)  # MSO_SHAPE.RECTANGLE == 1
    add_shape_3d(shape)

    assert "3d" in effects_mod.detect_shape_effects(shape)
    removed = effects_mod.remove_shape_effects(shape)
    assert "3d" in removed
    assert "3d" not in effects_mod.detect_shape_effects(shape)
