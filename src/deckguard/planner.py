"""Plan a deck from a brief.

The one place a model is involved. Everything else in the tool is
deterministic: this turns prose -- a brief, a pasted announcement email
-- into a spec of archetypes and content, which the same renderer then
draws exactly as it draws a hand-picked deck. A plan is a starting
point, never a final answer; the caller edits it afterwards.

Lifted out of the parked `skill_bridge`, which mixed this with the
archetype registry that everything needs.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

import anthropic

from dataclasses import dataclass

from deckguard.registry import (
    RegistryError,
    _archetype_image_slots,
    _derived_content_keys,
    _kone_catalog,
    _load_archetypes,
    _sample_agrees,
    _sample_without_image_paths,
)

DEFAULT_MODEL = "claude-opus-5"


@dataclass(frozen=True)
class Usage:
    """What the planning call cost, so a caller can report it."""

    input_tokens: int
    output_tokens: int
    model: str


class PlanningError(RegistryError):
    """The planning call could not produce a usable spec."""


def _stream_final_message(client, **stream_kwargs):
    """Call `client.messages.stream(...)` and return the final message.

    Anthropic's own error types are translated here rather than letting
    a raw API error dict reach the user: a 429 or a 5xx is transient and
    on Anthropic's side, and saying so is the difference between "try
    again in a minute" and "something is wrong with my brief".
    """
    try:
        with client.messages.stream(**stream_kwargs) as stream:
            return stream.get_final_message()
    except anthropic.APIStatusError as exc:
        if exc.status_code == 429 or exc.status_code >= 500:
            raise PlanningError(
                f"Claude's API is rate-limited or overloaded (HTTP {exc.status_code}) -- "
                "nothing to do with your brief. Wait a moment and try again."
            ) from exc
        raise PlanningError(f"Claude API error (HTTP {exc.status_code}): {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise PlanningError(f"Could not reach the Anthropic API: {exc}") from exc


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


def _contract_for(name: str):
    """The archetype's contract, or None if it is outside the two sets.

    Kept behind a function so the guide degrades to what it always
    said rather than failing when a mined design has no contract.
    """
    try:
        from deckguard import contracts

        return contracts.for_archetype(name)
    except Exception:  # noqa: BLE001
        return None


def _kone_archetype_guide() -> str:
    """One entry per known archetype: purpose, routing keywords, slots
    (all from catalog.json when present) and a worked content example
    (from archetypes.SAMPLES) -- built at call time from the skill's own
    data so it can never drift out of sync with whatever archetypes the
    skill actually ships."""
    archetypes = _load_archetypes()
    catalog = dict(_kone_catalog())
    # Extras carry their own routing: they are not in `catalog.json`,
    # and an archetype the planner has no reason to choose is one that
    # never gets chosen.
    from deckguard.layouts import _EXTRA_META

    for key, meta in _EXTRA_META.items():
        if key in archetypes.ARCHETYPES:
            entry = dict(catalog.get(key) or {})
            entry.setdefault("purpose", meta.get("purpose", ""))
            entry.setdefault("keywords", meta.get("keywords", []))
            entry.setdefault("notes", meta.get("notes", []))
            catalog[key] = entry
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
        # The authority, derived from the registry the renderer will
        # actually use. `catalog.json` covers 22 of 80 archetypes and
        # `SAMPLES` 41, so most were described by name alone -- and a
        # stale sample is worse than none: `agenda_a_table`'s advertised
        # `text1..text4` long after the renderer was rebuilt to read
        # `items`, so a planner emitted four keys nothing reads and the
        # agenda came out as a title on an empty slide.
        keys = _derived_content_keys(name)
        if keys:
            lines.append(
                "Content keys (authoritative -- anything else is discarded): "
                + "; ".join(keys)
            )
        # What the slide must HAVE to be worth choosing, as opposed to
        # what it will accept. The key list says `items (list of up to
        # 3 x {heading, text})`, which reads as an allowance; a deck
        # with one item in a three-column grid has two holes in it.
        contract = _contract_for(name)
        if contract is not None and contract.needs:
            lines.append(
                "Do not choose this unless the source gives you: "
                + " · ".join(s.describe() for s in contract.needs))
        slot = _archetype_image_slots().get(name)
        if slot is not None:
            lines.append(
                "Pictures: this archetype has picture slot(s), filled automatically from the slide's own "
                "images -- do NOT emit an image path or filename yourself."
            )
        for note in (catalog.get(name, {}) or {}).get("notes", []):
            lines.append(f"Rule: {note}")
        sample = archetypes.SAMPLES.get(name)
        if sample is not None and _sample_agrees(name, sample):
            lines.append(f"Example content: {json.dumps(_sample_without_image_paths(name, sample), ensure_ascii=False)}")
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
            raise PlanningError("ANTHROPIC_API_KEY is not set -- redesign needs an Anthropic API key")
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
        raise PlanningError("Claude declined the deck-planning request (safety refusal) -- try again or adjust the brief")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise PlanningError(f"no text content in the model response (stop_reason={response.stop_reason!r})")
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("\n") + 1:] if "\n" in text else text
    try:
        spec = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanningError(f"model response was not valid JSON: {exc}") from exc

    usage = Usage(input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens, model=model)
    return spec, usage


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
        raise PlanningError(
            "the model's deck spec doesn't fit the kone-deck-generator skill's archetypes:\n  - "
            + "\n  - ".join(errors)
        )
