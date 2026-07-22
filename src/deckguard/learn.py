"""Derive brand_rules.yaml updates by diffing an old deck against an
already-on-brand reference deck.

This formalizes, as a repeatable tool feature, the workflow used to grow
brand_rules.yaml from real decks throughout this project: extract each
deck's color/font usage, correlate which old value disappeared while a
new one appeared at a similar count (the signal that it was replaced),
and propose colors.remap / fonts.remap additions. Ambiguous or
low-confidence matches are flagged rather than silently guessed — same
"never destructive, prefer flagging over guessing" principle as the rest
of the engine.

Not covered here: layout/structural differences. This only reasons about
color and font *usage*, not shape identity or position, since two deck
revisions rarely have 1:1-matching shape names/ids (see the shape-name
drift observed between real old/new deck pairs).
"""

from __future__ import annotations

import copy
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ruamel.yaml import YAML

from deckguard import colors as colors_mod
from deckguard.fonts import normalize_key
from deckguard.inventory import build_inventory, iter_shapes_recursive

HIGH_CONFIDENCE_SCORE = 0.7
CONFIDENCE_LEVELS = {"low": 0, "high": 1}


@dataclass
class ColorProposal:
    role: str  # fill | line | text
    old_hex: str
    new_hex: str
    old_count: int
    new_count: int
    confidence: str  # high | low


@dataclass
class FontProposal:
    old_font: str
    old_bold: bool
    new_font: str
    new_bold: bool
    old_count: int
    new_count: int
    confidence: str


@dataclass
class LearnResult:
    color_proposals: list[ColorProposal] = field(default_factory=list)
    font_proposals: list[FontProposal] = field(default_factory=list)
    unmatched_old_colors: list[tuple[str, str, int]] = field(default_factory=list)  # role, hex, count
    unmatched_old_fonts: list[tuple[str, bool, int]] = field(default_factory=list)  # name, bold, count


def _color_usage(prs) -> Counter:
    inv = build_inventory(prs)
    usage: Counter = Counter()
    for slide in inv.slides:
        for shape in iter_shapes_recursive(slide.shapes):
            if shape.fill and shape.fill.type in ("solid", "gradient"):
                for c in shape.fill.colors:
                    if c.hex:
                        usage[("fill", c.hex)] += 1
            if shape.line and shape.line.color and shape.line.color.hex:
                usage[("line", shape.line.color.hex)] += 1
            for para in shape.paragraphs:
                for run in para.runs:
                    if not run.text.strip():
                        continue
                    if run.color and run.color.hex:
                        usage[("text", run.color.hex)] += 1
    return usage


def _font_usage(prs) -> Counter:
    inv = build_inventory(prs)
    usage: Counter = Counter()
    for slide in inv.slides:
        for shape in iter_shapes_recursive(slide.shapes):
            for para in shape.paragraphs:
                for run in para.runs:
                    if not run.text.strip() or run.font_raw is None:
                        continue
                    usage[(run.font_raw, run.bold)] += 1
    return usage


def _score(old_count: int, new_count: int) -> float:
    """1.0 = identical counts; decays toward 0 as they diverge."""
    lo, hi = sorted((old_count, new_count))
    return lo / hi if hi else 0.0


def _greedy_match(
    old_items: list[tuple], new_items: list[tuple], key_fn: Callable
) -> tuple[list[tuple[int, int, float]], list[tuple]]:
    """old_items/new_items: [(identity, count), ...]. Greedily pairs the
    highest-scoring (old, new) combinations first, restricted to pairs
    where key_fn(old_identity) == key_fn(new_identity) (role for colors,
    bold-flag for fonts). Returns (matches, unmatched_old_items)."""
    candidates = []
    for oi, (o_id, o_count) in enumerate(old_items):
        for ni, (n_id, n_count) in enumerate(new_items):
            if key_fn(o_id) != key_fn(n_id):
                continue
            candidates.append((_score(o_count, n_count), oi, ni))
    candidates.sort(key=lambda c: -c[0])

    used_old: set[int] = set()
    used_new: set[int] = set()
    matches = []
    for score, oi, ni in candidates:
        if oi in used_old or ni in used_new:
            continue
        used_old.add(oi)
        used_new.add(ni)
        matches.append((oi, ni, score))
    unmatched = [item for idx, item in enumerate(old_items) if idx not in used_old]
    return matches, unmatched


def learn(old_prs, new_prs, config: dict) -> LearnResult:
    colors_cfg = config.get("colors", {}) or {}
    approved = {colors_mod.normalize_hex(h) for h in colors_cfg.get("approved", []) or []}
    remap = {colors_mod.normalize_hex(k) for k in (colors_cfg.get("remap", {}) or {}).keys()}

    old_colors = _color_usage(old_prs)
    new_colors = _color_usage(new_prs)

    old_items = [
        ((role, hexval), count)
        for (role, hexval), count in old_colors.items()
        if hexval not in approved and hexval not in remap
    ]
    new_items = [((role, hexval), count) for (role, hexval), count in new_colors.items()]

    matches, unmatched = _greedy_match(old_items, new_items, key_fn=lambda ident: ident[0])

    color_proposals = []
    for oi, ni, score in matches:
        (role, old_hex), old_count = old_items[oi]
        (_, new_hex), new_count = new_items[ni]
        if old_hex == new_hex:
            continue
        color_proposals.append(
            ColorProposal(
                role=role,
                old_hex=old_hex,
                new_hex=new_hex,
                old_count=old_count,
                new_count=new_count,
                confidence="high" if score >= HIGH_CONFIDENCE_SCORE else "low",
            )
        )
    unmatched_old_colors = [(role, hexval, count) for (role, hexval), count in unmatched]

    fonts_cfg = config.get("fonts", {}) or {}
    font_approved_keys = {normalize_key(n) for n in fonts_cfg.get("approved", []) or []}
    font_remap_keys = {normalize_key(k) for k in (fonts_cfg.get("remap", {}) or {}).keys()}

    old_fonts = _font_usage(old_prs)
    new_fonts = _font_usage(new_prs)
    old_font_items = [
        ((name, bold), count)
        for (name, bold), count in old_fonts.items()
        if normalize_key(name) not in font_approved_keys and normalize_key(name) not in font_remap_keys
    ]
    new_font_items = [((name, bold), count) for (name, bold), count in new_fonts.items()]

    font_matches, unmatched_fonts = _greedy_match(old_font_items, new_font_items, key_fn=lambda ident: ident[1])
    font_proposals = []
    for oi, ni, score in font_matches:
        (old_name, old_bold), old_count = old_font_items[oi]
        (new_name, new_bold), new_count = new_font_items[ni]
        if normalize_key(old_name) == normalize_key(new_name):
            continue
        font_proposals.append(
            FontProposal(
                old_font=old_name,
                old_bold=old_bold,
                new_font=new_name,
                new_bold=new_bold,
                old_count=old_count,
                new_count=new_count,
                confidence="high" if score >= HIGH_CONFIDENCE_SCORE else "low",
            )
        )
    unmatched_old_fonts = [(name, bold, count) for (name, bold), count in unmatched_fonts]

    return LearnResult(
        color_proposals=sorted(color_proposals, key=lambda p: -p.old_count),
        font_proposals=sorted(font_proposals, key=lambda p: -p.old_count),
        unmatched_old_colors=sorted(unmatched_old_colors, key=lambda t: -t[2]),
        unmatched_old_fonts=sorted(unmatched_old_fonts, key=lambda t: -t[2]),
    )


def apply_learned(config: dict, result: LearnResult, min_confidence: str = "high") -> dict:
    """Return a NEW config dict with proposals at/above min_confidence merged
    in. Never mutates the passed-in config. Later (higher-count) proposals
    never overwrite an earlier one already set in this same call -- for
    colors specifically, colors.remap is keyed by hex only (not role-aware),
    so if the same hex was proposed with two different targets under
    different roles, the higher-count one wins and the other is dropped."""
    config = copy.deepcopy(config)
    threshold = CONFIDENCE_LEVELS[min_confidence]

    colors_cfg = config.setdefault("colors", {})
    remap = colors_cfg.setdefault("remap", {})
    approved = colors_cfg.setdefault("approved", [])
    approved_set = {colors_mod.normalize_hex(h) for h in approved}

    for p in result.color_proposals:
        if CONFIDENCE_LEVELS[p.confidence] < threshold:
            continue
        remap.setdefault(f"#{p.old_hex}", f"#{p.new_hex}")
        if p.new_hex not in approved_set:
            approved.append(f"#{p.new_hex}")
            approved_set.add(p.new_hex)

    fonts_cfg = config.setdefault("fonts", {})
    font_remap = fonts_cfg.setdefault("remap", {})
    font_approved = fonts_cfg.setdefault("approved", [])
    font_approved_keys = {normalize_key(n) for n in font_approved}

    for p in result.font_proposals:
        if CONFIDENCE_LEVELS[p.confidence] < threshold:
            continue
        font_remap.setdefault(p.old_font, p.new_font)
        if normalize_key(p.new_font) not in font_approved_keys:
            font_approved.append(p.new_font)
            font_approved_keys.add(normalize_key(p.new_font))

    return config


def write_learned_to_yaml(path: str | Path, result: LearnResult, min_confidence: str = "high") -> int:
    """Apply proposals directly onto the YAML file at `path`, in place,
    preserving its existing comments/structure (via ruamel's round-trip
    mode) rather than round-tripping through a plain dict, which would
    flatten brand_rules.yaml's hand-curated comments and grouping.

    Returns the number of proposals actually applied (skips anything
    already present).
    """
    path = Path(path)
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)  # matches brand_rules.yaml's existing style
    with path.open("r", encoding="utf-8") as f:
        data = yaml.load(f)

    threshold = CONFIDENCE_LEVELS[min_confidence]
    applied = 0

    colors_cfg = data.setdefault("colors", {})
    remap = colors_cfg.setdefault("remap", {})
    approved = colors_cfg.setdefault("approved", [])
    approved_set = {colors_mod.normalize_hex(str(h)) for h in approved}
    remap_keys = {colors_mod.normalize_hex(str(k)) for k in remap.keys()}

    for p in result.color_proposals:
        if CONFIDENCE_LEVELS[p.confidence] < threshold:
            continue
        if p.old_hex in remap_keys:
            continue
        remap[f"#{p.old_hex}"] = f"#{p.new_hex}"
        remap_keys.add(p.old_hex)
        applied += 1
        if p.new_hex not in approved_set:
            approved.append(f"#{p.new_hex}")
            approved_set.add(p.new_hex)

    fonts_cfg = data.setdefault("fonts", {})
    font_remap = fonts_cfg.setdefault("remap", {})
    font_approved = fonts_cfg.setdefault("approved", [])
    font_approved_keys = {normalize_key(str(n)) for n in font_approved}
    font_remap_keys = {normalize_key(str(k)) for k in font_remap.keys()}

    for p in result.font_proposals:
        if CONFIDENCE_LEVELS[p.confidence] < threshold:
            continue
        if normalize_key(p.old_font) in font_remap_keys:
            continue
        font_remap[p.old_font] = p.new_font
        font_remap_keys.add(normalize_key(p.old_font))
        applied += 1
        if normalize_key(p.new_font) not in font_approved_keys:
            font_approved.append(p.new_font)
            font_approved_keys.add(normalize_key(p.new_font))

    if applied:
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(data, f)

    return applied
