"""HTML rendering for the web app. Plain f-strings, no template engine —
keeps the web extra's dependency footprint to just FastAPI/uvicorn.
"""

from __future__ import annotations

import html

SEVERITY_COLOR = {"critical": "#FF5F28", "major": "#FFA023", "minor": "#8C8C8C"}

BASE_CSS = """
  :root {
    --bg: #FBF9F5; --surface: #FFFFFF; --surface-sunken: #F3EEE6;
    --ink: #141414; --ink-muted: #5B5B5B; --ink-faint: #8C8C8C;
    --border: #E2DDD3; --accent: #1450F5; --accent-soft: #D0DCFD; --accent-softer: #EEF2FE;
    --ok: #1ED273; --ok-soft: #E4FAEE; --danger: #FF5F28; --danger-soft: #FFEEE7;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #131211; --surface: #1B1A18; --surface-sunken: #221F1B;
      --ink: #F3EEE6; --ink-muted: #B8B2A6; --ink-faint: #8A8478;
      --border: #322E27; --accent: #6D93FF; --accent-soft: #23335C; --accent-softer: #1B2440;
      --ok: #4BE39A; --ok-soft: #12301F; --danger: #FF8259; --danger-soft: #3A1D12;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  .wrap { max-width: 880px; margin: 0 auto; padding: 2.5rem 1.5rem 5rem; }
  header { display: flex; align-items: baseline; gap: 0.75rem; margin-bottom: 0.4rem; }
  header h1 { font-size: 1.5rem; margin: 0; letter-spacing: -0.01em; }
  header .tag {
    font-family: ui-monospace, "SF Mono", Consolas, monospace; font-size: 0.72rem;
    color: var(--accent); background: var(--accent-softer); padding: 0.15rem 0.55rem; border-radius: 999px;
  }
  p.lede { color: var(--ink-muted); margin: 0 0 2rem; font-size: 0.95rem; }
  .card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    padding: 1.5rem; margin-bottom: 1.5rem;
  }
  .drop {
    border: 2px dashed var(--border); border-radius: 12px; padding: 2.5rem 1.5rem;
    text-align: center; background: var(--surface);
  }
  .drop p { margin: 0 0 1rem; color: var(--ink-muted); }
  input[type="file"] { margin-bottom: 1rem; }
  .btn-row { display: flex; gap: 0.75rem; justify-content: center; flex-wrap: wrap; }
  button {
    font: inherit; font-weight: 600; font-size: 0.9rem;
    padding: 0.6rem 1.3rem; border-radius: 8px; border: 1px solid transparent;
    cursor: pointer;
  }
  button.primary { background: var(--accent); color: white; }
  button.secondary { background: var(--surface); color: var(--ink); border-color: var(--border); }
  a.dl {
    display: inline-block; background: var(--accent); color: white; text-decoration: none;
    font-weight: 600; font-size: 0.85rem; padding: 0.5rem 1rem; border-radius: 8px; margin: 0.2rem 0.4rem 0.2rem 0;
  }
  a.dl.secondary { background: var(--surface); color: var(--ink); border: 1px solid var(--border); }
  .stat-row { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
  .stat {
    flex: 1; min-width: 110px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 0.85rem 1rem;
  }
  .stat b { display: block; font-size: 1.4rem; font-variant-numeric: tabular-nums; }
  .stat span { font-size: 0.72rem; color: var(--ink-faint); text-transform: uppercase; letter-spacing: 0.04em; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th, td { text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--border); vertical-align: top; }
  th { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-faint); }
  .sev { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 0.4rem; }
  .table-wrap { overflow-x: auto; }
  code { font-family: ui-monospace, "SF Mono", Consolas, monospace; font-size: 0.85em; background: var(--surface-sunken); padding: 0.1em 0.35em; border-radius: 4px; }
  .error { background: var(--danger-soft); color: var(--danger); border-radius: 10px; padding: 1rem 1.2rem; font-size: 0.9rem; }
  .empty { color: var(--ink-faint); font-size: 0.88rem; padding: 0.5rem 0; }
  footer { color: var(--ink-faint); font-size: 0.78rem; margin-top: 2.5rem; }
  footer code { background: none; padding: 0; }
"""


def _esc(v) -> str:
    return html.escape(str(v)) if v is not None else ""


def page_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>{BASE_CSS}</style>
</head><body><div class="wrap">
<header><h1>deckguard</h1><span class="tag">KONE brand compliance</span></header>
<p class="lede">Upload a .pptx to audit it against brand_rules.yaml, or fix it automatically.</p>
{body}
<footer>Deterministic engine only — colors, fonts, effects, alignment. No content is sent to any AI model.</footer>
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
</div>
<div class="card">
<h2 style="margin-top:0;font-size:1.05rem;">Make an old deck look like a reference deck</h2>
<p style="color:var(--ink-muted);font-size:0.88rem;margin:0 0 1rem;">
  Upload a deck that isn't on-brand yet, plus a deck that already is. Colors
  and fonts that changed between them are proposed as new brand rules
  (high-confidence ones applied automatically); the old deck's own text is
  never touched, only its styling.
</p>
<form method="post" action="/learn" enctype="multipart/form-data">
  <label style="display:block;font-size:0.82rem;color:var(--ink-muted);margin-bottom:0.3rem;">Old deck (to be fixed)</label>
  <input type="file" name="old_file" accept=".pptx" required style="margin-bottom:1rem;">
  <label style="display:block;font-size:0.82rem;color:var(--ink-muted);margin-bottom:0.3rem;">Reference deck (already on-brand)</label>
  <input type="file" name="new_file" accept=".pptx" required style="margin-bottom:1rem;">
  <button type="submit" class="primary">Learn &amp; transform</button>
</form>
</div>"""


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


def fix_result_page(deck_name: str, fix_summary: dict, changes: list[dict], manual_review: list[dict], download_links: dict) -> str:
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
    body = f"""<div class="card"><h2 style="margin-top:0;font-size:1.05rem;">Fixed — {_esc(deck_name)}</h2>
{stats}
{dl}
</div>
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
