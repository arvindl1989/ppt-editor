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

from lxml import etree
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

from deckguard.colors import iter_slide_masters

_WS_HYPHEN_RE = re.compile(r"[\s\-]+")
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _a(tag: str) -> str:
    return f"{{{A_NS}}}{tag}"


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
