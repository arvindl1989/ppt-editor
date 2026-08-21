"""The two screens: give it something, then edit what came back."""

from __future__ import annotations

import os

import json

from deckguard import assemble
from deckguard import brandmode as bm
from deckguard import meter
from deckguard.ui import esc


def _thumb(name: str, content: dict | None = None) -> str:
    """A real picture of the slide where we have one, a wireframe where
    we do not.

    The wireframe knows where the boxes are and nothing about what the
    slide looks like -- at tile size a photo cover, a sand statement and
    a blue quote all come out as a pale rectangle with grey lines on it.
    `thumbs` renders the actual slide through LibreOffice offline, and
    those PNGs are what you pick from.
    """
    from deckguard import thumbs
    from deckguard.preview import archetype_preview_html, sample_content

    if thumbs.path_for(name) is not None:
        return (f'<img src="/preview/{esc(name)}.png" alt="{esc(name)}" '
                f'loading="lazy" width="520" height="293" class="shot">')
    return archetype_preview_html(name, content if content is not None
                                  else sample_content(name))


def _slide_tiles(stop: int) -> str:
    """The layouts eligible at one stop of the meter.

    Not greyed-out tiles for the stops above: showing someone a layout
    they cannot use invites them to argue with the control they just
    set. The meter moved, so the shelf changed.
    """
    from deckguard.registry import _load_archetypes

    built = set(_load_archetypes().ARCHETYPES)
    audience = meter.audience_for_stop(stop)
    eligible = meter.pool_for_stop(stop)
    out = []
    for slide in bm.slides_in(audience):
        name = slide["archetype"]
        if eligible and name not in eligible:
            continue
        if name not in built:
            out.append(f'''<span class="tile off">
  <span class="frame"><span class="stub">Not built yet</span></span>
  <span class="name"><span>{esc(name)}</span></span>
  <span class="from">{esc(slide["group"])}</span></span>''')
            continue
        out.append(f'''<label class="tile">
  <span class="frame">{_thumb(name)}</span>
  <span class="name">
    <input type="checkbox" name="pick" value="{esc(audience)}:{slide['n']}">
    <span>{esc(name)}</span></span>
  <span class="from">{esc(slide["group"])} &middot; {esc(slide["field"])}</span>
</label>''')
    return "".join(out)


def _section_chips() -> str:
    """What the deck should cover, as chips rather than a dropdown.

    A dropdown hides its options behind a click, and the whole value
    here is seeing the dozen things a deck might need and recognising
    the four you actually have material for.
    """
    out = []
    for key, entry in bm.DECK_SECTIONS.items():
        label = esc(entry["label"])
        hint = esc(entry["hint"])
        out.append(
            '<label class="chip" title="' + hint + '">'
            '<input type="checkbox" name="section" value="' + esc(key) + '">'
            "<span>" + label + "</span></label>"
        )
    return "".join(out)


def _meter_control() -> str:
    """Four stops, the segmented control the page already has."""
    out = []
    for entry in meter.stops():
        n = entry.get("n")
        checked = " checked" if n == meter.DEFAULT_STOP else ""
        out.append(
            '<label title="' + esc(entry.get("help", "")) + '">'
            f'<input type="radio" name="stop" value="{n}"{checked} '
            f'onchange="showStop({n})"> ' + esc(entry.get("label", "")) + "</label>")
    return '<div class="seg meter">' + "".join(out) + "</div>"


def home(error: str = "") -> str:
    note = f'<p class="note bad">{esc(error)}</p>' if error else ""
    # Said once, and only when it is true. The page used to explain the
    # brief, the sections, the audience and the upload in four
    # paragraphs nobody reads twice.
    ai_note = "" if os.environ.get("ANTHROPIC_API_KEY") else (
        '<p class="hint">No API key here — pick slides below instead.</p>')
    open_note = "" if os.environ.get("DECKGUARD_WEB_PASSWORD") else (
        '<p class="hint">No password set.</p>')
    meter_json = json.dumps(
        {e["n"]: meter.summary(e["n"]) for e in meter.stops()})

    panels = "".join(
        f'<div class="set" data-stop="{n}" style="display:none">'
        f'<div class="grid">{_slide_tiles(n)}</div></div>'
        for n in range(1, len(meter.stops()) + 1))

    return f"""{note}
<div class="rule"></div>
<h2 class="section">Build a KONE deck</h2>

<form method="post" action="/generate" enctype="multipart/form-data">
  <div class="field">
    <span class="label">How far from the template</span>
    {_meter_control()}
    <p class="hint" id="meter-note">{esc(meter.summary(meter.DEFAULT_STOP))}</p>
  </div>
  <div class="cols">
    <div>
      <div class="field">
        <span class="label">Brief, or an email to turn into slides</span>
        <textarea name="brief" rows="9" placeholder="Paste the announcement, the notes, or a
sentence about what the deck is for."></textarea>
        {ai_note}
      </div>
      <div class="field">
        <span class="label">Deck title</span>
        <input type="text" name="title" placeholder="Taken from the brief">
      </div>
    </div>
    <div>
      <div class="field">
        <span class="label">What the deck should cover</span>
        <div class="chips">{_section_chips()}</div>
      </div>
      <div class="field">
        <span class="label">Your own deck</span>
        <input type="file" name="deck" accept=".pptx">
      </div>
      <div class="field">
        <label class="check"><input type="checkbox" name="validate" checked>
          Check the deck against the brand rules</label>
        <p class="hint">Reports copy that will not fit, wording lifted
          straight from the brief, and type off the scale. Never blocks
          the download.</p>
      </div>
      <div class="actions">
        <button type="submit">Build the deck</button>
      </div>
      {open_note}
    </div>
  </div>

  <div class="hair"></div>
  <span class="label">Or pick slides</span>
  {panels}
</form>

<script>
var METER = {meter_json};
function showStop(n) {{
  document.querySelectorAll('.set').forEach(function (p) {{
    var on = p.dataset.stop === String(n);
    p.style.display = on ? 'block' : 'none';
    if (!on) p.querySelectorAll('input[name=pick]').forEach(function (c) {{ c.checked = false; }});
  }});
  var note = document.getElementById('meter-note');
  if (note && METER[n]) note.textContent = METER[n];
}}
showStop({meter.DEFAULT_STOP});
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


def result(token: str, plan: dict, audience: str, mined: dict, checks: dict,
           gate: list = (), validating: bool = True) -> str:
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

    # Gate 1, grouped by check rather than by slide. A reader wants to
    # know "is any copy lifted from the brief", not to walk eleven
    # slides looking for the pattern themselves.
    if not validating:
        gate_note = ('<div class="note">Brand checks were switched off for this '
                     'build. Tick the box to run them.</div>')
    elif gate:
        by_check: dict = {}
        for finding in gate:
            by_check.setdefault(finding.check, []).append(finding)
        blocks = []
        for check, found in sorted(by_check.items(), key=lambda kv: -len(kv[1])):
            lines = "".join(f"<li>{esc(f.as_line())}</li>" for f in found[:6])
            extra = (f"<li class='hint'>and {len(found) - 6} more</li>"
                     if len(found) > 6 else "")
            blocks.append(f"<p><b>{esc(check)}</b> &middot; {len(found)}</p>"
                          f"<ul>{lines}{extra}</ul>")
        # Red only when something is actually configured to stop a
        # build. Every check ships at `report`, so painting the panel as
        # an alarm for "no speaker notes" is how a panel gets dismissed
        # unread -- and then the one that matters is dismissed with it.
        from deckguard import validate as V

        loud = " bad" if V.worst(gate) != V.REPORT else ""
        gate_note = (f'<div class="note{loud}"><b>Brand checks found '
                     f'{len(gate)}</b>{"".join(blocks)}'
                     '<p class="hint">Reported, not blocked — the deck above is '
                     'yours either way.</p></div>')
    else:
        gate_note = ('<div class="note">Brand checks clean — copy fits its slots, '
                     'nothing lifted from the brief, type on the scale.</div>')

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
  <div><div class="v">{len(gate) if validating else "&mdash;"}</div>
    <div class="k">Brand checks</div></div>
</div>
{repeat_note}

<div class="actions" style="margin-bottom:26px;">
  <a class="btn" href="/download/{esc(token)}/deck.pptx">Download .pptx</a>
  <a class="btn ghost" href="/">Start again</a>
</div>

{mined_note}
{preflight}
{gate_note}

<form method="post" action="/rebuild/{esc(token)}">
  <label class="check" style="margin-bottom:18px;display:block;">
    <input type="checkbox" name="validate"{" checked" if validating else ""}>
    Check the deck against the brand rules</label>
  {"".join(rows)}
  <div class="actions" style="margin-top:24px;">
    <button type="submit">Apply changes and rebuild</button>
  </div>
</form>"""
