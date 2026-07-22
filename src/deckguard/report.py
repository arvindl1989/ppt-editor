"""Rendering: inspect/audit/fix reports as JSON, Markdown, or CSV."""

from __future__ import annotations

import csv
import dataclasses
import io
import json
from datetime import datetime, timezone

SEVERITY_ICON = {"critical": "🔴", "major": "🟠", "minor": "🟡"}


def _clean(value):
    """Recursively convert dataclasses/sets to JSON-safe plain structures,
    dropping the live python-pptx/lxml object references (`obj`, `target`)."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        out = {}
        for f in dataclasses.fields(value):
            if f.name in ("obj", "target"):
                continue
            out[f.name] = _clean(getattr(value, f.name))
        return out
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, set):
        return sorted(_clean(v) for v in value)
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    return value


def to_json(value) -> str:
    return json.dumps(_clean(value), indent=2, default=str)


# --------------------------------------------------------------------------
# inspect
# --------------------------------------------------------------------------


def inventory_to_dict(inventory) -> dict:
    return _clean(inventory)


def render_inventory_md(inventory, deck_name: str) -> str:
    lines = [f"# Inventory — {deck_name}", ""]
    lines.append(f"- Slide size: {inventory.aspect_ratio} ({inventory.slide_width_emu}x{inventory.slide_height_emu} EMU)")
    lines.append(f"- Slides: {len(inventory.slides)}")
    lines.append("")
    for slide in inventory.slides:
        lines.append(f"## Slide {slide.index} — layout: {slide.layout_name} (master: {slide.master_name})")
        for shape in slide.shapes:
            lines.append(f"- **{shape.name}** ({shape.shape_type}) @ ({shape.left_in}, {shape.top_in}) in, "
                          f"{shape.width_in}x{shape.height_in} in")
            if shape.fill and shape.fill.type not in ("inherited", "none", None):
                colors = ", ".join(f"#{c.hex}" for c in shape.fill.colors if c.hex)
                lines.append(f"  - fill: {shape.fill.type} {colors}")
            if shape.line and shape.line.color and shape.line.color.hex:
                lines.append(f"  - line: #{shape.line.color.hex}")
            if shape.effects:
                lines.append(f"  - effects: {', '.join(sorted(shape.effects))}")
            if shape.image:
                lines.append(f"  - image: {shape.image.filename} phash={shape.image.phash}")
            for para in shape.paragraphs:
                for run in para.runs:
                    if not run.text.strip():
                        continue
                    color = f"#{run.color.hex}" if run.color and run.color.hex else "-"
                    fx = f" effects={sorted(run.effects)}" if run.effects else ""
                    lines.append(
                        f"  - text {run.text!r}: font={run.font_raw!r} bold={run.bold} "
                        f"size={run.size_pt}pt color={color} align={para.alignment}{fx}"
                    )
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# audit
# --------------------------------------------------------------------------


def audit_summary_dict(deck_name: str, violations, summary: dict) -> dict:
    return {
        "deck": deck_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "violations": [_violation_dict(v) for v in violations],
    }


def _violation_dict(v) -> dict:
    d = _clean(v)
    return d


def render_audit_md(deck_name: str, violations, summary: dict) -> str:
    lines = [f"# Audit report — {deck_name}", ""]
    lines.append(
        f"**{summary['total']} violations** — "
        f"{summary['critical']} critical, {summary['major']} major, {summary['minor']} minor "
        f"({summary['auto_fixable']} auto-fixable)"
    )
    lines.append("")
    if not violations:
        lines.append("No violations found.")
        return "\n".join(lines)

    lines.append("| Slide | Severity | Rule | Element | Shape | Message | Auto-fixable | Source |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for v in violations:
        icon = SEVERITY_ICON.get(v.severity, "")
        lines.append(
            f"| {v.slide_index} | {icon} {v.severity} | {v.rule} | {v.element} | "
            f"{v.shape_name or ''} | {v.message} | {'yes' if v.auto_fixable else 'no'} | {v.source} |"
        )
    return "\n".join(lines)


def render_audit_csv(violations) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["slide_index", "severity", "rule", "element", "shape_id", "shape_name", "message", "auto_fixable", "source"])
    for v in violations:
        writer.writerow([v.slide_index, v.severity, v.rule, v.element, v.shape_id, v.shape_name, v.message, v.auto_fixable, v.source])
    return buf.getvalue()


def render_batch_summary_csv(rows: list[dict]) -> str:
    """rows: [{deck, slides, critical, major, minor, total, pct_auto_fixable}, ...]"""
    buf = io.StringIO()
    fieldnames = ["deck", "slides", "critical", "major", "minor", "total", "pct_auto_fixable"]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


# --------------------------------------------------------------------------
# fix
# --------------------------------------------------------------------------


def fix_report_to_dict(report) -> dict:
    return {
        "source": report.source_path,
        "output": report.output_path,
        "dry_run": report.dry_run,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": report.summary,
        "changes": [c.to_dict() for c in report.changes],
        "manual_review": [_violation_dict(v) for v in report.manual_review],
    }


def remap_overrides_summary(report) -> dict:
    """Aggregate a fix run's applied color/font changes into unique
    old->new pairs, for the web UI's review-and-override table.

    Scoped to rules that represent a static palette remap (legacy_color,
    near_miss_color, unapproved_font, legacy_font) -- these have one
    deterministic target per old value, so redirecting that target to a
    different brand-approved color/font and re-running is safe. Excludes
    per-instance derived decisions like text_contrast (the target there
    depends on the shape's own background, not a fixed palette entry, so
    there's nothing meaningful to override at the "old value" level).
    """
    colors: dict[str, dict] = {}
    fonts: dict[str, dict] = {}
    color_fields = {"fill color", "line color", "gradient stop color", "theme color", "text color"}
    font_fields = {"font", "theme font", "master default font"}
    for c in report.changes:
        if c.rule in ("legacy_color", "near_miss_color") and c.field in color_fields:
            old = str(c.old).lstrip("#").upper()
            new = str(c.new).lstrip("#").upper()
            if len(old) != 6 or len(new) != 6:
                continue
            entry = colors.setdefault(old, {"old_hex": old, "new_hex": new, "count": 0})
            entry["count"] += 1
        elif c.rule in ("unapproved_font", "legacy_font") and c.field in font_fields:
            old, new = str(c.old), str(c.new)
            if not old or not new:
                continue
            entry = fonts.setdefault(old, {"old_font": old, "new_font": new, "count": 0})
            entry["count"] += 1
    return {
        "colors": sorted(colors.values(), key=lambda x: -x["count"]),
        "fonts": sorted(fonts.values(), key=lambda x: -x["count"]),
    }


def render_fix_md(report) -> str:
    lines = [f"# Fix report — {report.source_path}", ""]
    mode = "DRY RUN (no file written)" if report.dry_run else f"Output: `{report.output_path}`"
    lines.append(mode)
    lines.append("")
    lines.append(f"**{len(report.changes)} changes applied**, **{len(report.manual_review)} need manual review**")
    lines.append("")

    if report.changes:
        lines.append("## Changes")
        lines.append("| Scope | Slide | Shape | Rule | Field | Old | New | Location |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for c in report.changes:
            lines.append(
                f"| {c.scope} | {c.slide_index or ''} | {c.shape_name or ''} | {c.rule} | {c.field} | "
                f"{c.old} | {c.new} | {c.location or ''} |"
            )
        lines.append("")

    if report.manual_review:
        lines.append("## Manual review required")
        lines.append("| Slide | Severity | Rule | Shape | Message |")
        lines.append("|---|---|---|---|---|")
        for v in report.manual_review:
            icon = SEVERITY_ICON.get(v.severity, "")
            lines.append(f"| {v.slide_index} | {icon} {v.severity} | {v.rule} | {v.shape_name or ''} | {v.message} |")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# learn
# --------------------------------------------------------------------------

CONFIDENCE_ICON = {"high": "✅", "low": "❓"}


def learn_result_to_dict(result) -> dict:
    return _clean(result)


def render_learn_md(result, old_name: str, new_name: str) -> str:
    lines = [f"# Learned brand differences — {old_name} → {new_name}", ""]
    all_proposals = result.color_proposals + result.font_proposals + result.layout_panel_proposals
    n_high = sum(1 for p in all_proposals if p.confidence == "high")
    n_low = sum(1 for p in all_proposals if p.confidence == "low")
    lines.append(f"**{n_high} high-confidence**, **{n_low} low-confidence** proposals; "
                 f"{len(result.unmatched_old_colors)} unmatched color(s), "
                 f"{len(result.unmatched_old_fonts)} unmatched font(s)")
    lines.append("")

    if result.color_proposals:
        lines.append("## Color proposals")
        lines.append("| | Role | Old | New | Old count | New count |")
        lines.append("|---|---|---|---|---|---|")
        for p in result.color_proposals:
            icon = CONFIDENCE_ICON.get(p.confidence, "")
            lines.append(f"| {icon} {p.confidence} | {p.role} | #{p.old_hex} | #{p.new_hex} | {p.old_count} | {p.new_count} |")
        lines.append("")

    if result.layout_panel_proposals:
        lines.append("## Layout background-panel proposals")
        lines.append("_Large background panels defined on a slide layout (not any slide) — "
                      "invisible to ordinary slide-level color remap._")
        lines.append("")
        lines.append("| | Layout | Old shape | New shape | Old | New | Area (in²) |")
        lines.append("|---|---|---|---|---|---|---|")
        for p in result.layout_panel_proposals:
            icon = CONFIDENCE_ICON.get(p.confidence, "")
            lines.append(
                f"| {icon} {p.confidence} | {p.layout_name} | {p.old_shape_name} | {p.new_shape_name} "
                f"| #{p.old_hex} | #{p.new_hex} | {p.area_sq_in} |"
            )
        lines.append("")

    if result.font_proposals:
        lines.append("## Font proposals")
        lines.append("| | Old | New | Old count | New count |")
        lines.append("|---|---|---|---|---|")
        for p in result.font_proposals:
            icon = CONFIDENCE_ICON.get(p.confidence, "")
            old_label = f"{p.old_font}" + (" (bold)" if p.old_bold else "")
            new_label = f"{p.new_font}" + (" (bold)" if p.new_bold else "")
            lines.append(f"| {icon} {p.confidence} | {old_label} | {new_label} | {p.old_count} | {p.new_count} |")
        lines.append("")

    if result.unmatched_old_colors:
        lines.append("## Unmatched colors (in old deck, no confident match in new deck)")
        lines.append("| Role | Hex | Count |")
        lines.append("|---|---|---|")
        for role, hexval, count in result.unmatched_old_colors:
            lines.append(f"| {role} | #{hexval} | {count} |")
        lines.append("")

    if result.unmatched_old_fonts:
        lines.append("## Unmatched fonts")
        lines.append("| Font | Bold | Count |")
        lines.append("|---|---|---|")
        for name, bold, count in result.unmatched_old_fonts:
            lines.append(f"| {name} | {bold} | {count} |")

    return "\n".join(lines)
