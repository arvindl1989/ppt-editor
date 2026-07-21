from deckguard.fonts import FontTables, canonical_key, normalize_key, remap_theme_fonts
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
