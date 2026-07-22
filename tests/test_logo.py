from deckguard import logo as logo_mod
from tests.helpers import add_picture, make_pattern_png, make_solid_png, new_deck, set_background_image


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


def test_find_background_blip_returns_none_when_no_bg_element(tmp_path):
    prs = new_deck()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    assert logo_mod.find_background_blip(slide._element) is None


def test_find_background_blip_finds_a_picture_fill_background(tmp_path):
    """Regression coverage for a real gap: a logo baked into a slide's
    page-level background-FILL image (<p:cSld><p:bg>) rather than being a
    picture shape at all -- outside the shape tree entirely, so no
    shape-based scan (however thorough) can see it without this."""
    logo_img = make_pattern_png(tmp_path / "logo.png", seed=1)
    prs = new_deck()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    blip = set_background_image(slide, str(logo_img))

    assert logo_mod.find_background_blip(slide._element) is blip


def test_find_old_logo_background_match_by_similar_image(tmp_path):
    old_logo = make_pattern_png(tmp_path / "old_logo.png", seed=1)
    old_hash = logo_mod.compute_phash(old_logo.read_bytes())

    prs = new_deck()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background_image(slide, str(old_logo))

    match = logo_mod.find_old_logo_background_match(slide.part, slide._element, [old_hash], threshold=5)
    assert match is not None
    assert match.matched_hash == old_hash


def test_find_old_logo_background_match_none_for_unrelated_image(tmp_path):
    old_logo = make_pattern_png(tmp_path / "old_logo.png", seed=1)
    old_hash = logo_mod.compute_phash(old_logo.read_bytes())
    unrelated = make_pattern_png(tmp_path / "unrelated.png", seed=2)

    prs = new_deck()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background_image(slide, str(unrelated))

    match = logo_mod.find_old_logo_background_match(slide.part, slide._element, [old_hash], threshold=5)
    assert match is None


def test_replace_background_image_swaps_the_blob(tmp_path):
    old_logo = make_pattern_png(tmp_path / "old_logo.png", seed=1)
    new_logo = make_pattern_png(tmp_path / "new_logo.png", seed=3)

    prs = new_deck()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    blip = set_background_image(slide, str(old_logo))

    logo_mod.replace_background_image(slide.part, blip, str(new_logo))

    rid = blip.get(f"{{{logo_mod.R_NS}}}embed")
    assert slide.part.related_part(rid).blob == new_logo.read_bytes()
