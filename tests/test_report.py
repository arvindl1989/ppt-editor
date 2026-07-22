from deckguard.fixer import Change, FixReport
from deckguard.report import remap_overrides_summary


def _report(changes):
    return FixReport(source_path="in.pptx", output_path="out.pptx", dry_run=False, changes=changes)


def test_remap_overrides_summary_aggregates_color_changes_by_old_value():
    changes = [
        Change(scope="slide", rule="legacy_color", field="fill color", old="#005EB8", new="#1450F5", slide_index=1),
        Change(scope="slide", rule="legacy_color", field="line color", old="#005EB8", new="#1450F5", slide_index=2),
        Change(scope="theme", rule="legacy_color", field="theme color", old="#F3EEEA", new="#F3EEE6"),
    ]
    summary = remap_overrides_summary(_report(changes))
    by_old = {c["old_hex"]: c for c in summary["colors"]}
    assert by_old["005EB8"] == {"old_hex": "005EB8", "new_hex": "1450F5", "count": 2}
    assert by_old["F3EEEA"]["count"] == 1
    assert summary["fonts"] == []


def test_remap_overrides_summary_aggregates_font_changes_by_old_value():
    changes = [
        Change(scope="slide", rule="unapproved_font", field="font", old="Calibri", new="Inter", slide_index=1),
        Change(scope="theme", rule="legacy_font", field="theme font", old="Calibri", new="Inter"),
    ]
    summary = remap_overrides_summary(_report(changes))
    assert summary["colors"] == []
    assert summary["fonts"] == [{"old_font": "Calibri", "new_font": "Inter", "count": 2}]


def test_remap_overrides_summary_excludes_derived_text_contrast_changes():
    """text_contrast's target depends on the shape's own background, not a
    fixed palette entry -- there's nothing meaningful to override at the
    old-value level, so these must never show up in the remap table."""
    changes = [
        Change(scope="slide", rule="text_contrast", field="text color", old="#141414", new="#FFFFFF", slide_index=1),
    ]
    summary = remap_overrides_summary(_report(changes))
    assert summary == {"colors": [], "fonts": []}


def test_remap_overrides_summary_ignores_non_color_fields_for_color_rules():
    """rule=legacy_color always implies a color field in practice, but the
    aggregator should not choke on/misfile an unexpected field pairing."""
    changes = [
        Change(scope="slide", rule="legacy_color", field="effects", old="bad", new="data", slide_index=1),
    ]
    summary = remap_overrides_summary(_report(changes))
    assert summary == {"colors": [], "fonts": []}
