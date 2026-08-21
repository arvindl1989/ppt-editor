"""The deviation meter: one control, four stops, one axis.

Claude Design's design, and the argument for it is the part worth
keeping: an audience switch plus a freedom slider is two controls for
one decision, and the corners of that matrix are decks nobody should be
able to make -- a customer deck with a pink panel, an all-hands with no
icons. Collapsing them means the illegal combinations cannot be
expressed.

**The meter changes which layouts are eligible and nothing else.** It
does not loosen colour, type, icons or chrome as it moves right. Those
are properties of the archetype and the set, not of the stop:

    1  On template          the master's own layouts               external
    2  Slight deviation     master bands, re-divided               external
    3  Moderate deviation   off-master composition on the grid     internal
    4  Internal slide types plus the programme artefacts           internal

Pools are cumulative, so stop 4 contains stop 1. Audience is inferred
from the stop -- there is no second switch.

The tiers live in `docs/design-handoff/meter.json` rather than in this
file, because that is the artefact a designer edits.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

# The packaged copy is the one that is read. `docs/design-handoff/` holds
# the handoff as received, which is outside the package -- a pip install
# would not ship it, and the meter would have come up with no stops on
# Railway while working perfectly here.
_PACKAGED = Path(__file__).parent / "assets" / "kone-design" / "meter.json"
_RECEIVED = (Path(__file__).resolve().parent.parent.parent
             / "docs" / "design-handoff" / "meter.json")
METER_FILE = _PACKAGED if _PACKAGED.is_file() else _RECEIVED

DEFAULT_STOP = 1


@functools.lru_cache(maxsize=1)
def spec() -> dict:
    """The meter, as data. Empty if the file is missing."""
    try:
        return json.loads(METER_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def stops() -> list:
    return list(spec().get("stops") or [])


def stop(n: int) -> dict:
    """One stop, clamped into range."""
    every = stops()
    if not every:
        return {}
    n = max(1, min(int(n or DEFAULT_STOP), len(every)))
    return next((s for s in every if s.get("n") == n), every[0])


def audience_for_stop(n: int) -> str:
    """Which set a stop builds from. Stops 1-2 external, 3-4 internal."""
    return str(stop(n).get("audience") or "internal")


def pool_for_stop(n: int) -> set:
    """Archetype names eligible at this stop. Cumulative.

    The pool is the whole enforcement: a model cannot choose a layout it
    was never shown, so nothing downstream has to re-validate the
    choice against the meter.
    """
    tiers = set(stop(n).get("tiers") or [])
    if not tiers:
        return set()
    return {name for name, entry in (spec().get("archetypes") or {}).items()
            if entry.get("tier") in tiers}


def built_pool_for_stop(n: int) -> list:
    """The eligible archetypes that the renderer can actually draw, in
    the order the audience's set lists them."""
    from deckguard import brandmode as bm
    from deckguard.registry import _load_archetypes

    eligible = pool_for_stop(n)
    built = set(_load_archetypes().ARCHETYPES)
    audience = audience_for_stop(n)
    out = [s["archetype"] for s in bm.slides_in(audience)
           if s["archetype"] in eligible and s["archetype"] in built]
    # An archetype can be eligible at this stop and belong to the other
    # set -- `divider_numbering` serves both. Anything the set order
    # does not cover is appended so the pool is never short of what the
    # meter promised.
    out += sorted(n for n in eligible & built if n not in out)
    return out


def summary(n: int) -> str:
    """The one line of live consequence under the control."""
    where = stop(n)
    if not where:
        return ""
    count = len(built_pool_for_stop(n))
    promised = where.get("pool_size")
    short = ""
    if promised and count < promised:
        short = f" · {promised - count} not built yet"
    safe = "customer-safe" if where.get("audience") == "external" else "internal only"
    return f"{count} layouts · {safe}{short}"
