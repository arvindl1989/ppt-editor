"""The unified Transform pipeline: plan -> human review -> execute -> audit.

This is the consolidation seam over deckguard's three primitives --
analyze (`propose_rebrand`), rebuild (org layout via `apply_rebrand` /
archetype via `apply_archetype_overrides_to_deck`), and patch
(`fix_deck`, already inside `apply_rebrand`) -- exposed as ONE flow with
a human decision point in the middle, instead of four separate blind
upload->download tabs. Nothing here re-implements those primitives: the
plan IS `propose_rebrand`'s output (so plan and execution can never
disagree), the AI archetype suggestions ARE the same fail-closed
`select_archetype_overrides_for_rebrand` pass brand-mode review uses,
and execution IS `apply_rebrand(accepted_indexes=...)` -- the
guided-review hook that existed in the engine all along but never had a
caller.

Two starting points, one result shape:

- `plan_transform(deck_path, ...)` -> per-slide plan for an EXISTING
  deck (with optional reference deck driving layout carryover exactly
  as Learn/brand-mode always did). Each slide gets a default action a
  human can override: keep / rebuild on a named org layout (or
  reference layout) / rebuild as a suggested archetype.
- `plan_transform_from_brief(brief, ...)` -> per-slide plan for a NEW
  deck (the old Create/Redesign brief-only path): the archetype spec
  the model planned, shown slide by slide for approval before anything
  renders.

`execute_transform` / `execute_transform_from_brief` then run exactly
the approved subset, and `audit_transform_result` reports the result's
brand-rule audit -- with archetype-rendered slides excluded from the
violation list, because they are compliant by construction and
`rules_engine`'s generic text rules would false-positive on their
deliberate styling (the known `#727272` caption case) -- plus, when a
reference deck was given, a similarity report against it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from pptx import Presentation

from deckguard.config import default_config_path, load_config
from deckguard.inventory import build_inventory, iter_shapes_recursive
from deckguard.redesign import DEFAULT_MODEL
from deckguard.retemplate import (
    SlideProfile,
    _extract_slide_content,
    apply_rebrand,
    propose_rebrand,
)
from deckguard.rules_engine import audit_deck, sort_violations, summarize


@dataclass
class SlidePlan:
    index: int  # 1-based
    default_action: str  # "keep" | "rebuild" | "reference_layout" | "archetype" | "new"
    layout_name: Optional[str] = None  # org/reference layout the rebuild would use
    archetype: Optional[dict] = None  # {"archetype": name, ...content...} when the AI suggested one
    reason: Optional[str] = None  # why a slide is keep-only (ineligible)
    title_preview: Optional[str] = None
    body_preview: Optional[str] = None
    image_count: int = 0
    # Verbatim content, for rendering a faithful proposed-slide preview
    # (org-layout previews place these into the layout's real
    # placeholder boxes). None for slides that were never extracted
    # (ineligible/keep-only ones).
    title: Optional[str] = None
    text_blocks: list = field(default_factory=list)  # list[list[str]]


@dataclass
class TransformPlan:
    slides: list  # list[SlidePlan]
    ai_suggestions_ran: bool = False
    deck_title: Optional[str] = None  # brief-only plans: the planned cover title


def plan_transform(
    deck_path,
    reference_path: Optional[str] = None,
    template_path=None,
    rules_config: Optional[dict] = None,
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
    client=None,
    suggest_archetypes: bool = True,
) -> TransformPlan:
    """Per-slide plan for an existing deck. Deterministic core
    (`propose_rebrand`), plus -- when an API key/client is available and
    `suggest_archetypes` is on -- one fail-closed model call offering an
    archetype for any eligible ordinary-content slide; a failure or
    missing key just means no suggestions, never a failed plan."""
    del rules_config  # planning needs no rules; execution loads them itself
    plan = propose_rebrand(deck_path, template_path=template_path, reference_path=reference_path)
    reference_indices = set(plan.reference_layout_by_index)

    # Verbatim content for every eligible slide -- feeds both the
    # proposed-slide previews and (below) the AI suggestion call.
    prs = Presentation(str(deck_path))
    slide_height_in = prs.slide_height / 914400 if prs.slide_height else None
    content_by_index: dict = {}
    for p in plan.proposals:
        if not p.eligible or p.slide_index in reference_indices:
            continue
        title, text_blocks, images, reason = _extract_slide_content(
            prs.slides[p.slide_index - 1], slide_height_in
        )
        if not reason:
            content_by_index[p.slide_index] = (title, text_blocks, images)

    suggestions: dict = {}
    ai_ran = False
    if suggest_archetypes:
        from deckguard.skill_bridge import select_archetype_overrides_for_rebrand

        cover_end = {plan.cover_index, plan.end_index}
        profile_by_index = {
            idx: SlideProfile(title=t, text_blocks=blocks, images=images, eligible=True)
            for idx, (t, blocks, images) in content_by_index.items()
            if idx not in cover_end
        }
        if profile_by_index:
            suggestions = select_archetype_overrides_for_rebrand(
                profile_by_index, model=model, api_key=api_key, client=client,
            )
            ai_ran = True

    slides = []
    for p in plan.proposals:
        if p.slide_index in suggestions:
            default_action = "archetype"
        elif p.slide_index in reference_indices:
            default_action = "reference_layout"
        elif p.eligible:
            default_action = "rebuild"
        else:
            default_action = "keep"
        slides.append(
            SlidePlan(
                index=p.slide_index,
                default_action=default_action,
                layout_name=p.layout_name,
                archetype=suggestions.get(p.slide_index),
                reason=p.reason,
                title_preview=p.title_preview,
                body_preview=p.body_preview,
                image_count=p.image_count,
                title=content_by_index.get(p.slide_index, (None, [], []))[0],
                text_blocks=[
                    [text for _level, text in block]
                    for block in content_by_index.get(p.slide_index, (None, [], []))[1]
                ],
            )
        )
    return TransformPlan(slides=slides, ai_suggestions_ran=ai_ran)


def plan_transform_from_brief(
    brief: str,
    target_slides: Optional[int] = None,
    model: str = DEFAULT_MODEL,
    notes: Optional[str] = None,
    api_key: Optional[str] = None,
    client=None,
) -> TransformPlan:
    """Per-slide plan for a NEW deck from a brief: the archetype spec
    the model planned (same call the brief-only redesign path uses),
    reshaped into reviewable SlidePlan entries -- one per BODY slide;
    the retained master cover/outro aren't choices, so they don't
    appear. Raises RedesignError on a failed planning call, same as the
    brief-only path always has (unlike existing-deck planning there is
    no deterministic fallback to degrade to)."""
    from deckguard.skill_bridge import _validate_kone_spec, _load_archetypes, call_claude_for_kone_spec

    spec, _usage = call_claude_for_kone_spec(
        brief, target_slides=target_slides, model=model, notes=notes, api_key=api_key, client=client,
    )
    _validate_kone_spec(spec, set(_load_archetypes().ARCHETYPES.keys()))

    slides = []
    for i, s in enumerate(spec["slides"], start=1):
        content = {k: v for k, v in s.items() if k != "archetype"}
        slides.append(
            SlidePlan(
                index=i,
                default_action="new",
                archetype={"archetype": s["archetype"], **content},
                title_preview=str(content.get("title") or content.get("statement") or content.get("quote") or ""),
            )
        )
    return TransformPlan(slides=slides, ai_suggestions_ran=True, deck_title=spec.get("title"))


@dataclass
class TransformOutcome:
    out_path: str
    rebuilt: list = field(default_factory=list)  # org-layout rebuilds actually executed
    reference_carryover: list = field(default_factory=list)
    archetype_swapped: list = field(default_factory=list)
    kept: list = field(default_factory=list)
    layouts_used: dict = field(default_factory=dict)  # {index: layout-or-archetype name}


def execute_transform(
    deck_path,
    out_path,
    plan: TransformPlan,
    actions: Optional[dict] = None,
    reference_path: Optional[str] = None,
    template_path=None,
    rules_config: Optional[dict] = None,
) -> TransformOutcome:
    """Run exactly the approved subset of `plan`. `actions` maps
    1-based slide index -> "keep" | "rebuild" | "archetype"; a slide
    absent from `actions` follows its plan default. "rebuild" covers
    both ordinary org-layout rebuilds and reference-layout carryovers
    (`apply_rebrand` distinguishes them itself); "archetype" is only
    honored where the plan actually carries a suggestion -- a stray
    "archetype" choice with no suggestion degrades to "rebuild" rather
    than failing or inventing content."""
    actions = actions or {}
    plan_by_index = {s.index: s for s in plan.slides}

    chosen: dict = {}
    for s in plan.slides:
        choice = actions.get(s.index, s.default_action)
        if choice == "archetype" and s.archetype is None:
            choice = "rebuild"
        if choice in ("rebuild", "reference_layout"):
            choice = "rebuild" if s.default_action != "keep" else "keep"  # can't rebuild an ineligible slide
        elif choice not in ("keep", "archetype"):
            choice = "keep"
        chosen[s.index] = choice

    rebuild_indices = {i for i, c in chosen.items() if c == "rebuild"}
    archetype_indices = {i for i, c in chosen.items() if c == "archetype"}

    rebrand_result = apply_rebrand(
        str(deck_path), str(out_path), template_path=template_path, rules_config=rules_config,
        reference_path=reference_path, accepted_indexes=rebuild_indices,
    )

    # "keep" means the slide's STRUCTURE is untouched -- deck-wide brand
    # patches (colors/fonts/effects) still apply everywhere, Transform's
    # baseline promise. apply_rebrand runs fix_deck itself whenever it
    # rebuilds anything, but its nothing-to-rebuild early path returns a
    # plain copy with no fix pass at all -- cover that case here so an
    # all-keep transform is still a brand fix, not a no-op.
    if not rebuild_indices and not rebrand_result.reference_layout_indices:
        from deckguard.fixer import fix_deck

        config = rules_config if rules_config is not None else load_config(default_config_path())
        prs_out = Presentation(str(out_path))
        fix_deck(prs_out, config, source_path=str(out_path), output_path=str(out_path), dry_run=False)

    layouts_used = {
        p.slide_index: p.layout_name
        for p in rebrand_result.proposals
        if p.slide_index in rebuild_indices and p.layout_name
    }

    if archetype_indices:
        from deckguard.skill_bridge import apply_archetype_overrides_to_deck

        prs = Presentation(str(deck_path))
        slide_height_in = prs.slide_height / 914400 if prs.slide_height else None
        images_by_index: dict = {}
        for idx in archetype_indices:
            _title, _blocks, images, reason = _extract_slide_content(prs.slides[idx - 1], slide_height_in)
            if not reason:
                images_by_index[idx] = images
        overrides = {i: plan_by_index[i].archetype for i in archetype_indices}
        swapped = apply_archetype_overrides_to_deck(str(out_path), overrides, images_by_index=images_by_index)
        layouts_used.update(swapped)

    return TransformOutcome(
        out_path=str(out_path),
        rebuilt=sorted(rebuild_indices - set(rebrand_result.reference_layout_indices)),
        reference_carryover=sorted(rebrand_result.reference_layout_indices),
        archetype_swapped=sorted(archetype_indices),
        kept=sorted(i for i, c in chosen.items() if c == "keep"),
        layouts_used=layouts_used,
    )


def execute_transform_from_brief(out_path, plan: TransformPlan, approved_indices: Optional[set] = None) -> TransformOutcome:
    """Render the approved subset of a brief-only plan through the
    skill's own whole-deck builder (retained master cover + outro, same
    as the brief-only path always produced)."""
    from deckguard.skill_bridge import _load_creator

    creator = _load_creator()
    approved = approved_indices if approved_indices is not None else {s.index for s in plan.slides}
    spec_slides = [dict(s.archetype) for s in plan.slides if s.index in approved and s.archetype]
    spec = {"title": plan.deck_title or "Untitled deck", "slides": spec_slides}
    creator.build_deck(spec, str(out_path))
    return TransformOutcome(
        out_path=str(out_path),
        archetype_swapped=sorted(s.index for s in plan.slides if s.index in approved),
        kept=sorted(s.index for s in plan.slides if s.index not in approved),
        layouts_used={s.index: s.archetype["archetype"] for s in plan.slides if s.index in approved and s.archetype},
    )


def audit_transform_result(out_path, archetype_indices: Optional[set] = None, rules_config: Optional[dict] = None) -> dict:
    """Brand-rule audit of a transform result. Findings on
    archetype-rendered slides are EXCLUDED from the reported list (and
    counted separately): those slides are compliant by construction --
    the archetype engine writes only its own approved treatment -- and
    `rules_engine`'s generic text rules provably false-positive on their
    deliberate styling (e.g. flagging kone_engine's muted caption grey
    as a text_color violation). Suppressing a false alarm and SAYING SO
    beats reporting a defect that isn't one."""
    archetype_indices = archetype_indices or set()
    config = rules_config if rules_config is not None else load_config(default_config_path())
    prs = Presentation(str(out_path))
    violations = sort_violations(audit_deck(build_inventory(prs), config))
    reported = [v for v in violations if v.slide_index not in archetype_indices]
    suppressed = len(violations) - len(reported)
    return {
        "summary": summarize(reported),
        "violations": reported,
        "suppressed_archetype_findings": suppressed,
    }


def reference_similarity(out_path, reference_path) -> dict:
    """How close the transformed deck landed to the reference deck --
    deterministic, structural signals only (no rendering, no AI):
    per-index layout-name matches, plus colors and fonts present in the
    result that the reference itself never uses (each one a spot the
    result still visibly diverges)."""

    def _population(prs):
        inv = build_inventory(prs)
        colors: set = set()
        fonts: set = set()
        layouts: list = []
        for slide in inv.slides:
            layouts.append(slide.layout_name)
            for shape in iter_shapes_recursive(slide.shapes):
                if shape.fill:
                    for c in shape.fill.colors:
                        if c.hex:
                            colors.add(c.hex.upper())
                for para in shape.paragraphs:
                    for run in para.runs:
                        if run.color and run.color.hex:
                            colors.add(run.color.hex.upper())
                        if run.font_effective:
                            fonts.add(run.font_effective)
        return layouts, colors, fonts

    out_layouts, out_colors, out_fonts = _population(Presentation(str(out_path)))
    ref_layouts, ref_colors, ref_fonts = _population(Presentation(str(reference_path)))

    n = min(len(out_layouts), len(ref_layouts))
    layout_matches = sum(1 for i in range(n) if out_layouts[i] == ref_layouts[i])
    return {
        "slides_compared": n,
        "layout_matches": layout_matches,
        "colors_not_in_reference": sorted(out_colors - ref_colors),
        "fonts_not_in_reference": sorted(out_fonts - ref_fonts),
    }
