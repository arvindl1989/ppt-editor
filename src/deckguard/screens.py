"""The two screens: give it something, then edit what came back."""

from __future__ import annotations

import os

from deckguard import assemble
from deckguard import brandmode as bm
from deckguard.ui import esc


def _slide_tiles(audience: str) -> str:
    from deckguard.preview import archetype_preview_html, sample_content
    from deckguard.registry import _load_archetypes

    built = set(_load_archetypes().ARCHETYPES)
    out = []
    for slide in bm.slides_in(audience):
        name = slide["archetype"]
        if name not in built:
            out.append(f'''<span class="tile off">
  <span class="frame"><span class="stub">Not built yet</span></span>
  <span class="name">{esc(name)}</span>
  <span class="from">{esc(slide["group"])}</span></span>''')
            continue
        out.append(f'''<label class="tile">
  <input type="checkbox" name="pick" value="{esc(audience)}:{slide['n']}">
  <span class="frame">{archetype_preview_html(name, sample_content(name))}</span>
  <span class="name">{esc(name)}</span>
  <span class="from">{esc(slide["group"])} &middot; {esc(slide["field"])}</span>
</label>''')
    return "".join(out)


def home(error: str = "") -> str:
    note = f'<p class="note bad">{esc(error)}</p>' if error else ""
    ai = bool(os.environ.get("ANTHROPIC_API_KEY"))
    ai_hint = (
        "Paste a brief or an announcement email and it drafts the slides for you."
        if ai else
        "No API key on this server, so briefs are not planned — pick slides below instead. "
        "Everything else works without one."
    )
    open_note = "" if os.environ.get("DECKGUARD_WEB_PASSWORD") else (
        '<p class="hint">No password is set on this server.</p>')

    panels = "".join(
        f'<div class="set" data-audience="{a}" style="display:none">'
        f'<div class="grid">{_slide_tiles(a)}</div></div>'
        for a in bm.set_names())

    return f"""{note}
<div class="rule"></div>
<h2 class="section">Build a KONE deck</h2>
<p class="lede">Give it a brief, pick the slides yourself, or attach a deck and use its own
  designs as templates. Any combination. It builds straight away and you edit afterwards.</p>

<form method="post" action="/generate" enctype="multipart/form-data">
  <div class="cols">
    <div>
      <div class="field">
        <span class="label">Brief, or an email to turn into slides</span>
        <textarea name="brief" rows="9" placeholder="Paste the announcement, the notes, or a
sentence about what the deck is for."></textarea>
        <p class="hint">{ai_hint}</p>
      </div>
      <div class="field">
        <span class="label">Deck title</span>
        <input type="text" name="title" placeholder="Taken from the brief if you leave it empty">
      </div>
    </div>
    <div>
      <div class="field">
        <span class="label">Audience</span>
        <div class="seg">
          <label><input type="radio" name="audience" value="internal" checked
            onchange="showSet('internal')"> Internal</label>
          <label><input type="radio" name="audience" value="external"
            onchange="showSet('external')"> External</label>
        </div>
        <p class="hint">Internal allows the secondary colours and the icon-led layouts.
          External is blue, white, black and photography only.</p>
      </div>
      <div class="field">
        <span class="label">Your own deck (optional)</span>
        <input type="file" name="deck" accept=".pptx">
        <p class="hint">Its slide designs are read out as templates you can build from.
          Nothing in it is changed.</p>
      </div>
      <div class="actions">
        <button type="submit">Build the deck</button>
      </div>
      {open_note}
    </div>
  </div>

  <div class="hair"></div>
  <span class="label">Or pick slides — optional</span>
  <p class="hint" style="margin-bottom:16px;">Leave these alone and the brief decides.
    Pick some and it uses exactly those, in this order.</p>
  {panels}
</form>

<script>
function showSet(a) {{
  document.querySelectorAll('.set').forEach(function (p) {{
    var on = p.dataset.audience === a;
    p.style.display = on ? 'block' : 'none';
    if (!on) p.querySelectorAll('input[name=pick]').forEach(function (c) {{ c.checked = false; }});
  }});
}}
showSet('internal');
</script>"""


def _slot_field(index: int, key: str, hint: str, value) -> str:
    name = f"v:{index}:{key}"
    if isinstance(value, list):
        if value and isinstance(value[0], dict):
            text = "\n".join(" | ".join(str(v.get(f, "")) for f in value[0])
                             for v in value)
        else:
            text = "\n".join(str(v) for v in value)
        rows = max(2, min(6, len(value) + 1))
        return (f'<div class="slot"><label for="{name}">{esc(key)}</label>'
                f'<textarea id="{name}" name="{name}" rows="{rows}">{esc(text)}</textarea></div>')
    if value is None and "list of" in hint:
        return (f'<div class="slot"><label for="{name}">{esc(key)} — {esc(hint)}</label>'
                f'<textarea id="{name}" name="{name}" rows="3"></textarea></div>')
    long = len(str(value or "")) > 70 or key in ("body", "lede", "context", "quote", "text")
    if long:
        return (f'<div class="slot"><label for="{name}">{esc(key)}</label>'
                f'<textarea id="{name}" name="{name}" rows="2">{esc(value or "")}</textarea></div>')
    return (f'<div class="slot"><label for="{name}">{esc(key)}</label>'
            f'<input type="text" id="{name}" name="{name}" value="{esc(value or "")}"></div>')


def result(token: str, plan: dict, audience: str, mined: dict, checks: dict) -> str:
    from deckguard.preview import archetype_preview_html

    slides = plan.get("slides") or []
    rows = []
    for index, slide in enumerate(slides):
        name = slide.get("archetype", "")
        content = {k: v for k, v in slide.items() if k != "archetype"}
        fields = "".join(_slot_field(index, key, hint, value)
                         for key, hint, value in assemble.slots_for(name, content))
        rows.append(f'''<div class="slide-row">
  <div>{archetype_preview_html(name, content)}
    <span class="from">{index + 1:02d} &middot; {esc(name)}</span></div>
  <div>{fields or '<p class="hint">This slide takes no text.</p>'}</div>
  <div class="tools">
    <label>order <input type="number" name="o:{index}" value="{(index + 1) * 10}"
      step="1" style="width:5rem;padding:4px 6px;"></label>
    <label><input type="checkbox" name="drop:{index}"> drop</label>
    <label><input type="checkbox" name="dup:{index}"> duplicate</label>
  </div>
</div>''')

    mix = assemble.variety(plan)
    repeat_note = ""
    if mix["repeats"]:
        worst = ", ".join(f"{esc(n)} &times;{c}" for n, c in mix["repeats"][:3])
        repeat_note = (
            f'<div class="note">Reusing {worst}. Dividers repeating is right; '
            "a content layout repeating usually means the brief did not give it "
            "enough to work with. Rebuild with more detail, or pick the slides "
            "yourself below.</div>")

    findings = checks.get("findings") or []
    if findings:
        items = "".join(f"<li>Slide {n}: {esc(m)}</li>" for n, m in findings[:12])
        more = (f"<p class='hint'>and {len(findings) - 12} more</p>"
                if len(findings) > 12 else "")
        preflight = (f'<div class="note bad"><b>Preflight found '
                     f'{len(findings)}</b><ul>{items}</ul>{more}</div>')
    else:
        preflight = ('<div class="note">Preflight clean — nothing but black, white and '
                     'KONE Blue, one logo a slide, real bullets, everything above the floor.</div>')

    mined_note = ""
    templates = (mined or {}).get("archetypes") or {}
    if templates:
        sources = (mined or {}).get("sources") or {}
        listed = ", ".join(
            f"{esc(n)} (slide {min(sources.get(n) or [0])})" for n in list(templates)[:8])
        mined_note = (f'<div class="note"><b>{len(templates)} templates read from your deck.</b> '
                      f'{listed}. Pick them on the next build.</div>')
    elif (mined or {}).get("error"):
        mined_note = (f'<div class="note bad">Could not read that deck: '
                      f'{esc(mined["error"])}</div>')

    return f"""<div class="rule"></div>
<h2 class="section">{esc(plan.get("title"))}</h2>
<p class="lede">{len(slides)} slides, {esc(audience)}. Edit anything below and rebuild —
  or take the file as it is.</p>

<div class="stat-row">
  <div><div class="v">{checks.get("slides", 0)}</div><div class="k">Slides</div></div>
  <div><div class="v">{mix["distinct"]}</div><div class="k">Distinct layouts</div></div>
  <div><div class="v">{len(findings)}</div><div class="k">Preflight findings</div></div>
</div>
{repeat_note}

<div class="actions" style="margin-bottom:26px;">
  <a class="btn" href="/download/{esc(token)}/deck.pptx">Download .pptx</a>
  <a class="btn ghost" href="/">Start again</a>
</div>

{mined_note}
{preflight}

<form method="post" action="/rebuild/{esc(token)}">
  {"".join(rows)}
  <div class="actions" style="margin-top:24px;">
    <button type="submit">Apply changes and rebuild</button>
  </div>
</form>"""
