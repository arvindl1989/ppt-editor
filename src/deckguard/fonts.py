"""Font name normalization and matching.

PowerPoint stores font names inconsistently ("Inter Semi Bold",
"Inter-SemiBold", "Inter SemiBold", or "Inter" + a bold attribute). All
matching against the config (approved list, remap table, typography
rules) goes through the helpers here so every caller normalizes the same
way: case-insensitive, hyphens/spaces stripped, with the bold attribute
folded into a "Semi Bold" family when the raw name is the bare base
family.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from lxml import etree
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

from deckguard.colors import iter_slide_masters

_WS_HYPHEN_RE = re.compile(r"[\s\-]+")
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


def _a(tag: str) -> str:
    return f"{{{A_NS}}}{tag}"


def _p(tag: str) -> str:
    return f"{{{P_NS}}}{tag}"


def normalize_key(name: str | None) -> str:
    """Case-insensitive, hyphen/space-stripped comparison key."""
    if not name:
        return ""
    return _WS_HYPHEN_RE.sub("", name.strip().lower())


def canonical_key(name: str | None, bold: bool = False) -> str:
    """Normalization key that also folds `name + bold` onto the semi-bold family.

    "Inter" with bold=True and "Inter Semi Bold" both resolve to the same
    key ("intersemibold"), since PowerPoint represents that weight either
    way.
    """
    key = normalize_key(name)
    if bold and key and not key.endswith("semibold") and not key.endswith("bold"):
        return key + "semibold"
    return key


@dataclass(frozen=True)
class FontTables:
    """Precomputed lookup tables built once from brand_rules.yaml."""

    approved_by_key: dict[str, str]
    remap_by_key: dict[str, str]

    @classmethod
    def from_config(cls, fonts_config: dict) -> "FontTables":
        approved = fonts_config.get("approved", []) or []
        remap = fonts_config.get("remap", {}) or {}
        return cls(
            approved_by_key={normalize_key(n): n for n in approved},
            remap_by_key={normalize_key(k): v for k, v in remap.items()},
        )

    def match_approved(self, name: str | None, bold: bool = False) -> str | None:
        """Return the approved-list name this run's font resolves to, or None."""
        key = canonical_key(name, bold)
        if key in self.approved_by_key:
            return self.approved_by_key[key]
        # Fall back to the un-bolded key so "Inter" (bold=False) still
        # matches the approved "Inter" entry even though canonical_key
        # only folds semibold when bold is True.
        plain_key = normalize_key(name)
        return self.approved_by_key.get(plain_key)

    def remap_target(self, name: str | None) -> str | None:
        """Return the replacement font name if `name` is a legacy/off-brand font."""
        key = normalize_key(name)
        return self.remap_by_key.get(key)

    def is_approved(self, name: str | None, bold: bool = False) -> bool:
        return self.match_approved(name, bold) is not None


_TX_STYLE_TAG = {"title": "titleStyle", "body": "bodyStyle", "other": "otherStyle"}


def read_theme_font_scheme(master) -> dict[str, str]:
    """{'major': typeface, 'minor': typeface} read from the master's theme part."""
    theme_part = master.part.part_related_by(RT.THEME)
    root = etree.fromstring(theme_part.blob)
    font_scheme = root.find(f".//{_a('fontScheme')}")
    result: dict[str, str] = {}
    if font_scheme is None:
        return result
    for slot, key in (("majorFont", "major"), ("minorFont", "minor")):
        slot_el = font_scheme.find(_a(slot))
        if slot_el is None:
            continue
        latin = slot_el.find(_a("latin"))
        if latin is not None and latin.get("typeface"):
            result[key] = latin.get("typeface")
    return result


def read_master_style_font(master, category: str, level: int) -> Optional[str]:
    """The master's <p:txStyles> default Latin typeface for `category`
    ('title' | 'body' | 'other') at paragraph outline `level` (0-8) -- the
    font text with no explicit run-level override actually renders with.
    Falls back to level 0 if the specific level has no defRPr/latin of its
    own, matching how OOXML paragraph levels inherit downward. May return
    a theme reference ('+mj-lt'/'+mn-lt') rather than a literal name --
    see resolve_theme_symbol.
    """
    style_tag = _TX_STYLE_TAG.get(category)
    if style_tag is None:
        return None
    tx_styles = master._element.find(_p("txStyles"))
    if tx_styles is None:
        return None
    style_el = tx_styles.find(_p(style_tag))
    if style_el is None:
        return None
    for lvl in dict.fromkeys((level, 0)):  # try the specific level, then level 0, no dupes
        lvl_el = style_el.find(_a(f"lvl{lvl + 1}pPr"))
        if lvl_el is None:
            continue
        def_rpr = lvl_el.find(_a("defRPr"))
        if def_rpr is None:
            continue
        latin = def_rpr.find(_a("latin"))
        if latin is not None and latin.get("typeface"):
            return latin.get("typeface")
    return None


def resolve_theme_symbol(typeface: Optional[str], theme_fonts: dict[str, str]) -> Optional[str]:
    if typeface == "+mj-lt":
        return theme_fonts.get("major")
    if typeface == "+mn-lt":
        return theme_fonts.get("minor")
    return typeface


def resolve_effective_font(
    font_raw: Optional[str],
    category: str,
    level: int,
    master,
    theme_fonts: dict[str, str],
) -> Optional[str]:
    """The font a run actually renders with. An explicit run-level override
    wins outright; otherwise this falls back to the slide master's
    txStyles for the run's shape category ('title'/'body'/'other') and
    paragraph outline level, resolving theme font-scheme references.

    Layout- or placeholder-specific style overrides *between* the master
    and the run aren't resolved (uncommon relative to run-level or pure
    master-default styling in practice) -- those cases return None, same
    as an unresolvable run today, rather than guessing.
    """
    if font_raw is not None:
        return font_raw
    typeface = read_master_style_font(master, category, level)
    return resolve_theme_symbol(typeface, theme_fonts)


def remap_literal_fonts_in_master_txstyles(prs, remap: dict[str, str]) -> list[dict]:
    """Rewrite a literal (non-theme-reference) legacy font in the master's
    txStyles -- the paragraph-level defaults that text with no explicit
    run-level *or* theme-level font inherits. `remap_theme_fonts` only
    corrects the theme's own fontScheme (what `+mj-lt`/`+mn-lt` resolve
    to); `_remap_explicit_fonts_in_masters_and_layouts` (fixer.py) only
    corrects literal overrides on actual master/layout shape runs. Neither
    touches txStyles, which is a third, independent place a legacy font
    name can be hardcoded.
    """
    remap_by_key = {normalize_key(k): v for k, v in remap.items()}
    changes: list[dict] = []
    seen_masters = set()
    for master in iter_slide_masters(prs):
        if id(master.part) in seen_masters:
            continue
        seen_masters.add(id(master.part))
        tx_styles = master._element.find(_p("txStyles"))
        if tx_styles is None:
            continue
        for style_tag in _TX_STYLE_TAG.values():
            style_el = tx_styles.find(_p(style_tag))
            if style_el is None:
                continue
            for lvl_el in style_el:
                def_rpr = lvl_el.find(_a("defRPr"))
                if def_rpr is None:
                    continue
                latin = def_rpr.find(_a("latin"))
                if latin is None:
                    continue
                current = latin.get("typeface")
                if not current or current.startswith("+"):
                    continue  # theme reference, not literal -- remap_theme_fonts' job
                target = remap_by_key.get(normalize_key(current))
                if not target or target == current:
                    continue
                latin.set("typeface", target)
                changes.append({"master": master.name, "style": style_tag, "old": current, "new": target})
    return changes


def remap_theme_fonts(prs, remap: dict[str, str]) -> list[dict]:
    """Rewrite the theme's major/minor Latin typeface if it's a legacy font.

    Placeholders that don't set an explicit font inherit through
    `+mj-lt`/`+mn-lt` theme references, so correcting the theme's
    fontScheme fixes every such placeholder across every layout built on
    it in one operation — the font analogue of `remap_theme_colors`.
    """
    remap_by_key = {normalize_key(k): v for k, v in remap.items()}
    changes: list[dict] = []
    seen_theme_parts = set()
    for master in iter_slide_masters(prs):
        theme_part = master.part.part_related_by(RT.THEME)
        if id(theme_part) in seen_theme_parts:
            continue
        seen_theme_parts.add(id(theme_part))

        root = etree.fromstring(theme_part.blob)
        font_scheme = root.find(f".//{_a('fontScheme')}")
        if font_scheme is None:
            continue
        changed = False
        for slot in ("majorFont", "minorFont"):
            slot_el = font_scheme.find(_a(slot))
            if slot_el is None:
                continue
            latin = slot_el.find(_a("latin"))
            if latin is None:
                continue
            current = latin.get("typeface")
            target = remap_by_key.get(normalize_key(current))
            if not target or target == current:
                continue
            latin.set("typeface", target)
            changed = True
            changes.append(
                {
                    "theme_part": theme_part.partname,
                    "slot": slot,
                    "old": current,
                    "new": target,
                }
            )
        if changed:
            theme_part._blob = etree.tostring(  # noqa: SLF001 — see colors.remap_theme_colors
                root, xml_declaration=True, encoding="UTF-8", standalone=True
            )
    return changes
