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

    logo_cfg = config.get("logo", {}) or {}
    logo_path = logo_cfg.get("new_logo_path")
    if not logo_path:
        errors.append("logo.new_logo_path is required")
    else:
        resolved = (base_dir / logo_path).resolve()
        if not resolved.exists():
            errors.append(f"logo.new_logo_path does not exist: {resolved}")

    layout_cfg = config.get("layout", {}) or {}
    slide_size = layout_cfg.get("slide_size")
    if slide_size not in (None, "16:9", "4:3"):
        errors.append(f"layout.slide_size '{slide_size}' is not one of: 16:9, 4:3")

    audit_cfg = config.get("audit", {}) or {}
    for sev in audit_cfg.get("fail_on", []) or []:
        if sev not in SEVERITIES:
            errors.append(f"audit.fail_on contains unknown severity '{sev}' (expected one of {SEVERITIES})")

    return errors
