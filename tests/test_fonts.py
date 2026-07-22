from deckguard.fonts import (
    FontTables,
    canonical_key,
    normalize_key,
    read_master_style_font,
    read_theme_font_scheme,
    remap_literal_fonts_in_master_txstyles,
    remap_theme_fonts,
    resolve_effective_font,
    resolve_theme_symbol,
)
from tests.helpers import new_deck, set_theme_font

APPROVED = {
    "approved": ["Inter", "Inter Semi Bold", "KONE Information"],
    "remap": {"Calibri": "Inter", "Arial": "Inter", "Segoe UI": "Inter"},
}


def test_normalize_key_strips_hyphens_and_spaces_case_insensitive():
    assert normalize_key("Inter Semi Bold") == "intersemibold"
    assert normalize_key("Inter-SemiBold") == "intersemibold"
    assert normalize_key("InterSemiBold") == "intersemibold"
    assert normalize_key("  Inter  ") == "inter"
    assert normalize_key(None) == ""


def test_canonical_key_folds_bold_onto_semibold_family():
    assert canonical_key("Inter", bold=True) == canonical_key("Inter Semi Bold", bold=False)
    assert canonical_key("Inter", bold=False) != canonical_key("Inter Semi Bold", bold=False)


def test_font_tables_matches_all_naming_variants():
    tables = FontTables.from_config(APPROVED)
    for variant in ("Inter Semi Bold", "Inter-SemiBold", "Inter SemiBold", "inter-semi-bold"):
        assert tables.match_approved(variant) == "Inter Semi Bold", variant
    assert tables.match_approved("Inter", bold=True) == "Inter Semi Bold"
    assert tables.match_approved("Inter", bold=False) == "Inter"
    assert tables.match_approved("Calibri") is None
    assert tables.is_approved("KONE Information")


def test_font_tables_remap_target():
    tables = FontTables.from_config(APPROVED)
    assert tables.remap_target("Calibri") == "Inter"
    assert tables.remap_target("calibri") == "Inter"
    assert tables.remap_target("Comic Sans MS") is None


def test_remap_theme_fonts_rewrites_major_and_minor():
    prs = new_deck()
    set_theme_font(prs, "majorFont", "Calibri")
    set_theme_font(prs, "minorFont", "Calibri")

    changes = remap_theme_fonts(prs, {"Calibri": "Inter"})

    assert {c["slot"] for c in changes} == {"majorFont", "minorFont"}
    assert all(c["new"] == "Inter" for c in changes)


def test_remap_theme_fonts_no_op_when_already_correct():
    prs = new_deck()
    set_theme_font(prs, "majorFont", "Inter")
    set_theme_font(prs, "minorFont", "Inter")
    changes = remap_theme_fonts(prs, {"Calibri": "Inter"})
    assert changes == []


def test_read_theme_font_scheme_reads_major_and_minor():
    prs = new_deck()
    set_theme_font(prs, "majorFont", "Inter")
    set_theme_font(prs, "minorFont", "Arial")
    fonts = read_theme_font_scheme(prs.slide_masters[0])
    assert fonts == {"major": "Inter", "minor": "Arial"}


def test_read_master_style_font_reads_the_a_namespace_lvl_elements():
    """Regression test for a real bug: <p:titleStyle>/<p:bodyStyle>/
    <p:otherStyle> are in the presentationml namespace, but their child
    <a:lvl1pPr>...<a:lvl9pPr> elements are in the drawingml namespace --
    looking them up with the wrong namespace silently finds nothing and
    every run falls back to unresolved, defeating the whole feature."""
    master = new_deck().slide_masters[0]
    # python-pptx's stock template titleStyle/bodyStyle reference the
    # theme via +mj-lt/+mn-lt at level 0 (lvl1pPr) -- real, present data.
    assert read_master_style_font(master, "title", 0) == "+mj-lt"
    assert read_master_style_font(master, "body", 0) == "+mn-lt"


def test_read_master_style_font_falls_back_to_level_0():
    master = new_deck().slide_masters[0]
    # No level 8 (9th indent) override in the stock template -- must fall
    # back to level 0 rather than returning None.
    assert read_master_style_font(master, "body", 8) == "+mn-lt"


def test_resolve_theme_symbol():
    theme_fonts = {"major": "Inter", "minor": "Arial"}
    assert resolve_theme_symbol("+mj-lt", theme_fonts) == "Inter"
    assert resolve_theme_symbol("+mn-lt", theme_fonts) == "Arial"
    assert resolve_theme_symbol("Papyrus", theme_fonts) == "Papyrus"
    assert resolve_theme_symbol(None, theme_fonts) is None


def test_resolve_effective_font_prefers_explicit_override():
    master = new_deck().slide_masters[0]
    assert resolve_effective_font("Papyrus", "title", 0, master, {"major": "Inter"}) == "Papyrus"


def test_resolve_effective_font_falls_back_to_master_and_theme():
    prs = new_deck()
    set_theme_font(prs, "majorFont", "Inter")
    master = prs.slide_masters[0]
    theme_fonts = read_theme_font_scheme(master)
    assert resolve_effective_font(None, "title", 0, master, theme_fonts) == "Inter"


def test_remap_literal_fonts_in_master_txstyles_rewrites_hardcoded_legacy_font():
    """A legacy font can be hardcoded directly in the master's txStyles
    (not via a theme reference) -- neither remap_theme_fonts (theme
    fontScheme only) nor the shape-run font remap (actual shape runs
    only) touches this third, independent place a font name can live."""
    from pptx.oxml.ns import qn

    prs = new_deck()
    master = prs.slide_masters[0]
    tx_styles = master._element.find(qn("p:txStyles"))
    title_lvl1 = tx_styles.find(qn("p:titleStyle")).find(qn("a:lvl1pPr"))
    title_lvl1.find(qn("a:defRPr")).find(qn("a:latin")).set("typeface", "Papyrus")

    changes = remap_literal_fonts_in_master_txstyles(prs, {"Papyrus": "Inter"})

    assert len(changes) == 1
    assert changes[0]["old"] == "Papyrus" and changes[0]["new"] == "Inter"
    assert read_master_style_font(master, "title", 0) == "Inter"


def test_remap_literal_fonts_in_master_txstyles_ignores_theme_references():
    prs = new_deck()
    changes = remap_literal_fonts_in_master_txstyles(prs, {"+mj-lt": "Inter"})
    assert changes == []
