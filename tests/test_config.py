import pytest

from deckguard.config import ConfigError, default_config_path, load_config, validate_config


def test_default_config_loads_and_validates():
    config = load_config(default_config_path())
    errors = validate_config(config, base_dir=default_config_path().parent)
    assert errors == []


def test_default_config_remaps_aptos_to_inter():
    """Regression test for a real bug report: a deck authored/edited in
    current Office inherits its theme font from Aptos/Aptos Display (the
    default since late 2023), not Calibri -- and this project's font
    remap table only listed the older Office defaults. An unmapped
    inherited font stays "manual review" forever AND silently disables
    the text_contrast check for that text (it only applies once a run's
    font resolves to something on the approved list), so a KONE-blue
    panel's own body text never got corrected to white."""
    config = load_config(default_config_path())
    remap = config["fonts"]["remap"]
    assert remap.get("Aptos") == "Inter"
    assert remap.get("Aptos Display") == "Inter"


def test_load_config_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yaml")


def test_load_config_bad_yaml(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("colors: [unterminated", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(p)


def test_validate_rejects_bad_hex(tmp_path):
    config = {
        "brand": {"name": "X"},
        "colors": {"approved": ["#GGGGGG"], "remap": {}},
        "fonts": {"approved": ["Inter"], "remap": {}},
        "typography_rules": {},
        "logo": {"new_logo_path": "assets/logo.png"},
        "layout": {},
        "audit": {},
    }
    errors = validate_config(config, base_dir=tmp_path)
    assert any("invalid hex" in e for e in errors)


def test_validate_rejects_malformed_old_logo_region_in(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n")
    config = {
        "brand": {"name": "X"},
        "colors": {"approved": ["#1450F5"], "remap": {}},
        "fonts": {"approved": ["Inter"], "remap": {}},
        "typography_rules": {},
        "logo": {"new_logo_path": "assets/logo.png", "old_logo_region_in": [1, 2, -3]},
        "layout": {},
        "audit": {},
    }
    errors = validate_config(config, base_dir=tmp_path)
    assert any("old_logo_region_in" in e for e in errors)


def test_validate_accepts_a_well_formed_old_logo_region_in(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n")
    config = {
        "brand": {"name": "X"},
        "colors": {"approved": ["#1450F5"], "remap": {}},
        "fonts": {"approved": ["Inter"], "remap": {}},
        "typography_rules": {},
        "logo": {"new_logo_path": "assets/logo.png", "old_logo_region_in": [10.5, 0.0, 2.8, 1.2]},
        "layout": {},
        "audit": {},
    }
    errors = validate_config(config, base_dir=tmp_path)
    assert not any("old_logo_region_in" in e for e in errors)


def test_validate_rejects_remap_target_not_approved(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n")
    config = {
        "brand": {"name": "X"},
        "colors": {"approved": ["#111111"], "remap": {"#222222": "#333333"}},
        "fonts": {"approved": ["Inter"], "remap": {}},
        "typography_rules": {},
        "logo": {"new_logo_path": "assets/logo.png"},
        "layout": {},
        "audit": {},
    }
    errors = validate_config(config, base_dir=tmp_path)
    assert any("not in colors.approved" in e for e in errors)


def test_validate_rejects_font_remap_target_not_approved(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n")
    config = {
        "brand": {"name": "X"},
        "colors": {"approved": ["#111111"], "remap": {}},
        "fonts": {"approved": ["Inter"], "remap": {"Calibri": "Comic Sans"}},
        "typography_rules": {},
        "logo": {"new_logo_path": "assets/logo.png"},
        "layout": {},
        "audit": {},
    }
    errors = validate_config(config, base_dir=tmp_path)
    assert any("not in fonts.approved" in e for e in errors)


def test_validate_ok_config(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n")
    config = {
        "brand": {"name": "X"},
        "colors": {"approved": ["#111111", "#222222"], "remap": {"#333333": "#111111"}, "tolerance": 0},
        "fonts": {"approved": ["Inter"], "remap": {"Calibri": "Inter"}},
        "typography_rules": {},
        "logo": {"new_logo_path": "assets/logo.png"},
        "layout": {"slide_size": "16:9"},
        "audit": {"fail_on": ["critical"]},
    }
    errors = validate_config(config, base_dir=tmp_path)
    assert errors == []
