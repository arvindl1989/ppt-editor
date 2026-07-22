"""XML-only audit: apply brand_rules.yaml to a DeckInventory, emit violations.

Severity mapping (per spec):
  critical — old logo present, old KONE Blue (or its tints), non-approved
             font in a heading
  major    — any other non-approved/off-brand color, an approved
             body font used in a non-approved text color, forbidden
             all-caps usage, a decorative-only font used as heading/body,
             forbidden text effects
  minor    — alignment violations, sub-minimum text sizes, near-miss
             colors within tolerance

This module never calls the Anthropic API — everything here is decidable
from the parsed XML tree alone. Judgment calls (layout consistency, "used
sparingly", clear-space) are Phase 2 AI-audit territory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from deckguard import colors as colors_mod
from deckguard import logo as logo_mod
from deckguard.fonts import FontTables
from deckguard.inventory import DeckInventory, ShapeRecord, iter_shapes_recursive

HEADING_PLACEHOLDER_TYPES = {"TITLE", "CENTER_TITLE"}
OLD_KONE_BLUE = "005EB8"


@dataclass
class Violation:
    slide_index: int
    shape_id: Optional[int]
    shape_name: str
    element: str
    rule: str
    message: str
    severity: str  # critical | major | minor
    auto_fixable: bool
    source: str = "xml"
    details: dict = field(default_factory=dict)
    # The record (ShapeRecord/RunRecord/ParagraphRecord) the fixer should
    # mutate for this violation. Not serialized in reports.
    target: object = field(default=None, repr=False, compare=False)


def _is_heading(shape: ShapeRecord) -> bool:
    return shape.placeholder_type in HEADING_PLACEHOLDER_TYPES


def _is_exception_candidate(shape: ShapeRecord, text: str, slide_height_in: Optional[float]) -> bool:
    """Heuristic for pagination/footnote/navigation text — see typography_rules.alignment.

    Deliberately conservative: only skip the alignment rule when the
    heuristic is confident (numeric-only content in a small box near a
    slide edge). Anything ambiguous still gets flagged (as minor), per
    the spec's "prefer false positives over silent misses".
    """
    stripped = text.strip()
    if not stripped:
        return False
    numeric_like = all(c.isdigit() or c in ".-/%–— " for c in stripped)
    if not numeric_like:
        return False
    small_box = (shape.width_in or 99) < 2.5 and (shape.height_in or 99) < 0.6
    near_edge = False
    if slide_height_in and shape.top_in is not None:
        near_edge = shape.top_in < 0.75 or shape.top_in > slide_height_in - 0.9
    return small_box and near_edge


def _color_violations(
    color_info,
    element: str,
    slide_idx: int,
    shape: ShapeRecord,
    colors_cfg: dict,
    approved_hexes: set[str],
    remap: dict[str, str],
    tolerance: float,
    target=None,
    extra_details: Optional[dict] = None,
) -> list[Violation]:
    if color_info is None or color_info.kind == "none" or not color_info.hex:
        return []
    hexval = color_info.hex
    violations: list[Violation] = []
    base_details = dict(extra_details or {})

    if hexval in remap:
        new_hex = colors_mod.normalize_hex(remap[hexval])
        severity = "critical" if hexval == OLD_KONE_BLUE else "major"
        violations.append(
            Violation(
                slide_index=slide_idx,
                shape_id=shape.shape_id,
                shape_name=shape.name,
                element=element,
                rule="legacy_color",
                message=f"legacy color #{hexval} should be remapped to #{new_hex}",
                severity=severity,
                auto_fixable=True,
                details={**base_details, "current": f"#{hexval}", "target": f"#{new_hex}"},
                target=target,
            )
        )
        return violations

    if hexval in approved_hexes:
        return []

    if tolerance > 0:
        rgb = colors_mod.hex_to_rgb(hexval)
        nearest = min(
            approved_hexes,
            key=lambda h: colors_mod.rgb_distance(rgb, colors_mod.hex_to_rgb(h)),
            default=None,
        )
        if nearest is not None:
            dist = colors_mod.rgb_distance(rgb, colors_mod.hex_to_rgb(nearest))
            if dist <= tolerance:
                violations.append(
                    Violation(
                        slide_index=slide_idx,
                        shape_id=shape.shape_id,
                        shape_name=shape.name,
                        element=element,
                        rule="near_miss_color",
                        message=f"color #{hexval} is a near-miss of approved #{nearest} (distance {dist:.1f})",
                        severity="minor",
                        auto_fixable=True,
                        details={**base_details, "current": f"#{hexval}", "target": f"#{nearest}"},
                        target=target,
                    )
                )
                return violations

    violations.append(
        Violation(
            slide_index=slide_idx,
            shape_id=shape.shape_id,
            shape_name=shape.name,
            element=element,
            rule="unapproved_color",
            message=f"color #{hexval} is not in the approved palette",
            severity="major",
            auto_fixable=False,
            details=base_details,
        )
    )
    return violations


def _check_shape(
    shape: ShapeRecord,
    slide_idx: int,
    slide_height_in: Optional[float],
    config: dict,
    font_tables: FontTables,
    approved_hexes: set[str],
    remap: dict[str, str],
    tolerance: float,
) -> list[Violation]:
    violations: list[Violation] = []
    colors_cfg = config.get("colors", {}) or {}
    typo = config.get("typography_rules", {}) or {}
    fonts_cfg = config.get("fonts", {}) or {}
    layout_cfg = config.get("layout", {}) or {}

    # --- shape fill / line colors ---
    if shape.fill and shape.fill.type == "solid":
        for c in shape.fill.colors:
            violations += _color_violations(
                c, "fill", slide_idx, shape, colors_cfg, approved_hexes, remap, tolerance, target=shape
            )
    if shape.fill and shape.fill.type == "gradient":
        for i, c in enumerate(shape.fill.colors):
            violations += _color_violations(
                c,
                "gradient stop",
                slide_idx,
                shape,
                colors_cfg,
                approved_hexes,
                remap,
                tolerance,
                target=shape,
                extra_details={"gradient_index": i},
            )
    if shape.line and shape.line.color:
        violations += _color_violations(
            shape.line.color, "line", slide_idx, shape, colors_cfg, approved_hexes, remap, tolerance, target=shape
        )

    # --- shape-level effects ---
    # Note: "3d" is covered here (it's in typography_rules.text_effects.forbidden)
    # rather than duplicated under forbidden_elements, to avoid double-flagging
    # the same shape-level <a:sp3d>/<a:scene3d>.
    forbidden_effects = set(typo.get("text_effects", {}).get("forbidden", []) or [])
    shape_effects = shape.effects & forbidden_effects
    for eff in shape_effects:
        violations.append(
            Violation(
                slide_index=slide_idx,
                shape_id=shape.shape_id,
                shape_name=shape.name,
                element="shape",
                rule="text_effect",
                message=f"forbidden effect '{eff}' present on shape",
                severity="major",
                auto_fixable=True,
                details={"effect": eff},
                target=shape,
            )
        )

    # --- forbidden layout elements ---
    forbidden_elements = set(layout_cfg.get("forbidden_elements", []) or [])
    if shape.is_wordart and "wordart" in forbidden_elements:
        violations.append(
            Violation(
                slide_index=slide_idx,
                shape_id=shape.shape_id,
                shape_name=shape.name,
                element="shape",
                rule="forbidden_element",
                message="WordArt-style text warp is not permitted",
                severity="major",
                auto_fixable=False,
                details={"element": "wordart"},
            )
        )

    # --- text / paragraphs ---
    is_heading = _is_heading(shape)
    text_colors_cfg = typo.get("text_colors", {}) or {}
    all_caps_cfg = typo.get("all_caps", {}) or {}
    forbidden_caps_fonts = set(all_caps_cfg.get("forbidden_fonts", []) or [])
    allowed_words = {w.upper() for w in all_caps_cfg.get("allowed_words", []) or []}
    required_caps_fonts = set(all_caps_cfg.get("required_fonts", []) or [])
    role_restrictions = typo.get("role_restrictions", {}) or {}
    alignment_cfg = typo.get("alignment", {}) or {}
    default_align = alignment_cfg.get("default", "left")
    min_body_pt = fonts_cfg.get("min_body_size_pt")
    min_title_pt = fonts_cfg.get("min_title_size_pt")
    min_size_by_level = {int(k): v for k, v in (fonts_cfg.get("min_size_by_level", {}) or {}).items()}

    contrast_cfg = typo.get("contrast", {}) or {}
    contrast_fonts = set(contrast_cfg.get("fonts", []) or [])
    contrast_dark = colors_mod.normalize_hex(contrast_cfg["dark_hex"]) if contrast_cfg.get("dark_hex") else None
    contrast_light = colors_mod.normalize_hex(contrast_cfg["light_hex"]) if contrast_cfg.get("light_hex") else None
    # Brand-consistency override: these backgrounds always get the light
    # (white) text color regardless of what the WCAG contrast math would
    # otherwise pick -- e.g. KONE Blue's 60% tint is technically light
    # enough for black text to score a higher contrast ratio, but the
    # brand wants every one of these treated as "a blue panel", not
    # computed per-shade. Deliberately NOT the full tint scale: the
    # palest tints are light enough that white text would be genuinely
    # illegible, which defeats the purpose of a legibility rule.
    always_light_bg = {colors_mod.normalize_hex(h) for h in contrast_cfg.get("always_light_text_backgrounds", []) or []}
    # Brand-consistency override: title/heading text is always dark,
    # regardless of background -- a stronger rule than "compute contrast"
    # since it's not about legibility per background, it's a fixed
    # editorial choice for that role.
    heading_always_dark = bool(contrast_cfg.get("heading_always_dark", False))
    # Only checkable when the shape has its own resolved solid background --
    # text sitting on an inherited/layout/no-fill background can't be
    # evaluated here without full z-order resolution, so it's left alone
    # rather than guessed at.
    bg_hex = None
    if shape.fill and shape.fill.type == "solid" and shape.fill.colors:
        first = shape.fill.colors[0]
        if first.hex:
            bg_hex = first.hex

    for para in shape.paragraphs:
        full_text = "".join(r.text for r in para.runs).strip()

        if para.alignment_explicit and para.alignment != default_align:
            if not _is_exception_candidate(shape, full_text, slide_height_in):
                violations.append(
                    Violation(
                        slide_index=slide_idx,
                        shape_id=shape.shape_id,
                        shape_name=shape.name,
                        element="paragraph",
                        rule="alignment",
                        message=f"paragraph alignment '{para.alignment}' should be '{default_align}'",
                        severity="minor",
                        auto_fixable=True,
                        details={"current": para.alignment, "target": default_align},
                        target=para,
                    )
                )

        for run in para.runs:
            if not run.text.strip():
                continue

            # general legacy/unapproved literal color check, independent of font approval
            violations += _color_violations(
                run.color, "text", slide_idx, shape, colors_cfg, approved_hexes, remap, tolerance, target=run
            )

            # Family-specific checks (approval, text color, caps, role
            # restrictions) require a resolved font name. A run with no
            # explicit override inherits from the placeholder/layout/master
            # chain -- font_effective resolves that (paragraph level ->
            # master txStyles -> theme fontScheme; see
            # fonts.resolve_effective_font). Layout/placeholder-specific
            # overrides between the master and the run aren't resolved
            # (uncommon relative to run-level or pure master-default
            # styling), so those still fall through to None and are
            # skipped here rather than guessed at.
            if run.font_effective is not None:
                matched_approved = font_tables.match_approved(run.font_effective, run.bold)
                remap_target = font_tables.remap_target(run.font_effective)

                if matched_approved is None:
                    severity = "critical" if is_heading else "major"
                    # An unapproved font found only via inheritance (no
                    # explicit run-level override) isn't safely fixable by
                    # rewriting this one run -- that would hardcode an
                    # override where the deck relied on inheritance. The
                    # correct fix is upstream, at the master/theme level
                    # (see fonts.remap_literal_fonts_in_master_txstyles),
                    # which fixer.py runs before this check ever sees the
                    # run -- so surfacing here without auto-fixing is the
                    # safety net for whatever that pass doesn't cover.
                    inherited = run.font_raw is None
                    violations.append(
                        Violation(
                            slide_index=slide_idx,
                            shape_id=shape.shape_id,
                            shape_name=shape.name,
                            element="run",
                            rule="unapproved_font",
                            message=(
                                f"font '{run.font_effective}' is not approved"
                                + (" (used in a heading)" if is_heading else "")
                                + (" (inherited, not an explicit override)" if inherited else "")
                            ),
                            severity=severity,
                            auto_fixable=remap_target is not None and not inherited,
                            details={"current": run.font_effective, "target": remap_target},
                            target=run,
                        )
                    )
                    matched_approved = None
                elif (
                    is_heading
                    and heading_always_dark
                    and matched_approved in contrast_fonts
                    and contrast_dark is not None
                ):
                    # Explicit brand-consistency rule: PowerPoint title/
                    # heading text is always black -- overrides contrast/
                    # background computation entirely for headings, not
                    # just a default choice among two legible options.
                    current_hex = run.color.hex if run.color and run.color.kind != "none" else None
                    if current_hex != contrast_dark:
                        violations.append(
                            Violation(
                                slide_index=slide_idx,
                                shape_id=shape.shape_id,
                                shape_name=shape.name,
                                element="run",
                                rule="text_contrast",
                                message=(
                                    f"'{matched_approved}' heading text must be #{contrast_dark} "
                                    "(headings are always dark), found "
                                    + (f"#{current_hex}" if current_hex else "no explicit color (inherited)")
                                ),
                                severity="major",
                                auto_fixable=True,
                                details={
                                    "current": f"#{current_hex}" if current_hex else None,
                                    "target": f"#{contrast_dark}",
                                },
                                target=run,
                            )
                        )
                else:
                    # Legibility on a known background is the more specific,
                    # more correct check (e.g. white -- not black -- text on
                    # KONE Blue), so it takes over entirely for fonts/shapes
                    # where it applies; the generic allowed-colors-list check
                    # below is the fallback for everything else (no resolved
                    # background to check contrast against, e.g. text on the
                    # page's plain canvas, or a font contrast isn't configured for).
                    contrast_applies = (
                        matched_approved in contrast_fonts
                        and bg_hex is not None
                        and contrast_dark is not None
                        and contrast_light is not None
                    )
                    if contrast_applies and run.color:
                        # A run with NO explicit color (inherits from the
                        # theme/master) is just as much in scope as one
                        # with an explicit-but-wrong color -- inheritance
                        # isn't resolved for color the way it is for font
                        # (schemeClr + lumMod/lumOff brightness would need
                        # reproducing by hand), so rather than silently
                        # trusting an unknown inherited color against a
                        # background we DO know, this sets it explicitly.
                        # Always correct (computed from the same WCAG
                        # check either way), never destructive.
                        current_hex = run.color.hex if run.color.kind != "none" else None
                        if bg_hex in always_light_bg:
                            expected_hex = contrast_light
                        else:
                            expected_hex = colors_mod.expected_contrast_text_hex(bg_hex, contrast_dark, contrast_light)
                        if current_hex != expected_hex:
                            violations.append(
                                Violation(
                                    slide_index=slide_idx,
                                    shape_id=shape.shape_id,
                                    shape_name=shape.name,
                                    element="run",
                                    rule="text_contrast",
                                    message=(
                                        f"'{matched_approved}' text on background #{bg_hex} should be "
                                        f"#{expected_hex} for legibility, found "
                                        + (f"#{current_hex}" if current_hex else "no explicit color (inherited)")
                                    ),
                                    severity="major",
                                    auto_fixable=True,
                                    details={
                                        "current": f"#{current_hex}" if current_hex else None,
                                        "target": f"#{expected_hex}",
                                        "background": f"#{bg_hex}",
                                    },
                                    target=run,
                                )
                            )
                    elif not contrast_applies:
                        # run text color vs. that font's allowed text colors (config
                        # list order is significant — e.g. KONE Information lists
                        # blue first as the preferred color — preserve it rather
                        # than sorting).
                        allowed_colors_ordered = [
                            colors_mod.normalize_hex(h) for h in text_colors_cfg.get(matched_approved, [])
                        ]
                        allowed_colors = set(allowed_colors_ordered)
                        if allowed_colors and run.color and run.color.kind != "none" and run.color.hex:
                            if run.color.hex not in allowed_colors:
                                violations.append(
                                    Violation(
                                        slide_index=slide_idx,
                                        shape_id=shape.shape_id,
                                        shape_name=shape.name,
                                        element="run",
                                        rule="text_color",
                                        message=(
                                            f"'{matched_approved}' text must use one of "
                                            f"{['#' + h for h in allowed_colors_ordered]}, found #{run.color.hex}"
                                        ),
                                        severity="major",
                                        auto_fixable=True,
                                        details={
                                            "current": f"#{run.color.hex}",
                                            "target": f"#{allowed_colors_ordered[0]}",
                                        },
                                        target=run,
                                    )
                                )

                    # all-caps rules — flagged only, not auto-fixed:
                    # transforming case is a content edit (can't safely
                    # recover intended capitalization or distinguish
                    # acronyms), outside the deterministic-fix bullet list,
                    # so these always need manual review.
                    words = set(w.strip(".,!?:;").upper() for w in run.text.split())
                    only_allowed_words = words.issubset(allowed_words) if words else False
                    if run.all_upper and matched_approved in forbidden_caps_fonts and not only_allowed_words:
                        violations.append(
                            Violation(
                                slide_index=slide_idx,
                                shape_id=shape.shape_id,
                                shape_name=shape.name,
                                element="run",
                                rule="all_caps",
                                message=f"'{matched_approved}' text must not be ALL CAPS: {run.text!r}",
                                severity="major",
                                auto_fixable=False,
                                details={"text": run.text},
                            )
                        )
                    if not run.all_upper and matched_approved in required_caps_fonts:
                        violations.append(
                            Violation(
                                slide_index=slide_idx,
                                shape_id=shape.shape_id,
                                shape_name=shape.name,
                                element="run",
                                rule="all_caps",
                                message=f"'{matched_approved}' text must be ALL CAPS: {run.text!r}",
                                severity="major",
                                auto_fixable=False,
                                details={"text": run.text},
                            )
                        )

                    # role restrictions (e.g. KONE Information as heading/body, oversized)
                    restriction = role_restrictions.get(matched_approved)
                    if restriction:
                        max_size = restriction.get("max_size_pt")
                        if max_size and run.size_pt and run.size_pt > max_size:
                            violations.append(
                                Violation(
                                    slide_index=slide_idx,
                                    shape_id=shape.shape_id,
                                    shape_name=shape.name,
                                    element="run",
                                    rule="role_restriction",
                                    message=f"'{matched_approved}' used at {run.size_pt}pt, max is {max_size}pt",
                                    severity="major",
                                    auto_fixable=False,
                                    details={"current_pt": run.size_pt, "max_pt": max_size},
                                )
                            )
                        forbidden_roles = restriction.get("forbidden_roles", []) or []
                        if is_heading and "heading" in forbidden_roles:
                            violations.append(
                                Violation(
                                    slide_index=slide_idx,
                                    shape_id=shape.shape_id,
                                    shape_name=shape.name,
                                    element="run",
                                    rule="role_restriction",
                                    message=f"'{matched_approved}' must not be used as a heading",
                                    severity="major",
                                    auto_fixable=False,
                                )
                            )

            # forbidden run-level text effects
            run_effects = run.effects & forbidden_effects
            for eff in run_effects:
                violations.append(
                    Violation(
                        slide_index=slide_idx,
                        shape_id=shape.shape_id,
                        shape_name=shape.name,
                        element="run",
                        rule="text_effect",
                        message=f"forbidden effect '{eff}' present on text {run.text!r}",
                        severity="major",
                        auto_fixable=True,
                        details={"effect": eff},
                        target=run,
                    )
                )

            # minimum size — headings use a flat floor; placeholder body
            # text uses the master's own per-outline-level sizes (it's
            # deliberately not flat: footnote-tier levels go down to 11pt
            # by design). Plain, non-placeholder text boxes (footnotes, tab
            # labels, page numbers dropped in free-form) have no
            # master-defined floor at all, so they're intentionally exempt
            # rather than guessed at.
            if is_heading:
                min_pt = min_title_pt
            elif shape.is_placeholder:
                min_pt = min_size_by_level.get(para.level, min_body_pt)
            else:
                min_pt = None
            if min_pt and run.size_pt and run.size_pt < min_pt:
                violations.append(
                    Violation(
                        slide_index=slide_idx,
                        shape_id=shape.shape_id,
                        shape_name=shape.name,
                        element="run",
                        rule="min_size",
                        message=f"text size {run.size_pt}pt is below minimum {min_pt}pt",
                        severity="minor",
                        auto_fixable=False,
                        details={"current_pt": run.size_pt, "min_pt": min_pt},
                    )
                )

    return violations


def audit_deck(inventory: DeckInventory, config: dict) -> list[Violation]:
    violations: list[Violation] = []

    colors_cfg = config.get("colors", {}) or {}
    approved_hexes = {colors_mod.normalize_hex(h) for h in colors_cfg.get("approved", []) or []}
    remap = {colors_mod.normalize_hex(k): v for k, v in (colors_cfg.get("remap", {}) or {}).items()}
    tolerance = colors_cfg.get("tolerance", 0) or 0
    font_tables = FontTables.from_config(config.get("fonts", {}) or {})

    layout_cfg = config.get("layout", {}) or {}
    expected_size = layout_cfg.get("slide_size")
    if expected_size and inventory.aspect_ratio != expected_size:
        violations.append(
            Violation(
                slide_index=0,
                shape_id=None,
                shape_name="(deck)",
                element="presentation",
                rule="slide_size",
                message=f"slide size is {inventory.aspect_ratio}, expected {expected_size}",
                severity="major",
                auto_fixable=False,
                details={"current": inventory.aspect_ratio, "target": expected_size},
            )
        )

    logo_cfg = config.get("logo", {}) or {}
    old_hashes = logo_cfg.get("old_logo_hashes", []) or []

    approved_layouts = layout_cfg.get("approved_layouts")

    slide_height_in = inventory.slide_height_emu / 914400 if inventory.slide_height_emu else None

    for slide in inventory.slides:
        top_shapes = slide.shapes
        all_shapes = list(iter_shapes_recursive(top_shapes))

        # A slide built on a layout outside the sanctioned template (e.g. a
        # bespoke layout an agency/team added on the side) isn't something
        # color/font rules can catch -- those checks only ever see whatever
        # that custom layout happens to define. Surfaced as its own
        # category rather than silently trusted or silently recolored.
        if approved_layouts is not None and slide.layout_name not in approved_layouts:
            violations.append(
                Violation(
                    slide_index=slide.index,
                    shape_id=None,
                    shape_name="(slide)",
                    element="slide",
                    rule="non_standard_layout",
                    message=(
                        f"slide uses layout '{slide.layout_name}', which is not part of "
                        f"the approved template"
                    ),
                    severity="major",
                    auto_fixable=False,
                    details={"layout_name": slide.layout_name},
                )
            )

        if old_hashes:
            matches = logo_mod.find_old_logo_matches([s.obj for s in top_shapes], old_hashes)
            for m in matches:
                shape_rec = next((s for s in all_shapes if s.obj is m.shape), None)
                violations.append(
                    Violation(
                        slide_index=slide.index,
                        shape_id=shape_rec.shape_id if shape_rec else None,
                        shape_name=shape_rec.name if shape_rec else m.shape.name,
                        element="image",
                        rule="old_logo",
                        message=f"image matches an old logo hash (distance {m.distance})",
                        severity="critical",
                        auto_fixable=True,
                        details={"phash": m.phash, "matched": m.matched_hash},
                        target=shape_rec,
                    )
                )

        for shape in all_shapes:
            violations += _check_shape(
                shape, slide.index, slide_height_in, config, font_tables, approved_hexes, remap, tolerance
            )

    return violations


SEVERITY_RANK = {"critical": 0, "major": 1, "minor": 2}


def sort_violations(violations: list[Violation]) -> list[Violation]:
    return sorted(violations, key=lambda v: (SEVERITY_RANK.get(v.severity, 9), v.slide_index, v.rule))


def summarize(violations: list[Violation]) -> dict:
    summary = {"critical": 0, "major": 0, "minor": 0, "total": len(violations), "auto_fixable": 0}
    for v in violations:
        summary[v.severity] = summary.get(v.severity, 0) + 1
        if v.auto_fixable:
            summary["auto_fixable"] += 1
    return summary
