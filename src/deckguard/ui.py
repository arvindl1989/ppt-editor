"""The tool's own look, built from the brand it enforces.

Every colour and type size here is read from `brandmode`, not chosen.
That is deliberate: the interface is a live check on the tokens. If the
type scale is wrong, this page looks wrong too, and someone notices
before a deck does.

KONE is a square brand -- corner radius 0 everywhere, no shadows, no
gradients. Inter for everything except labels, which are KONE
Information in caps.
"""

from __future__ import annotations

import html

from deckguard import brandmode as bm


def esc(value) -> str:
    return html.escape(str(value)) if value is not None else ""


def _css() -> str:
    """The stylesheet, generated from the brand tokens."""
    t = bm.TYPE_SCALE
    return f"""
:root {{
  --blue: #{bm.BLUE};
  --black: #{bm.BLACK};
  --white: #{bm.WHITE};
  --sand: #{bm.SAND};
  --light-blue: #{bm.LIGHT_BLUE};
  --pink: #{bm.PINK};
  --hairline: #D8D8D8;
  --hairline-strong: #{bm.BLACK};
}}
* {{ box-sizing: border-box; border-radius: 0 !important; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{
  margin: 0; background: var(--white); color: var(--black);
  font-family: Inter, "Helvetica Neue", Arial, sans-serif;
  font-size: {t["body"][1]}px; line-height: {t["body"][3]};
  font-weight: 400;
}}
.label, .eyebrow, .footer-note {{
  font-family: "KONE Information", Inter, sans-serif;
  text-transform: uppercase; letter-spacing: .08em;
}}
.eyebrow {{ font-size: {t["eyebrow"][1]}px; color: var(--blue); }}
.label   {{ font-size: {t["label"][1]}px; color: var(--blue); letter-spacing: .06em; }}
.footer-note {{ font-size: {t["footer"][1]}px; letter-spacing: .05em; color: var(--black); }}

header.bar {{
  border-bottom: 1px solid var(--hairline); padding: 22px 45px;
  display: flex; align-items: baseline; gap: 18px;
}}
header.bar .mark {{
  background: var(--blue); color: #fff; font-weight: 600;
  padding: 3px 8px; letter-spacing: .12em; font-size: 13px;
}}
header.bar h1 {{ margin: 0; font-size: 19px; font-weight: 400; }}
header.bar .spacer {{ flex: 1; }}

main {{ max-width: 1320px; margin: 0 auto; padding: 34px 45px 90px; }}

h2.section {{
  font-size: {t["title"][1]}px; line-height: {t["title"][3]};
  letter-spacing: {t["title"][4]}em; font-weight: 400; margin: 0 0 6px;
}}
p.lede {{ font-size: 19px; line-height: 1.45; margin: 0 0 28px; max-width: 70ch; }}

.rule {{ height: 6px; background: var(--blue); width: 220px; margin: 0 0 26px; }}
.hair {{ height: 1px; background: var(--hairline); margin: 32px 0; }}

.field {{ margin-bottom: 22px; }}
.field > .label {{ display: block; margin-bottom: 7px; }}
textarea, input[type=text], input[type=number], select {{
  width: 100%; font-family: inherit; font-size: 16px; color: var(--black);
  background: var(--white); border: 1px solid var(--hairline);
  padding: 11px 12px;
}}
textarea:focus, input:focus, select:focus {{
  outline: none; border-color: var(--blue); box-shadow: inset 0 0 0 1px var(--blue);
}}
input[type=file] {{ font-size: 14px; }}
.hint {{ font-size: 14px; margin: 6px 0 0; }}

button, .btn {{
  font-family: inherit; font-size: 16px; font-weight: 400; cursor: pointer;
  padding: 12px 22px; border: 1px solid var(--blue); background: var(--blue);
  color: #fff; text-decoration: none; display: inline-block;
}}
button.ghost, .btn.ghost {{ background: var(--white); color: var(--black);
  border-color: var(--hairline); }}
button:disabled {{ opacity: .45; cursor: not-allowed; }}
.actions {{ display: flex; gap: 12px; align-items: center; margin-top: 8px; }}

.cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 34px; }}
@media (max-width: 900px) {{ .cols {{ grid-template-columns: 1fr; }} }}

.chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.chip {{ display: inline-flex; align-items: center; gap: 7px; cursor: pointer;
  border: 1px solid var(--hairline); padding: 7px 13px; font-size: 14px;
  user-select: none; }}
.chip input {{ accent-color: var(--blue); margin: 0; }}
.chip:has(input:checked) {{ border-color: var(--blue); background: var(--light-blue); }}
.chip:hover {{ border-color: var(--black); }}

.seg {{ display: flex; gap: 0; border: 1px solid var(--hairline); width: fit-content; }}
.seg label {{ padding: 9px 18px; cursor: pointer; font-size: 15px; }}
.seg input {{ position: absolute; opacity: 0; pointer-events: none; }}
.seg label:has(input:checked) {{ background: var(--blue); color: #fff; }}

.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(226px, 1fr)); gap: 18px; }}
.tile {{ display: block; cursor: pointer; position: relative; }}
/* The checkbox sits under the picture, not on it. Floated over the
   top-left corner it covered the very thing you are choosing between --
   on a real render that corner holds the eyebrow or the headline. */
.tile input {{ width: 16px; height: 16px; accent-color: var(--blue);
  margin: 0; flex: none; }}
.tile .frame {{ display: block; outline: 2px solid transparent; outline-offset: 2px; }}
.tile:hover .frame {{ outline-color: var(--hairline); }}
.tile:has(input:checked) .frame {{ outline-color: var(--blue); }}
.tile .name {{ display: flex; align-items: center; gap: 8px;
  margin-top: 9px; font-size: 14px; }}
.tile .from {{ display: block; font-size: 11px; color: var(--black); opacity: .65;
  text-transform: uppercase; letter-spacing: .05em; margin-top: 2px; padding-left: 24px; }}
.tile.off {{ opacity: .45; cursor: not-allowed; }}
.tile img.shot {{ display: block; width: 100%; height: auto; aspect-ratio: 1280/720;
  object-fit: cover; border: 1px solid var(--hairline); background: var(--white); }}
.tile .stub {{ display: flex; align-items: center; justify-content: center;
  aspect-ratio: 1280/720; border: 1px dashed var(--hairline); font-size: 12px;
  text-transform: uppercase; letter-spacing: .06em; }}

.slide-row {{ display: grid; grid-template-columns: 210px 1fr auto; gap: 20px;
  padding: 18px 0; border-top: 1px solid var(--hairline); align-items: start; }}
.slide-row .slot {{ margin-bottom: 10px; }}
.slide-row .slot label {{ display: block; font-size: 11px; text-transform: uppercase;
  letter-spacing: .05em; margin-bottom: 3px; opacity: .7; }}
.slide-row .tools {{ display: flex; flex-direction: column; gap: 7px; font-size: 13px;
  white-space: nowrap; }}

.note {{ border-left: 6px solid var(--blue); padding: 14px 18px; background: var(--sand);
  margin: 0 0 26px; font-size: 15px; }}
.note.bad {{ border-left-color: #B00020; background: var(--pink); }}
.stat-row {{ display: flex; gap: 46px; margin: 0 0 30px; }}
.stat-row .v {{ font-size: {t["stat_value"][1]}px; line-height: 1; color: var(--blue);
  letter-spacing: -.02em; }}
.stat-row .k {{ font-family: "KONE Information", Inter, sans-serif; font-size: 12px;
  text-transform: uppercase; letter-spacing: .06em; margin-top: 10px; }}
"""


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>{_css()}</style>
</head><body>
<header class="bar">
  <span class="mark">KONE</span>
  <h1><a href="/" style="color:inherit;text-decoration:none;">Deck builder</a></h1>
  <span class="spacer"></span>
  <span class="footer-note">Dedicated to People Flow&trade;</span>
</header>
<main>{body}</main>
</body></html>"""
