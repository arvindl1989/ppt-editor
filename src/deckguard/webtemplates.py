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
  :root {
    --bg: #FFFFFF; --surface: #FFFFFF; --surface-sunken: #F3EEE6;
    --ink: #141414; --ink-muted: #727272; --ink-faint: #A1A1A1;
    --border: #E6E6E6; --border-strong: #D0D0D0;
    --accent: #1450F5; --accent-hover: #4373F7; --accent-soft: #D0DCFD; --accent-softer: #EEF2FE;
    --ok: #1ED273; --ok-soft: #E4FAEE; --danger: #FF5F28; --danger-soft: #FFEEE7; --warn: #FFA023;
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
      --ok: #4BE39A; --ok-soft: #12301F; --danger: #FF8259; --danger-soft: #3A1D12; --warn: #FFB84D;
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
  .wrap { max-width: 920px; margin: 0 auto; padding: 0 1.5rem 5rem; }
  .topbar {
    display: flex; align-items: center; justify-content: space-between; gap: 1rem;
    padding: 1.4rem 0; border-bottom: 1px solid var(--border); margin-bottom: 0.3rem;
  }
  .brand { display: flex; align-items: center; gap: 0.7rem; }
  .brand svg { width: 30px; height: auto; flex: none; }
  .brand h1 { font-size: 1.15rem; font-weight: 600; margin: 0; letter-spacing: -0.01em; }
  .tag {
    font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--accent); background: var(--accent-softer); padding: 0.25rem 0.6rem; border-radius: 999px;
  }
  nav.jump { display: flex; gap: 1.25rem; flex-wrap: wrap; font-size: 0.82rem; }
  nav.jump a { color: var(--ink-muted); font-weight: 500; }
  nav.jump a:hover { color: var(--accent); text-decoration: none; }
  p.lede { color: var(--ink-muted); margin: 1.3rem 0 2rem; font-size: 0.95rem; max-width: 62ch; }
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
  .card h2, .card h3 { font-weight: 600; }
  .drop {
    border: 1.5px dashed var(--border-strong); border-radius: 10px; padding: 2.25rem 1.5rem;
    text-align: center; background: var(--surface-sunken);
  }
  .drop p { margin: 0 0 1rem; color: var(--ink-muted); }
  input[type="file"] { margin-bottom: 1rem; font-size: 0.85rem; }
  .btn-row { display: flex; gap: 0.75rem; justify-content: center; flex-wrap: wrap; }
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
  th { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; color: var(--ink-faint); }
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
    nav = (
        '<nav class="jump">'
        '<a href="#fix">Fix &amp; audit</a>'
        '<a href="#learn">Learn from reference</a>'
        '<a href="#create">Create new</a>'
        '<a href="#redesign">AI redesign</a>'
        "</nav>"
        if home else
        '<a href="/" style="font-size:0.85rem;font-weight:600;">&larr; deckguard</a>'
    )
    lede = (
        '<p class="lede">Every tool below is fully working. Fix or audit an existing deck, '
        "learn new brand rules from a reference pair, compose a new deck from an outline straight "
        "onto approved layouts, or let Claude redesign one end to end.</p>"
        if home else ""
    )
    return f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>{BASE_CSS}</style>
</head><body><div class="wrap">
<div class="topbar">
  <div class="brand">{KONE_LOGO_SVG}<h1>deckguard</h1><span class="tag">Brand Compliance</span></div>
  {nav}
</div>
{lede}
{body}
<footer>Deterministic engine by default — colors, fonts, effects, alignment, layout. No content is sent to
any AI model unless you explicitly use AI redesign, which needs its own API key set by the operator.</footer>
</div></body></html>"""


def upload_form(error: str | None = None) -> str:
    error_html = f'<div class="error">{_esc(error)}</div><div style="height:1rem"></div>' if error else ""
    return f"""{error_html}<div class="card">
<form class="drop" method="post" action="/fix" enctype="multipart/form-data" id="uploadForm">
  <p>Choose a .pptx deck (max 50&nbsp;MB)</p>
  <input type="file" name="file" accept=".pptx" required>
  <div class="btn-row">
    <button type="submit" class="primary" formaction="/fix">Fix deck</button>
    <button type="submit" class="secondary" formaction="/audit">Audit only</button>
  </div>
</form>
</div>"""


def learn_form(error: str | None = None) -> str:
    error_html = f'<div class="error">{_esc(error)}</div><div style="height:1rem"></div>' if error else ""
    return f"""{error_html}<div class="card">
<form method="post" action="/learn" enctype="multipart/form-data">
  <label class="field-label">Old deck (to be fixed)</label>
  <input type="file" name="old_file" accept=".pptx" required style="margin-bottom:1rem;">
  <label class="field-label">Reference deck (already on-brand)</label>
  <input type="file" name="new_file" accept=".pptx" required style="margin-bottom:1rem;">
  <button type="submit" class="primary">Learn &amp; transform</button>
</form>
</div>"""


SAMPLE_OUTLINE = """slides:
  - kind: cover
    title: "Deck title"
    subtitle: "Subtitle line"

  - kind: agenda
    title: "Agenda"
    bullets: ["First topic", "Second topic", "Third topic"]

  - kind: content
    title: "Three priorities"
    columns:
      - ["Reliability", {level: 1, text: "Supporting detail"}]
      - ["Speed"]
      - ["Simplicity"]

  - kind: quote
    title: "Customer voice"
    quote_text: "A short, punchy quote goes here."
    quote_author: "Attribution"

  - kind: end
    title: "Thank you"
"""


def compose_form(error: str | None = None) -> str:
    error_html = f'<div class="error">{_esc(error)}</div><div style="height:1rem"></div>' if error else ""
    return f"""{error_html}<div class="card">
<h2 style="margin-top:0;font-size:1.05rem;">Compose a new deck</h2>
<p style="color:var(--ink-muted);font-size:0.88rem;margin:0 0 1rem;">
  Describe your slides as a YAML outline; every slide is built directly on
  one of the org template's own approved layouts, so there's nothing to fix
  afterward. See the README for the full outline schema (slide kinds: cover,
  agenda, section, content, quote, statement, stat, timeline, end, blank).
</p>
<form method="post" action="/create">
  <textarea name="outline" rows="16" style="width:100%;font-family:ui-monospace,'SF Mono',Consolas,monospace;
    font-size:0.85rem;padding:0.75rem;border-radius:8px;border:1px solid var(--border);
    background:var(--surface);color:var(--ink);" required>{_esc(SAMPLE_OUTLINE)}</textarea>
  <div style="height:0.75rem"></div>
  <label style="display:block;font-size:0.82rem;color:var(--ink-muted);margin-bottom:0.3rem;">
    Optional: append these slides to an existing deck instead of starting a new one
  </label>
  <input type="file" name="existing_file" accept=".pptx" style="margin-bottom:1rem;">
  <div class="btn-row">
    <button type="submit" class="primary">Compose deck</button>
  </div>
</form>
</div>"""


def compose_result_page(out_name: str, result_dict: dict, download_links: dict) -> str:
    stats = f"""<div class="stat-row">
  <div class="stat"><b style="color:#1ED273">{result_dict['slide_count']}</b><span>slides built</span></div>
  <div class="stat"><b>{len(result_dict['manual_review'])}</b><span>need review</span></div>
</div>"""
    dl = (
        f'<a class="dl" href="{download_links["pptx"]}">Download composed .pptx</a>'
        f'<a class="dl secondary" href="/">Compose another deck</a>'
    )
    layouts_used = ", ".join(sorted(set(result_dict["layouts_used"])))
    body = f"""<div class="card"><h2 style="margin-top:0;font-size:1.05rem;">Composed — {_esc(out_name)}</h2>
{stats}
<p class="muted" style="margin:0.5rem 0 1rem;">Layouts used: {_esc(layouts_used)}</p>
{dl}
</div>
<div class="card"><h3 style="margin-top:0;font-size:0.95rem;">Manual review ({len(result_dict['manual_review'])})</h3>
<div class="table-wrap"><table>
<thead><tr><th>Slide</th><th>Severity</th><th>Rule</th><th>Shape</th><th>Message</th><th>Fix?</th></tr></thead>
<tbody>{_violation_rows(result_dict['manual_review'])}</tbody>
</table></div></div>"""
    return body


def redesign_form(error: str | None = None, ai_enabled: bool = True) -> str:
    error_html = f'<div class="error">{_esc(error)}</div><div style="height:1rem"></div>' if error else ""
    mode_options = (
        '<option value="rewrite" selected>AI rewrite — Claude picks each slide\'s layout and lays out its '
        "existing wording verbatim, splitting dense slides across several if needed</option>"
        '<option value="brand">Brand only — deterministic, no API call, wording and images kept exactly as written</option>'
    ) if ai_enabled else (
        '<option value="brand" selected>Brand only — deterministic, no API call, wording and images kept exactly as written</option>'
    )
    ai_note = "" if ai_enabled else (
        '<p class="muted" style="margin:0 0 1rem;">AI rewrite mode isn\'t enabled on this server — set '
        '<code>ANTHROPIC_API_KEY</code> to turn it on. Brand mode below needs no key: it never touches your '
        "wording, it just carries the deck's own text and images onto approved, on-brand layouts.</p>"
    )
    review_row = (
        """<label class="checkbox-row">
    <input type="checkbox" name="review" value="1">
    <span><strong>AI review</strong> (brand only, needs an API key) — one small extra call that rebuilds any
    slide reading as a divider/transition page onto the org template's Section Divider layout, and flags
    (never auto-fixes) leftover placeholder text or an odd confidentiality notice.</span>
  </label>"""
        if ai_enabled else ""
    )
    return f"""{error_html}<div class="card">
<h2 style="margin-top:0;font-size:1.05rem;">Redesign a deck</h2>
<p style="color:var(--ink-muted);font-size:0.88rem;margin:0 0 1rem;">
  Two modes, and neither one ever rewords your existing content. <strong>AI rewrite</strong> works from any
  starting point (an existing deck, a brief to fill its blank slides, or a brief alone with no deck at all) —
  for a slide that already has real content, Claude only decides which layout fits it and, if it doesn't fit
  on one slide, how to split its wording verbatim across several; a blank slide or a bare brief is the one
  case it authors real content, grounded in what you tell it. <strong>Brand only</strong> needs an existing
  deck and is fully deterministic — it carries the deck's own text and images onto approved layouts (picked
  for visual variety, with the cover/closing slide swapped to the current brand look) and leaves everything
  else exactly as written. Both modes run the same deterministic engine <code>create</code> uses for
  color/font/layout compliance. A slide with a table, chart, or embedded media is always left alone and
  reported, never guessed at, in either mode.
</p>
{ai_note}<form method="post" action="/redesign" enctype="multipart/form-data">
  <label style="display:block;font-size:0.82rem;color:var(--ink-muted);margin-bottom:0.3rem;">
    Existing deck (required for Brand only; optional for AI rewrite — omit to build a new deck from just the brief below)
  </label>
  <input type="file" name="file" accept=".pptx" style="margin-bottom:1rem;">
  <label style="display:block;font-size:0.82rem;color:var(--ink-muted);margin-bottom:0.3rem;">Mode</label>
  <select name="mode" style="display:block;margin-bottom:1rem;">{mode_options}</select>
  {review_row}
  <label style="display:block;font-size:0.82rem;color:var(--ink-muted);margin-bottom:0.3rem;">
    Brief (AI rewrite only — required if no deck is uploaded; also authors any blank slides in an uploaded deck)
  </label>
  <textarea name="brief" rows="2" placeholder="e.g. a short deck on predictive maintenance for facilities managers"
    style="width:100%;font-size:0.85rem;padding:0.6rem;border-radius:8px;border:1px solid var(--border);
    background:var(--surface);color:var(--ink);margin-bottom:1rem;"></textarea>
  <label style="display:block;font-size:0.82rem;color:var(--ink-muted);margin-bottom:0.3rem;">
    Optional steering notes for the model (AI rewrite only)
  </label>
  <textarea name="notes" rows="2" placeholder="e.g. prefer stat slides for anything with a percentage"
    style="width:100%;font-size:0.85rem;padding:0.6rem;border-radius:8px;border:1px solid var(--border);
    background:var(--surface);color:var(--ink);margin-bottom:1rem;"></textarea>
  <div style="display:flex;gap:1rem;margin-bottom:1rem;flex-wrap:wrap;">
    <label style="font-size:0.82rem;color:var(--ink-muted);">Model (AI rewrite only)
      <select name="model" style="display:block;margin-top:0.3rem;">
        <option value="claude-opus-5" selected>claude-opus-5 (recommended)</option>
        <option value="claude-sonnet-5">claude-sonnet-5 (cheaper)</option>
      </select>
    </label>
    <label style="font-size:0.82rem;color:var(--ink-muted);">Effort (AI rewrite only)
      <select name="effort" style="display:block;margin-top:0.3rem;">
        <option value="low">low</option>
        <option value="medium">medium</option>
        <option value="high" selected>high</option>
        <option value="xhigh">xhigh</option>
      </select>
    </label>
    <label style="font-size:0.82rem;color:var(--ink-muted);">Target slide count (AI rewrite only)
      <input type="number" name="slides" min="1" max="60" style="display:block;margin-top:0.3rem;width:6rem;">
    </label>
  </div>
  <div class="btn-row">
    <button type="submit" class="primary">Redesign</button>
  </div>
</form>
</div>"""


def redesign_result_page(deck_name: str, redesign_dict: dict, compose_dict: dict, download_links: dict) -> str:
    usage = redesign_dict["usage"]
    stats = f"""<div class="stat-row">
  <div class="stat"><b style="color:#1ED273">{compose_dict['slide_count']}</b><span>slides built</span></div>
  <div class="stat"><b>{len(redesign_dict['skipped'])}</b><span>skipped</span></div>
  <div class="stat"><b>{len(compose_dict['manual_review'])}</b><span>need review</span></div>
  <div class="stat"><b>${usage['estimated_cost_usd']:.3f}</b><span>est. cost</span></div>
</div>"""
    dl = (
        f'<a class="dl" href="{download_links["pptx"]}">Download redesigned .pptx</a>'
        f'<a class="dl secondary" href="/">Redesign another deck</a>'
    )
    layouts_used = ", ".join(sorted(set(compose_dict["layouts_used"])))
    usage_line = (
        "brand mode — fully deterministic, no API call made" if usage["model"] == "none" else
        f"{_esc(usage['input_tokens'])} in / {_esc(usage['output_tokens'])} out tokens ({_esc(usage['model'])})"
    )
    skipped_rows = "".join(
        f"<tr><td>{_esc(s['slide_index'])}</td><td>{_esc(s['reason'])}</td></tr>" for s in redesign_dict["skipped"]
    ) or '<tr><td colspan="2" class="empty">Every slide was eligible.</td></tr>'
    skipped_note = (
        "Left untouched — carry a table, chart, embedded media, or too much text to migrate verbatim."
        if usage["model"] == "none" else
        "Never sent to the model — carry a table, chart, embedded media, or too much content to redesign safely."
    )
    review_notes = redesign_dict.get("review_notes") or []
    review_section = ""
    if review_notes:
        items = "".join(f"<li>{_esc(n)}</li>" for n in review_notes)
        review_section = f"""<div class="card"><h3 style="margin-top:0;font-size:0.95rem;">--review findings ({len(review_notes)})</h3>
<p class="muted" style="margin:0 0 0.5rem;">Flagged for a human to look at — nothing here was auto-fixed beyond divider/transition slides.</p>
<ul style="margin:0;padding-left:1.2rem;font-size:0.88rem;">{items}</ul>
</div>"""
    body = f"""<div class="card"><h2 style="margin-top:0;font-size:1.05rem;">Redesigned — {_esc(deck_name)}</h2>
{stats}
<p class="muted" style="margin:0.5rem 0 1rem;">Layouts used: {_esc(layouts_used)} &middot; {usage_line}</p>
{dl}
</div>
{review_section}
<div class="card"><h3 style="margin-top:0;font-size:0.95rem;">Skipped slides ({len(redesign_dict['skipped'])})</h3>
<p class="muted" style="margin:0 0 0.5rem;">{skipped_note}</p>
<div class="table-wrap"><table>
<thead><tr><th>Slide</th><th>Reason</th></tr></thead>
<tbody>{skipped_rows}</tbody>
</table></div></div>
<div class="card"><h3 style="margin-top:0;font-size:0.95rem;">Manual review ({len(compose_dict['manual_review'])})</h3>
<div class="table-wrap"><table>
<thead><tr><th>Slide</th><th>Severity</th><th>Rule</th><th>Shape</th><th>Message</th><th>Fix?</th></tr></thead>
<tbody>{_violation_rows(compose_dict['manual_review'])}</tbody>
</table></div></div>"""
    return body


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
    body = f"""<div class="card"><h2 style="margin-top:0;font-size:1.05rem;">Audit — {_esc(deck_name)}</h2>
{stats}
<div class="table-wrap"><table>
<thead><tr><th>Slide</th><th>Severity</th><th>Rule</th><th>Shape</th><th>Message</th><th>Fix?</th></tr></thead>
<tbody>{_violation_rows(violations)}</tbody>
</table></div>
<div style="height:1rem"></div>{dl}
</div>"""
    return body


def _change_rows(changes: list[dict]) -> str:
    if not changes:
        return '<tr><td colspan="5" class="empty">No changes applied.</td></tr>'
    rows = []
    for c in changes[:500]:
        rows.append(
            f"<tr><td>{_esc(c['scope'])}</td><td>{_esc(c.get('shape_name') or c.get('location') or '')}</td>"
            f"<td>{_esc(c['rule'])}</td><td>{_esc(c['old'])}</td><td>{_esc(c['new'])}</td></tr>"
        )
    truncated = ""
    if len(changes) > 500:
        truncated = f'<tr><td colspan="5" class="empty">…and {len(changes) - 500} more (see the JSON download for the full list)</td></tr>'
    return "".join(rows) + truncated


def _color_select(field_name: str, current_hex: str, approved_colors: list[str]) -> str:
    options = []
    seen = set()
    for hexval in approved_colors:
        norm = hexval.lstrip("#").upper()
        seen.add(norm)
        selected = " selected" if norm == current_hex else ""
        options.append(f'<option value="{_esc(norm)}"{selected}>#{_esc(norm)}</option>')
    if current_hex not in seen:
        options.insert(0, f'<option value="{_esc(current_hex)}" selected>#{_esc(current_hex)}</option>')
    swatch_id = f"swatch_{_esc(field_name)}"
    onchange = f"document.getElementById('{swatch_id}').style.background='#'+this.value"
    return (
        f'<span class="swatch" id="{swatch_id}" style="background:#{_esc(current_hex)}"></span>'
        f'<select name="{_esc(field_name)}" onchange="{onchange}">{"".join(options)}</select>'
    )


def _font_select(field_name: str, current_font: str, approved_fonts: list[str]) -> str:
    options = []
    seen = set()
    for font in approved_fonts:
        seen.add(font)
        selected = " selected" if font == current_font else ""
        options.append(f'<option value="{_esc(font)}"{selected}>{_esc(font)}</option>')
    if current_font not in seen:
        options.insert(0, f'<option value="{_esc(current_font)}" selected>{_esc(current_font)}</option>')
    return f'<select name="{_esc(field_name)}">{"".join(options)}</select>'


def remap_override_section(
    remap_summary: dict, approved_colors: list[str], approved_fonts: list[str], token: str
) -> str:
    colors = remap_summary.get("colors", [])
    fonts = remap_summary.get("fonts", [])
    if not colors and not fonts:
        return ""

    color_rows = ""
    if colors:
        rows = []
        for row in colors:
            old_hex, new_hex = row["old_hex"], row["new_hex"]
            rows.append(
                f"<tr><td><span class='swatch' style='background:#{_esc(old_hex)}'></span><code>#{_esc(old_hex)}</code></td>"
                f"<td>&rarr;</td>"
                f"<td>{_color_select(f'color_override__{old_hex}', new_hex, approved_colors)}</td>"
                f"<td>{_esc(row['count'])}</td></tr>"
            )
        color_rows = f"""<h4 style="margin:1.25rem 0 0.5rem;font-size:0.85rem;">Colors</h4>
<div class="table-wrap"><table>
<thead><tr><th>Original</th><th></th><th>Remapped to</th><th>Uses</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
</table></div>"""

    font_rows = ""
    if fonts:
        rows = []
        for row in fonts:
            old_font, new_font = row["old_font"], row["new_font"]
            rows.append(
                f"<tr><td>{_esc(old_font)}</td><td>&rarr;</td>"
                f"<td>{_font_select(f'font_override__{old_font}', new_font, approved_fonts)}</td>"
                f"<td>{_esc(row['count'])}</td></tr>"
            )
        font_rows = f"""<h4 style="margin:1.25rem 0 0.5rem;font-size:0.85rem;">Fonts</h4>
<div class="table-wrap"><table>
<thead><tr><th>Original</th><th></th><th>Remapped to</th><th>Uses</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
</table></div>"""

    return f"""<div class="card">
<h3 style="margin-top:0;font-size:0.95rem;">Review remapped colors &amp; fonts</h3>
<p class="muted" style="margin:0 0 0.5rem;">Every original color/font found in the deck, and what it was
remapped to. Pick a different target (constrained to the approved brand palette/fonts) and regenerate.</p>
<form method="post" action="/regenerate/{_esc(token)}">
{color_rows}
{font_rows}
<div style="height:1rem"></div>
<button type="submit" class="primary">Regenerate with these choices</button>
</form>
</div>"""


def fix_result_page(
    deck_name: str,
    fix_summary: dict,
    changes: list[dict],
    manual_review: list[dict],
    download_links: dict,
    migrate_note: str | None = None,
    remap_summary: dict | None = None,
    approved_colors: list[str] | None = None,
    approved_fonts: list[str] | None = None,
    token: str | None = None,
) -> str:
    stats = f"""<div class="stat-row">
  <div class="stat"><b style="color:#1ED273">{fix_summary['changes_applied']}</b><span>changes applied</span></div>
  <div class="stat"><b>{fix_summary['manual_review_required']}</b><span>need review</span></div>
  <div class="stat"><b style="color:#FF5F28">{fix_summary['manual_review_by_severity']['critical']}</b><span>critical left</span></div>
</div>"""
    dl = (
        f'<a class="dl" href="{download_links["pptx"]}">Download fixed .pptx</a>'
        f'<a class="dl secondary" href="{download_links["json"]}">JSON change log</a>'
        f'<a class="dl secondary" href="{download_links["md"]}">Markdown change log</a>'
        f'<a class="dl secondary" href="/">Fix another deck</a>'
    )
    note_html = (
        f'<p style="color:var(--ink-muted);font-size:0.85rem;margin-top:0.75rem;">{_esc(migrate_note)}</p>'
        if migrate_note else ""
    )
    override_section = ""
    if remap_summary is not None and token is not None:
        override_section = remap_override_section(
            remap_summary, approved_colors or [], approved_fonts or [], token
        )
    body = f"""<div class="card"><h2 style="margin-top:0;font-size:1.05rem;">Fixed — {_esc(deck_name)}</h2>
{stats}
{dl}
{note_html}
</div>
{override_section}
<div class="card"><h3 style="margin-top:0;font-size:0.95rem;">Changes applied</h3>
<div class="table-wrap"><table>
<thead><tr><th>Scope</th><th>Where</th><th>Rule</th><th>Old</th><th>New</th></tr></thead>
<tbody>{_change_rows(changes)}</tbody>
</table></div></div>
<div class="card"><h3 style="margin-top:0;font-size:0.95rem;">Manual review ({len(manual_review)})</h3>
<div class="table-wrap"><table>
<thead><tr><th>Slide</th><th>Severity</th><th>Rule</th><th>Shape</th><th>Message</th><th>Fix?</th></tr></thead>
<tbody>{_violation_rows(manual_review)}</tbody>
</table></div></div>"""
    return body


def _color_proposal_rows(proposals: list[dict]) -> str:
    if not proposals:
        return '<tr><td colspan="6" class="empty">No color differences found.</td></tr>'
    rows = []
    for p in proposals:
        conf_color = "#1ED273" if p["confidence"] == "high" else "#FFA023"
        rows.append(
            f"<tr><td><span class='sev' style='background:{conf_color}'></span>{_esc(p['confidence'])}</td>"
            f"<td>{_esc(p['role'])}</td>"
            f"<td><span style='display:inline-block;width:14px;height:14px;border-radius:4px;"
            f"background:#{_esc(p['old_hex'])};vertical-align:-2px;margin-right:0.3em;'></span><code>#{_esc(p['old_hex'])}</code></td>"
            f"<td><span style='display:inline-block;width:14px;height:14px;border-radius:4px;"
            f"background:#{_esc(p['new_hex'])};vertical-align:-2px;margin-right:0.3em;'></span><code>#{_esc(p['new_hex'])}</code></td>"
            f"<td>{_esc(p['old_count'])}</td><td>{_esc(p['new_count'])}</td></tr>"
        )
    return "".join(rows)


def _font_proposal_rows(proposals: list[dict]) -> str:
    if not proposals:
        return '<tr><td colspan="5" class="empty">No font differences found.</td></tr>'
    rows = []
    for p in proposals:
        conf_color = "#1ED273" if p["confidence"] == "high" else "#FFA023"
        old_label = p["old_font"] + (" (bold)" if p["old_bold"] else "")
        new_label = p["new_font"] + (" (bold)" if p["new_bold"] else "")
        rows.append(
            f"<tr><td><span class='sev' style='background:{conf_color}'></span>{_esc(p['confidence'])}</td>"
            f"<td>{_esc(old_label)}</td><td>{_esc(new_label)}</td>"
            f"<td>{_esc(p['old_count'])}</td><td>{_esc(p['new_count'])}</td></tr>"
        )
    return "".join(rows)


def _layout_panel_proposal_rows(proposals: list[dict]) -> str:
    if not proposals:
        return '<tr><td colspan="7" class="empty">No layout background-panel differences found.</td></tr>'
    rows = []
    for p in proposals:
        conf_color = "#1ED273" if p["confidence"] == "high" else "#FFA023"
        rows.append(
            f"<tr><td><span class='sev' style='background:{conf_color}'></span>{_esc(p['confidence'])}</td>"
            f"<td>{_esc(p['layout_name'])}</td>"
            f"<td>{_esc(p['old_shape_name'])}</td><td>{_esc(p['new_shape_name'])}</td>"
            f"<td><span style='display:inline-block;width:14px;height:14px;border-radius:4px;"
            f"background:#{_esc(p['old_hex'])};vertical-align:-2px;margin-right:0.3em;'></span><code>#{_esc(p['old_hex'])}</code></td>"
            f"<td><span style='display:inline-block;width:14px;height:14px;border-radius:4px;"
            f"background:#{_esc(p['new_hex'])};vertical-align:-2px;margin-right:0.3em;'></span><code>#{_esc(p['new_hex'])}</code></td>"
            f"<td>{_esc(p['area_sq_in'])}</td></tr>"
        )
    return "".join(rows)


def learn_result_page(
    old_name: str,
    new_name: str,
    result_dict: dict,
    fix_summary: dict,
    applied_count: int,
    download_links: dict,
) -> str:
    color_proposals = result_dict["color_proposals"]
    font_proposals = result_dict["font_proposals"]
    layout_panel_proposals = result_dict.get("layout_panel_proposals", [])
    all_proposals = color_proposals + font_proposals + layout_panel_proposals
    n_high = sum(1 for p in all_proposals if p["confidence"] == "high")
    n_low = sum(1 for p in all_proposals if p["confidence"] == "low")

    stats = f"""<div class="stat-row">
  <div class="stat"><b style="color:#1ED273">{n_high}</b><span>high-confidence</span></div>
  <div class="stat"><b style="color:#FFA023">{n_low}</b><span>low-confidence</span></div>
  <div class="stat"><b style="color:#1ED273">{fix_summary['changes_applied']}</b><span>changes applied</span></div>
  <div class="stat"><b>{fix_summary['manual_review_required']}</b><span>need review</span></div>
</div>"""

    dl = (
        f'<a class="dl" href="{download_links["pptx"]}">Download transformed .pptx</a>'
        f'<a class="dl secondary" href="{download_links["yaml"]}">Updated brand_rules.yaml</a>'
        f'<a class="dl secondary" href="{download_links["json"]}">Full proposal (JSON)</a>'
        f'<a class="dl secondary" href="/">Try another pair</a>'
    )

    low_note = ""
    if n_low:
        low_note = (
            f'<p style="color:var(--ink-muted);font-size:0.85rem;margin-top:0.75rem;">'
            f"{n_low} low-confidence difference(s) were <b>not</b> applied automatically — "
            f"review them below and re-run with the CLI's <code>--min-confidence low</code> if they're correct.</p>"
        )

    body = f"""<div class="card"><h2 style="margin-top:0;font-size:1.05rem;">Learned — {_esc(old_name)} → {_esc(new_name)}</h2>
{stats}
{dl}
{low_note}
</div>
<div class="card"><h3 style="margin-top:0;font-size:0.95rem;">Color differences</h3>
<div class="table-wrap"><table>
<thead><tr><th>Confidence</th><th>Role</th><th>Old</th><th>New</th><th>Old count</th><th>New count</th></tr></thead>
<tbody>{_color_proposal_rows(color_proposals)}</tbody>
</table></div></div>
<div class="card"><h3 style="margin-top:0;font-size:0.95rem;">Font differences</h3>
<div class="table-wrap"><table>
<thead><tr><th>Confidence</th><th>Old</th><th>New</th><th>Old count</th><th>New count</th></tr></thead>
<tbody>{_font_proposal_rows(font_proposals)}</tbody>
</table></div></div>
<div class="card"><h3 style="margin-top:0;font-size:0.95rem;">Layout background-panel differences</h3>
<p style="color:var(--ink-muted);font-size:0.85rem;margin-top:-0.25rem;">Large background panels defined on a slide layout rather than any slide — invisible to ordinary slide-level color remap.</p>
<div class="table-wrap"><table>
<thead><tr><th>Confidence</th><th>Layout</th><th>Old shape</th><th>New shape</th><th>Old</th><th>New</th><th>Area (in²)</th></tr></thead>
<tbody>{_layout_panel_proposal_rows(layout_panel_proposals)}</tbody>
</table></div></div>"""
    return body
