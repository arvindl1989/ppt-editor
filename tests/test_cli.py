import json

import pytest
from click.testing import CliRunner

from deckguard.cli import main
from tests.helpers import add_slide, new_deck, set_run, title_run


def _write_violating_deck(path):
    prs = new_deck()
    slide = add_slide(prs)
    set_run(title_run(slide), text="Title", font="Calibri", color_hex="005EB8")
    prs.save(str(path))


def _write_clean_deck(path):
    from pptx.enum.text import PP_ALIGN

    from tests.helpers import body_run, set_theme_font, set_theme_slot

    prs = new_deck()
    set_theme_slot(prs, "dk1", "141414")
    set_theme_font(prs, "majorFont", "Inter")
    set_theme_font(prs, "minorFont", "Inter")
    slide = add_slide(prs)
    set_run(title_run(slide), text="Title", font="Inter Semi Bold", color_hex="141414")
    slide.shapes.title.text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    set_run(body_run(slide), text="Body copy", font="Inter", color_hex="141414")
    slide.placeholders[1].text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    prs.save(str(path))


def test_validate_rules_default_ok():
    runner = CliRunner()
    result = runner.invoke(main, ["validate-rules"])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_validate_rules_bad_file(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("colors: {approved: ['#GGGGGG']}", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, ["validate-rules", str(bad)])
    assert result.exit_code == 1


def test_inspect_json_is_valid_json(tmp_path):
    deck = tmp_path / "d.pptx"
    _write_violating_deck(deck)
    runner = CliRunner()
    result = runner.invoke(main, ["inspect", str(deck), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["slides"][0]["shapes"]


def test_audit_exits_nonzero_when_critical_violation_present(tmp_path):
    deck = tmp_path / "d.pptx"
    _write_violating_deck(deck)
    runner = CliRunner()
    result = runner.invoke(main, ["audit", str(deck), "--format", "json"])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["summary"]["critical"] >= 1


def test_audit_exits_zero_for_clean_deck(tmp_path):
    deck = tmp_path / "clean.pptx"
    _write_clean_deck(deck)
    runner = CliRunner()
    result = runner.invoke(main, ["audit", str(deck), "--format", "json"])
    assert result.exit_code == 0


def test_audit_folder_mode_writes_summary_csv(tmp_path):
    _write_violating_deck(tmp_path / "a.pptx")
    _write_clean_deck(tmp_path / "b.pptx")
    out_dir = tmp_path / "reports"
    runner = CliRunner()
    result = runner.invoke(main, ["audit", str(tmp_path), "--out", str(out_dir)])
    assert (out_dir / "summary.csv").exists()
    content = (out_dir / "summary.csv").read_text()
    assert "a.pptx" in content and "b.pptx" in content


def test_fix_dry_run_leaves_source_untouched(tmp_path):
    deck = tmp_path / "d.pptx"
    _write_violating_deck(deck)
    original = deck.read_bytes()

    runner = CliRunner()
    result = runner.invoke(main, ["fix", str(deck), "--dry-run", "--out", str(tmp_path / "out")])
    assert result.exit_code == 0
    assert deck.read_bytes() == original
    assert not (tmp_path / "out" / "d_fixed.pptx").exists()
    assert (tmp_path / "out" / "d_changelog.json").exists()
    assert (tmp_path / "out" / "d_changelog.md").exists()


def test_fix_writes_fixed_file(tmp_path):
    deck = tmp_path / "d.pptx"
    _write_violating_deck(deck)

    runner = CliRunner()
    result = runner.invoke(main, ["fix", str(deck), "--out", str(tmp_path / "out")])
    assert result.exit_code == 0
    assert (tmp_path / "out" / "d_fixed.pptx").exists()


def test_hash_logo_prints_hash(tmp_path):
    from tests.helpers import make_pattern_png

    img = make_pattern_png(tmp_path / "logo.png", seed=9)
    runner = CliRunner()
    result = runner.invoke(main, ["hash-logo", str(img)])
    assert result.exit_code == 0
    assert len(result.stdout.strip()) == 16


def test_inspect_on_corrupt_file_gives_clean_error(tmp_path):
    bad = tmp_path / "not_a_deck.pptx"
    bad.write_bytes(b"not a real pptx file")
    runner = CliRunner()
    result = runner.invoke(main, ["inspect", str(bad)])
    assert result.exit_code == 1
    assert "error" in result.output.lower()
    assert "Traceback" not in result.output


def test_migrate_replaces_non_standard_cover_and_outro(tmp_path):
    from deckguard.slide_import import default_template_path

    if not default_template_path().exists():
        pytest.skip("bundled template asset not present")

    deck = tmp_path / "d.pptx"
    _write_violating_deck(deck)  # a single, non-KONE-layout slide
    runner = CliRunner()
    result = runner.invoke(main, ["migrate", str(deck), "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "cover replaced" in result.output
    assert "outro replaced" in result.output
    assert (tmp_path / "d_migrated.pptx").exists()


def test_redesign_mode_brand_needs_no_api_key(tmp_path, monkeypatch):
    """--mode brand is fully deterministic -- unlike --mode rewrite
    (default), it must run with no ANTHROPIC_API_KEY set at all."""
    from deckguard.slide_import import default_template_path

    if not default_template_path().exists():
        pytest.skip("bundled template asset not present")

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    deck = tmp_path / "d.pptx"
    _write_violating_deck(deck)
    out_path = tmp_path / "rebranded.pptx"

    runner = CliRunner()
    result = runner.invoke(main, ["redesign", str(deck), "--out", str(out_path), "--mode", "brand"])

    assert result.exit_code == 0, result.output
    assert "mode: brand" in result.output
    assert out_path.exists()


def test_redesign_mode_rewrite_still_requires_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    deck = tmp_path / "d.pptx"
    _write_violating_deck(deck)
    out_path = tmp_path / "out.pptx"

    runner = CliRunner()
    result = runner.invoke(main, ["redesign", str(deck), "--out", str(out_path)])

    assert result.exit_code == 1
    assert "ANTHROPIC_API_KEY is not set" in result.output


def test_redesign_mode_brand_without_deck_errors_cleanly(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, ["redesign", "--out", str(tmp_path / "out.pptx"), "--mode", "brand"])

    assert result.exit_code == 1
    assert "needs a DECK" in result.output


def test_redesign_mode_brand_with_review_requires_api_key(tmp_path, monkeypatch):
    """Unlike plain --mode brand, --review makes one small API call and
    needs a key even though the rest of brand mode doesn't."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    deck = tmp_path / "d.pptx"
    _write_violating_deck(deck)
    runner = CliRunner()
    result = runner.invoke(
        main, ["redesign", str(deck), "--out", str(tmp_path / "out.pptx"), "--mode", "brand", "--review"]
    )

    assert result.exit_code == 1
    assert "ANTHROPIC_API_KEY is not set" in result.output


def test_redesign_review_rejects_rewrite_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    deck = tmp_path / "d.pptx"
    _write_violating_deck(deck)
    runner = CliRunner()
    result = runner.invoke(
        main, ["redesign", str(deck), "--out", str(tmp_path / "out.pptx"), "--mode", "rewrite", "--review"]
    )

    assert result.exit_code == 1
    assert "--review only applies to --mode brand" in result.output
