"""Render every form of the Orbit Browser mark.

The mark is the Orbit family's (scripts/orbitmark.swift, the renderer the
other Orbit apps share): a globe drawn in line, white on teal, the family's
tilted orbit for its equator and a moon riding the orbit. Edit the
geometry or the colours there, never the outputs:

    .venv/bin/python scripts/build_icon.py
    .venv/bin/python scripts/build_icon.py --wordmark-font InterDisplay-SemiBold.ttf

Needs macOS (swiftc through xcrun, and iconutil) and Pillow; fontTools for the
wordmark, which is only rewritten when a font is given: Inter Display
SemiBold, from https://github.com/rsms/inter (SIL Open Font License). The
outputs are committed, so building the browser needs none of this.

Outputs, all under branding/:
    mark.svg, logo.svg, icon.svg       the tile, the bare mark, the macOS icon
    content/                           replaces chrome://branding/content/ in the browser
    content/apps/                      the Orbit apps' marks, for the toolbar's Orbit menu and bookmarks
    skin/sidebar-firefox.svg           the toolbar-coloured mark Firefox's theme shows
    mac/firefox.icns, document.icns    the Mac app and its documents
    windows/*.ico, VisualElements*     the Windows executables and Start tiles
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: Orbit Pass keeps its own mark (the family renderer doesn't draw it); it is
#: taken from the Orbit Pass checkout beside this one.
ORBIT_PASS = ROOT.parent / "Orbit Pass"
#: The Orbit apps in the browser's Orbit menu and bookmarks, by their mark in
#: scripts/orbitmark.swift ("pass" comes from Orbit Pass).
APP_MARKS = ("ai", "mail", "calendar", "chat", "control", "pass")
OUT = ROOT / "branding"
SOURCE = ROOT / "scripts" / "orbitmark.swift"
DARK = (22, 24, 29, 255)  # the about dialog and private windows' tile


class Renderer:
    """scripts/orbitmark.swift, compiled once."""

    def __init__(self, workdir: Path):
        self.binary = workdir / "orbitmark"
        sdk = subprocess.run(["xcrun", "--show-sdk-path"], capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["xcrun", "swiftc", "-sdk", sdk, "-O", "-o", str(self.binary), str(SOURCE)], check=True)
        self.workdir = workdir

    def svg(self, mark: str, layout: str, size: str, *detail: str) -> str:
        return subprocess.run([str(self.binary), "svg", mark, layout, size, *detail], capture_output=True, text=True, check=True).stdout

    def png(self, mark: str, layout: str, size: str, *detail: str):
        from PIL import Image

        target = self.workdir / "out.png"
        subprocess.run([str(self.binary), "png", mark, str(target), size, layout, *detail], check=True)
        return Image.open(target).convert("RGBA")

    def colour(self, mark: str) -> str:
        return subprocess.run([str(self.binary), "colour", mark], capture_output=True, text=True, check=True).stdout.strip()


def detail(px: int) -> tuple[str, ...]:
    """The family's levels of detail: the object alone at 16 px, bolder to 48."""
    return ("tiny",) if px <= 16 else ("small",) if px <= 48 else ()


def write_svgs(r: Renderer) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mark.svg").write_text(r.svg("browser", "tile", "64"))
    (OUT / "logo.svg").write_text(r.svg("browser", "colour", "512"))
    (OUT / "icon.svg").write_text(r.svg("browser", "mac", "1024"))
    content = OUT / "content"
    content.mkdir(parents=True, exist_ok=True)
    # Next to the wordmark (the about dialog, the home page's logo).
    (content / "about-logo.svg").write_text(r.svg("browser", "colour", "512x512"))
    # Orbit AI's own mark, wherever the browser names Orbit AI (the sidebar, the menus).
    (content / "orbit-ai.svg").write_text(r.svg("ai", "tile", "64"))
    skin = OUT / "skin"
    skin.mkdir(parents=True, exist_ok=True)
    # A page with its corner folded and the mark: Windows shows it for PDFs.
    mark = r.svg("browser", "tile", "120").split(">", 1)[1].rsplit("</svg>", 1)[0]
    (content / "document_pdf.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">\n'
        '<path d="M48 12h108l52 52v180H48z" fill="#fff" stroke="#8a8a8a" stroke-width="6" stroke-linejoin="round"/>\n'
        '<path d="M156 12v52h52" fill="#e9e9e9" stroke="#8a8a8a" stroke-width="6" stroke-linejoin="round"/>\n'
        f'<svg x="68" y="110" width="120" height="120" viewBox="0 0 1024 1024">{mark}</svg>\n</svg>\n'
    )
    # The Orbit apps, for the Orbit menu (SVG) and the default bookmarks (PNG,
    # inlined by scripts/build.py).
    apps = content / "apps"
    apps.mkdir(parents=True, exist_ok=True)
    for mark in APP_MARKS:
        if mark == "pass":
            shutil.copyfile(ORBIT_PASS / "static" / "brand" / "mark.svg", apps / "pass.svg")
            shutil.copyfile(ORBIT_PASS / "extension" / "icons" / "icon-32.png", apps / "pass-32.png")
        else:
            (apps / f"{mark}.svg").write_text(r.svg(mark, "tile", "64"))
            r.png(mark, "tile", "32", "small").save(apps / f"{mark}-32.png")
    # The toolbar's Orbit button: the family's planet in orbit, in the toolbar's colour.
    planet = r.svg("orbit", "current", "16x16", "small").replace('fill="currentColor"', 'fill="context-fill"')
    (skin / "orbit-button.svg").write_text(planet)
    # Firefox's theme draws its logo in the toolbar's colour (context-fill).
    sidebar = r.svg("browser", "current", "26x26", "small").replace('fill="currentColor"', 'fill="context-fill"')
    (skin / "sidebar-firefox.svg").write_text(sidebar)


def tile(r: Renderer, px: int):
    return r.png("browser", "tile", str(px), *detail(px))


def dark_tile(r: Renderer, px: int):
    """The mark in its colours on a dark tile: private windows."""
    from PIL import Image, ImageDraw

    ss = 4
    big = Image.new("RGBA", (px * ss, px * ss), (0, 0, 0, 0))
    ImageDraw.Draw(big).rounded_rectangle([0, 0, px * ss - 1, px * ss - 1], radius=int(px * ss * 0.225), fill=DARK)
    big = big.resize((px, px), Image.LANCZOS)
    inner = max(8, round(px * 0.8))
    mark = r.png("browser", "colour", f"{inner}x{inner}", *detail(px))
    big.alpha_composite(mark, ((px - inner) // 2, (px - inner) // 2))
    return big


def document(r: Renderer, px: int):
    """A page with a folded corner and the mark: files the browser opens."""
    from PIL import Image, ImageDraw

    ss = 4
    big = px * ss
    k = big / 256
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    width = max(1, int(6 * k))
    line = (138, 138, 138, 255)
    draw.polygon([(48 * k, 12 * k), (156 * k, 12 * k), (208 * k, 64 * k), (208 * k, 244 * k), (48 * k, 244 * k)], fill=(255, 255, 255, 255), outline=line, width=width)
    draw.polygon([(156 * k, 12 * k), (156 * k, 64 * k), (208 * k, 64 * k)], fill=(233, 233, 233, 255), outline=line, width=width)
    image = image.resize((px, px), Image.LANCZOS)
    inner = max(8, round(px * 0.5))
    image.alpha_composite(tile(r, inner), (round(px * 0.25), round(px * 0.42)))
    return image


def write_pngs(r: Renderer) -> None:
    from PIL import Image

    content = OUT / "content"
    for px in (16, 32, 48, 64, 128):
        tile(r, px).save(content / f"icon{px}.png")
    r.png("browser", "colour", "192x192").save(content / "about-logo.png")
    r.png("browser", "colour", "384x384").save(content / "about-logo@2x.png")
    # Private browsing pages are dark: the mark in white.
    r.png("browser", "white", "192x192").save(content / "about-logo-private.png")
    r.png("browser", "white", "384x384").save(content / "about-logo-private@2x.png")
    about = Image.new("RGBA", (300, 236), (0, 0, 0, 0))
    about.alpha_composite(r.png("browser", "colour", "180x180"), (60, 28))
    about.save(content / "about.png")

    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    windows = OUT / "windows"
    windows.mkdir(parents=True, exist_ok=True)
    ico(windows / "firefox.ico", {px: tile(r, px) for px in sizes})
    ico(windows / "private_browsing.ico", {px: dark_tile(r, px) for px in sizes})
    ico(windows / "document.ico", {px: document(r, px) for px in sizes})
    shutil.copyfile(windows / "document.ico", content / "document.ico")
    # Start menu tiles: the bare white mark; the manifests give the colour behind it.
    for px in (150, 70):
        canvas = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        inner = round(px * 0.62)
        canvas.alpha_composite(r.png("browser", "white", f"{inner}x{inner}", *detail(inner)), ((px - inner) // 2, (px - inner) // 2))
        canvas.save(windows / f"VisualElements_{px}.png")
        canvas = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        canvas.alpha_composite(r.png("browser", "colour", f"{inner}x{inner}", *detail(inner)), ((px - inner) // 2, (px - inner) // 2))
        canvas.save(windows / f"PrivateBrowsing_{px}.png")
    (windows / "tile-colour.txt").write_text(r.colour("browser") + "\n")

    mac = OUT / "mac"
    mac.mkdir(parents=True, exist_ok=True)
    icns(mac / "firefox.icns", lambda px: r.png("browser", "mac", str(px), *detail(px)))
    icns(mac / "document.icns", lambda px: document(r, px))


def ico(target: Path, frames: dict) -> None:
    """A Windows icon with each size drawn for itself (Pillow would otherwise
    shrink the largest)."""
    order = sorted(frames)
    largest = frames[order[-1]]
    largest.save(target, format="ICO", sizes=[(px, px) for px in order], append_images=[frames[px] for px in order[:-1]])


def icns(target: Path, make) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icon.iconset"
        iconset.mkdir()
        for points in (16, 32, 128, 256, 512):
            make(points).save(iconset / f"icon_{points}x{points}.png")
            make(points * 2).save(iconset / f"icon_{points}x{points}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", "-o", str(target), str(iconset)], check=True)


# -- the wordmark ---------------------------------------------------------------------


def write_wordmark(font_path: Path) -> None:
    """"Orbit Browser" in Inter Display SemiBold, as outlines, so it needs no
    font: about-wordmark.svg (the about dialog colours it) and
    firefox-wordmark.svg (the name the browser's pages ask for)."""
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont

    font = TTFont(str(font_path))
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    kern = _kerning(font)
    names = [cmap[ord(ch)] for ch in "Orbit Browser"]
    k = 80.0 / font["OS/2"].sCapHeight
    advance = 0.0
    placed = []
    for i, name in enumerate(names):
        placed.append((name, advance))
        advance += glyphs[name].width
        if i + 1 < len(names):
            advance += kern.get((name, names[i + 1]), 0)
    bounds = BoundsPen(glyphs)
    for name, x in placed:
        glyphs[name].draw(TransformPen(bounds, (1, 0, 0, 1, x, 0)))
    x_min, y_min, x_max, y_max = bounds.bounds
    pen = SVGPathPen(glyphs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    for name, x in placed:
        # Font units have y up; the SVG's y goes down from the tallest letter.
        glyphs[name].draw(TransformPen(pen, (k, 0, 0, -k, (x - x_min) * k, y_max * k)))
    box = f"0 0 {(x_max - x_min) * k:.2f} {(y_max - y_min) * k:.2f}"
    note = "<!-- Orbit Browser wordmark: Inter Display SemiBold (SIL OFL), outlined by scripts/build_icon.py. -->"
    content = OUT / "content"
    (content / "about-wordmark.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}">{note}<path fill="context-fill" d="{pen.getCommands()}"/></svg>\n'
    )
    (content / "firefox-wordmark.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" fill="context-fill #111111" viewBox="{box}">{note}<path d="{pen.getCommands()}"/></svg>\n'
    )


def _kerning(font) -> dict:
    """Pair kerning from GPOS pair adjustments (format 1 covers these letters in Inter)."""
    pairs: dict = {}
    if "GPOS" not in font:
        return pairs
    for lookup in font["GPOS"].table.LookupList.Lookup:
        for sub in lookup.SubTable:
            sub = getattr(sub, "ExtSubTable", sub)
            if getattr(sub, "LookupType", None) != 2 or getattr(sub, "Format", None) != 1:
                continue
            for first, pairset in zip(sub.Coverage.glyphs, sub.PairSet):
                for record in pairset.PairValueRecord:
                    value = record.Value1
                    if value is not None and getattr(value, "XAdvance", 0):
                        pairs.setdefault((first, record.SecondGlyph), value.XAdvance)
    return pairs


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        renderer = Renderer(Path(tmp))
        write_svgs(renderer)
        write_pngs(renderer)
    if "--wordmark-font" in sys.argv:
        write_wordmark(Path(sys.argv[sys.argv.index("--wordmark-font") + 1]))
    print("Orbit Browser mark written.")
