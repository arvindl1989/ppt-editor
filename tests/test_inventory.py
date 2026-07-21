from deckguard.inventory import build_inventory
from tests.helpers import add_picture, add_slide, body_run, make_pattern_png, new_deck, set_run, title_run


def test_build_inventory_basic_shape_fields():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(title_run(slide), text="Hello", font="Inter", bold=True, size_pt=32, color_hex="141414")

    inv = build_inventory(prs)
    assert len(inv.slides) == 1
    shapes = inv.slides[0].shapes
    title_shape = next(s for s in shapes if s.placeholder_type in ("TITLE", "CENTER_TITLE"))
    run = title_shape.paragraphs[0].runs[0]
    assert run.text == "Hello"
    assert run.font_raw == "Inter"
    assert run.bold is True
    assert run.size_pt == 32
    assert run.color.hex == "141414"


def test_build_inventory_picks_up_image_phash(tmp_path):
    prs = new_deck()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    img = make_pattern_png(tmp_path / "img.png", seed=5)
    add_picture(slide, str(img))

    inv = build_inventory(prs)
    shape = inv.slides[0].shapes[0]
    assert shape.image is not None
    assert shape.image.phash is not None
    assert len(shape.image.phash) == 16


def test_build_inventory_all_upper_detection():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(body_run(slide), text="SHOUT", font="Inter")
    set_run(title_run(slide), text="Mixed Case", font="Inter")

    inv = build_inventory(prs)
    runs = {r.text: r for s in inv.slides[0].shapes for p in s.paragraphs for r in p.runs}
    assert runs["SHOUT"].all_upper is True
    assert runs["Mixed Case"].all_upper is False
