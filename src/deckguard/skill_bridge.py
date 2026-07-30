"""Bridge to the `kone-deck-generator` Claude Code skill, for deckguard's
"build a brand-new deck from a brief, no source deck at all" capability
(`redesign_deck(deck_path=None, brief=...)`).

That capability used to go through `compose.py`'s own `build_deck`: a
content/stat/timeline slide gets FIT onto whichever of deckguard's ~25
org-template layouts matches its shape (`match_layout`), placeholder
text is left theme-inherited, then one `fix_deck` pass resolves that
inheritance to an explicit brand color. That machinery exists to serve
THREE different callers of `redesign_deck` at once (redesign real
content, fill gaps in an existing deck, or author one from nothing),
and for the "real content, possibly from an existing deck" cases it's
still the right tool -- there's no source content here to hand to a
purpose-built, hand-tuned renderer instead.

But for the pure "nothing but a brief" case, the `kone-deck-generator`
skill (an independently maintained sibling of the `kone-design` skill,
normally installed under `~/.claude/skills/`) is a BETTER renderer for
exactly this one job: a library of 23 real slide ARCHETYPES (data, not
code -- `kone_engine.py`'s declarative region/group renderer plus
`archetypes_batch1/2/3.py`'s definitions), each a near-literal
transcription of a real KONE slide with real icons/charts/backgrounds,
already-compliant KONE brand colors and shrink-to-fit text -- compliant
by construction, not by a subsequent inherited-color-resolution pass.
This module imports that skill's own `kone_deck_creator.build_deck`
(never copies it, so improving an archetype there benefits both the
standalone skill and deckguard at once) and does the planning step
(brief -> spec JSON) the same way `redesign.py`'s own
`call_claude_for_outline` does -- same client/model/Usage conventions
-- but targeting the skill's own archetype-keyed spec schema instead
of compose.py's, with per-archetype guidance built at call time from
the skill's own `catalog.json` (purpose/keywords/slots) and
`archetypes.SAMPLES` (a worked content example per archetype), not
hand-duplicated here. Content shape varies too much archetype-to-
archetype (a 5-icon row vs. a 2x2 matrix vs. a comparison table) for a
single rigid structured-output schema the way the old 6-layout system
had one, so this asks for plain JSON in the response and validates/
parses it here instead -- the same approach the skill's own (now
retired) `kone_planner.call_claude` used before deckguard had any
tighter integration at all.

Deliberately NOT used for the other two `redesign_deck` starting
points (an existing deck, with or without a brief): the skill's
`build_deck` always starts fresh from its OWN bundled master file and
has no notion of appending onto an incoming deck, so real extracted
slide content stays on `compose.py`'s path, which already has that
(`existing_deck_path` / `import_layouts`).

Where the skill is loaded from (`_skill_dir`, in order):
1. `KONE_DECK_GENERATOR_DIR`, if set -- an explicit override, e.g. for
   a developer actively co-editing the live skill.
2. `~/.claude/skills/kone-deck-generator`, if present -- the standard
   Claude Code interactive-session location, so nothing changes for
   anyone developing deckguard and the skill together right here.
3. deckguard's OWN bundled copy under `deckguard/assets/kone_deck_generator/`
   -- a plain file copy (not a symlink, not re-fetched at build time),
   vendored so the capability actually works wherever deckguard itself
   is deployed (a Railway build has no `~/.claude/skills/` at all).
   `kone_deck_creator.py`/`kone_planner.py` are copied byte-for-byte,
   never modified -- keeping them re-syncable from the skill by just
   copying the files again, not a fork to keep merging. Its `MASTER`
   pptx path resolves as a sibling `kone-design/uploads/...` directory
   (the skill's own default, unmodified), which is why that file lives
   at `deckguard/assets/kone-design/uploads/...` here too.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Optional

import anthropic

from deckguard.compose import ComposeResult
from deckguard.redesign import (
    DEFAULT_MODEL,
    RedesignError,
    RedesignResult,
    Usage,
    _stream_final_message,
)

_INTERACTIVE_SKILL_DIR = "~/.claude/skills/kone-deck-generator"
_VENDORED_SKILL_DIR = Path(__file__).with_name("assets") / "kone_deck_generator"

_creator_module = None  # cached after first successful import
_archetypes_module = None  # cached after first successful import
_catalog_cache: Optional[dict] = None


def _skill_dir() -> Path:
    """Resolve the skill's directory -- see this module's own docstring
    for the full 3-step fallback and why each step exists."""
    env = os.environ.get("KONE_DECK_GENERATOR_DIR")
    if env:
        return Path(env).expanduser()
    interactive = Path(_INTERACTIVE_SKILL_DIR).expanduser()
    if (interactive / "kone_deck_creator.py").is_file():
        return interactive
    return _VENDORED_SKILL_DIR


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
    return _archetypes_module


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


# --------------------------------------------------------------------------
# Planning: brief -> the skill's own spec JSON (title + slides, each a
# {"archetype": <name>, ...that archetype's own content fields...}).
# Content shape varies too much archetype-to-archetype (a 5-icon row vs.
# a 2x2 matrix vs. a comparison table) for one rigid structured-output
# schema, so this builds a plain-text prompt (rules + the full archetype
# guide, generated from the skill's own catalog.json + archetypes.SAMPLES)
# and parses the model's JSON response directly, same approach the
# skill's own (now retired) kone_planner.call_claude used.
# --------------------------------------------------------------------------

_KONE_SYSTEM_RULES = """\
You are the deck planner for KONE's deck generator. You do NOT design visuals -- a
separate engine renders each archetype to exact KONE brand spec (geometry, fonts,
colors, icons, charts, backgrounds). Your only job: turn a brief into a slide-by-slide
plan as strict JSON.

RULES
- The cover (intro) and closing (outro) are added automatically from the KONE master.
  Do NOT plan a cover or a thank-you slide. Plan the BODY only.
- For each idea in the brief, pick the archetype whose PURPOSE and shape fit best --
  use the "Use when"/keywords guidance below, not variety for its own sake.
- Fill only that archetype's own content fields, matching the shape of its worked
  example below (same keys; a "groups"-style example is a list of dicts, keep it a
  list of dicts with the same per-item keys).
- Never invent facts, numbers, or names beyond what the brief supports -- if the
  brief doesn't give you enough for a specific claim, write a more general but still
  concrete statement rather than a fabricated number.
- KONE voice: sentence case, plain, confident, no marketing fluff, no emoji.
- Vary archetypes across the deck; don't reuse one archetype for everything.
- Output ONLY a JSON object, no prose, no markdown fences, of this exact shape:
  {"title": "<deck title, fills the retained cover>",
   "slides": [{"archetype": "<name>", ...that archetype's own content fields...}, ...]}
"""


def _kone_archetype_guide() -> str:
    """One entry per known archetype: purpose, routing keywords, slots
    (all from catalog.json when present) and a worked content example
    (from archetypes.SAMPLES) -- built at call time from the skill's own
    data so it can never drift out of sync with whatever archetypes the
    skill actually ships."""
    archetypes = _load_archetypes()
    catalog = _kone_catalog()
    parts = []
    for name in sorted(archetypes.ARCHETYPES.keys()):
        info = catalog.get(name, {})
        lines = [f"### {name}"]
        if info.get("purpose"):
            lines.append(f"Purpose: {info['purpose']}")
        if info.get("keywords"):
            lines.append(f"Use when: {', '.join(info['keywords'])}")
        if info.get("slots"):
            lines.append(f"Slots: {info['slots']}")
        sample = archetypes.SAMPLES.get(name)
        if sample is not None:
            lines.append(f"Example content: {json.dumps(sample, ensure_ascii=False)}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _kone_system_prompt() -> str:
    return _KONE_SYSTEM_RULES + "\n\nAvailable archetypes:\n\n" + _kone_archetype_guide()


def _build_kone_messages(brief: str, target_slides: Optional[int], notes: Optional[str]) -> list:
    sections = [f"Brief describing the deck to build:\n{brief}"]
    if target_slides is not None:
        sections.append(f"Aim for approximately {target_slides} total BODY slides (excluding the retained cover/thank-you).")
    if notes:
        sections.append(f"Additional guidance from the operator running this tool:\n{notes}")
    return [{"role": "user", "content": "\n\n".join(sections)}]


def call_claude_for_kone_spec(
    brief: str,
    target_slides: Optional[int] = None,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    notes: Optional[str] = None,
    api_key: Optional[str] = None,
    client=None,
) -> tuple[dict, Usage]:
    """Same call shape as `redesign.call_claude_for_outline`, targeting
    the skill's archetype-keyed spec instead of compose.py's outline
    schema. `effort` is accepted for interface parity with the rest of
    `redesign_deck`'s callers but currently unused: this call doesn't use
    structured-output's `output_config` (see module docstring for why),
    and that's the only place this codebase's `effort` knob attaches.
    `client` is the same test-injection point (any `.messages.stream(...)`
    Anthropic-SDK-shaped object) the rest of the redesign test suite uses.
    """
    del effort
    if client is None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RedesignError("ANTHROPIC_API_KEY is not set -- redesign needs an Anthropic API key")
        client = anthropic.Anthropic(api_key=key)

    system = _kone_system_prompt()
    messages = _build_kone_messages(brief, target_slides, notes)
    response = _stream_final_message(
        client,
        model=model,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=system,
        messages=messages,
    )

    if response.stop_reason == "refusal":
        raise RedesignError("Claude declined the deck-planning request (safety refusal) -- try again or adjust the brief")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise RedesignError(f"no text content in the model response (stop_reason={response.stop_reason!r})")
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("\n") + 1:] if "\n" in text else text
    try:
        spec = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RedesignError(f"model response was not valid JSON: {exc}") from exc

    usage = Usage(input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens, model=model)
    return spec, usage


# --------------------------------------------------------------------------
# Validation: STRUCTURAL only (known archetype name, a slide dict that
# actually names one) -- content shape is deliberately NOT re-validated
# per-archetype here: `kone_engine.render_archetype` is already
# defensive about a missing/short content list (a region whose content
# key is absent is just skipped; a `groups` list shorter than its origin
# slots just leaves the extra slots empty -- see its own `zip` over
# `origins`/`items`), so there's no missing-content failure mode this
# needs to catch before rendering the way the old fixed 6-layout system
# did (exactly-N-columns, exactly-N-stats). Character/length limits
# were dropped from validation entirely back when the skill's own
# shrink-to-fit renderer made them advisory (see the commit that did
# that for the previous archetype set) -- still true here.
# --------------------------------------------------------------------------


def _validate_kone_spec(spec: dict, known_archetypes: set) -> None:
    errors: list = []
    if not spec.get("title"):
        errors.append("spec: missing deck 'title'")
    slides = spec.get("slides") or []
    if not slides:
        errors.append("spec: zero slides")

    for i, s in enumerate(slides, start=1):
        if not isinstance(s, dict):
            errors.append(f"slide {i}: not a JSON object")
            continue
        archetype = s.get("archetype")
        if archetype not in known_archetypes:
            errors.append(f"slide {i}: unknown archetype {archetype!r} -- not one of {sorted(known_archetypes)}")

    if errors:
        raise RedesignError(
            "the model's deck spec doesn't fit the kone-deck-generator skill's archetypes:\n  - "
            + "\n  - ".join(errors)
        )


def build_deck_via_skill(
    brief: str,
    out_path,
    target_slides: Optional[int] = None,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    notes: Optional[str] = None,
    api_key: Optional[str] = None,
    client=None,
) -> tuple[ComposeResult, RedesignResult]:
    """Plan a spec from `brief` and render it with the skill's own
    `build_deck`, wrapped into the same `(ComposeResult, RedesignResult)`
    shape every other `redesign_deck` path returns, so callers (the CLI,
    tests) don't need to know which renderer produced a given result.
    """
    creator = _load_creator()
    archetypes = _load_archetypes()
    spec, usage = call_claude_for_kone_spec(
        brief, target_slides=target_slides, model=model, effort=effort, notes=notes,
        api_key=api_key, client=client,
    )
    _validate_kone_spec(spec, set(archetypes.ARCHETYPES.keys()))

    creator.build_deck(spec, str(out_path))

    layouts_used = ["Cover F"] + [s["archetype"] for s in spec["slides"]] + ["Outro"]
    compose_result = ComposeResult(slide_count=len(layouts_used), layouts_used=layouts_used, manual_review=[])
    # No compose.py `Outline` exists for this path -- nothing downstream
    # reads `RedesignResult.outline`, so this is left None rather than
    # forcing a fake Outline into being just to satisfy the type.
    redesign_result = RedesignResult(outline=None, skipped=[], usage=usage)
    return compose_result, redesign_result
