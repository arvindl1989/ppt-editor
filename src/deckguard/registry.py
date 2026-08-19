"""The archetype registry: what exists, and what each one reads.

Split out of `skill_bridge`, which had grown to 1,453 lines by mixing
this -- the one thing every part of the tool needs -- with AI planning
and deck assembly, which only the parked brief flow needs. Importing the
registry used to drag the planner, the composer and the fixer in behind
it.

Nothing here calls a model or writes a file. It answers three questions:
which archetypes exist, what content keys each one reads, and which of
them have picture slots.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

class RegistryError(RuntimeError):
    """The skill the registry reads from is missing or unusable.

    Defined here rather than imported from the parked redesign module:
    the code that raises an error should own it, and core must not
    import from `legacy`. `legacy.redesign.RedesignError` subclasses
    this, so every existing `except RedesignError` still catches.
    """


# `_ensure_skill_on_path` raised `RedesignError` by name after the split
# without importing it -- a missing skill produced a NameError instead
# of the clean message the caller was promised.
RedesignError = RegistryError

_INTERACTIVE_SKILL_DIR = "~/.claude/skills/kone-deck-generator"
_VENDORED_SKILL_DIR = Path(__file__).with_name("assets") / "kone_deck_generator"

_catalog_cache: Optional[dict] = None
_image_slots_cache: Optional[dict] = None
_creator_module = None      # cached after first successful import
_archetypes_module = None   # cached after first successful import
_photo_cache: Optional[list] = None


def _skill_dir() -> Path:
    """Resolve the skill's directory -- see this module's own docstring
    for the full 3-step fallback and why each step exists."""
    env = os.environ.get("KONE_DECK_GENERATOR_DIR")
    if env:
        return Path(env).expanduser()
    interactive = Path(_INTERACTIVE_SKILL_DIR).expanduser()
    if _usable(interactive):
        return interactive
    return _VENDORED_SKILL_DIR


def _usable(skill_dir: Path) -> bool:
    """Is this copy of the skill complete enough to build a deck?

    Having `kone_deck_creator.py` is not enough. The creator resolves
    the master template through a SIBLING `kone-design` directory, and
    an installed skill whose sibling sits somewhere else -- under
    `skills/synced/`, say -- has a creator that imports fine and then
    fails at `Presentation(MASTER)`. Which copy answered used to depend
    on sys.path ordering, so this failed only sometimes.
    """
    if not (skill_dir / "kone_deck_creator.py").is_file():
        return False
    uploads = skill_dir.parent / "kone-design" / "uploads"
    return any(uploads.glob("*.pptx"))

def _ensure_skill_on_path() -> Path:
    skill_dir = _skill_dir()
    if not (skill_dir / "kone_deck_creator.py").is_file():
        raise RedesignError(
            f"the kone-deck-generator skill isn't installed at {skill_dir} -- "
            "building a deck from a brief with no source deck needs it. Install it "
            "(see the skill's own setup.sh) or set KONE_DECK_GENERATOR_DIR to point at it."
        )
    if str(skill_dir) not in sys.path:
        sys.path.insert(0, str(skill_dir))
    return skill_dir

def _load_creator():
    """Import the skill's `kone_deck_creator` module by path, once.
    Raises a clean `RedesignError` (never a raw ImportError) if the
    skill isn't installed on this machine -- this capability is the
    one place in deckguard with an out-of-repo dependency, so a
    missing skill needs to fail with an actionable message, not a
    traceback deep in `redesign_deck`."""
    global _creator_module
    if _creator_module is not None:
        return _creator_module
    skill_dir = _ensure_skill_on_path()
    try:
        _creator_module = importlib.import_module("kone_deck_creator")
    except Exception as exc:
        raise RedesignError(f"failed to load the kone-deck-generator skill from {skill_dir}: {exc}") from exc
    return _creator_module

def _load_archetypes():
    """Import the skill's `archetypes` module -- `ARCHETYPES` (the known
    names) and `SAMPLES` (one worked content example per name), both
    used to build the planning prompt and to validate a spec, dynamically
    rather than hand-duplicated here."""
    global _archetypes_module
    if _archetypes_module is not None:
        return _archetypes_module
    skill_dir = _ensure_skill_on_path()
    try:
        _archetypes_module = importlib.import_module("archetypes")
    except Exception as exc:
        raise RedesignError(f"failed to load the kone-deck-generator skill from {skill_dir}: {exc}") from exc

    # kone-design's HTML gallery names 39 archetypes this engine has never
    # implemented, and people write briefs against THAT list. The finished
    # gallery (covers, dividers, agendas, closers) is parsed straight out
    # of its own markup and merged into the registry here, so every
    # runtime-derived thing -- signatures, previews, picture slots, the
    # planning prompt -- gains them without knowing they came from
    # elsewhere. Never load-bearing: a missing gallery adds nothing.
    _install_gallery(_archetypes_module)

    # And the rest of the vocabulary, generated from the master's own
    # published geometry. This runs last and never overwrites: anything
    # the engine or the gallery already implements was tuned against a
    # real rendering, while these are derived from a description.
    # Between the three the registry covers all 61 canonical archetypes.
    try:
        from deckguard import layouts as layouts_mod

        layouts_mod.install(_archetypes_module)
    except Exception:  # noqa: BLE001 -- additive, same as above
        pass
    return _archetypes_module

def _install_gallery(module) -> None:
    """Merge the archetypes kone-design's HTML gallery names.

    These used to be parsed out of that markup on every import, by code
    that also mined decks and built galleries. The parse is now a
    one-off whose output is committed next door, so what the registry
    holds is reviewable in a diff -- and so retiring one is an edit
    rather than a side effect. Never load-bearing: a missing file adds
    nothing.
    """
    path = Path(__file__).with_name("assets") / "gallery-archetypes.json"
    try:
        data = json.loads(path.read_text())
    except Exception:  # noqa: BLE001 -- additive by design
        return
    for name, spec in data.get("archetypes", {}).items():
        module.ARCHETYPES.setdefault(name, spec)
    for attr, key in (("BG", "bg"), ("SAMPLES", "samples")):
        target = getattr(module, attr, None)
        if isinstance(target, dict):
            for name, value in data.get(key, {}).items():
                target.setdefault(name, value)


def _kone_catalog() -> dict:
    """`catalog.json` -- purpose/keywords/slots per archetype, for
    routing a brief's ideas onto the archetype whose shape fits. Not
    every archetype has a catalog entry (a few predate the catalog and
    are self-explanatory, e.g. `three_stats`); those just get a shorter
    prompt entry built from their sample alone."""
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache
    skill_dir = _ensure_skill_on_path()
    catalog_path = skill_dir / "catalog.json"
    _catalog_cache = json.loads(catalog_path.read_text()) if catalog_path.is_file() else {}
    return _catalog_cache

def _derived_content_keys(name: str) -> list:
    """What the archetype's spec says it reads, or nothing if unknown."""
    try:
        from deckguard.layouts import content_keys

        return content_keys(_load_archetypes().ARCHETYPES.get(name) or {})
    except Exception:  # noqa: BLE001 -- the guide degrades, it never fails
        return []

def _sample_agrees(name: str, sample) -> bool:
    """Does the worked example still match what the renderer reads?

    A sample that predates a rebuilt archetype teaches the wrong keys,
    and the model follows the concrete example over the abstract slot
    list every time. Shown only while it agrees.
    """
    if not isinstance(sample, dict):
        return True
    keys = _derived_content_keys(name)
    if not keys:
        return True
    known = {k.split(" (")[0] for k in keys}
    return not (set(sample) - known)

def _sample_without_image_paths(name: str, sample: dict) -> dict:
    """The skill's own SAMPLES carry real absolute image paths for
    picture archetypes (they're built to render a standalone gallery).
    Showing those in the planning prompt invites the model to echo or
    invent a path, when picture slots are filled automatically from the
    slide's own images afterward -- so strip them from the worked
    example, leaving every other field exactly as the skill wrote it."""
    slot = _archetype_image_slots().get(name)
    if slot is None or not isinstance(sample, dict):
        return sample
    out = dict(sample)
    if slot[0] == "single":
        out.pop(slot[1], None)
        return out
    _, group_key, item_key = slot
    items = out.get(group_key)
    if isinstance(items, list):
        out[group_key] = [
            {k: v for k, v in item.items() if k != item_key} if isinstance(item, dict) else item
            for item in items
        ]
    return out

def _archetype_image_slots() -> dict:
    global _image_slots_cache
    if _image_slots_cache is not None:
        return _image_slots_cache
    try:
        mod = _load_archetypes()
    except RedesignError:
        return {}
    figures = getattr(mod, "FIGURES", {}) or {}
    slots: dict = {}
    for name, arch in mod.ARCHETYPES.items():
        fig_keys = set(figures.get(name, {}))
        single = None
        group = None
        for reg in arch.get("regions", []):
            if reg.get("role") in ("picture", "image_band") and reg.get("content") and reg["content"] not in fig_keys:
                single = ("single", reg["content"])
                break
        for grp in arch.get("groups", []):
            for reg in grp.get("regions", []):
                if reg.get("role") in ("picture", "image_band") and reg.get("content"):
                    group = ("group", grp["content"], reg["content"])
                    break
            if group:
                break
        if group:
            slots[name] = group  # group slots win: per-item pictures are the archetype's visual point
        elif single:
            slots[name] = single
    _image_slots_cache = slots
    return slots

def archetype_image_capacity(archetype_name: str) -> int:
    """How many source images `archetype_name` can actually place. 0 for
    an archetype with no picture slots (most of them). Used to tell the
    planning call what each archetype can hold, and to cap how many
    images are written out for one."""
    slot = _archetype_image_slots().get(archetype_name)
    if slot is None:
        return 0
    if slot[0] == "single":
        return 1
    return 99  # group-based: bounded by however many group items the content actually has

def _photo_library() -> list:
    """KONE's own photography, for picture slots nothing else can fill.

    Resolved like the skill itself: an explicit env override, then the
    installed `kone-design` skill, then the copy vendored into this
    package so a deploy without the skills installed still has photos.
    """
    from pathlib import Path

    candidates = []
    env = os.environ.get("KONE_DESIGN_DIR")
    if env:
        candidates.append(Path(env) / "assets" / "photos")
    candidates.append(Path.home() / ".claude" / "skills" / "kone-design" / "assets" / "photos")
    candidates.append(Path(__file__).parent / "assets" / "kone-design" / "photos")
    for directory in candidates:
        try:
            photos = sorted(p for p in directory.glob("*.jpg") if p.is_file())
        except OSError:
            continue
        if photos:
            return [str(p) for p in photos]
    return []

def fill_empty_photo_slots(spec: dict) -> int:
    """Give every unfilled picture slot in a from-scratch deck spec a
    real KONE photograph.

    `kone_engine._image()` draws a flat sand rectangle when handed no
    path. That is the right fallback for a missing file; it is the wrong
    OUTCOME for a deck built from a brief, where there is no source deck
    to carry images from and so EVERY photo slot is empty. The review
    previews drew those slots as "PHOTO", the built deck came back with
    blank sand blocks, and the two didn't match.

    Selection is deterministic -- keyed on the slide's own text, so the
    same brief always produces the same deck -- and walks the library
    rather than repeating one image down the deck.

    Returns how many slots were filled. A no-op when the archetype has
    no picture slot, when the slot is already filled (a transform
    carrying the source deck's own images always wins), or when no photo
    library is reachable.
    """
    photos = _photo_library()
    if not photos:
        return 0
    slots = _archetype_image_slots()
    filled = 0
    used = 0

    def _next_photo(seed: str) -> str:
        nonlocal used
        start = sum(ord(c) for c in seed) if seed else 0
        photo = photos[(start + used) % len(photos)]
        used += 1
        return photo

    for slide in spec.get("slides") or []:
        slot = slots.get(slide.get("archetype"))
        if not slot:
            continue
        seed = str(slide.get("title") or slide.get("heading") or slide.get("archetype") or "")
        if slot[0] == "single":
            key = slot[1]
            if not slide.get(key):
                slide[key] = _next_photo(seed)
                filled += 1
        else:
            _kind, group_key, item_key = slot
            for item in slide.get(group_key) or []:
                if isinstance(item, dict) and not item.get(item_key):
                    item[item_key] = _next_photo(seed)
                    filled += 1
    return filled

def invalidate_archetype_caches() -> None:
    """Drop the derived views of the registry.

    Signatures and picture-slot maps are computed once and cached, which
    is right for a fixed registry and wrong the moment archetypes are
    ADDED at runtime -- designs mined from a reference deck were
    registered and then never seen by the matcher, because the cache
    predated them.
    """
    global _signature_cache, _image_slots_cache
    _signature_cache = None
    _image_slots_cache = None


def register_mined(mined: dict) -> list:
    """Add archetypes read out of someone's own deck to the registry.

    Without this the renderer looks up a mined name, finds nothing, and
    draws a slide with no content on it -- the deck builds, the file
    downloads, and every page from your own templates is blank. The
    same silent failure the picker had for unbuilt archetypes.

    KONE's own always win a name clash: mined designs are additive.
    Returns the names actually added.
    """
    archetypes = _load_archetypes()
    added = []
    for name, spec in (mined.get("archetypes") or {}).items():
        if name not in archetypes.ARCHETYPES:
            archetypes.ARCHETYPES[name] = spec
            added.append(name)
    for attr, key in (("SAMPLES", "samples"), ("BG", "bg")):
        target = getattr(archetypes, attr, None)
        if isinstance(target, dict):
            for name, value in (mined.get(key) or {}).items():
                target.setdefault(name, value)
    _register_role_styles(mined.get("role_styles") or {})
    if added:
        global _image_slots_cache
        _image_slots_cache = None
    return added


def _register_role_styles(styles: dict) -> None:
    """Teach the engine the type a mined deck used.

    Mined roles are auto-named from what they render -- `ref_i53_141414`
    is "Inter 53 black" -- so the engine has never heard of them and
    raises KeyError mid-draw. They also arrive with the colour as a hex
    string where the engine wants an RGB triple.

    These deliberately are NOT mapped onto brand roles. The point of
    mining someone's deck is to reuse THEIR design; preflight is what
    then says where that design is off-brand.
    """
    if not styles:
        return
    try:
        engine = _load_archetypes().E
        table = engine.ROLE_STYLE
    except Exception:  # noqa: BLE001
        return
    for role, style in styles.items():
        if role in table:
            continue
        entry = list(style)
        if len(entry) >= 3 and isinstance(entry[2], str):
            # The engine assigns this straight to `font.color.rgb`, which
            # only accepts an RGBColor -- a plain tuple raises just as a
            # hex string does.
            from pptx.dml.color import RGBColor

            text = entry[2].lstrip("#")
            try:
                entry[2] = RGBColor.from_string(text.upper())
            except Exception:  # noqa: BLE001
                entry[2] = RGBColor(0x14, 0x14, 0x14)
        table[role] = tuple(entry)
