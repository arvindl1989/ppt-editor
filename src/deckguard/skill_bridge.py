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
exactly this one job: 6 body layouts, each a near-literal transcription
of the org LAYOUTS.md spec with hand-placed geometry and hardcoded,
already-compliant KONE brand colors -- compliant by construction, not
by a subsequent inherited-color-resolution pass. This module imports
that skill's own `kone_deck_creator.build_deck` (never copies it, so
improving a layout there benefits both the standalone skill and
deckguard at once) and does the planning step (brief -> spec JSON) the
same way `redesign.py`'s own `call_claude_for_outline` does -- same
client/model/effort/Usage conventions -- but targeting the skill's own
flatter, layout-name-keyed spec schema instead of compose.py's.

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


# --------------------------------------------------------------------------
# Planning: brief -> the skill's own spec JSON (title + slides, each a
# {"layout": ..., ...that layout's own fields}). A flat schema with
# every layout's fields always present (nulled/emptied when unused),
# same convention `redesign.py`'s own OUTLINE_ITEM_SCHEMA uses -- one
# object shape a structured-output call can hold to, rather than a
# discriminated union.
# --------------------------------------------------------------------------

_COLUMN_SCHEMA = {
    "type": "object",
    "properties": {"heading": {"type": "string"}, "bullets": {"type": "array", "items": {"type": "string"}}},
    "required": ["heading", "bullets"],
    "additionalProperties": False,
}
_STAT_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string"}, "value": {"type": "string"}, "desc": {"type": "string"},
    },
    "required": ["label", "value", "desc"],
    "additionalProperties": False,
}
_PHASE_SCHEMA = {
    "type": "object",
    "properties": {
        "year": {"type": "string"}, "title": {"type": "string"}, "desc": {"type": "string"},
    },
    "required": ["year", "title", "desc"],
    "additionalProperties": False,
}

KONE_SLIDE_LAYOUTS = ["section_divider", "title_content", "two_content", "three_stats", "roadmap", "quote"]

KONE_SLIDE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "layout": {"type": "string", "enum": KONE_SLIDE_LAYOUTS},
        "eyebrow": {"type": ["string", "null"]},
        "title": {"type": ["string", "null"]},
        "bullets": {"type": "array", "items": {"type": "string"}},
        "columns": {"type": "array", "items": _COLUMN_SCHEMA},
        "stats": {"type": "array", "items": _STAT_SCHEMA},
        "phases": {"type": "array", "items": _PHASE_SCHEMA},
        "label": {"type": ["string", "null"]},
        "quote": {"type": ["string", "null"]},
        "attribution": {"type": ["string", "null"]},
    },
    "required": [
        "layout", "eyebrow", "title", "bullets", "columns", "stats", "phases",
        "label", "quote", "attribution",
    ],
    "additionalProperties": False,
}

KONE_SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "slides": {"type": "array", "items": KONE_SLIDE_ITEM_SCHEMA},
    },
    "required": ["title", "slides"],
    "additionalProperties": False,
}


def _kone_planner_system_prompt() -> str:
    """The skill's own planning rules/schema guidance (`kone_planner.py`),
    imported rather than restated here -- deckguard's structured-output
    `KONE_SPEC_SCHEMA` above is what actually constrains the model's
    JSON shape; this text is guidance on top of that, and living in the
    skill keeps it in sync with the skill's own layout catalog."""
    _ensure_skill_on_path()
    return importlib.import_module("kone_planner").SYSTEM_PROMPT


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
    the skill's spec schema instead of compose.py's outline schema.
    `client` is the same test-injection point (any `.messages.stream(...)`
    Anthropic-SDK-shaped object)."""
    if client is None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RedesignError("ANTHROPIC_API_KEY is not set -- redesign needs an Anthropic API key")
        client = anthropic.Anthropic(api_key=key)

    system = _kone_planner_system_prompt()
    messages = _build_kone_messages(brief, target_slides, notes)
    response = _stream_final_message(
        client,
        model=model,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=system,
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": KONE_SPEC_SCHEMA}},
        messages=messages,
    )

    if response.stop_reason == "refusal":
        raise RedesignError("Claude declined the deck-planning request (safety refusal) -- try again or adjust the brief")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise RedesignError(f"no text content in the model response (stop_reason={response.stop_reason!r})")
    try:
        spec = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RedesignError(f"model response was not valid JSON: {exc}") from exc

    usage = Usage(input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens, model=model)
    return spec, usage


# --------------------------------------------------------------------------
# Validation: STRUCTURAL only (right layout name, required fields
# present, the counts each layout function actually indexes into --
# e.g. `two_content` zips its columns against exactly 2 fixed x-offsets,
# so a 1- or 3-column spec would silently drop/ignore content, not just
# look bad). Character-length limits are deliberately NOT re-enforced
# here anymore: the renderer itself (kone_deck_creator.py, as of the
# skill's shrink-to-fit update) measures and shrinks single-line text
# to its box width and falls back to PowerPoint's own shrink-on-overflow
# for multi-line text, making those limits advisory on the skill's own
# side -- re-rejecting a slightly-over value here would just resurrect
# the exact "the model's deck spec doesn't fit" failure the skill's own
# fix was built to eliminate.
# --------------------------------------------------------------------------


def _validate_kone_spec(spec: dict, known_layouts: set) -> None:
    errors: list = []
    if not spec.get("title"):
        errors.append("spec: missing deck 'title'")
    slides = spec.get("slides") or []
    if not slides:
        errors.append("spec: zero slides")

    for i, s in enumerate(slides, start=1):
        layout = s.get("layout")
        where = f"slide {i} ({layout})"
        if layout not in known_layouts:
            errors.append(f"{where}: unknown layout {layout!r} -- not one of {sorted(known_layouts)}")
            continue

        if layout == "section_divider":
            if not s.get("title"):
                errors.append(f"{where}: missing 'title'")

        elif layout == "title_content":
            if not s.get("title"):
                errors.append(f"{where}: missing 'title'")
            if not s.get("bullets"):
                errors.append(f"{where}: needs at least one bullet")

        elif layout == "two_content":
            if not s.get("title"):
                errors.append(f"{where}: missing 'title'")
            columns = s.get("columns") or []
            if len(columns) != 2:
                errors.append(f"{where}: needs exactly 2 columns, got {len(columns)}")

        elif layout == "three_stats":
            if not s.get("title"):
                errors.append(f"{where}: missing 'title'")
            stats = s.get("stats") or []
            if len(stats) != 3:
                errors.append(f"{where}: needs exactly 3 stats, got {len(stats)}")

        elif layout == "roadmap":
            if not s.get("title"):
                errors.append(f"{where}: missing 'title'")
            phases = s.get("phases") or []
            if not (2 <= len(phases) <= 5):
                errors.append(f"{where}: needs 2-5 phases, got {len(phases)}")
            for ph in phases:
                if not ph.get("year"):
                    errors.append(f"{where}: a phase is missing 'year'")

        elif layout == "quote":
            if not s.get("quote"):
                errors.append(f"{where}: missing 'quote'")
            if not s.get("attribution"):
                errors.append(f"{where}: missing 'attribution'")

    if errors:
        raise RedesignError(
            "the model's deck spec doesn't fit the kone-deck-generator skill's layouts:\n  - "
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
    spec, usage = call_claude_for_kone_spec(
        brief, target_slides=target_slides, model=model, effort=effort, notes=notes,
        api_key=api_key, client=client,
    )
    _validate_kone_spec(spec, set(creator.REGISTRY.keys()))

    creator.build_deck(spec, str(out_path))

    layouts_used = ["Cover F"] + [s["layout"] for s in spec["slides"]] + ["Outro"]
    compose_result = ComposeResult(slide_count=len(layouts_used), layouts_used=layouts_used, manual_review=[])
    # No compose.py `Outline` exists for this path -- nothing downstream
    # reads `RedesignResult.outline`, so this is left None rather than
    # forcing a fake Outline into being just to satisfy the type.
    redesign_result = RedesignResult(outline=None, skipped=[], usage=usage)
    return compose_result, redesign_result
