"""Turn whatever the user gave us into a deck.

One function decides what a deck is. The interface collects inputs and
shows results; this is where a brief, a set of picks, and a mined deck
become an ordered list of slides with content in them.

The rules, in order:

  1. Slides the user picked are honoured exactly, in the order picked.
  2. A brief with no picks is planned -- the model chooses archetypes
     from the audience's set and writes the content.
  3. A brief WITH picks fills those picks rather than choosing its own.
  4. With neither, a mined deck's own templates are the deck.

Nothing here asks a question. A missing slot stays empty and shows as
empty; a slide that cannot be built is dropped and reported. The caller
edits afterwards.
"""

from __future__ import annotations

import re
from typing import Optional

from deckguard import brandmode as bm
from deckguard.registry import _derived_content_keys, _load_archetypes


def plan(
    *,
    brief: str = "",
    audience: str = "internal",
    picks: Optional[list] = None,
    mined: Optional[dict] = None,
    title: str = "",
) -> dict:
    """The deck, as a spec, before anything is drawn."""
    picks = list(picks or [])
    mined = mined or {}
    built = set(_load_archetypes().ARCHETYPES) | set(mined.get("archetypes") or {})

    chosen = _chosen_archetypes(picks, audience, mined, built)
    samples = mined.get("samples") or {}
    if brief.strip():
        slides = _from_brief(brief, audience, chosen)
    elif chosen:
        slides = [_seed(name, samples) for name in chosen]
    else:
        # A deck and nothing else: rebuild it from its own designs,
        # carrying the words that were on those slides. An archetype
        # with no content renders as an empty page, which is not a
        # template anyone can judge.
        slides = [_seed(name, samples) for name in _mined_names(mined)][:25]

    return {
        "title": title or _title_from(brief) or "Untitled deck",
        "audience": audience,
        "date": bm_date(),
        "slides": slides,
    }


def _seed(name: str, samples: dict) -> dict:
    """A slide, pre-filled from its mined sample where there is one."""
    sample = samples.get(name)
    return {"archetype": name, **(dict(sample) if isinstance(sample, dict) else {})}


def _chosen_archetypes(picks, audience, mined, built) -> list:
    """Picks are `set:n` for a KONE slide or `mined:name` for one of
    yours. Anything not actually built is dropped rather than silently
    producing a blank slide."""
    names = []
    for pick in picks:
        source, _, rest = pick.partition(":")
        if source == "mined":
            if rest in (mined.get("archetypes") or {}):
                names.append(rest)
            continue
        try:
            number = int(rest)
        except ValueError:
            continue
        for slide in bm.slides_in(source if source in bm.set_names() else audience):
            if slide["n"] == number and slide["archetype"] in built:
                names.append(slide["archetype"])
                break
    return names


def _mined_names(mined: dict) -> list:
    order = mined.get("sources") or {}
    return sorted((mined.get("archetypes") or {}),
                  key=lambda n: min(order.get(n) or [999]))


def _from_brief(brief: str, audience: str, chosen: list) -> list:
    """Plan the content. With picks already made, the planner fills
    those; without, it chooses from the audience's set too."""
    from deckguard.planner import call_claude_for_kone_spec

    notes = None
    if chosen:
        notes = (
            "Use EXACTLY these archetypes, in this order, one slide each:\n"
            + "\n".join(f"  {i:02d}. {name}" for i, name in enumerate(chosen, 1))
            + "\nDo not add, drop or reorder them."
        )
    else:
        entries = bm.slides_in(audience)
        notes = (
            f"This is a KONE {audience} deck. Choose archetypes only from this "
            "set, and keep them in the set's order:\n"
            + "\n".join(f"  {s['archetype']}" for s in entries)
        )
    spec, _usage = call_claude_for_kone_spec(brief, notes=notes)
    slides = spec.get("slides") or []
    return slides or [{"archetype": name} for name in chosen]


def _title_from(brief: str) -> str:
    line = (brief or "").strip().splitlines()[:1]
    if not line:
        return ""
    text = re.sub(r"^(subject|re|fwd)\s*:\s*", "", line[0], flags=re.I).strip()
    return text[:70]


def bm_date() -> str:
    from datetime import date

    return date.today().strftime("%d %B %Y").lstrip("0")


# --------------------------------------------------------------------------
# building
# --------------------------------------------------------------------------


def build(plan_dict: dict, out_path: str, mined: Optional[dict] = None) -> dict:
    """Draw the deck and run preflight over it. Returns the findings."""
    from deckguard import layouts
    from deckguard.registry import fill_empty_photo_slots, register_mined

    # Mined designs have to be in the registry before the renderer looks
    # one up, or it finds nothing and draws an empty slide.
    if mined:
        register_mined(mined)

    spec = {
        "title": plan_dict.get("title") or "Untitled deck",
        "date": plan_dict.get("date"),
        "slides": [dict(s) for s in plan_dict.get("slides") or []],
    }
    fill_empty_photo_slots(spec)
    layouts.build_deck(spec, out_path)
    return preflight(out_path)


def _is_dash_marker(text: str) -> bool:
    """Is this run a dash pretending to be a bullet?

    Checking `text.strip().startswith("— ")` missed the real case: the
    marker is its own run holding exactly `"—  "`, and stripping it
    leaves a bare dash with no trailing space. So the check passed on
    every deck while the violation it was written for went out the
    door.
    """
    stripped = (text or "").strip()
    if stripped in ("-", "—", "–", "*", "•-"):
        return True
    return stripped.startswith(("- ", "— ", "– "))


def _below_the_floor(shape, px) -> bool:
    """Does this text region hang below the floor?

    The floor is about content, not about the slide. A full-bleed
    photograph reaches y=720 by design, and so does a cover's own
    banner -- flagging those made preflight cry wolf on every deck,
    which is the fastest way to teach someone to ignore it.
    """
    try:
        top, height, width = shape.top, shape.height, shape.width
    except Exception:  # noqa: BLE001
        return False
    if None in (top, height, width):
        return False
    if width <= 0 or height <= 0:
        # The master's latent DATE / FOOTER / SLIDE_NUMBER placeholders
        # come back as 0x0 boxes parked at y=720. They draw nothing, and
        # flagging them made every deck report two findings it could not
        # act on.
        return False
    if width / px > 1000 and height / px > 300:
        return False                      # full-bleed art, not a text region
    return (top + height) / px > bm.FOOTER_Y + 22


def preflight(deck_path: str) -> dict:
    """The checks from BRAND_MODE section 10 that can be read back off a
    built file. A deck that fails one is still returned -- the point is
    to say so, not to withhold it."""
    from pptx import Presentation

    findings: list = []
    prs = Presentation(deck_path)
    px = prs.slide_width / 1280
    allowed = {bm.BLACK, bm.WHITE, bm.BLUE}

    for number, slide in enumerate(prs.slides, start=1):
        logos = 0
        for shape in slide.shapes:
            name = (getattr(shape, "name", "") or "").lower()
            if "logo" in name:
                logos += 1
            if not getattr(shape, "has_text_frame", False):
                continue
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    text = run.text or ""
                    if not text.strip():
                        continue
                    colour = None
                    try:
                        if run.font.color and run.font.color.type is not None:
                            colour = str(run.font.color.rgb)
                    except Exception:  # noqa: BLE001
                        colour = None
                    if colour and colour.upper() not in allowed:
                        findings.append((number, f"type in #{colour}, which is not "
                                                 "black, white or KONE Blue"))
                    if _is_dash_marker(text):
                        findings.append((number, "a dash standing in for a bullet"))
            if _below_the_floor(shape, px):
                bottom = (shape.top + shape.height) / px
                findings.append((number, f"a region reaching y={bottom:.0f}, past the floor"))
        if logos > 1:
            findings.append((number, f"{logos} logos; there must be exactly one"))

    seen, unique = set(), []
    for item in findings:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return {"slides": len(prs.slides), "findings": unique}


# --------------------------------------------------------------------------
# edits from the result page
# --------------------------------------------------------------------------


def apply_edits(plan_dict: dict, form) -> dict:
    """Text, order, drop and duplicate, read back off the result page.

    Order is a number that only has to sort, which is what makes
    inserting a slide between two others easy.
    """
    slides = []
    for index, slide in enumerate(plan_dict.get("slides") or []):
        sid = str(index)
        if form.get(f"drop:{sid}"):
            continue
        updated = dict(slide)
        for key in list(updated):
            if key == "archetype":
                continue
            field = form.get(f"v:{sid}:{key}")
            if field is None:
                continue
            updated[key] = _retype(updated[key], str(field))
        try:
            order = float(form.get(f"o:{sid}") or index)
        except ValueError:
            order = float(index)
        slides.append((order, updated))
        if form.get(f"dup:{sid}"):
            slides.append((order + 0.5, dict(updated)))

    return {**plan_dict,
            "slides": [s for _o, s in sorted(slides, key=lambda pair: pair[0])]}


def _retype(original, edited: str):
    """Keep a slot's shape. A list edited as lines stays a list; a list
    of dicts keeps its keys, split on pipes in the order they appear."""
    text = edited.strip()
    if isinstance(original, list):
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if original and isinstance(original[0], dict):
            fields = list(original[0])
            out = []
            for line in lines:
                parts = [p.strip() for p in line.split("|")]
                out.append({f: (parts[i] if i < len(parts) else "")
                            for i, f in enumerate(fields)})
            return out
        return lines
    return text


def slots_for(archetype: str, content: dict) -> list:
    """The editable slots for a slide: what the renderer reads, in the
    order it reads them, with what is currently in each."""
    slots = []
    for raw in _derived_content_keys(archetype):
        key = raw.split(" (")[0]
        if "filled automatically" in raw:
            continue
        slots.append((key, raw[len(key):].strip(" ()"), content.get(key)))
    return slots
