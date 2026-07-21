import json

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


def test_migrate_stub(tmp_path):
    deck = tmp_path / "d.pptx"
    template = tmp_path / "t.pptx"
    _write_violating_deck(deck)
    _write_violating_deck(template)
    runner = CliRunner()
    result = runner.invoke(main, ["migrate", str(deck), "--template", str(template)])
    assert result.exit_code == 0
    assert "not yet implemented" in result.output
