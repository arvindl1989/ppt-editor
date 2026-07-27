from pptx.util import Emu, Inches

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


def test_find_shapes_in_region_matches_only_fully_contained_shapes():
    prs = new_deck()
    master = prs.slide_masters[0]
    spTree = master.shapes._spTree
    id_ = master.shapes._next_shape_id
    inside = spTree.add_textbox(id_, "Inside", Inches(11), Inches(0.2), Inches(1), Inches(0.5))
    id_ += 1
    straddling = spTree.add_textbox(id_, "Straddling", Inches(9), Inches(0.2), Inches(3), Inches(0.5))

    region = (Emu(Inches(10.5)), Emu(Inches(0)), Emu(Inches(2.8)), Emu(Inches(1.2)))
    matches = logo_mod.find_shapes_in_region(master.shapes, region)

    matched_elements = {s._element for s in matches}
    assert inside in matched_elements
    assert straddling not in matched_elements  # left edge (9in) is outside the region -- not fully contained


def test_find_shapes_in_region_empty_when_nothing_is_inside():
    prs = new_deck()
    master = prs.slide_masters[0]
    region = (Emu(Inches(10.5)), Emu(Inches(0)), Emu(Inches(2.8)), Emu(Inches(1.2)))
    # the master's own default title/body/date/footer placeholders all live elsewhere
    assert logo_mod.find_shapes_in_region(master.shapes, region) == []


def test_replace_shapes_in_region_with_logo_removes_matches_and_inserts_sized_picture(tmp_path):
    new_logo = make_pattern_png(tmp_path / "new_logo.png", seed=4)

    prs = new_deck()
    master = prs.slide_masters[0]
    spTree = master.shapes._spTree
    id_ = logo_mod._next_shape_id_in_tree(spTree)
    old_mark = spTree.add_textbox(id_, "OldMark", Inches(11), Inches(0.2), Inches(1), Inches(0.5))
    before_count = len(master.shapes)

    region = (Emu(Inches(10.5)), Emu(Inches(0)), Emu(Inches(2.8)), Emu(Inches(1.2)))
    matches = logo_mod.find_shapes_in_region(master.shapes, region)
    assert len(matches) == 1

    logo_mod.replace_shapes_in_region_with_logo(master.shapes, matches, str(new_logo), region)

    assert len(master.shapes) == before_count  # one removed, one added -- net unchanged
    assert old_mark.getparent() is None  # actually removed from the tree, not just unreferenced

    pictures = [s for s in master.shapes if s.shape_type is not None and s.shape_type.name == "PICTURE"]
    assert len(pictures) == 1
    pic = pictures[0]
    # fits inside the region on both axes, aspect ratio preserved (not stretched)
    r_left, r_top, r_width, r_height = region
    assert r_left <= pic.left and pic.left + pic.width <= r_left + r_width
    assert r_top <= pic.top and pic.top + pic.height <= r_top + r_height


def test_replace_shapes_in_region_with_logo_on_a_master_never_assigns_a_layout_id(tmp_path):
    """Regression test for a real report: PowerPoint outright refused to
    open a .pptx this produced. Root cause -- confirmed by inspecting the
    output XML directly -- was calling python-pptx's own `_next_shape_id`
    on a MASTER's shape tree: a slide master always has a sibling
    `p:sldLayoutIdLst` (listing the layouts that belong to it) whose
    `p:sldLayoutId` elements use a completely different id namespace
    starting at 2**31 by OOXML convention, and `_next_shape_id`'s
    document-wide `//@id` XPath scan picks those up too, handing back an
    id like 2147483687 -- past the signed-32-bit range PowerPoint's own
    parser tolerates. Every stock python-pptx master has this sibling
    list (it's how a master knows which layouts belong to it), so this
    isn't specific to any one deck's quirks."""
    new_logo = make_pattern_png(tmp_path / "new_logo.png", seed=5)

    prs = new_deck()
    master = prs.slide_masters[0]
    assert len(master.shapes._spTree.xpath("//@id")) > 0  # sanity: sldLayoutIdLst ids are visible in this scan
    spTree = master.shapes._spTree
    id_ = logo_mod._next_shape_id_in_tree(spTree)
    spTree.add_textbox(id_, "OldMark", Inches(11), Inches(0.2), Inches(1), Inches(0.5))

    region = (Emu(Inches(10.5)), Emu(Inches(0)), Emu(Inches(2.8)), Emu(Inches(1.2)))
    matches = logo_mod.find_shapes_in_region(master.shapes, region)

    logo_mod.replace_shapes_in_region_with_logo(master.shapes, matches, str(new_logo), region)

    pic = next(s for s in master.shapes if s.shape_type is not None and s.shape_type.name == "PICTURE")
    assert pic.shape_id < 2**31


def test_next_shape_id_in_tree_ignores_sibling_sldLayoutIdLst_ids():
    """Unit-level version of the same regression: a master's own
    _next_shape_id_in_tree must stay scoped to p:cNvPr ids and ignore
    the 2**31+ range p:sldLayoutId elements use, unlike python-pptx's
    own _next_shape_id (a document-wide XPath scan)."""
    prs = new_deck()
    master = prs.slide_masters[0]
    spTree = master.shapes._spTree

    buggy = master.shapes._next_shape_id  # python-pptx's own property
    fixed = logo_mod._next_shape_id_in_tree(spTree)

    assert buggy >= 2**31
    assert fixed < 100  # a stock master's own placeholder ids are all small


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
