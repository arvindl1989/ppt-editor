import hashlib

from pptx import Presentation
from pptx.enum.text import PP_ALIGN

from deckguard.config import load_config, default_config_path
from deckguard.fixer import fix_deck
from deckguard.inventory import build_inventory
from deckguard.rules_engine import audit_deck
from tests.helpers import (
    add_shadow_effect,
    add_slide,
    body_run,
    new_deck,
    set_run,
    set_theme_font,
    set_theme_slot,
    title_run,
)

CONFIG = load_config(default_config_path())


def _violating_deck():
    prs = new_deck()
    slide = add_slide(prs)
    set_run(title_run(slide), text="Title", font="Calibri", color_hex="005EB8")
    run = set_run(body_run(slide), text="body copy", font="Inter", color_hex="141414")
    add_shadow_effect(run)
    slide.placeholders[1].text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    set_theme_slot(prs, "accent1", "005EB8")
    set_theme_font(prs, "majorFont", "Calibri")
    set_theme_font(prs, "minorFont", "Calibri")
    return prs


def test_fix_applies_changes_and_reduces_violations(tmp_path):
    prs = _violating_deck()
    before_count = len(audit_deck(build_inventory(prs), CONFIG))

    out_path = tmp_path / "out.pptx"
    report = fix_deck(prs, CONFIG, source_path="in.pptx", output_path=str(out_path), dry_run=False)

    assert len(report.changes) > 0
    assert out_path.exists()

    saved = Presentation(str(out_path))
    after_count = len(audit_deck(build_inventory(saved), CONFIG))
    assert after_count < before_count


def test_fix_dry_run_writes_no_output_file(tmp_path):
    prs = _violating_deck()
    out_path = tmp_path / "out.pptx"

    report = fix_deck(prs, CONFIG, source_path="in.pptx", output_path=str(out_path), dry_run=True)

    assert report.dry_run is True
    assert report.output_path is None
    assert not out_path.exists()
    # dry-run still computes what *would* change, for the preview/changelog
    assert len(report.changes) > 0


def test_fix_never_touches_the_source_file(tmp_path):
    src_path = tmp_path / "source.pptx"
    _violating_deck().save(str(src_path))
    original_bytes = src_path.read_bytes()
    original_hash = hashlib.sha256(original_bytes).hexdigest()

    prs = Presentation(str(src_path))
    out_path = tmp_path / "fixed.pptx"
    fix_deck(prs, CONFIG, source_path=str(src_path), output_path=str(out_path), dry_run=False)

    assert src_path.read_bytes() == original_bytes
    assert hashlib.sha256(src_path.read_bytes()).hexdigest() == original_hash
    assert out_path.exists()
    assert out_path.read_bytes() != original_bytes


def test_fix_is_idempotent_on_a_clean_deck():
    prs = new_deck()
    # python-pptx's default template theme is itself legacy (black
    # dk1, Calibri major/minor font) — bring it up to brand first so this
    # test reflects a deck that's *already* on-brand, not the stock template.
    set_theme_slot(prs, "dk1", "141414")
    set_theme_font(prs, "majorFont", "Inter")
    set_theme_font(prs, "minorFont", "Inter")

    slide = add_slide(prs)
    set_run(title_run(slide), text="Title", font="Inter Semi Bold", color_hex="141414")
    set_run(body_run(slide), text="Body copy", font="Inter", color_hex="141414")
    slide.placeholders[1].text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT

    report = fix_deck(prs, CONFIG, source_path="clean.pptx", output_path=None, dry_run=True)
    # Nothing to fix except the (unfixable) slide-size mismatch of the
    # default python-pptx template.
    assert report.changes == []
    assert all(v.rule == "slide_size" for v in report.manual_review)


def test_fix_report_summary_counts_match():
    prs = _violating_deck()
    report = fix_deck(prs, CONFIG, source_path="in.pptx", output_path=None, dry_run=True)
    summary = report.summary
    assert summary["changes_applied"] == len(report.changes)
    assert summary["manual_review_required"] == len(report.manual_review)
