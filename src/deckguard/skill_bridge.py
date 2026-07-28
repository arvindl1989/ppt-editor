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

# Mirrors the kone-design skill's own KONE_DESIGN_DIR convention: an
# out-of-repo, per-machine directory, not something deckguard vendors
# or pins a version of -- see this module's own docstring for why
# that's the right trade for this one capability. Overridable for a
# machine where the skill lives somewhere other than the default
# Claude Code skills directory.
_DEFAULT_SKILL_DIR = "~/.claude/skills/kone-deck-generator"

_creator_module = None  # cached after first successful import


def _skill_dir() -> Path:
    raw = os.environ.get("KONE_DECK_GENERATOR_DIR") or _DEFAULT_SKILL_DIR
    return Path(raw).expanduser()


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
# Validation: the renderer (`kone_deck_creator.py`) hand-places every
# text box at a fixed geometry with no overflow handling of its own
# (confirmed by reading it -- no length checks, no auto-shrink), so a
# spec that violates the character limits its own layout functions were
# sized for would silently overflow/overlap on the rendered slide.
# Structured-output schemas constrain shape, not string length, so this
# re-checks the limits documented in the skill's own SKILL.md/
# kone_planner.py before anything is rendered, and reports every
# violation at once rather than failing on the first.
# --------------------------------------------------------------------------

_LIMITS = {
    "section_divider": {"eyebrow": 60, "title": 90},
    "title_content": {"title": 60, "bullet": 90},
    "two_content": {"title": 60, "heading": 30, "bullet": 90},
    "three_stats": {"title": 90, "label": 18, "value": 6, "desc": 70},
    "roadmap": {"eyebrow": 60, "title": 60, "phase_title": 20, "phase_desc": 90},
    "quote": {"label": 20, "quote": 140, "attribution": 60},
}


def _check_len(errors: list, where: str, value: Optional[str], limit: int) -> None:
    if value and len(value) > limit:
        errors.append(f"{where}: {len(value)} chars, over the {limit}-char limit ({value!r})")


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
        limits = _LIMITS[layout]

        if layout == "section_divider":
            if not s.get("title"):
                errors.append(f"{where}: missing 'title'")
            _check_len(errors, f"{where} title", s.get("title"), limits["title"])
            _check_len(errors, f"{where} eyebrow", s.get("eyebrow"), limits["eyebrow"])

        elif layout == "title_content":
            if not s.get("title"):
                errors.append(f"{where}: missing 'title'")
            _check_len(errors, f"{where} title", s.get("title"), limits["title"])
            bullets = s.get("bullets") or []
            if not bullets:
                errors.append(f"{where}: needs at least one bullet")
            for b in bullets:
                _check_len(errors, f"{where} bullet", b, limits["bullet"])

        elif layout == "two_content":
            if not s.get("title"):
                errors.append(f"{where}: missing 'title'")
            _check_len(errors, f"{where} title", s.get("title"), limits["title"])
            columns = s.get("columns") or []
            if len(columns) != 2:
                errors.append(f"{where}: needs exactly 2 columns, got {len(columns)}")
            for col in columns:
                _check_len(errors, f"{where} column heading", col.get("heading"), limits["heading"])
                for b in col.get("bullets") or []:
                    _check_len(errors, f"{where} column bullet", b, limits["bullet"])

        elif layout == "three_stats":
            if not s.get("title"):
                errors.append(f"{where}: missing 'title'")
            _check_len(errors, f"{where} title", s.get("title"), limits["title"])
            stats = s.get("stats") or []
            if len(stats) != 3:
                errors.append(f"{where}: needs exactly 3 stats, got {len(stats)}")
            for st in stats:
                _check_len(errors, f"{where} stat label", st.get("label"), limits["label"])
                _check_len(errors, f"{where} stat value", st.get("value"), limits["value"])
                _check_len(errors, f"{where} stat desc", st.get("desc"), limits["desc"])

        elif layout == "roadmap":
            if not s.get("title"):
                errors.append(f"{where}: missing 'title'")
            _check_len(errors, f"{where} title", s.get("title"), limits["title"])
            _check_len(errors, f"{where} eyebrow", s.get("eyebrow"), limits["eyebrow"])
            phases = s.get("phases") or []
            if not (2 <= len(phases) <= 5):
                errors.append(f"{where}: needs 2-5 phases, got {len(phases)}")
            for ph in phases:
                if not ph.get("year"):
                    errors.append(f"{where}: a phase is missing 'year'")
                _check_len(errors, f"{where} phase title", ph.get("title"), limits["phase_title"])
                _check_len(errors, f"{where} phase desc", ph.get("desc"), limits["phase_desc"])

        elif layout == "quote":
            if not s.get("quote"):
                errors.append(f"{where}: missing 'quote'")
            if not s.get("attribution"):
                errors.append(f"{where}: missing 'attribution'")
            _check_len(errors, f"{where} quote", s.get("quote"), limits["quote"])
            _check_len(errors, f"{where} attribution", s.get("attribution"), limits["attribution"])
            _check_len(errors, f"{where} label", s.get("label"), limits["label"])

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
