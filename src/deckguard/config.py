"""Loading and validating brand_rules.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

from deckguard import colors as colors_mod

SEVERITIES = ("critical", "major", "minor")

DEFAULT_RULES_FILENAME = "brand_rules.yaml"


class ConfigError(ValueError):
    """Raised for structurally invalid config (missing required sections)."""


def load_config(path: str | Path) -> dict:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"rules file not found: {path}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a YAML mapping at the top level")

    # logo.new_logo_path is written relative to the rules file itself (see
    # brand_rules.yaml), but every consumer downstream (fixer.py's logo
    # replacement, both the hash-matched and region-matched paths) just
    # does Path(new_logo_path).exists() with no base_dir of its own to
    # resolve against -- so a relative path silently depended on the
    # PROCESS's own current working directory at runtime, not the config
    # file's location. That happens to match on a local checkout (cwd ==
    # repo root) but has no reason to hold in a deployed environment,
    # and a mismatch fails this completely silently: no error, the logo
    # replacement step just no-ops. Resolving to absolute here, once, at
    # load time, makes every downstream consumer's behavior independent
    # of the process's cwd.
    logo_cfg = data.get("logo")
    if isinstance(logo_cfg, dict):
        logo_path = logo_cfg.get("new_logo_path")
        if logo_path and not Path(logo_path).is_absolute():
            logo_cfg["new_logo_path"] = str((path.parent / logo_path).resolve())

    return data


def default_config_path() -> Path:
    return Path(__file__).with_name(DEFAULT_RULES_FILENAME)


def validate_config(config: dict, base_dir: str | Path = ".") -> list[str]:
    """Return a list of human-readable error strings; empty means valid."""
    errors: list[str] = []
    base_dir = Path(base_dir)

    for section in ("brand", "colors", "fonts", "typography_rules", "logo", "layout", "audit"):
        if section not in config:
            errors.append(f"missing top-level section: '{section}'")

    colors_cfg = config.get("colors", {}) or {}
    approved = colors_cfg.get("approved", []) or []
    if not approved:
        errors.append("colors.approved must list at least one hex color")

    approved_norm: set[str] = set()
    for value in approved:
        try:
            approved_norm.add(colors_mod.normalize_hex(value))
        except ValueError as exc:
            errors.append(f"colors.approved: {exc}")

    remap = colors_cfg.get("remap", {}) or {}
    for old, new in remap.items():
        try:
            colors_mod.normalize_hex(old)
        except ValueError as exc:
            errors.append(f"colors.remap key: {exc}")
        try:
            new_norm = colors_mod.normalize_hex(new)
        except ValueError as exc:
            errors.append(f"colors.remap value: {exc}")
            continue
        if new_norm not in approved_norm:
            errors.append(
                f"colors.remap target '{new}' (for '{old}') is not in colors.approved"
            )

    tolerance = colors_cfg.get("tolerance", 0)
    if not isinstance(tolerance, (int, float)) or tolerance < 0:
        errors.append("colors.tolerance must be a non-negative number")

    layout_panel_remap = colors_cfg.get("layout_panel_remap", {}) or {}
    for old, new in layout_panel_remap.items():
        try:
            colors_mod.normalize_hex(old)
        except ValueError as exc:
            errors.append(f"colors.layout_panel_remap key: {exc}")
        try:
            new_norm = colors_mod.normalize_hex(new)
        except ValueError as exc:
            errors.append(f"colors.layout_panel_remap value: {exc}")
            continue
        if new_norm not in approved_norm:
            errors.append(
                f"colors.layout_panel_remap target '{new}' (for '{old}') is not in colors.approved"
            )

    layout_panel_min_area = colors_cfg.get("layout_panel_min_area_sq_in", 8.0)
    if not isinstance(layout_panel_min_area, (int, float)) or layout_panel_min_area < 0:
        errors.append("colors.layout_panel_min_area_sq_in must be a non-negative number")

    fallback_cfg = colors_cfg.get("unlisted_panel_fallback", {}) or {}
    if fallback_cfg:
        for key in ("grey_target", "default_target"):
            val = fallback_cfg.get(key)
            if not val:
                continue
            try:
                norm = colors_mod.normalize_hex(val)
            except ValueError as exc:
                errors.append(f"colors.unlisted_panel_fallback.{key}: {exc}")
                continue
            if norm not in approved_norm:
                errors.append(f"colors.unlisted_panel_fallback.{key} '{val}' is not in colors.approved")
        spread = fallback_cfg.get("grey_max_channel_spread", 20)
        if not isinstance(spread, (int, float)) or spread < 0:
            errors.append("colors.unlisted_panel_fallback.grey_max_channel_spread must be a non-negative number")

    fonts_cfg = config.get("fonts", {}) or {}
    fonts_approved = set(fonts_cfg.get("approved", []) or [])
    if not fonts_approved:
        errors.append("fonts.approved must list at least one font name")
    fonts_remap = fonts_cfg.get("remap", {}) or {}
    for old, new in fonts_remap.items():
        if new not in fonts_approved:
            errors.append(f"fonts.remap target '{new}' (for '{old}') is not in fonts.approved")

    for key in ("min_body_size_pt", "min_title_size_pt"):
        val = fonts_cfg.get(key)
        if val is not None and (not isinstance(val, (int, float)) or val <= 0):
            errors.append(f"fonts.{key} must be a positive number")

    min_size_by_level = fonts_cfg.get("min_size_by_level", {}) or {}
    for level, val in min_size_by_level.items():
        try:
            level_int = int(level)
        except (TypeError, ValueError):
            errors.append(f"fonts.min_size_by_level key {level!r} must be an integer (paragraph outline level)")
            continue
        if not 0 <= level_int <= 8:
            errors.append(f"fonts.min_size_by_level key {level!r} must be between 0 and 8")
        if not isinstance(val, (int, float)) or val <= 0:
            errors.append(f"fonts.min_size_by_level[{level!r}] must be a positive number")

    typo_cfg = config.get("typography_rules", {}) or {}
    contrast_cfg = typo_cfg.get("contrast", {}) or {}
    if contrast_cfg:
        for key in ("dark_hex", "light_hex"):
            val = contrast_cfg.get(key)
            if not val:
                errors.append(f"typography_rules.contrast.{key} is required when contrast is configured")
                continue
            try:
                norm = colors_mod.normalize_hex(val)
            except ValueError as exc:
                errors.append(f"typography_rules.contrast.{key}: {exc}")
                continue
            if norm not in approved_norm:
                errors.append(f"typography_rules.contrast.{key} '{val}' is not in colors.approved")
        if not contrast_cfg.get("fonts"):
            errors.append("typography_rules.contrast.fonts must list at least one font name")
        for val in contrast_cfg.get("always_light_text_backgrounds", []) or []:
            try:
                norm = colors_mod.normalize_hex(val)
            except ValueError as exc:
                errors.append(f"typography_rules.contrast.always_light_text_backgrounds: {exc}")
                continue
            if norm not in approved_norm:
                errors.append(
                    f"typography_rules.contrast.always_light_text_backgrounds '{val}' is not in colors.approved"
                )

    logo_cfg = config.get("logo", {}) or {}
    logo_path = logo_cfg.get("new_logo_path")
    if not logo_path:
        errors.append("logo.new_logo_path is required")
    else:
        resolved = (base_dir / logo_path).resolve()
        if not resolved.exists():
            errors.append(f"logo.new_logo_path does not exist: {resolved}")

    old_logo_region = logo_cfg.get("old_logo_region_in")
    if old_logo_region is not None:
        valid_shape = isinstance(old_logo_region, list) and len(old_logo_region) == 4
        if not valid_shape or not all(isinstance(v, (int, float)) and v >= 0 for v in old_logo_region):
            errors.append("logo.old_logo_region_in must be a list of 4 non-negative numbers: [left, top, width, height] in inches")

    layout_cfg = config.get("layout", {}) or {}
    slide_size = layout_cfg.get("slide_size")
    if slide_size not in (None, "16:9", "4:3"):
        errors.append(f"layout.slide_size '{slide_size}' is not one of: 16:9, 4:3")

    approved_layouts = layout_cfg.get("approved_layouts")
    if approved_layouts is not None and not isinstance(approved_layouts, list):
        errors.append("layout.approved_layouts must be a list of layout names")

    audit_cfg = config.get("audit", {}) or {}
    for sev in audit_cfg.get("fail_on", []) or []:
        if sev not in SEVERITIES:
            errors.append(f"audit.fail_on contains unknown severity '{sev}' (expected one of {SEVERITIES})")

    return errors
