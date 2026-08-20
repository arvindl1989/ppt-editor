"""The brand mode -- role to type, and the two curated sets.

`BRAND_MODE.md` is the source. These tests pin the answers that were
previously guessed at, so a regression shows up as a failure rather than
as a slide that looks slightly wrong.
"""

import pytest

from deckguard import brandmode as B


def test_a_quote_sizes_to_its_panel_not_to_body():
    """The `quote_b` symptom: a short quote set at paragraph size in a
    657x349 panel. The box was right; only the type was a guess."""
    assert B.resolve("quote", width=657)["px"] == 30
    assert B.resolve("quote", width=420)["px"] == 24
    assert B.resolve("quote", width=600)["px"] == 30, "600 is the boundary, inclusive"


def test_a_title_is_32_everywhere_except_a_narrow_column():
    assert B.resolve("title", width=1190)["px"] == 32
    assert B.resolve("title", width=575)["px"] == 32
    narrow = B.resolve("title", width=330)
    assert narrow["px"] == 28 and narrow["role"] == "title_narrow"
    assert B.resolve("title", width=374)["px"] == 28, "374 is the boundary, inclusive"


def test_heading_is_the_only_semibold_role():
    semibold = {r for r, v in B.TYPE_SCALE.items() if v[2] == 600}
    assert semibold == {"heading", "on_panel_heading"}


def test_no_role_is_grey_and_inter_is_never_blue():
    for role, (font, _px, _wt, _lead, _tr, colour, caps) in B.TYPE_SCALE.items():
        assert colour in (B.BLACK, B.WHITE, B.BLUE), f"{role} is {colour}"
        if font == B.INTER and colour == B.BLUE:
            # KONE numbers are the sole exception: the figure is blue, the
            # label under it black, so the blue reads as the number.
            assert role in ("stat_value", "stat_value_md", "number"), role
        if font == B.INTER:
            assert not caps, f"{role}: Inter is never uppercase"
        else:
            assert caps, f"{role}: KONE Information is always uppercase"


def test_retired_role_names_read_back_to_an_intent():
    """`gal_i64_141414` means "Inter 64 black" -- an output, not a
    decision. `body_muted` is the grey that got banned."""
    assert B.canonical("body_muted") == "body"
    assert B.resolve("body_muted")["color"] == B.BLACK
    assert B.canonical("gal_i64_141414") == "hero_value"
    # deliberately unmapped: it reads as bullets OR heading by slot
    assert "gal_i19_141414" not in B.RETIRED_ROLES


def test_type_on_dark_swaps_to_the_light_twin():
    assert B.resolve("title", width=1190, on_dark=True)["color"] == B.WHITE
    assert B.resolve("body", width=800, on_dark=True)["role"] == "on_panel_body"
    assert B.resolve("eyebrow", on_dark=True)["color"] == B.WHITE
    # a role with no dark twin keeps its own colour rather than guessing
    assert B.resolve("stat_value", on_dark=True)["role"] == "stat_value"


def test_both_content_starts_come_out_of_one_rule():
    """227 and 264 both appear in LAYOUTS.md, which is why neither is the
    standard on its own: a block starts 32px below the one above it, and
    a row of objects starts 69px below a title instead."""
    assert B.content_start() == 227
    assert B.content_start(objects=True) == 264
    assert B.content_start(has_subtitle=True) == 264
    assert B.CONTENT_START_TEXT == B.TITLE_BAND_BOTTOM + B.GAP_TEXT
    assert B.CONTENT_START_OBJECTS == B.TITLE_BAND_BOTTOM + B.GAP_OBJECTS


def test_an_unknown_role_returns_nothing_rather_than_a_default():
    """Guessing a default is what put 223 regions in this state."""
    assert B.resolve("not_a_role") is None


# --------------------------------------------------------------------------
# the curated sets
# --------------------------------------------------------------------------


def test_both_sets_are_twenty_five_slides_in_deck_order():
    for name in B.set_names():
        slides = B.slides_in(name)
        assert len(slides) == 25, name
        assert [s["n"] for s in slides] == list(range(1, 26)), name


def test_the_external_set_uses_no_secondary_colour():
    """The external treatment is blue, white, black and photography only."""
    fields = {s["field"] for s in B.slides_in("external")}
    assert fields <= {"white", "photo", "blue"}, fields
    # and blue is a full field on exactly two slides
    blue = [s["n"] for s in B.slides_in("external") if s["field"] == "blue"]
    assert blue == [20]


def test_six_archetypes_serve_both_sets():
    """Build once, parameterise the field and the on-field type colour."""
    assert B.shared_archetypes() == {
        "divider_numbering", "hero_stat", "how_it_works_3step",
        "image_section_divider", "kone_numbers", "outro",
    }


def test_the_canonical_library_is_forty_four():
    canonical = B.canonical_archetypes()
    assert len(canonical) == 44
    # every slide in both sets resolves into it
    for name in B.set_names():
        assert {s["archetype"] for s in B.slides_in(name)} <= canonical


def test_an_unknown_set_says_what_it_has():
    with pytest.raises(KeyError, match="internal"):
        B.slides_in("sideways")


# --------------------------------------------------------------------------
# chrome
# --------------------------------------------------------------------------


def test_chrome_follows_the_kind_of_slide_not_its_name():
    for cover in ("cover_a_cut4", "cover_b_cut3", "cover_f_fullbleed"):
        assert B.slide_kind(cover) == "cover"
        assert not B.wants_footer(cover) and B.logo_on_left(cover)
    for divider in ("divider_numbering", "divider_title_only", "image_section_divider"):
        assert B.slide_kind(divider) == "divider"
        assert not B.wants_footer(divider) and B.logo_on_left(divider)
    assert not B.wants_footer("outro") and B.logo_on_left("outro")
    for content in ("title_content", "kone_numbers", "quote_a", "timeline"):
        assert B.wants_footer(content), content
        assert not B.logo_on_left(content)
    # a blank takes none of it, and is not a cover either
    assert B.slide_kind("blank") == "bare" and not B.wants_footer("blank")


# --------------------------------------------------------------------------
# what each slide is for
# --------------------------------------------------------------------------


def test_every_slide_in_both_sets_carries_a_job():
    """A planner given bare archetype names cannot choose between
    `matrix_2x2` and `segment_breakdown` on merit, because a name is not
    a reason -- so it falls back to the order it was given, and briefs
    came out reusing the same first handful."""
    for audience in B.set_names():
        lines = B.menu(audience).splitlines()
        assert len(lines) == 25, audience
        without = [l for l in lines if " — " not in l]
        assert not without, (audience, without)


def test_a_job_says_what_the_slide_is_for(): 
    assert "cover" in B.job_for("cover_a_cut4", "external").lower()
    assert "numbered" in B.job_for("agenda_b_numbered", "external").lower()
    # an archetype only in the other set still resolves rather than blanking
    assert B.job_for("matrix_2x2", "internal")
    assert B.job_for("not_an_archetype", "internal") == ""


def test_the_job_table_needs_multiline_matching():
    """`^` without re.M anchors to the start of the whole document and
    matches nothing in a markdown table. It silently returned 0 of 50."""
    assert B._JOB_ROW.flags & __import__("re").M
