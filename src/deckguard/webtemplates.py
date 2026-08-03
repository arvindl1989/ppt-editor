"""HTML rendering for the web app. Plain f-strings, no template engine —
keeps the web extra's dependency footprint to just FastAPI/uvicorn.
"""

from __future__ import annotations

import html

SEVERITY_COLOR = {"critical": "#FF5F28", "major": "#FFA023", "minor": "#8C8C8C"}

# KONE Design System tokens (see the kone-design skill: colors.css / typography.css /
# radius.css / elevation.css) mapped onto this app's own --bg/--surface/--ink/--accent
# aliases, so every existing f-string below keeps working unchanged. KONE Blue leads,
# Inter is the only typeface, sand is the one secondary surface, radius stays modest
# and square-leaning (the brand's own note: "a geometric, square-cornered brand").
BASE_CSS = """
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  @font-face {
    font-family: 'KONE Information'; src: url('/static/KONE_Information.ttf') format('truetype');
    font-weight: 400; font-style: normal; font-display: swap;
  }
  :root {
    --bg: #FFFFFF; --surface: #FFFFFF; --surface-sunken: #F3EEE6;
    --ink: #141414; --ink-muted: #727272; --ink-faint: #A1A1A1;
    --border: #E6E6E6; --border-strong: #D0D0D0;
    --accent: #1450F5; --accent-hover: #4373F7; --accent-soft: #D0DCFD; --accent-softer: #EEF2FE;
    --ok: #1ED273; --ok-soft: #E4FAEE; --danger: #FF5F28; --danger-soft: #FFEEE7; --warn: #FFA023; --warn-soft: #FFF3E2;
    --shadow-1: 0 1px 2px rgba(20,20,20,.06);
    --shadow-2: 0 6px 20px rgba(20,20,20,.08), 0 1px 3px rgba(20,20,20,.05);
    --shadow-focus: 0 0 0 3px rgba(20,80,245,.28);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #131211; --surface: #1B1A18; --surface-sunken: #221F1B;
      --ink: #F3EEE6; --ink-muted: #B8B2A6; --ink-faint: #8A8478;
      --border: #322E27; --border-strong: #43403A;
      --accent: #7296F9; --accent-hover: #A1B9FB; --accent-soft: #23335C; --accent-softer: #1B2440;
      --ok: #4BE39A; --ok-soft: #12301F; --danger: #FF8259; --danger-soft: #3A1D12; --warn: #FFB84D; --warn-soft: #3A2A0F;
      --shadow-1: 0 1px 2px rgba(0,0,0,.3); --shadow-2: 0 6px 20px rgba(0,0,0,.4); --shadow-focus: 0 0 0 3px rgba(114,150,249,.35);
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: 'Inter', 'Helvetica Neue', Arial, 'Noto Sans', sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { color: var(--accent-hover); text-decoration: underline; }
  .wrap { max-width: 760px; margin: 0 auto; padding: 0 1.5rem 5rem; }
  .topbar {
    display: flex; align-items: center; gap: 0.65rem;
    padding: 1.6rem 0 1.2rem;
  }
  .brand { display: flex; align-items: center; gap: 0.6rem; }
  .brand svg { width: 26px; height: auto; flex: none; }
  .brand h1 { font-size: 1.05rem; font-weight: 600; margin: 0; letter-spacing: -0.01em; }
  /* KONE Information: the brand's secondary caps typeface, for labels/eyebrows/page numbers */
  .tag, .stat span, th, .hero .eyebrow { font-family: 'KONE Information', 'Inter', sans-serif; }
  .tag {
    font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--accent); background: var(--accent-softer); padding: 0.25rem 0.6rem; border-radius: 999px;
  }
  nav.jump { display: flex; gap: 1.25rem; flex-wrap: wrap; font-size: 0.82rem; }
  nav.jump a { color: var(--ink-muted); font-weight: 500; }
  nav.jump a:hover { color: var(--accent); text-decoration: none; }
  p.lede { color: var(--ink-muted); margin: 0 0 1.5rem; font-size: 0.95rem; max-width: 60ch; }
  .section-head { margin: 2.6rem 0 0.9rem; }
  .section-head:first-of-type { margin-top: 1.8rem; }
  .section-head h2 { font-size: 1.05rem; font-weight: 600; margin: 0 0 0.2rem; display: flex; align-items: center; gap: 0.5rem; }
  .section-head p { margin: 0; color: var(--ink-muted); font-size: 0.85rem; }
  .kicker {
    display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px;
    border-radius: 6px; background: var(--accent-softer); color: var(--accent); font-size: 0.72rem; font-weight: 700;
  }
  .card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 1.5rem; margin-bottom: 1.25rem; box-shadow: var(--shadow-1);
  }
  .card h2, .card h3 { font-weight: 600; margin-top: 0; }
  .result-head { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 0.9rem; }
  .result-head h2 { margin-bottom: 0; }
  .pill {
    display: inline-flex; align-items: center; font-family: 'KONE Information', 'Inter', sans-serif;
    font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
    padding: 0.2rem 0.6rem; border-radius: 999px;
  }
  .pill-danger { background: var(--danger-soft); color: var(--danger); }
  .pill-warn { background: var(--warn-soft); color: var(--warn); }
  .pill-ok { background: var(--ok-soft); color: var(--ok); }
  .notice {
    border-left: 3px solid var(--warn); background: var(--warn-soft); border-radius: 6px;
    padding: 0.8rem 1rem; margin: 0 0 1.25rem; font-size: 0.85rem; color: var(--ink);
  }
  .notice b { display: block; margin-bottom: 0.25rem; }
  .notice p { margin: 0.35rem 0 0; color: var(--ink-muted); }
  .drop {
    border: 1.5px dashed var(--border-strong); border-radius: 10px; padding: 2.25rem 1.5rem;
    text-align: center; background: var(--surface-sunken);
  }
  .drop p { margin: 0 0 1rem; color: var(--ink-muted); }
  input[type="file"] { margin-bottom: 1rem; font-size: 0.85rem; }
  .btn-row { display: flex; gap: 0.75rem; justify-content: center; flex-wrap: wrap; }

  .field { margin-bottom: 1.1rem; }
  .field:last-child { margin-bottom: 0; }
  .field-hint { color: var(--ink-faint); font-size: 0.78rem; margin: 0.35rem 0 0; }

  .mini-toggle { display: inline-flex; gap: 0.25rem; background: var(--surface-sunken); border-radius: 8px; padding: 0.25rem; }
  .mini-toggle input { position: absolute; opacity: 0; pointer-events: none; }
  .mini-toggle label {
    padding: 0.4rem 0.85rem; border-radius: 6px; cursor: pointer; font-size: 0.82rem; font-weight: 600; color: var(--ink-muted);
    transition: background-color 140ms ease, color 140ms ease;
  }
  .mini-toggle input:checked + label { background: var(--surface); color: var(--ink); box-shadow: var(--shadow-1); }

  details.advanced { margin-top: 0.25rem; }
  details.advanced summary {
    cursor: pointer; font-size: 0.82rem; font-weight: 600; color: var(--ink-muted);
    padding: 0.4rem 0; list-style: none; display: flex; align-items: center; gap: 0.35rem;
  }
  details.advanced summary::-webkit-details-marker { display: none; }
  details.advanced summary::before { content: "›"; display: inline-block; transition: transform 140ms ease; font-size: 1rem; }
  details.advanced[open] summary::before { transform: rotate(90deg); }
  details.advanced summary:hover { color: var(--ink); }
  details.advanced .field { margin-top: 1rem; }
  button {
    font: inherit; font-weight: 600; font-size: 0.88rem;
    padding: 0.62rem 1.35rem; border-radius: 8px; border: 1px solid transparent;
    cursor: pointer; transition: background-color 140ms ease, filter 140ms ease;
  }
  button.primary { background: var(--accent); color: #FFFFFF; }
  button.primary:hover { background: var(--accent-hover); }
  button.secondary { background: var(--surface); color: var(--ink); border-color: var(--border-strong); }
  button.secondary:hover { background: var(--surface-sunken); }
  a.dl {
    display: inline-block; background: var(--accent); color: #FFFFFF !important; text-decoration: none !important;
    font-weight: 600; font-size: 0.85rem; padding: 0.55rem 1.1rem; border-radius: 8px; margin: 0.2rem 0.4rem 0.2rem 0;
    transition: background-color 140ms ease;
  }
  a.dl:hover { background: var(--accent-hover); }
  a.dl.secondary { background: var(--surface); color: var(--ink) !important; border: 1px solid var(--border-strong); }
  a.dl.secondary:hover { background: var(--surface-sunken); }
  .stat-row { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
  .stat {
    flex: 1; min-width: 110px; background: var(--surface-sunken); border: 1px solid transparent;
    border-radius: 8px; padding: 0.85rem 1rem;
  }
  .stat b { display: block; font-size: 1.4rem; font-variant-numeric: tabular-nums; }
  .stat span { font-size: 0.68rem; color: var(--ink-faint); text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th, td { text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--border); vertical-align: top; }
  th {
    font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; color: var(--ink-faint);
    position: sticky; top: 0; background: var(--surface); box-shadow: 0 1px 0 var(--border);
  }
  tbody tr:nth-child(even) { background: var(--surface-sunken); }
  tbody tr:hover { background: var(--accent-softer); }
  .sev { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 0.4rem; }
  .table-wrap { overflow-x: auto; }
  code { font-family: ui-monospace, "SF Mono", Consolas, monospace; font-size: 0.85em; background: var(--surface-sunken); padding: 0.1em 0.35em; border-radius: 4px; }
  .error { background: var(--danger-soft); color: var(--danger); border-radius: 8px; padding: 1rem 1.2rem; font-size: 0.9rem; }
  .note { background: var(--accent-softer); color: var(--ink); border-radius: 8px; padding: 0.9rem 1.1rem; font-size: 0.85rem; margin-bottom: 1rem; }
  .empty { color: var(--ink-faint); font-size: 0.88rem; padding: 0.5rem 0; }
  footer { color: var(--ink-faint); font-size: 0.78rem; margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--border); }
  footer code { background: none; padding: 0; }
  select {
    font: inherit; font-size: 0.85rem; padding: 0.35rem 0.55rem; border-radius: 6px;
    border: 1px solid var(--border-strong); background: var(--surface); color: var(--ink);
  }
  textarea, input[type="text"], input[type="number"] {
    font: inherit; border-radius: 8px; border: 1px solid var(--border-strong);
    background: var(--surface); color: var(--ink);
  }
  textarea:focus, input:focus, select:focus { outline: none; box-shadow: var(--shadow-focus); border-color: var(--accent); }
  label.field-label { display: block; font-size: 0.82rem; color: var(--ink-muted); margin-bottom: 0.3rem; font-weight: 500; }
  .swatch {
    display: inline-block; width: 14px; height: 14px; border-radius: 4px;
    vertical-align: -2px; margin-right: 0.4em; border: 1px solid var(--border);
  }
  .muted { color: var(--ink-muted); font-size: 0.85rem; }
  .checkbox-row { display: flex; align-items: flex-start; gap: 0.5rem; font-size: 0.85rem; color: var(--ink); margin-bottom: 1rem; }
  .checkbox-row input { margin-top: 0.2rem; }
  .badge-working {
    font-size: 0.65rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
    color: var(--ok); background: var(--ok-soft); padding: 0.15rem 0.5rem; border-radius: 999px;
  }

  /* -- transform review cards -- */
  .review-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 0.9rem; }
  @media (max-width: 620px) { .review-cols { grid-template-columns: 1fr; } }
  .prev-label {
    margin: 0 0 0.3rem; font-family: 'KONE Information', 'Inter', sans-serif;
    font-size: 0.65rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.07em; color: var(--ink-faint);
  }

  /* -- home hero: orientation for a first-time visitor, above the tool card -- */
  .hero { padding: 0.4rem 0 2.4rem; }
  .hero .eyebrow {
    display: inline-block;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--accent); margin-bottom: 0.7rem;
  }
  .hero h1 { font-size: 1.9rem; font-weight: 600; letter-spacing: -0.015em; margin: 0 0 0.6rem; line-height: 1.15; }
  .hero p.lede { font-size: 1rem; max-width: 56ch; margin: 0; }
  .capstrip {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; margin-top: 1.9rem;
    border-top: 1px solid var(--border); border-left: 1px solid var(--border);
  }
  .capstrip .cap {
    padding: 1rem 1.1rem; border-right: 1px solid var(--border); border-bottom: 1px solid var(--border);
  }
  .capstrip .cap b { display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.25rem; }
  .capstrip .cap span { display: block; font-size: 0.78rem; color: var(--ink-muted); line-height: 1.45; }
  @media (max-width: 640px) {
    .capstrip { grid-template-columns: 1fr 1fr; }
  }
"""

KONE_LOGO_SVG = (
    '<svg viewBox="0 0 1193.36 461.76" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="KONE">'
    '<rect x="0" y="0" width="269.36" height="461.76" fill="#1450F5"/>'
    '<rect x="307.84" y="0" width="269.36" height="461.76" fill="#1450F5"/>'
    '<rect x="615.67" y="0" width="269.36" height="461.76" fill="#1450F5"/>'
    '<rect x="924.01" y="0" width="269.36" height="461.76" fill="#1450F5"/>'
    '<path d="M48.22 132.07 100.91 132.07 100.91 218.29 166.14 132.07 228.2 132.07 156.18 225.09 233.14 329.69 168.65 329.69 100.91 236.06 100.91 329.69 48.22 329.69 48.22 132.07Z" fill="#FFFFFF"/>'
    '<path d="M662.48 132.07 708.51 132.07 789.32 239.42 789.32 132.07 838.22 132.07 838.22 329.69 794.28 329.69 711.22 214.01 711.22 329.69 662.48 329.69 662.48 132.07Z" fill="#FFFFFF"/>'
    '<path d="M442.5 127.72C385.71 127.72 340.03 169.65 340.03 230.84 340.03 292.03 385.71 334.04 442.5 334.04 499.29 334.04 544.99 292.02 544.99 230.84 544.99 169.66 499.31 127.72 442.5 127.72ZM442.5 287.4C414.42 287.4 392.72 264.39 392.72 230.85 392.72 197.31 414.41 174.3 442.5 174.3 470.59 174.3 492.27 197.39 492.27 230.85 492.27 264.31 470.5 287.4 442.5 287.4Z" fill="#FFFFFF"/>'
    '<path d="M1133.44 175.62 1036 175.62 1036 209.03 1117.47 209.03 1117.45 251.34 1036 251.34 1036 284.85 1133.44 284.85 1133.44 329.71 983.93 329.71 983.93 132.05 1133.44 132.05 1133.44 175.62Z" fill="#FFFFFF"/>'
    '</svg>'
)


def _esc(v) -> str:
    return html.escape(str(v)) if v is not None else ""


def page_shell(title: str, body: str, home: bool = False) -> str:
    back = "" if home else '<a href="/" style="font-size:0.85rem;font-weight:600;">&larr; deckguard</a>'
    return f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>{BASE_CSS}</style>
</head><body><div class="wrap">
<div class="topbar">
  <div class="brand">{KONE_LOGO_SVG}<h1>deckguard</h1></div>
  {back}
</div>
{body}
<footer>Deterministic by default — colors, fonts, effects, layout. The AI is only ever a suggestion
layer (archetype proposals, brief planning), needs an API key set by the operator, and nothing executes
without your per-slide approval.</footer>
</div>

</body></html>"""


def home_hero() -> str:
    """Orientation for a first-time visitor: the one Transform flow,
    told as its four steps."""
    caps = [
        ("1 · Upload", "An old deck to transform, a reference deck to match, a brief for a new deck — any combination."),
        ("2 · Review", "Every slide side by side: what it is now, what it would become — approve or override each one."),
        ("3 · Transform", "Approved slides rebuild onto approved layouts or KONE archetypes; everything gets brand patches."),
        ("4 · Audit", "The result is audited against the brand rules — and against your reference deck, when given."),
    ]
    cap_html = "".join(f'<div class="cap"><b>{_esc(t)}</b><span>{_esc(d)}</span></div>' for t, d in caps)
    return f"""<div class="hero">
  <span class="eyebrow">KONE &middot; Dedicated to People Flow&trade;</span>
  <h1>Every deck, on brand.</h1>
  <p class="lede">Deterministic brand compliance for PowerPoint, with AI assistance where it earns its keep --
    color, font, effect and layout rules apply the same way whether a deck is fixed, redesigned, or built
    from nothing.</p>
  <div class="capstrip">{cap_html}</div>
</div>"""




def _status_pill(critical: int, major: int, minor: int) -> str:
    """An at-a-glance verdict next to a result page's title -- the stat
    row below already has the exact numbers, but reading five stat
    boxes to tell "is this deck okay" is more work than one glance
    should need."""
    if critical:
        return f'<span class="pill pill-danger">{critical} critical</span>'
    if major:
        return f'<span class="pill pill-warn">{major} major</span>'
    if minor:
        return f'<span class="pill pill-warn">{minor} minor</span>'
    return '<span class="pill pill-ok">All clear</span>'


def _violation_rows(violations: list[dict]) -> str:
    if not violations:
        return '<tr><td colspan="6" class="empty">No violations found.</td></tr>'
    rows = []
    for v in violations[:500]:  # keep the page responsive on very large decks
        color = SEVERITY_COLOR.get(v["severity"], "#8C8C8C")
        rows.append(
            f"<tr><td>{_esc(v['slide_index'])}</td>"
            f"<td><span class='sev' style='background:{color}'></span>{_esc(v['severity'])}</td>"
            f"<td>{_esc(v['rule'])}</td>"
            f"<td>{_esc(v.get('shape_name') or '')}</td>"
            f"<td>{_esc(v['message'])}</td>"
            f"<td>{'yes' if v['auto_fixable'] else 'no'}</td></tr>"
        )
    truncated = ""
    if len(violations) > 500:
        truncated = f'<tr><td colspan="6" class="empty">…and {len(violations) - 500} more (see the JSON download for the full list)</td></tr>'
    return "".join(rows) + truncated


def audit_result_page(deck_name: str, summary: dict, violations: list[dict], download_links: dict) -> str:
    stats = f"""<div class="stat-row">
  <div class="stat"><b>{summary['total']}</b><span>total</span></div>
  <div class="stat"><b style="color:#FF5F28">{summary['critical']}</b><span>critical</span></div>
  <div class="stat"><b style="color:#FFA023">{summary['major']}</b><span>major</span></div>
  <div class="stat"><b style="color:#8C8C8C">{summary['minor']}</b><span>minor</span></div>
  <div class="stat"><b style="color:#1ED273">{summary['auto_fixable']}</b><span>auto-fixable</span></div>
</div>"""
    dl = (
        f'<a class="dl" href="{download_links["json"]}">Download JSON report</a>'
        f'<a class="dl secondary" href="/">Audit another deck</a>'
    )
    pill = _status_pill(summary["critical"], summary["major"], summary["minor"])
    body = f"""<div class="card"><div class="result-head"><h2 style="font-size:1.05rem;">Audit — {_esc(deck_name)}</h2>{pill}</div>
{stats}
<div class="note">Audit is read-only. <a href="/">Transform this deck</a> to fix these — patches, layout
rebuilds and archetype upgrades, each slide approved by you first.</div>
<div class="table-wrap"><table>
<thead><tr><th>Slide</th><th>Severity</th><th>Rule</th><th>Shape</th><th>Message</th><th>Fix?</th></tr></thead>
<tbody>{_violation_rows(violations)}</tbody>
</table></div>
<div style="height:1rem"></div>{dl}
</div>"""
    return body



def transform_card(ai_enabled: bool = True, error: str | None = None) -> str:
    """The home page's single tool: one form, three optional inputs --
    an old deck, a reference deck, a brief -- covering every starting
    point the four old tabs handled between them. Deck alone =
    fix/rebrand; deck + reference = the old Learn flow; brief alone =
    a new deck; deck + brief isn't a combination the engine supports
    yet, so the brief is ignored when a deck is present (said in the
    hint, not silently)."""
    error_html = f'<div class="error">{_esc(error)}</div><div style="height:1rem"></div>' if error else ""
    ai_hint = (
        "AI archetype suggestions are on (server has an API key) — each one still needs your approval."
        if ai_enabled else
        "No <code>ANTHROPIC_API_KEY</code> configured — deck transforms stay fully deterministic "
        "(no archetype suggestions), and a brief-only new deck is unavailable."
    )
    return f"""{error_html}<div class="card tool-card">
<form method="post" action="/plan" enctype="multipart/form-data">
  <div class="field">
    <label class="field-label">Deck to transform (.pptx)</label>
    <input type="file" name="file" accept=".pptx">
    <p class="field-hint">Leave empty to build a new deck from the brief below instead.</p>
  </div>
  <div class="field">
    <label class="field-label">Reference deck (optional, already on-brand)</label>
    <input type="file" name="reference" accept=".pptx">
    <p class="field-hint">Slides sharing a layout with it keep that exact layout (chrome refreshed from the
      reference), and the final audit includes a similarity report against it.</p>
  </div>
  <div class="field">
    <label class="field-label">Brief (for a new deck, when no file is uploaded)</label>
    <textarea name="brief" rows="2" placeholder="e.g. a Marketing Hub Q2 review: volume up ~2x, 91% resolution, 2025–2027 roadmap"
      style="width:100%;font-size:0.85rem;padding:0.6rem;"></textarea>
  </div>
  <p class="field-hint" style="margin:0 0 1.1rem;">{ai_hint}</p>
  <div class="btn-row">
    <button type="submit" class="primary">Plan transform</button>
    <button type="submit" class="secondary" formaction="/audit">Audit only</button>
  </div>
</form>
</div>"""


_ACTION_LABELS = {
    "keep": "Keep (structure untouched; brand patches still apply)",
    "rebuild": "Rebuild on layout",
    "reference_layout": "Keep layout, refresh chrome from reference",
    "archetype": "Use archetype",
}


def _review_card(entry: dict) -> str:
    """One slide's review card: current preview | proposed preview,
    plus the action radios. `entry` carries pre-rendered preview HTML
    (built by the route, which has file access) and the plan fields."""
    idx = entry["index"]
    default = entry["default_action"]

    options = []
    if default == "keep" and not entry.get("archetype_name"):
        reason = entry.get("reason") or "not eligible for a rebuild"
        options.append(f'<p class="field-hint" style="margin:0;">Kept as-is: {_esc(reason)}.</p>')
        options.append(f'<input type="hidden" name="action_{idx}" value="keep">')
    elif default == "keep":
        # Too big for any org-template layout, but an archetype CAN hold
        # it -- offer that rather than writing the slide off.
        reason = entry.get("reason") or "no org-template layout fits this slide"
        options.append(
            f'<p class="field-hint" style="margin:0 0 0.5rem;">No org-template layout fits this slide '
            f"({_esc(reason)}) — but an archetype does:</p>"
        )
        options.append(
            f'<label class="checkbox-row" style="margin-bottom:0.35rem;">'
            f'<input type="radio" name="action_{idx}" value="archetype">'
            f"<span>{_ACTION_LABELS['archetype']} <b>{_esc(entry['archetype_name'])}</b></span></label>"
        )
        options.append(
            f'<label class="checkbox-row" style="margin-bottom:0.35rem;">'
            f'<input type="radio" name="action_{idx}" value="keep" checked>'
            f"<span>{_ACTION_LABELS['keep']}</span></label>"
        )
    else:
        def radio(value: str, label: str) -> str:
            checked = " checked" if value == default else ""
            return (
                f'<label class="checkbox-row" style="margin-bottom:0.35rem;">'
                f'<input type="radio" name="action_{idx}" value="{value}"{checked}>'
                f"<span>{label}</span></label>"
            )
        if entry.get("archetype_name"):
            options.append(radio("archetype", f"{_ACTION_LABELS['archetype']} <b>{_esc(entry['archetype_name'])}</b>"))
        if default == "reference_layout":
            options.append(radio("rebuild", _ACTION_LABELS["reference_layout"]))
        elif entry.get("layout_name"):
            options.append(radio("rebuild", f"{_ACTION_LABELS['rebuild']} <b>{_esc(entry['layout_name'])}</b>"))
        options.append(radio("keep", _ACTION_LABELS["keep"]))

    current = entry.get("current_html") or ""
    proposed = entry.get("proposed_html") or ""
    cols = ""
    if current and proposed:
        cols = f"""<div class="review-cols">
  <div><p class="prev-label">Current</p>{current}</div>
  <div><p class="prev-label">Proposed</p>{proposed}</div>
</div>"""
    elif proposed:
        cols = f'<div><p class="prev-label">Proposed</p>{proposed}</div>'
    elif current:
        cols = f'<div><p class="prev-label">Current</p>{current}</div>'

    return f"""<div class="card">
<h3 style="font-size:0.92rem;">Slide {idx}{': ' + _esc(entry.get('title_preview') or '') if entry.get('title_preview') else ''}</h3>
{cols}
<div style="margin-top:0.9rem;">{''.join(options)}</div>
</div>"""


def transform_review_page(deck_name: str, token: str, entries: list[dict], mode: str, ai_ran: bool) -> str:
    """The human decision point: one card per slide, then one Transform
    button. `mode` is "deck" or "brief" (brief cards are include/skip
    checkboxes rather than action radios -- handled by the entries'
    default "new" action rendering as a checkbox here)."""
    if mode == "brief":
        cards = []
        for e in entries:
            idx = e["index"]
            cards.append(f"""<div class="card">
<h3 style="font-size:0.92rem;">Slide {idx}: {_esc(e.get('archetype_name') or '')}</h3>
<div><p class="prev-label">Proposed</p>{e.get('proposed_html') or ''}</div>
<label class="checkbox-row" style="margin-top:0.9rem;">
  <input type="checkbox" name="include_{idx}" value="1" checked>
  <span>Include this slide</span>
</label>
</div>""")
        cards_html = "".join(cards)
        intro = "The planned deck, slide by slide — untick anything you don't want, then build."
    else:
        cards_html = "".join(_review_card(e) for e in entries)
        ai_note = "" if ai_ran else (
            '<p class="field-hint" style="margin:0.4rem 0 0;">Archetype suggestions were unavailable for this '
            "plan (no API key or the call failed) — every proposal below is deterministic.</p>"
        )
        intro = f"Approve or override each slide, then transform. Nothing executes until you do.{ai_note}"

    return f"""<div class="card"><div class="result-head"><h2 style="font-size:1.05rem;">Review plan — {_esc(deck_name)}</h2></div>
<p class="muted" style="margin:0;">{intro}</p>
</div>
<form method="post" action="/transform/{_esc(token)}">
{cards_html}
<div class="card" style="text-align:center;">
  <button type="submit" class="primary">Transform deck</button>
  <a class="dl secondary" href="/" style="margin-left:0.6rem;">Start over</a>
</div>
</form>"""


def transform_result_page(
    deck_name: str, outcome: dict, audit: dict, similarity: dict | None, download_links: dict,
) -> str:
    summary = audit["summary"]
    pill = _status_pill(summary["critical"], summary["major"], summary["minor"])
    stats = f"""<div class="stat-row">
  <div class="stat"><b style="color:#1ED273">{len(outcome['rebuilt'])}</b><span>rebuilt</span></div>
  <div class="stat"><b>{len(outcome['archetype_swapped'])}</b><span>archetypes</span></div>
  <div class="stat"><b>{len(outcome['reference_carryover'])}</b><span>ref layouts</span></div>
  <div class="stat"><b>{len(outcome['kept'])}</b><span>kept</span></div>
</div>"""
    dl = (
        f'<a class="dl" href="{download_links["pptx"]}">Download transformed .pptx</a>'
        f'<a class="dl secondary" href="{download_links["json"]}">JSON report</a>'
        f'<a class="dl secondary" href="/">Transform another deck</a>'
    )
    learned = outcome.get("learned_colors", 0) + outcome.get("learned_fonts", 0)
    transplanted = outcome.get("transplanted_shapes", 0)
    deduped = outcome.get("duplicate_logos_removed", 0)
    reference_note = ""
    if learned or transplanted or deduped:
        bits = []
        if learned:
            bits.append(f"{learned} color/font rule(s) learned from your reference deck")
        if transplanted:
            bits.append(f"{transplanted} shape style(s) copied straight off it")
        if deduped:
            bits.append(f"{deduped} duplicate logo(s) removed in favour of the reference's own mark")
        reference_note = (
            f'<p class="field-hint" style="margin:0.5rem 0 0;">Driven by your uploaded reference: '
            f'{"; ".join(bits)}.</p>'
        )

    # Slides the reference deck redrew from scratch. Restyling can't
    # reach them, so say so plainly rather than shipping a worse slide
    # and letting the user discover the gap in the meeting.
    redraw = outcome.get("needs_manual_redraw") or []
    redraw_note = ""
    if redraw:
        nums = ", ".join(str(i) for i in redraw)
        redraw_note = (
            f'<div class="notice"><b>Slide{"s" if len(redraw) > 1 else ""} {nums} need a manual redraw</b>'
            "Branding was applied, but the reference deck builds these slides out of different shapes "
            "(grouped diagrams, different connectors) rather than restyled versions of yours — too little "
            "lines up for deckguard to copy its treatment across. "
            "<p>Rebuild them by hand against the reference, or pick an archetype for them on the review "
            "screen and let the generator draw them fresh.</p></div>"
        )

    suppressed = audit.get("suppressed_archetype_findings", 0)
    suppressed_note = (
        f'<p class="field-hint" style="margin:0.5rem 0 0;">{suppressed} finding(s) on archetype-rendered slides '
        "excluded — those slides are brand-compliant by construction; the generic rules false-positive on their "
        "deliberate styling.</p>"
        if suppressed else ""
    )

    similarity_card = ""
    if similarity is not None:
        colors = similarity["colors_not_in_reference"]
        fonts = similarity["fonts_not_in_reference"]
        color_bits = " ".join(
            f'<span class="swatch" style="background:#{_esc(c)}"></span><code>#{_esc(c)}</code>' for c in colors[:8]
        ) or '<span class="muted">none — every color also appears in the reference</span>'
        font_bits = ", ".join(_esc(f) for f in fonts[:8]) or "none — every font also appears in the reference"
        similarity_card = f"""<div class="card"><h3 style="font-size:0.95rem;">Vs. reference deck</h3>
<div class="stat-row">
  <div class="stat"><b>{similarity['layout_matches']}/{similarity['slides_compared']}</b><span>layouts match</span></div>
  <div class="stat"><b>{len(colors)}</b><span>extra colors</span></div>
  <div class="stat"><b>{len(fonts)}</b><span>extra fonts</span></div>
</div>
<p class="muted" style="margin:0 0 0.4rem;">Colors used here but never in the reference: {color_bits}</p>
<p class="muted" style="margin:0;">Fonts used here but never in the reference: {font_bits}</p>
</div>"""

    violations = [
        v if isinstance(v, dict) else {
            "slide_index": v.slide_index, "severity": v.severity, "rule": v.rule,
            "shape_name": v.shape_name, "message": v.message, "auto_fixable": v.auto_fixable,
        }
        for v in audit["violations"]
    ]
    return f"""<div class="card"><div class="result-head"><h2 style="font-size:1.05rem;">Transformed — {_esc(deck_name)}</h2>{pill}</div>
{stats}
{reference_note}
{dl}
</div>
{redraw_note}
{similarity_card}
<div class="card"><h3 style="font-size:0.95rem;">Remaining findings ({len(violations)})</h3>
{suppressed_note}
<div class="table-wrap"><table>
<thead><tr><th>Slide</th><th>Severity</th><th>Rule</th><th>Shape</th><th>Message</th><th>Fix?</th></tr></thead>
<tbody>{_violation_rows(violations)}</tbody>
</table></div></div>"""
