"""Deterministic fix engine.

Runs in two stages:

1. Deck-wide: theme color remap, theme font remap, and explicit font
   overrides on master/layout placeholders. These correct every
   downstream shape that inherits from them in one operation.
2. Per-violation, to a fixpoint: re-audits the (now theme-corrected) deck
   and applies every `auto_fixable` violation directly via the live
   object each `Violation.target` record points at, then repeats until a
   pass makes no further changes. Looping matters because fixing one
   thing on a run (e.g. its font) can newly unlock another check on that
   same run (e.g. that font's allowed text colors) — a single pass would
   otherwise leave mechanically-resolvable cases in "manual review".

Never touches the input file — callers pass a `Presentation` already
loaded from a copy, and `--dry-run` simply skips the final `prs.save()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_COLOR_TYPE
from pptx.enum.shapes import MSO_SHAPE_TYPE

from deckguard import colors as colors_mod
from deckguard import effects as effects_mod
from deckguard import logo as logo_mod
from deckguard.fonts import FontTables, normalize_key, remap_theme_fonts
from deckguard.inventory import ALIGN_BY_NAME, build_inventory
from deckguard.rules_engine import Violation, audit_deck, sort_violations, summarize


@dataclass
class Change:
    scope: str  # "theme" | "master" | "layout" | "slide"
    rule: str
    field: str
    old: object
    new: object
    slide_index: int = 0
    shape_id: Optional[int] = None
    shape_name: Optional[str] = None
    location: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "scope": self.scope,
            "rule": self.rule,
            "field": self.field,
            "old": self.old,
            "new": self.new,
            "slide_index": self.slide_index,
            "shape_id": self.shape_id,
            "shape_name": self.shape_name,
            "location": self.location,
        }


@dataclass
class FixReport:
    source_path: str
    output_path: Optional[str]
    dry_run: bool
    changes: list = field(default_factory=list)
    manual_review: list = field(default_factory=list)  # list[Violation], auto_fixable=False

    @property
    def summary(self) -> dict:
        s = summarize(self.manual_review) if self.manual_review else {"critical": 0, "major": 0, "minor": 0}
        return {
            "changes_applied": len(self.changes),
            "manual_review_required": len(self.manual_review),
            "manual_review_by_severity": {
                k: s.get(k, 0) for k in ("critical", "major", "minor")
            },
        }


def _remap_explicit_fonts_in_masters_and_layouts(prs, font_remap: dict[str, str]) -> list[Change]:
    """Fix explicit (non-inherited) font overrides on master/layout placeholders.

    Theme fontScheme remap (see fonts.remap_theme_fonts) already fixes
    everything that inherits the default; this catches shapes on a
    master/layout that set a legacy font name directly.
    """
    changes: list[Change] = []
    remap_by_key = {normalize_key(k): v for k, v in font_remap.items()}
    if not remap_by_key:
        return changes

    seen_masters = set()
    for master in colors_mod.iter_slide_masters(prs):
        if id(master.part) not in seen_masters:
            seen_masters.add(id(master.part))
            changes += _remap_shapes_fonts(master.shapes, remap_by_key, "master", master.name)
        for layout in master.slide_layouts:
            changes += _remap_shapes_fonts(layout.shapes, remap_by_key, "layout", layout.name)
    return changes


def _remap_shapes_fonts(shapes, remap_by_key: dict[str, str], scope: str, location: str) -> list[Change]:
    changes = []
    for shape in shapes:
        if getattr(shape, "shape_type", None) == MSO_SHAPE_TYPE.GROUP:
            changes += _remap_shapes_fonts(shape.shapes, remap_by_key, scope, location)
        if not getattr(shape, "has_text_frame", False):
            continue
        for para in shape.text_frame.paragraphs:
            for run in para.runs:
                current = run.font.name
                target = remap_by_key.get(normalize_key(current))
                if target and target != current:
                    run.font.name = target
                    changes.append(
                        Change(
                            scope=scope,
                            rule="legacy_font",
                            field="font",
                            old=current,
                            new=target,
                            shape_id=shape.shape_id,
                            shape_name=shape.name,
                            location=location,
                        )
                    )
    return changes


def _apply_violation(v: Violation, config: dict) -> Optional[Change]:
    target = v.target
    if target is None:
        return None

    if v.rule in ("legacy_color", "near_miss_color"):
        new_hex = v.details["target"].lstrip("#")
        old_hex = v.details["current"]
        if v.element == "fill":
            color_fmt = target.obj.fill.fore_color
        elif v.element == "line":
            color_fmt = target.obj.line.color
        elif v.element == "gradient stop":
            idx = v.details.get("gradient_index", 0)
            color_fmt = target.obj.fill.gradient_stops[idx].color
        elif v.element == "text":
            color_fmt = target.obj.font.color
        else:
            return None
        if color_fmt.type != MSO_COLOR_TYPE.RGB:
            # Scheme-typed color that survived the theme-level pass (e.g. a
            # different theme not covered, or an out-of-range tint) — leave
            # it for manual review rather than silently converting it to a
            # hardcoded literal.
            return None
        color_fmt.rgb = RGBColor.from_string(new_hex)
        return Change(
            scope="slide",
            rule=v.rule,
            field=f"{v.element} color",
            old=old_hex,
            new=v.details["target"],
            slide_index=v.slide_index,
            shape_id=v.shape_id,
            shape_name=v.shape_name,
        )

    if v.rule == "unapproved_font":
        target_font = v.details.get("target")
        if not target_font:
            return None
        old_font = target.font_raw
        target.obj.font.name = target_font
        return Change(
            scope="slide",
            rule=v.rule,
            field="font",
            old=old_font,
            new=target_font,
            slide_index=v.slide_index,
            shape_id=v.shape_id,
            shape_name=v.shape_name,
        )

    if v.rule == "text_color":
        new_hex = v.details["target"].lstrip("#")
        target.obj.font.color.rgb = RGBColor.from_string(new_hex)
        return Change(
            scope="slide",
            rule=v.rule,
            field="text color",
            old=v.details["current"],
            new=v.details["target"],
            slide_index=v.slide_index,
            shape_id=v.shape_id,
            shape_name=v.shape_name,
        )

    if v.rule == "text_effect":
        if v.element == "run":
            removed = effects_mod.remove_run_effects(target.obj)
        else:
            removed = effects_mod.remove_shape_effects(target.obj)
        if not removed:
            return None
        return Change(
            scope="slide",
            rule=v.rule,
            field="effects",
            old=sorted(removed),
            new=[],
            slide_index=v.slide_index,
            shape_id=v.shape_id,
            shape_name=v.shape_name,
        )

    if v.rule == "alignment":
        new_align = v.details["target"]
        target.obj.alignment = ALIGN_BY_NAME.get(new_align)
        return Change(
            scope="slide",
            rule=v.rule,
            field="alignment",
            old=v.details["current"],
            new=new_align,
            slide_index=v.slide_index,
            shape_id=v.shape_id,
            shape_name=v.shape_name,
        )

    if v.rule == "old_logo":
        logo_cfg = config.get("logo", {}) or {}
        new_logo_path = logo_cfg.get("new_logo_path")
        if not new_logo_path or not Path(new_logo_path).exists():
            return None
        logo_mod.replace_logo_image(target.obj, new_logo_path)
        return Change(
            scope="slide",
            rule=v.rule,
            field="image",
            old=v.details.get("matched"),
            new=new_logo_path,
            slide_index=v.slide_index,
            shape_id=v.shape_id,
            shape_name=v.shape_name,
        )

    return None


def fix_deck(prs, config: dict, source_path: str, output_path: Optional[str], dry_run: bool) -> FixReport:
    colors_cfg = config.get("colors", {}) or {}
    remap = {colors_mod.normalize_hex(k): v for k, v in (colors_cfg.get("remap", {}) or {}).items()}
    fonts_cfg = config.get("fonts", {}) or {}
    font_remap = fonts_cfg.get("remap", {}) or {}

    changes: list[Change] = []

    theme_color_changes = colors_mod.remap_theme_colors(prs, remap)
    for c in theme_color_changes:
        changes.append(
            Change(
                scope="theme",
                rule="legacy_color",
                field="theme color",
                old=c["old"],
                new=c["new"],
                location=f"{c['theme_part']} [{c['slot']}]",
            )
        )

    theme_font_changes = remap_theme_fonts(prs, font_remap)
    for c in theme_font_changes:
        changes.append(
            Change(
                scope="theme",
                rule="legacy_font",
                field="theme font",
                old=c["old"],
                new=c["new"],
                location=f"{c['theme_part']} [{c['slot']}]",
            )
        )

    changes += _remap_explicit_fonts_in_masters_and_layouts(prs, font_remap)

    # Apply auto-fixable violations to a fixpoint. Fixing one violation can
    # mechanically unlock another check on the very same run — e.g. renaming
    # an off-brand font from Arial to Inter means Inter's text-color rule
    # now applies to that run for the first time, and its existing color may
    # no longer be allowed. That's not ambiguous, just sequential, so a
    # single pass would wrongly leave it for "manual review" when it's
    # actually fully resolvable. Loop until a pass makes no further changes;
    # capped defensively since each pass only ever unlocks checks that were
    # previously gated on a now-fixed field, so this converges in a couple
    # of iterations for any real rule set.
    for _ in range(5):
        inventory = build_inventory(prs)
        violations = sort_violations(audit_deck(inventory, config))
        pass_changes = []
        for v in violations:
            if not v.auto_fixable:
                continue
            change = _apply_violation(v, config)
            if change:
                pass_changes.append(change)
        changes += pass_changes
        if not pass_changes:
            break

    # Anything still detected here needs a human either way: genuinely
    # unfixable violations, or (defensively) anything a fix attempt didn't
    # actually clear.
    manual_review = sort_violations(audit_deck(build_inventory(prs), config))

    if not dry_run and output_path:
        prs.save(output_path)

    return FixReport(
        source_path=source_path,
        output_path=None if dry_run else output_path,
        dry_run=dry_run,
        changes=changes,
        manual_review=manual_review,
    )
