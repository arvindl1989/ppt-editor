from deckguard import logo as logo_mod
from tests.helpers import add_picture, make_pattern_png, make_solid_png, new_deck


def test_compute_phash_stable_for_identical_image(tmp_path):
    p = make_solid_png(tmp_path / "a.png", rgb=(0, 94, 184))
    h1 = logo_mod.compute_phash(p.read_bytes())
    h2 = logo_mod.compute_phash(p.read_bytes())
    assert h1 == h2
    assert len(h1) == 16  # 8x8 phash -> 64 bits -> 16 hex chars


def test_hamming_distance_zero_for_same_hash():
    h = "abcdef1234567890"
    assert logo_mod.hamming_distance(h, h) == 0


def test_hamming_distance_large_for_different_patterns(tmp_path):
    a = make_pattern_png(tmp_path / "a.png", seed=1)
    b = make_pattern_png(tmp_path / "b.png", seed=2)
    ha = logo_mod.compute_phash(a.read_bytes())
    hb = logo_mod.compute_phash(b.read_bytes())
    assert logo_mod.hamming_distance(ha, hb) > 5


def test_find_old_logo_matches_by_similar_image(tmp_path):
    old_logo = make_pattern_png(tmp_path / "old_logo.png", seed=1)
    unrelated = make_pattern_png(tmp_path / "unrelated.png", seed=2)
    old_hash = logo_mod.compute_phash(old_logo.read_bytes())

    prs = new_deck()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    logo_shape = add_picture(slide, str(old_logo))
    add_picture(slide, str(unrelated), left_in=4)

    matches = logo_mod.find_old_logo_matches(slide.shapes, [old_hash], threshold=5)
    assert len(matches) == 1
    # python-pptx hands back a fresh proxy object per traversal, so compare
    # the underlying XML element rather than object identity.
    assert matches[0].shape._element is logo_shape._element


def test_replace_logo_image_preserves_position_and_size(tmp_path):
    old_logo = make_pattern_png(tmp_path / "old_logo.png", seed=1)
    new_logo = make_pattern_png(tmp_path / "new_logo.png", seed=3)

    prs = new_deck()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    shape = add_picture(slide, str(old_logo), left_in=2, top_in=3, width_in=1.5, height_in=0.75)
    left, top, width, height = shape.left, shape.top, shape.width, shape.height

    logo_mod.replace_logo_image(shape, str(new_logo))

    assert shape.left == left
    assert shape.top == top
    assert shape.width == width
    assert shape.height == height
    assert shape.image.blob == new_logo.read_bytes()
