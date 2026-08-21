"""Real pictures of the slides, for the page where you pick them.

`preview.archetype_preview_html` draws a wireframe: honest about where
the boxes are, silent about what the slide actually looks like. Asked to
choose between fifty of them, that is not enough -- a photo cover, a
sand statement and a blue quote all preview as a pale rectangle with
some grey lines in it.

So we render the truth once, offline: build a deck holding every
archetype, put it through the same LibreOffice conversion a person would
use to look at it, and keep one PNG per archetype under `assets/previews`.
The web page serves those; anything without one falls back to the
wireframe, so a new archetype is never a broken image.

Rendering needs LibreOffice and poppler, which the Railway image has no
reason to carry. That is why the PNGs are committed rather than built on
boot: `python -m deckguard.thumbs` regenerates them here, and the server
only ever reads files.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from deckguard import brandmode as bm

PREVIEW_DIR = Path(__file__).parent / "assets" / "previews"
WIDTH_PX = 520  # ~2x the widest tile the grid draws, so it stays crisp


def path_for(archetype: str, audience: str = "internal") -> Path | None:
    """The rendered thumbnail for an archetype in one set, if one exists.

    Per audience, not per archetype: six archetypes serve both sets and
    they carry different copy in each, so one PNG for both made the two
    sets read as one deck shown twice. An archetype only one set uses
    falls back to whichever was rendered.
    """
    for name in (archetype, ""):
        if not name or "/" in name or "\\" in name or ".." in name:
            continue
        for where in (audience, "external" if audience == "internal" else "internal"):
            candidate = PREVIEW_DIR / where / f"{name}.png"
            if candidate.is_file():
                return candidate
    return None


def set_archetypes(audience: str | None = None) -> list[str]:
    """Every archetype a set offers, in set order. Both sets if unnamed."""
    names: list[str] = []
    for name in ([audience] if audience else bm.set_names()):
        for slide in bm.slides_in(name):
            if slide["archetype"] not in names:
                names.append(slide["archetype"])
    return names


def _tools_present() -> None:
    for tool in ("soffice", "pdftoppm"):
        if shutil.which(tool) is None:
            raise RuntimeError(
                f"{tool} is not on PATH. Thumbnails are rendered offline and "
                "committed; you only need these to regenerate them.")


def render(out_dir: Path | None = None) -> list[Path]:
    """Render one PNG per slide, per set. Returns the files written."""
    from deckguard import assemble
    from deckguard.preview import sample_content
    from deckguard.registry import _load_archetypes

    _tools_present()
    out_dir = out_dir or PREVIEW_DIR
    built = set(_load_archetypes().ARCHETYPES)
    written: list[Path] = []

    for audience in bm.set_names():
        wanted = [n for n in set_archetypes(audience) if n in built]
        if not wanted:
            continue
        target = out_dir / audience
        target.mkdir(parents=True, exist_ok=True)
        spec = {
            "title": f"KONE {audience} previews",
            "date": assemble.bm_date(),
            # Named, because the renderer reads the field a slide's SET
            # declares from it. Without it the internal `hero_stat`
            # previewed white where its set says light-blue -- the very
            # defect these renders exist to make visible.
            "audience": audience,
            "slides": [{"archetype": n, **sample_content(n, audience)} for n in wanted],
        }
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            deck = work / "previews.pptx"
            assemble.build(spec, str(deck))
            subprocess.run(
                ["soffice", "--headless", "--convert-to", "pdf",
                 "--outdir", str(work), str(deck)],
                check=True, capture_output=True, timeout=900,
            )
            pdf = work / "previews.pdf"
            if not pdf.is_file():
                raise RuntimeError("LibreOffice produced no PDF")
            subprocess.run(
                ["pdftoppm", "-png", "-scale-to-x", str(WIDTH_PX), "-scale-to-y", "-1",
                 str(pdf), str(work / "page")],
                check=True, capture_output=True, timeout=900,
            )
            pages = sorted(work.glob("page-*.png"))
            # The deck keeps a "Thank you" at the end, and prepends a cut
            # cover only when the spec does not already open on one. Both
            # sets DO open on a cover, so the offset is currently zero --
            # but it was 1 while the master's own cover was retained, and
            # hard-coding it put every internal thumbnail one slide out.
            # Derived instead, so it cannot go stale again.
            offset = max(0, len(pages) - 1 - len(wanted))
            for index, name in enumerate(wanted):
                if index + offset >= len(pages):
                    break
                shutil.copyfile(pages[index + offset], target / f"{name}.png")
                written.append(target / f"{name}.png")
    return written


def main() -> None:
    files = render()
    print(f"{len(files)} thumbnails written to {PREVIEW_DIR}")


if __name__ == "__main__":
    main()
