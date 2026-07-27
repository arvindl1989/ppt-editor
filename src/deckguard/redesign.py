"""AI-assisted deck redesign: turn ANY starting point -- a completely
off-brand deck with real content, a mostly-empty deck, or no deck at
all, just a topic -- into a fresh outline of the kind `compose.py`
already knows how to build. The realization of the "Phase 2" judgment
layer this project's own README has flagged as not-yet-implemented
since Phase 1.

Deliberately narrow in scope, and deliberately NOT where any new brand
logic lives:

- Content extraction reuses `retemplate.py`'s own shape-walk
  (`_extract_slide_content`) verbatim, so a table, chart, embedded
  object, media, group shape, or overload of free-form decorative
  shapes is left alone and reported here exactly as it is for
  `retemplate` -- the model never sees a slide this project's own rules
  already consider unsafe to reinterpret, no matter what mode redesign
  is running in.
- What's DIFFERENT from `retemplate` on purpose: retemplate caps a
  slide at `MAX_TEXT_BLOCKS` (3) separate text boxes, because it
  carries content over VERBATIM -- that's the literal max placeholder
  count any layout offers, a real ceiling, not a style choice. redesign
  has no such cap on block *count* at all: it's already trusted to
  rewrite/condense wording, so how many boxes the original text was
  split across is irrelevant to whether it's safe to redesign. What it
  caps instead is total text *volume* (`REDESIGN_MAX_TEXT_CHARS`), and
  generously -- a sanity ceiling against a pathological/corrupted file,
  not a second-guess of an ordinary dense slide. (Two earlier versions
  of this file got this wrong: first reusing retemplate's block-count
  cap unmodified, then replacing it with a *higher* block-count cap
  that was still the wrong metric -- see `_classify_slide_for_redesign`.)
- The LLM call decides two things, and only two: per slide WITH source
  content, which `compose.py` slide *kind* best fits it (a light
  copy-edit, never inventing facts); and, for a blank slide or a bare
  topic brief with no slide behind it at all, what content to AUTHOR
  from the brief to make the deck whole. Those are different rules
  (never-invent vs. please-invent-from-the-brief) and the prompt keeps
  them explicitly separate so the model never blurs them.
- The model's output is validated against a JSON schema shaped exactly
  like `compose.py`'s own outline dict format (see `outline_from_list`),
  so a human-written YAML outline, a redesigned deck, and a
  from-scratch AI-authored one are indistinguishable from that point
  on -- they all run through the identical `build_deck` (same layout
  selection, same final `fix_deck` pass, same brand guarantees).
- Nothing about color, font, or layout-approval judgment is delegated to
  the model, in any of the three modes. That's exactly the split this
  project has used since Phase 1: deterministic first, AI second, and
  AI only for the one judgment call a shape-count heuristic can't make.
- A source slide's own images are carried into its redesigned replacement
  by `_attach_source_images`, keyed off `source_slide_index` -- this is
  deliberately NOT something the model decides. The outline schema the
  model fills in has no field for images at all: the model is never shown
  the actual pixels (only an `image_count`), so it has no basis to choose
  among them. Which images survive is a deterministic backfill after the
  model call, capped per slide at `REDESIGN_IMAGES_PER_SLIDE`.

Three ways to call `redesign_deck`, matched to the three starting points:

    redesign_deck("old_deck.pptx", out_path)                  # redesign
    redesign_deck("half_empty.pptx", out_path, brief="...")   # fill gaps
    redesign_deck(None, out_path, brief="...")                # from scratch

Requires the `anthropic` package (a base dependency -- see
requirements.txt / pyproject.toml) and an `ANTHROPIC_API_KEY` at
runtime. Everything else in `deckguard` works without either; this is
the one command in the whole tool that makes an outbound API call.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

from pptx import Presentation

from deckguard.compose import ComposeError, ComposeResult, Outline, build_deck, outline_from_list
from deckguard.retemplate import EMPTY_SLIDE_REASON, SlideProfile, _extract_slide_content

DEFAULT_MODEL = "claude-opus-5"

# Deliberately NOT a cap on text-block *count* (a first cut at this used
# one, at 10 -- still wrong, and for the same reason a cap of 3 was
# wrong: block count doesn't measure how much there is to condense. A
# slide split across 20 tiny caption boxes has less actual content than
# one with 3 paragraph-sized text boxes, and redesign condenses either
# way regardless of how the original was carved up. What actually bounds
# the work (and the cost) is total text VOLUME, so that's what's capped
# here -- generously, since even a genuinely dense slide is a few
# thousand characters at most; this exists to catch a pathological or
# corrupted file, not to second-guess an ordinary hand-built slide.
REDESIGN_MAX_TEXT_CHARS = 20_000
REDESIGN_MAX_IMAGES = 12

# How many of a source slide's own images get carried into its redesigned
# replacement. Not the same cap as REDESIGN_MAX_IMAGES above (that's an
# eligibility ceiling -- how many images before a slide is refused
# entirely); this is a per-slide output cap, set to the most any
# picture-carrying candidate layout in compose.py's CONTENT_LAYOUT_CANDIDATES
# actually has PICTURE placeholders for ("Two pictures and text *" tops out
# at 2). Keeping every image the model never even sees the pixels of and
# has no way to curate isn't the goal here -- just not silently discarding
# all of them, which is what happened before this existed.
REDESIGN_IMAGES_PER_SLIDE = 2

# As of this writing (see the claude-api skill's cached pricing table) --
# used only to give the caller a rough, clearly-labeled cost estimate
# alongside the real usage numbers the API returns. Verify against
# platform.claude.com/docs/en/pricing before trusting this for billing.
PRICE_PER_MTOK_USD = {
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}


def _classify_slide_for_redesign(slide, slide_height_in: Optional[float] = None) -> SlideProfile:
    """Same shape-safety rules as retemplate.classify_slide (a table,
    chart, embedded object, media, group, or decorative-shape overload
    is still a hard skip -- never touched, brief or no brief). No cap on
    text-block *count* at all -- redesign condenses rather than carrying
    content over verbatim, so how many boxes the original text happened
    to be split across is irrelevant; only total text *volume* is capped
    (generously), and image count gets a higher ceiling than
    retemplate's, since redesign is allowed to select a subset."""
    title, text_blocks, images, reason = _extract_slide_content(slide, slide_height_in)
    if reason:
        return SlideProfile(None, [], [], False, reason)
    if title is None and not text_blocks and not images:
        return SlideProfile(None, [], [], False, EMPTY_SLIDE_REASON)
    total_chars = sum(len(text) for block in text_blocks for _level, text in block)
    if total_chars > REDESIGN_MAX_TEXT_CHARS:
        return SlideProfile(None, [], [], False, "far more text than can be reasonably condensed onto one slide")
    if len(images) > REDESIGN_MAX_IMAGES:
        return SlideProfile(None, [], [], False, "far more images than any layout could hold")
    return SlideProfile(title=title, text_blocks=text_blocks, images=images, eligible=True)

KIND_GUIDE = """\
Available slide kinds and when to use each:

- cover: the deck's own title slide -- exactly one, first.
- agenda: a short list of upcoming topics/sections (an outline of the
  deck itself). Only worth including if the deck has enough distinct
  sections to preview.
- section: a chapter/divider slide -- just a short heading, marking a
  transition between topics. No body content.
- content: the default for an ordinary slide with a title and 1-3 blocks
  of bullet points. Use `columns` (one list of bullets per column) when
  the content visually reads as 2-3 side-by-side blocks; otherwise use a
  single `bullets` list.
- quote: a slide whose main content is a single attributed quotation.
  Needs quote_text and, if known, quote_author.
- statement: one short, unmissable, single-sentence message with no
  supporting bullets -- a big declarative claim, not a list.
- stat: a row of 2-3 numeric callouts (e.g. "40M / people moved daily").
  Needs `stats`, each with a short `number` and a `label`.
- timeline: a sequence of 2-3 dated/labeled milestones. Needs
  `milestones`, each with a `label` (date/phase) and `text` (what
  happens).
- end: the deck's closing/thank-you slide -- exactly one, last.
- blank: use only if a slide's content genuinely doesn't fit any of the
  above and you cannot responsibly summarize it (rare -- prefer content).

General rules:
- `source_slide_index` must be the 1-based index of the ORIGINAL slide
  (given below) an entry was built from, or `null` if you authored this
  slide from scratch (see below) with no original slide behind it.
- A coherent deck reads as a narrative, not a pile of unrelated slides:
  cover, optional agenda, then content grouped under section dividers
  where it naturally clusters, closing with end. Don't force an agenda
  or section dividers onto a short/simple deck that doesn't need them.
"""

REDESIGN_RULES = """\
Rules for slides that have ORIGINAL source content (see the extracted
text below) -- these are a REDESIGN, not a rewrite:
- Never invent facts, numbers, names, or claims that are not present in
  that slide's own extracted source text.
- Tighten and professionalize wording (sentence case, concise, no
  filler) but preserve the original meaning.
- Every layout has a real capacity limit (at most 3 body columns, a
  handful of bullets each). A source slide may have far more raw text
  than that -- it was likely built by hand with many separate text
  boxes. When that happens, DO NOT try to preserve every line: condense
  to the most important, representative points, the way an editor
  would summarize a dense slide into a clean one. Losing minor detail
  in service of a slide someone can actually read is correct behavior
  here, not a failure -- the alternative (an unreadable wall of bullets,
  or being skipped and left out of the deck entirely) is worse. Use
  `columns` to organize genuinely multi-part content into up to 3
  side-by-side groups if that reads better than one long list.
- Return exactly one outline entry per source slide provided, in order,
  each with its correct `source_slide_index`.
"""

AUTHORING_RULES = """\
Rules for content you are AUTHORING FROM SCRATCH (blank slides in the
source deck, and/or the brief below) -- this is the opposite of the
redesign rules above: there is no original text to preserve, so write
real, substantive, specific content grounded in the brief. Don't pad
with vague filler ("drives value", "best-in-class") -- if the brief
doesn't give you enough to make a claim specific, write a more general
but still concrete statement rather than invent a fake number or name.
Give these entries `source_slide_index: null`.
"""


def _target_slides_guidance(target_slides: Optional[int]) -> str:
    if target_slides is not None:
        return f"Aim for approximately {target_slides} total slides in the finished deck."
    return (
        "No specific slide count was requested -- use your judgment for a deck length "
        "that suits the brief's scope (a narrow topic might be 5-6 slides; a broad one 10-12)."
    )


OUTLINE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "source_slide_index": {"type": ["integer", "null"]},
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
    missing dependency, nothing to work from, or a malformed/unusable
    model response)."""


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
    skipped: list  # list[SkippedSlide] -- unsafe-to-touch slides, never sent to the model
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
    """Classify every slide with `_classify_slide_for_redesign` --
    retemplate's own shape-safety rules, but with redesign's own
    (higher) cap on text/image count, since redesign condenses rather
    than carrying content over verbatim. Returns (eligible:
    list[(index, SlideProfile)], skipped: list[SkippedSlide]) --
    `skipped` here includes blank slides; callers that need blanks
    split out separately should use `partition_skipped`."""
    slide_height_in = _slide_height_in(prs)
    eligible = []
    skipped = []
    for i, slide in enumerate(prs.slides, start=1):
        profile = _classify_slide_for_redesign(slide, slide_height_in)
        if profile.eligible:
            eligible.append((i, profile))
        else:
            skipped.append(SkippedSlide(slide_index=i, reason=profile.reason or "not eligible for redesign"))
    return eligible, skipped


def partition_skipped(skipped: list) -> tuple[list, list]:
    """Split `extract_eligible_slides`'s skip list into (blank slide
    indices, everything else). A blank slide has nothing to protect --
    it's safe to author content for it from a brief. Every other skip
    reason (table/chart/media/overfull) means real content this project
    has already decided is unsafe to reinterpret, brief or no brief."""
    blank_indices = [s.slide_index for s in skipped if s.reason == EMPTY_SLIDE_REASON]
    real_skipped = [s for s in skipped if s.reason != EMPTY_SLIDE_REASON]
    return blank_indices, real_skipped


def _build_messages(
    eligible: list, blank_count: int, brief: Optional[str], notes: Optional[str], target_slides: Optional[int]
) -> list:
    sections = [KIND_GUIDE]

    if eligible:
        sections.append(REDESIGN_RULES)
    if blank_count or brief or not eligible:
        sections.append(AUTHORING_RULES)
        sections.append(_target_slides_guidance(target_slides))

    if notes:
        sections.append(f"Additional guidance from the operator running this tool:\n{notes}")
    if brief:
        sections.append(f"Brief describing the deck to build (use this to author any new content needed):\n{brief}")

    if eligible:
        slides_json = json.dumps([_describe_slide(i, p) for i, p in eligible], indent=2)
        sections.append(
            f"Here is the extracted content of every slide with original source content, in order "
            f"(redesign each of these per the rules above):\n\n{slides_json}"
        )
    if blank_count:
        sections.append(
            f"The source deck also has {blank_count} blank slide(s) with no content at all -- "
            "author new slides for these (or fold them into a better overall structure) using the brief."
        )
    if not eligible and not blank_count:
        sections.append("There is no source deck -- author the entire outline from the brief above.")

    return [{"role": "user", "content": "\n\n".join(sections)}]


def call_claude_for_outline(
    eligible: list,
    blank_count: int = 0,
    brief: Optional[str] = None,
    target_slides: Optional[int] = None,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    notes: Optional[str] = None,
    api_key: Optional[str] = None,
    client=None,
) -> tuple[list, Usage]:
    """Send whatever's available -- extracted content, a count of blank
    slides to fill, and/or a topic brief -- to Claude and get back a
    list of outline-item dicts (compose.py's own schema) plus the call's
    token usage. `client` is an injection point for tests -- any object
    exposing `.messages.stream(...)` in the Anthropic SDK shape.
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

    messages = _build_messages(eligible, blank_count, brief, notes, target_slides)
    with client.messages.stream(
        model=model,
        max_tokens=32000,
        thinking={"type": "adaptive"},
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": OUTLINE_SCHEMA}},
        messages=messages,
    ) as stream:
        response = stream.get_final_message()

    if response.stop_reason == "refusal":
        raise RedesignError("Claude declined the redesign request (safety refusal) -- try again or adjust the brief/source deck")

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
    if not raw_slides:
        raise RedesignError("model returned zero slides")

    usage = Usage(input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens, model=model)
    return raw_slides, usage


def _strip_ai_only_fields(raw_slides: list) -> list:
    """source_slide_index is for our own traceability; compose.py's
    SlideSpec doesn't take it, and unknown keys are otherwise harmless
    (ignored via .get()), but stripping keeps the outline dict honestly
    scoped to what compose.py actually reads."""
    return [{k: v for k, v in s.items() if k != "source_slide_index"} for s in raw_slides]


def _attach_source_images(raw_slides: list, eligible: list) -> list:
    """Carry each source slide's own images into the outline entry built
    from it. Which images belong to which output slide is a fact already
    known from source_slide_index (compose.py's outline schema has no
    field for the model to report images itself -- it's never shown the
    pixels, so it isn't in a position to choose among them anyway); this
    is a deterministic backfill, not a judgment call, done after the
    model call rather than asking the model to round-trip image data it
    never needed to see. Capped per slide at REDESIGN_IMAGES_PER_SLIDE so
    a slide that had many images still lands on a layout match_layout can
    actually find (see that constant's own comment)."""
    images_by_source_index = {i: profile.images[:REDESIGN_IMAGES_PER_SLIDE] for i, profile in eligible}
    for slide in raw_slides:
        images = images_by_source_index.get(slide.get("source_slide_index"))
        if images:
            slide["images"] = images
    return raw_slides


def redesign_deck(
    deck_path=None,
    out_path=None,
    brief: Optional[str] = None,
    target_slides: Optional[int] = None,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    notes: Optional[str] = None,
    template_path=None,
    rules_config: Optional[dict] = None,
    api_key: Optional[str] = None,
    client=None,
) -> tuple[ComposeResult, RedesignResult]:
    """One entry point for all three starting points:

    - `deck_path` set, `brief` unset: redesign an existing deck's
      content onto the org template (blank slides in it are skipped,
      same as any other unsafe-to-touch content, since there's no brief
      to author them from).
    - `deck_path` set, `brief` set: redesign the deck's real content
      AND author its blank slides from the brief, as one coherent deck.
    - `deck_path` unset, `brief` set: no source deck at all -- author
      the entire outline from the brief, exactly like asking a designer
      to build a deck on a topic from nothing.

    Whichever mode, everything downstream is identical: the resulting
    outline runs through the same `build_deck`/`fix_deck` pipeline
    `deckguard create` uses, so layout selection and brand compliance
    are guaranteed the same way regardless of which mode produced it.
    Slides with real content this project's rules already consider
    unsafe to reinterpret (a table, chart, embedded object, or more
    content than any layout can hold) are never sent to the model in
    any mode; they're reported back in `RedesignResult.skipped`.
    """
    if out_path is None:
        raise RedesignError("out_path is required")

    eligible: list = []
    blank_indices: list = []
    skipped: list = []
    if deck_path is not None:
        prs = Presentation(str(deck_path))
        eligible, all_skipped = extract_eligible_slides(prs)
        blank_indices, skipped = partition_skipped(all_skipped)

    if not eligible and not blank_indices and not brief:
        raise RedesignError(
            "nothing to work with: the deck has no eligible content to redesign and no --brief was given "
            "to generate from (pass --brief to fill blank slides, or to build a new deck with no source at all)"
        )

    effective_target = target_slides
    if effective_target is None and (eligible or blank_indices):
        effective_target = len(eligible) + len(blank_indices)

    raw_slides, usage = call_claude_for_outline(
        eligible,
        blank_count=len(blank_indices),
        brief=brief,
        target_slides=effective_target,
        model=model,
        effort=effort,
        notes=notes,
        api_key=api_key,
        client=client,
    )
    raw_slides = _attach_source_images(raw_slides, eligible)
    outline = outline_from_list(_strip_ai_only_fields(raw_slides))

    compose_result = build_deck(outline, out_path, template_path=template_path, rules_config=rules_config)
    redesign_result = RedesignResult(outline=outline, skipped=skipped, usage=usage)
    return compose_result, redesign_result
