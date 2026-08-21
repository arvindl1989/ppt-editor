"""The package that goes to Claude Skills.

This handoff is an argument backed by numbers -- "29% of the library
bypasses BRAND_MODE" -- and the numbers are quoted verbatim in the prose
of TYPE_SYSTEM.md. If a migration lands and the audit moves, the prose
becomes a lie that nobody has any reason to re-read. So the test is that
the documents and the code still say the same thing.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def handoff():
    spec = importlib.util.spec_from_file_location(
        "skills_handoff", ROOT / "scripts" / "skills_handoff.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["skills_handoff"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def audit(handoff):
    return handoff.type_audit()


def test_the_prose_quotes_the_audit_it_was_written_from(handoff, audit):
    """Every number in TYPE_SYSTEM.md's opening block is live.

    The counts move with the registry -- a test that installs the
    gallery after the layouts leaves one region different from what the
    app builds -- so a hand-copied number in the prose would be right on
    the day it was typed and quietly wrong after. It is substituted
    instead, and this is the check that the substitution happened.
    """
    text = handoff.fill(handoff.TYPE_SYSTEM, audit)
    assert f"{audit['regions_with_baked_type']} regions carry a BAKED" in text
    assert f"{audit['regions_resolved_through_a_role']} regions resolve" in text
    assert f"{audit['percent_bypassing_brand_mode']}% of the library" in text
    assert f"{audit['disagreements']} of the {audit['regions_with_baked_type']}" in text


def test_every_document_is_fully_substituted(handoff, audit):
    """A stray `[[token]]` would ship in prose someone is meant to act on."""
    for name in ("README", "TYPE_SYSTEM", "PIPELINE", "OPEN_QUESTIONS",
                 "DIVIDER_HEAD"):
        filled = handoff.fill(getattr(handoff, name), audit)
        assert "[[" not in filled, name


def test_the_two_type_systems_are_still_both_there(audit):
    """The premise of the handoff. If either count goes to zero the
    argument is finished and the documents should be retired, not
    quietly kept."""
    assert audit["regions_with_baked_type"] > 0
    assert audit["regions_resolved_through_a_role"] > 0
    assert len(audit["rows"]) == audit["regions_with_baked_type"], \
        "the audit rows are the baked regions -- one row per baked region"


def test_every_disagreement_carries_both_values(audit):
    """A migration list is only usable if each row says what it is now
    and what the brand would make it."""
    for row in audit["rows"]:
        if not row["disagrees"]:
            continue
        assert row.get("baked"), row
        # Hedged on purpose: the slot NAME is not the role. This column
        # is a candidate to decide against, not an answer to apply.
        assert row.get("brand_for_that_slot_name"), row
        assert row["archetype"] and row["slot"], row


def test_the_divider_is_the_worked_example_it_claims_to_be(handoff):
    """The divider was the handoff's worked example of a BAKED slide and
    is now the worked example of a migrated one. It is the first
    archetype off the old system, so nothing here may carry a `dg`
    block, and every slot must name a role the brand actually defines --
    a role that resolves to None draws nothing at all."""
    from deckguard import brandmode as bm

    evidence = handoff.divider_evidence()
    slots = {r["slot"]: r for r in evidence["renders_as"] if r["slot"]}
    for name in ("number", "eyebrow", "title"):
        assert name in slots, f"the divider no longer has a {name} slot"
    assert not any(s["type"] for s in slots.values()), \
        "a divider slot went back to baked type"
    for name, region in slots.items():
        assert bm.resolve(region["role"]), \
            f"{name} names {region['role']!r}, which the brand does not define"


def test_the_pipeline_points_at_functions_that_exist(handoff):
    """The document tells a reader where to make a fix. A stale path
    sends them into a file that no longer has the code."""
    import deckguard.assemble
    import deckguard.layouts
    import deckguard.web

    for stage in handoff.pipeline().values():
        module_path, _, names = stage["where"].partition(" :: ")
        module = sys.modules["deckguard." + module_path.split("/")[-1][:-3]]
        for name in names.split(" / "):
            assert hasattr(module, name.strip()), f"{module_path} has no {name}"


def test_measuring_a_render_that_is_not_there_is_not_an_error(handoff, tmp_path):
    """The renders need LibreOffice. The generator has to survive a
    machine that has not got it rather than half-writing the package."""
    assert handoff.measure(tmp_path / "nothing.jpg") == {}
