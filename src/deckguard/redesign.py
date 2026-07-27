"""AI-assisted deck redesign: turn an arbitrary, not-necessarily-on-brand
deck into a fresh outline of the same kind `compose.py` already knows how
to build -- the realization of the "Phase 2" judgment layer this project's
own README has flagged as not-yet-implemented since Phase 1.

Deliberately narrow in scope, and deliberately NOT where any new brand
logic lives:

- Content extraction is 100% deterministic and reuses `retemplate.py`'s
  own `classify_slide` verbatim -- the same eligibility rules (a table,
  chart, embedded object, or over-full slide is left alone, never
  guessed at) apply here exactly as they do for `retemplate`. The model
  never sees a slide this project's own rules already consider unsafe to
  reinterpret.
- The ONLY thing an LLM call decides is, per eligible slide: which
  `compose.py` slide *kind* best fits its content, and a light copy-edit
  of that content into the kind's fields (bullets/quote/stats/...). The
  model's output is validated against a JSON schema shaped exactly like
  `compose.py`'s own outline dict format (see `outline_from_list`), so a
  human-written YAML outline and an AI-generated one are indistinguishable
  from that point on -- they run through the identical `build_deck` (same
  layout selection, same final `fix_deck` pass, same brand guarantees).
- Nothing about color, font, or layout-approval judgment is delegated to
  the model. That's exactly the split this project has used since Phase
  1: deterministic first, AI second, and AI only for the one judgment
  call -- "what kind of slide is this" -- that a shape-count heuristic
  can't make well.

Requires the `anthropic` package (a base dependency -- see
requirements.txt / pyproject.toml) and an `ANTHROPIC_API_KEY` at
runtime. Everything else in `deckguard` works without either; this is
the one command in the whole tool that makes an outbound API call.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pptx import Presentation

from deckguard.compose import ComposeError, ComposeResult, Outline, build_deck, outline_from_list
from deckguard.retemplate import SlideProfile, classify_slide

DEFAULT_MODEL = "claude-opus-5"

# As of this writing (see the claude-api skill's cached pricing table) --
# used only to give the caller a rough, clearly-labeled cost estimate
# alongside the real usage numbers the API returns. Verify against
# platform.claude.com/docs/en/pricing before trusting this for billing.
PRICE_PER_MTOK_USD = {
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

KIND_GUIDE = """\
Available slide kinds and when to use each:

- cover: the deck's own title slide. Only slide 1 of the ORIGINAL deck
  should ever become a cover.
- agenda: a short list of upcoming topics/sections (an outline of the
  deck itself).
- section: a chapter/divider slide -- just a short heading, marking a
  transition between topics. No body content.
- content: the default for an ordinary slide with a title and 1-3 blocks
  of bullet points. Use `columns` (one list of bullets per column) when
  the source slide visually reads as 2-3 side-by-side blocks; otherwise
  use a single `bullets` list.
- quote: a slide whose main content is a single attributed quotation.
  Needs quote_text and, if known, quote_author.
- statement: one short, unmissable, single-sentence message with no
  supporting bullets -- a big declarative claim, not a list.
- stat: a row of 2-3 numeric callouts (e.g. "40M / people moved daily").
  Needs `stats`, each with a short `number` and a `label`.
- timeline: a sequence of 2-3 dated/labeled milestones. Needs
  `milestones`, each with a `label` (date/phase) and `text` (what
  happens).
- end: the deck's closing/thank-you slide. Only the ORIGINAL deck's last
  slide should become this.
- blank: use only if a slide's content genuinely doesn't fit any of the
  above and you cannot responsibly summarize it (rare -- prefer content).

Rules:
- Never invent facts, numbers, names, or claims that are not present in
  the extracted source text for that slide.
- Tighten and professionalize wording (sentence case, concise, no
  filler) but preserve the original meaning -- this is a copy-edit, not
  a rewrite of what the slide says.
- `source_slide_index` must be the 1-based index of the ORIGINAL slide
  (given below) this entry was built from.
- Return exactly one outline entry per source slide provided to you, in
  the same order.
"""

OUTLINE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "source_slide_index": {"type": "integer"},
        "kind": {
            "type": "string",
            "enum": [
                "cover", "agenda", "section", "content", "quote",
                "statement", "stat", "timeline", "end", "blank",
            ],
        },
        "title": {"type": ["string", "null"]},
        "subtitle": {"type": ["string", "null"]},
        "bullets": {"type": "array", "items": {"type": "string"}},
        "columns": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
        "quote_text": {"type": ["string", "null"]},
        "quote_author": {"type": ["string", "null"]},
        "quote_label": {"type": ["string", "null"]},
        "stats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"number": {"type": "string"}, "label": {"type": "string"}},
                "required": ["number", "label"],
                "additionalProperties": False,
            },
        },
        "milestones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"label": {"type": "string"}, "text": {"type": "string"}},
                "required": ["label", "text"],
                "additionalProperties": False,
            },
        },
        "variant": {"type": ["string", "null"]},
    },
    "required": [
        "source_slide_index", "kind", "title", "subtitle", "bullets", "columns",
        "quote_text", "quote_author", "quote_label", "stats", "milestones", "variant",
    ],
    "additionalProperties": False,
}

OUTLINE_SCHEMA = {
    "type": "object",
    "properties": {"slides": {"type": "array", "items": OUTLINE_ITEM_SCHEMA}},
    "required": ["slides"],
    "additionalProperties": False,
}


class RedesignError(ComposeError):
    """Raised when the AI redesign step itself fails (missing API key,
    missing dependency, or a malformed/unusable model response)."""


@dataclass
class SkippedSlide:
    slide_index: int  # 1-based, original deck numbering
    reason: str


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int
    model: str

    @property
    def estimated_cost_usd(self) -> float:
        prices = PRICE_PER_MTOK_USD.get(self.model)
        if not prices:
            return 0.0
        return (self.input_tokens / 1_000_000) * prices["input"] + (self.output_tokens / 1_000_000) * prices["output"]


@dataclass
class RedesignResult:
    outline: Outline
    skipped: list  # list[SkippedSlide] -- ineligible slides, never sent to the model
    usage: Usage


def _slide_height_in(prs) -> Optional[float]:
    return prs.slide_height / 914400 if prs.slide_height else None


def _describe_slide(index: int, profile: SlideProfile) -> dict:
    return {
        "source_slide_index": index,
        "title": profile.title,
        "text_blocks": [[text for _level, text in block] for block in profile.text_blocks],
        "image_count": len(profile.images),
    }


def extract_eligible_slides(prs) -> tuple[list, list]:
    """Classify every slide with the exact same eligibility rules
    `retemplate.py` uses. Returns (eligible: list[(index, SlideProfile)],
    skipped: list[SkippedSlide])."""
    slide_height_in = _slide_height_in(prs)
    eligible = []
    skipped = []
    for i, slide in enumerate(prs.slides, start=1):
        profile = classify_slide(slide, slide_height_in)
        if profile.eligible:
            eligible.append((i, profile))
        else:
            skipped.append(SkippedSlide(slide_index=i, reason=profile.reason or "not eligible for redesign"))
    return eligible, skipped


def _build_messages(eligible: list, notes: Optional[str]) -> list:
    slides_json = json.dumps([_describe_slide(i, p) for i, p in eligible], indent=2)
    extra = f"\n\nAdditional guidance from the operator running this tool:\n{notes}\n" if notes else ""
    user_content = (
        f"{KIND_GUIDE}\n{extra}\n"
        "Here is the extracted content of every slide eligible for redesign, "
        f"in order:\n\n{slides_json}"
    )
    return [{"role": "user", "content": user_content}]


def call_claude_for_outline(
    eligible: list,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    notes: Optional[str] = None,
    api_key: Optional[str] = None,
    client=None,
) -> tuple[list, Usage]:
    """Send the extracted, eligible-only slide content to Claude and get
    back a list of outline-item dicts (compose.py's own schema) plus the
    call's token usage. `client` is an injection point for tests -- any
    object exposing `.messages.stream(...)` in the Anthropic SDK shape.
    """
    if client is None:
        try:
            import anthropic
        except ImportError as exc:
            raise RedesignError(
                "the 'anthropic' package is required for `redesign` -- run `pip install -e .` (or `pip install -r requirements.txt`)"
            ) from exc
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RedesignError("ANTHROPIC_API_KEY is not set -- redesign needs an Anthropic API key")
        client = anthropic.Anthropic(api_key=key)

    messages = _build_messages(eligible, notes)
    with client.messages.stream(
        model=model,
        max_tokens=32000,
        thinking={"type": "adaptive"},
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": OUTLINE_SCHEMA}},
        messages=messages,
    ) as stream:
        response = stream.get_final_message()

    if response.stop_reason == "refusal":
        raise RedesignError("Claude declined the redesign request (safety refusal) -- try again or adjust the source deck")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise RedesignError(f"no text content in the model response (stop_reason={response.stop_reason!r})")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RedesignError(f"model response was not valid JSON: {exc}") from exc

    raw_slides = parsed.get("slides")
    if not isinstance(raw_slides, list):
        raise RedesignError("model response had no 'slides' array")

    usage = Usage(input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens, model=model)
    return raw_slides, usage


def _strip_ai_only_fields(raw_slides: list) -> list:
    """source_slide_index is for our own traceability; compose.py's
    SlideSpec doesn't take it, and unknown keys are otherwise harmless
    (ignored via .get()), but stripping keeps the outline dict honestly
    scoped to what compose.py actually reads."""
    return [{k: v for k, v in s.items() if k != "source_slide_index"} for s in raw_slides]


def redesign_deck(
    deck_path,
    out_path,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    notes: Optional[str] = None,
    template_path=None,
    rules_config: Optional[dict] = None,
    api_key: Optional[str] = None,
    client=None,
) -> tuple[ComposeResult, RedesignResult]:
    """End to end: extract eligible content from `deck_path`, ask Claude to
    redesign it into a `compose.py` outline, then build that outline onto
    the org template exactly as `deckguard create` would -- same layout
    selection, same final brand-compliance pass. Ineligible slides
    (tables, charts, embedded media, overfull content) are never sent to
    the model and never appear in the output; they're reported back in
    `RedesignResult.skipped` for manual handling, same as `retemplate`.
    """
    prs = Presentation(str(deck_path))
    eligible, skipped = extract_eligible_slides(prs)
    if not eligible:
        raise RedesignError("no slide in this deck is eligible for automatic redesign (see skipped reasons)")

    raw_slides, usage = call_claude_for_outline(
        eligible, model=model, effort=effort, notes=notes, api_key=api_key, client=client
    )
    outline = outline_from_list(_strip_ai_only_fields(raw_slides))

    compose_result = build_deck(outline, out_path, template_path=template_path, rules_config=rules_config)
    redesign_result = RedesignResult(outline=outline, skipped=skipped, usage=usage)
    return compose_result, redesign_result
