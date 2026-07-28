"""
kone_planner.py
===============
"Claude as the prompt generator." Claude's job here is NOT to make things pretty —
the layout functions own the look. Claude's job is to read a brief and decide the
DECK PLAN: how many slides, which layout each one uses, and copy that fits each
layout's capacity. Output is strict JSON (the spec) that kone_deck_creator consumes.

Two ways to get a spec:
  1. Author it by hand (deterministic, no API).
  2. Call Claude with the brief + this system prompt (below) -> spec JSON.
Either way the rendering half is identical and offline.
"""

# The contract the creator expects. The intro/outro are retained from the master,
# so the plan only covers the BODY.
SPEC_SCHEMA = r"""
{
  "title": "<deck title — also fills the retained master cover>",
  "slides": [
    // choose one layout per slide, fill only that layout's fields:
    {"layout":"section_divider","eyebrow":"<short KONE-Information label>","title":"<section title>"},
    {"layout":"title_content","title":"<= 60 chars","bullets":["<= 90 chars", "..."]},   // 3–5 bullets
    {"layout":"two_content","title":"<= 60 chars","columns":[
        {"heading":"<= 30 chars","bullets":["...", "..."]},                                // exactly 2 columns
        {"heading":"<= 30 chars","bullets":["...", "..."]}]},
    {"layout":"three_stats","title":"<= 90 chars","stats":[                                 // exactly 3 stats
        {"label":"<= 18 chars","value":"<= 6 chars","desc":"<= 70 chars"}, {...}, {...}]},
    {"layout":"roadmap","eyebrow":"<label>","title":"<= 60 chars","phases":[                // 2–5 phases
        {"year":"<e.g. 2025>","title":"<= 20 chars","desc":"<= 90 chars"}, ...]},
    {"layout":"quote","label":"<= 24 chars","quote":"<= 140 chars","attribution":"<name, role>"}
  ]
}
"""

LAYOUT_CATALOG = """\
section_divider — open a new section / topic. Big statement title. Use to break a long deck into parts.
title_content   — one idea with 3–5 supporting points. The default content slide.
two_content     — compare / contrast two things, or before/after, or two workstreams. Exactly two columns.
three_stats     — three headline numbers (KPIs, results, scale). Great for exec audiences. Exactly three.
roadmap         — time-phased plan: years or quarters as a horizontal timeline. 2–5 phases.
quote           — a single testimonial, principle, or callout on a blue panel. One sentence.
"""

SYSTEM_PROMPT = f"""You are the deck planner for KONE's Marketing Hub deck creator.
You do NOT design visuals — a separate engine renders each layout to exact KONE brand
spec. Your only job: turn the brief into a slide-by-slide PLAN as strict JSON.

RULES
- The cover (intro) and closing (outro) are added automatically from the KONE master. \
Do NOT plan a cover or a thank-you slide. Plan the BODY only.
- Choose the layout that fits each idea's SHAPE, not by variety for its own sake:
{LAYOUT_CATALOG}
- Character limits are guidance, not hard constraints — the renderer shrinks text that would \
overflow. Prefer to stay under them for the best look, but never reject a spec or truncate \
mid-word just to hit a number; a slightly-over value is fine.
- Vary layouts across the deck; don't put everything on title_content.
- KONE voice: sentence case, plain, confident, no marketing fluff, no emoji.
- Aim for 5–9 body slides unless the brief implies otherwise. Open with a section_divider \
when the deck has clear parts.
- Output ONLY the JSON object matching this schema, no prose, no markdown fences:
{SPEC_SCHEMA}
"""

def build_messages(brief:str):
    return {"system":SYSTEM_PROMPT,
            "messages":[{"role":"user","content":f"BRIEF:\n{brief}\n\nReturn the deck spec JSON."}]}

def call_claude(brief:str, model="claude-opus-4-8"):
    """Optional. Needs `pip install anthropic` and ANTHROPIC_API_KEY."""
    import anthropic, json
    m=build_messages(brief)
    resp=anthropic.Anthropic().messages.create(
        model=model, max_tokens=2000, system=m["system"], messages=m["messages"])
    text="".join(b.text for b in resp.content if b.type=="text")
    return json.loads(text)   # -> spec dict, feed straight into build_deck()
