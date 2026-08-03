"""Visual audit: check what a preview actually RENDERS, not what its
markup says.

Everything else in deckguard verifies structure -- XML, shape trees,
color values. That catches a lot, and it missed both of the last two
real bugs outright: a duplicate logo (two perfectly valid pictures,
overlapping) and a preview whose type was sized in `cqh` inside an
inline-size container, so a 60pt heading rendered ~2.4x oversized and
blew out of its box. Both are invisible to any amount of XML reading and
obvious the instant something measures the laid-out result.

So this module lays the page out in headless Chromium and measures it.
It asserts invariants rather than diffing screenshots: pixel snapshots
break on every font and browser bump and tell you *that* something moved,
never *what* is wrong. Measurements say "shape 'TextBox 32' overflows its
box by 41px" -- which is the finding, and survives a Chromium upgrade.

The invariants are the ones a designer checks by eye:

- `text_overflow`  -- content is taller/wider than the shape holding it
- `outside_frame`  -- a shape hangs off the edge of the slide
- `tiny_text`      -- type rendered below the legible floor
- `low_contrast`   -- text too close in luminance to what's behind it
- `empty_frame`    -- a preview that drew nothing at all

Previews are HTML, so this runs today. The same `VisualFinding` shape and
the same checks apply to rendered .pptx slides once a working renderer is
available on the deploy image (LibreOffice is currently non-functional
there), which is the point: this is the measurement half of that loop,
built against the surface that can be measured now.

Playwright and Chromium are optional. `playwright_available()` reports
whether a real measurement can run, and every entry point degrades to an
empty finding list rather than raising, so nothing here is load-bearing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from deckguard.colors import contrast_ratio, hex_to_rgb

# Measure at true slide width so thresholds mean something in slide
# terms: at 1280px the frame is 1:1 with a 1280x720 slide, and one
# typographic point of a 13.333in deck is exactly 4/3 px.
RENDER_WIDTH_PX = 1280
PT_TO_PX = RENDER_WIDTH_PX / (13.333 * 72.0)

OVERFLOW_TOL_PX = 2.0  # sub-pixel rounding and 1px borders
EDGE_TOL_PX = 1.0
MIN_LEGIBLE_PT = 8.0  # the brand's own footer is 11px == 8.25pt, so 9 flagged
                      # every correctly-built slide; 8 is the real floor
MIN_CONTRAST = 3.0  # WCAG AA for large text; slide type is large


@dataclass
class VisualFinding:
    rule: str
    severity: str  # "major" | "minor"
    shape_name: str
    message: str
    frame_index: int = 0


@dataclass
class VisualReport:
    findings: list = field(default_factory=list)
    frames_measured: int = 0
    ran: bool = False  # False when Playwright/Chromium wasn't available

    @property
    def summary(self) -> dict:
        out = {"major": 0, "minor": 0}
        for f in self.findings:
            out[f.severity] = out.get(f.severity, 0) + 1
        return out


def playwright_available() -> bool:
    """Whether a real measurement can run here."""
    try:
        import playwright.sync_api  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return bool(_chromium_path())


def _chromium_path() -> Optional[str]:
    import os
    from pathlib import Path

    explicit = os.environ.get("DECKGUARD_CHROMIUM")
    if explicit and Path(explicit).exists():
        return explicit
    for candidate in ("/opt/pw-browsers/chromium", "/usr/bin/chromium", "/usr/bin/chromium-browser"):
        if Path(candidate).exists():
            return candidate
    return None  # let Playwright fall back to its own download, if any


# The page-side probe. Returns one record per preview frame, with the
# laid-out geometry of every shape box and every text run inside it.
# scrollHeight/scrollWidth vs clientHeight/clientWidth is the overflow
# signal: `overflow:hidden` clips painting, not layout, so the scroll
# size still reports what the content really needed.
#
# `effectiveBg` matters as much as the shape's own fill: a plain text
# placeholder has no fill, but if a painted panel sits behind it, THAT
# is what its text has to be legible against. Document order is paint
# order here (every box is absolutely positioned, no z-index), so the
# effective background is the last earlier box that both contains this
# one and is actually painted -- the same rule OOXML uses, and the
# difference between correctly reading white-on-blue and reporting
# white-on-white on every slide with a layout colour panel.
_PROBE = """() => {
  const opaque = c => c && c.indexOf('rgb') === 0 &&
    !(c.startsWith('rgba') && parseFloat(c.split(',')[3]) === 0);
  const contains = (outer, inner) =>
    outer.left <= inner.left + 1 && outer.top <= inner.top + 1 &&
    outer.right >= inner.right - 1 && outer.bottom >= inner.bottom - 1;
  const frames = [...document.querySelectorAll('[data-dg-frame]')];
  return frames.map(frame => {
    const fr = frame.getBoundingClientRect();
    const all = [...frame.querySelectorAll('[data-dg-shape]')];
    const boxes = all.map(el => el.getBoundingClientRect());
    const shapes = all.map((el, i) => {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      const runs = [...el.querySelectorAll('span')]
        .filter(s => s.textContent.trim())
        .map(s => ({
          text: s.textContent.slice(0, 40),
          fontPx: parseFloat(getComputedStyle(s).fontSize),
          color: getComputedStyle(s).color,
        }));
      let effectiveBg = opaque(cs.backgroundColor) ? cs.backgroundColor : null;
      if (!effectiveBg) {
        for (let j = i - 1; j >= 0; j--) {
          const bg = getComputedStyle(all[j]).backgroundColor;
          if (opaque(bg) && contains(boxes[j], r)) { effectiveBg = bg; break; }
        }
      }
      return {
        name: el.getAttribute('data-dg-shape') || '',
        left: r.left - fr.left, top: r.top - fr.top,
        width: r.width, height: r.height,
        overflowX: el.scrollWidth - el.clientWidth,
        overflowY: el.scrollHeight - el.clientHeight,
        background: cs.backgroundColor,
        effectiveBg,
        runs,
      };
    });
    return {
      width: fr.width, height: fr.height,
      background: getComputedStyle(frame).backgroundColor,
      shapes,
    };
  });
}"""


def measure_html(html_fragments: list) -> list:
    """Lay the given preview fragments out in headless Chromium and
    return the raw measurement records (one per frame). Empty list if no
    browser is available."""
    if not playwright_available():
        return []
    from playwright.sync_api import sync_playwright

    # Each fragment is width:100%, so wrap them in fixed-width holders to
    # pin the frame to exactly RENDER_WIDTH_PX.
    holders = "".join(
        f'<div style="width:{RENDER_WIDTH_PX}px">{frag}</div>' for frag in html_fragments
    )
    doc = (
        "<!doctype html><meta charset='utf-8'>"
        "<style>body{margin:0;font-family:Inter,Arial,sans-serif;}</style>"
        f"<body>{holders}</body>"
    )
    launch: dict = {}
    path = _chromium_path()
    if path:
        launch["executable_path"] = path
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch)
        try:
            page = browser.new_page(viewport={"width": RENDER_WIDTH_PX + 40, "height": 900})
            page.set_content(doc, wait_until="load")
            return page.evaluate(_PROBE)
        finally:
            browser.close()


def _parse_css_rgb(value: str) -> Optional[tuple]:
    """`rgb(20, 60, 245)` / `rgba(...)` -> (r, g, b). None if transparent."""
    if not value or "rgb" not in value:
        return None
    nums = value[value.index("(") + 1 : value.rindex(")")].split(",")
    try:
        parts = [float(n.strip()) for n in nums]
    except ValueError:
        return None
    if len(parts) >= 4 and parts[3] == 0:
        return None  # fully transparent -- whatever is behind shows through
    return tuple(int(round(p)) for p in parts[:3])


def check_measurements(frames: list) -> list:
    """Pure function: measurement records -> findings. Kept separate from
    the browser so the rules are testable without one."""
    findings: list = []
    for fi, frame in enumerate(frames):
        shapes = frame.get("shapes") or []
        if not shapes:
            findings.append(VisualFinding(
                "empty_frame", "minor", "",
                "preview rendered nothing -- the slide drew no visible shapes", fi,
            ))
            continue

        frame_bg = _parse_css_rgb(frame.get("background", "")) or (255, 255, 255)
        fw, fh = frame.get("width") or 0, frame.get("height") or 0

        for shape in shapes:
            name = shape.get("name") or "(unnamed)"

            over_y, over_x = shape.get("overflowY", 0), shape.get("overflowX", 0)
            if over_y > OVERFLOW_TOL_PX or over_x > OVERFLOW_TOL_PX:
                axis = "taller" if over_y >= over_x else "wider"
                by = max(over_y, over_x)
                findings.append(VisualFinding(
                    "text_overflow", "major", name,
                    f"content is {by:.0f}px {axis} than its box -- it will be clipped", fi,
                ))

            if fw and fh:
                right, bottom = shape["left"] + shape["width"], shape["top"] + shape["height"]
                if (shape["left"] < -EDGE_TOL_PX or shape["top"] < -EDGE_TOL_PX
                        or right > fw + EDGE_TOL_PX or bottom > fh + EDGE_TOL_PX):
                    findings.append(VisualFinding(
                        "outside_frame", "minor", name,
                        "extends past the edge of the slide", fi,
                    ))

            bg = (
                _parse_css_rgb(shape.get("effectiveBg") or "")
                or _parse_css_rgb(shape.get("background", ""))
                or frame_bg
            )
            for run in shape.get("runs") or []:
                pt = run["fontPx"] / PT_TO_PX
                if pt < MIN_LEGIBLE_PT:
                    findings.append(VisualFinding(
                        "tiny_text", "minor", name,
                        f"renders at {pt:.1f}pt, below the {MIN_LEGIBLE_PT:.0f}pt legible floor "
                        f'("{run["text"][:24]}")', fi,
                    ))
                fg = _parse_css_rgb(run.get("color", ""))
                if fg is not None:
                    ratio = contrast_ratio(fg, bg)
                    if ratio < MIN_CONTRAST:
                        findings.append(VisualFinding(
                            "low_contrast", "major", name,
                            f"text contrast {ratio:.1f}:1 against its background, under "
                            f'{MIN_CONTRAST:.0f}:1 ("{run["text"][:24]}")', fi,
                        ))
    return findings


def audit_previews(html_fragments: list) -> VisualReport:
    """Render the given previews and report what is visually wrong with
    them. Degrades to an empty, `ran=False` report with no browser."""
    if not playwright_available():
        return VisualReport(ran=False)
    try:
        frames = measure_html(html_fragments)
    except Exception:  # noqa: BLE001 -- a browser crash must not fail a transform
        return VisualReport(ran=False)
    return VisualReport(findings=check_measurements(frames), frames_measured=len(frames), ran=True)


def audit_deck_previews(deck_path) -> VisualReport:
    """Convenience: build every slide's preview for a deck and audit it."""
    from pptx import Presentation

    from deckguard.inventory import build_inventory
    from deckguard.preview import slide_preview_html

    prs = Presentation(str(deck_path))
    w_in = prs.slide_width / 914400
    h_in = prs.slide_height / 914400
    inv = build_inventory(prs)
    return audit_previews([slide_preview_html(rec, w_in, h_in) for rec in inv.slides])


def to_json(report: VisualReport) -> str:
    return json.dumps({
        "ran": report.ran,
        "frames_measured": report.frames_measured,
        "summary": report.summary,
        "findings": [
            {"slide": f.frame_index + 1, "rule": f.rule, "severity": f.severity,
             "shape": f.shape_name, "message": f.message}
            for f in report.findings
        ],
    }, indent=2)


__all__ = [
    "VisualFinding", "VisualReport", "audit_deck_previews", "audit_previews",
    "check_measurements", "measure_html", "playwright_available", "to_json",
]
