"""The package that goes to Claude Design.

It is generated, not written, so the thing to test is that what it
generates still matches the tool: a template with a key the renderer
does not read sends someone away to write copy that will be discarded.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def handoff():
    spec = importlib.util.spec_from_file_location(
        "design_handoff", ROOT / "scripts" / "design_handoff.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["design_handoff"] = module
    spec.loader.exec_module(module)
    return module


def test_the_template_asks_only_for_keys_the_renderer_reads(handoff):
    """The whole point of handing over a template rather than prose."""
    from deckguard import contracts as C

    data = handoff.contracts_json()
    template = handoff.placeholders_template(data)
    for audience, slides in template.items():
        for name, content in slides.items():
            have = set(C._registry_slots(name))
            unread = set(content) - have
            assert not unread, f"{audience}/{name} asks for {unread}"


def test_the_template_covers_every_required_slot(handoff):
    from deckguard import contracts as C

    data = handoff.contracts_json()
    template = handoff.placeholders_template(data)
    for audience, slides in template.items():
        for name, content in slides.items():
            contract = C.for_archetype(name, audience)
            missing = [s.key for s in contract.needs if s.key not in content]
            assert not missing, f"{audience}/{name} is missing {missing}"


def test_a_list_is_asked_for_at_the_length_the_layout_holds(handoff):
    """Three rows in a five-row agenda previews with two empty blocks."""
    from deckguard import contracts as C

    data = handoff.contracts_json()
    template = handoff.placeholders_template(data)
    for audience, slides in template.items():
        for name, content in slides.items():
            contract = C.for_archetype(name, audience)
            for slot in contract.slots:
                if not slot.fields or slot.key not in content:
                    continue
                assert len(content[slot.key]) == slot.maximum, f"{name}.{slot.key}"
                assert set(content[slot.key][0]) == {f.key for f in slot.fields}


def test_every_built_slide_in_both_sets_is_in_the_template(handoff):
    from deckguard import brandmode as bm
    from deckguard.registry import _load_archetypes

    built = set(_load_archetypes().ARCHETYPES)
    template = handoff.placeholders_template(handoff.contracts_json())
    for audience in bm.set_names():
        want = {s["archetype"] for s in bm.slides_in(audience)
                if s["archetype"] in built}
        assert want == set(template[audience])


def test_the_fit_budget_is_a_number_where_a_box_is_known(handoff):
    data = handoff.contracts_json()
    for entries in data["sets"].values():
        for entry in entries:
            if not entry["built"]:
                continue
            for slot in entry["slots"]:
                if slot["picture"] or "count" in slot:
                    continue
                fits = slot.get("fits_chars")
                assert fits is None or fits > 0, (entry["archetype"], slot["key"])


def test_the_documents_say_what_they_are_for(handoff):
    """A handoff whose instruction drifts from the tool is worse than
    none -- someone designs around a constraint that is not real."""
    assert "placeholders.json" in handoff.INSTRUCTIONS
    assert "placeholders.template.json" in handoff.INSTRUCTIONS
    # the icon rule was wrong once: a bogus name falls back to the
    # rotation, it does not leave a hole
    assert "falls back to the rotation" in handoff.INSTRUCTIONS
    assert "Phase 1" in handoff.README or "phase 2" in handoff.README
