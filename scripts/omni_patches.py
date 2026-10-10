"""Orbit Browser's changes to Mozilla's own files inside omni.ja.

There are two kinds, and both keep every change visible and in its own place:

- **Hand-written edits** are unified-diff **.patch files under `patches/`**, one
  per Mozilla file, applied with `git apply` at build time. This is how the
  Firefox forks keep their changes (Tor Browser, Mullvad, LibreWolf). `git apply`
  is strict: the context around each change must still match, so when a new
  Firefox moves the code the build stops and names the file and hunk. Fix the
  patch then (see the README, "Moving to a new Firefox"); never loosen it, or a
  feature Orbit removed comes back quietly. `patches/<jar>/<path>.patch` says
  which omni.ja the file is in (`browser` or `gre`) by its first folder; a
  `# platforms:` line in the header limits a patch to some builds.

- **Generated edits** (below) inject content built from Orbit's own data: the
  Orbit AI provider from ORBIT_AI_URL and the new tab's wallpapers from
  ORBIT_WALLPAPERS. They can't be static text, so they stay here, applied by
  replacing an exact Mozilla anchor that must appear exactly once. Two small
  appends (a stylesheet and the start-up categories) are here for the same
  reason.

Whole new Orbit files (the branding, the start-up module, the built-in add-ons)
are added by scripts/build.py, not here.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATCHES_DIR = ROOT / "patches"

#: Orbit AI's address for the browser: a fresh New Orbit each time (see
#: Orbit AI's README, "Orbit AI in Orbit Browser"). distribution/policies.json
#: locks browser.ml.chat.provider to the same address.
ORBIT_AI_URL = "https://ai.orbit.com.ai/threads/start/"

#: The new tab's own wallpapers, in place of Firefox's: space in the teal of
#: the mark, drawn by scripts/wallpapers.swift into branding/content/wallpapers/
#: (so chrome://branding/content/wallpapers/, which the new tab's content
#: security policy lets it load). They fill the category Firefox keeps for its
#: own, which the page names after the browser ({ -brand-product-name }), first
#: in the list. position is the CSS background-position: what stays in view
#: when the window crops the picture. name is what a screen reader says.
ORBIT_WALLPAPERS = [
    {"title": "orbit-planet", "file": "planet", "theme": "dark", "position": "right",
     "name": "A teal planet circled by its orbit, its moon at the top right"},
    {"title": "orbit-nebula", "file": "nebula", "theme": "dark", "position": "left",
     "name": "A teal and indigo nebula across a field of stars"},
    {"title": "orbit-horizon", "file": "horizon", "theme": "dark", "position": "bottom",
     "name": "The edge of a planet at night, lit teal by a rising sun"},
    {"title": "orbit-eclipse", "file": "eclipse", "theme": "dark", "position": "right",
     "name": "A planet in front of its star, ringed in teal light"},
    {"title": "orbit-comet", "file": "comet", "theme": "dark", "position": "top right",
     "name": "A comet with a long teal tail"},
    {"title": "orbit-orbits", "file": "orbits", "theme": "dark", "position": "bottom left",
     "name": "A teal planet and its moons on their orbits, on a dark background"},
    {"title": "orbit-orbits-light", "file": "orbits-light", "theme": "light", "position": "bottom left",
     "name": "A teal planet and its moons on their orbits, on a light background"},
    {"title": "orbit-daybreak", "file": "daybreak", "theme": "light", "position": "bottom right",
     "name": "Morning over a teal planet, a moon on its orbit in a pale sky"},
]


def orbit_wallpaper_records() -> list[dict]:
    """ORBIT_WALLPAPERS as the new tab's wallpaper feed hands them to the page,
    the way it hands on Mozilla's Remote Settings records."""
    base = "chrome://branding/content/wallpapers/"
    return [
        {
            "id": w["title"],
            "title": w["title"],
            "category": "firefox",
            "theme": w["theme"],
            "background_position": w["position"],
            "order": (i + 1) * 10,
            "fluent_id": f"newtab-wallpaper-{w['title']}",
            "wallpaperUrl": f"{base}{w['file']}.jpg",
            "thumbnail": f"{base}{w['file']}-thumb.jpg",
        }
        for i, w in enumerate(ORBIT_WALLPAPERS)
    ]


ORBIT_WALLPAPER_FEED = """    // Orbit Browser: its own wallpapers, shipped in the browser
    // (scripts/omni_patches.py, ORBIT_WALLPAPERS), in place of the Firefox
    // ones and the promotions Mozilla sends in their category. Mozilla's
    // other categories stay as they are.
    const orbitWallpapers = %s;
    records = [
      ...orbitWallpapers,
      ...records.filter(record => record.category !== "firefox"),
    ];

    const wallpapers = [
      ...records.map(record => {
""" % json.dumps(orbit_wallpaper_records(), indent=2).replace("\n", "\n    ")

ORBIT_WALLPAPER_NAMES = "newtab-wallpaper-category-title-firefox = { -brand-product-name }\n\n" + "".join(
    f"newtab-wallpaper-{w['title']} = {w['name']}\n" for w in ORBIT_WALLPAPERS
)

ORBIT_AI_PROVIDER = f"""  chatProviders: new Map([
    // Orbit Browser: Orbit AI, the only chatbot it offers (browser.ml.chat.providers
    // is locked to "orbitai", which hides the others). The prompt is typed into
    // Orbit AI's composer and sent (supportAutoSubmit), never put in the address.
    [
      "{ORBIT_AI_URL}",
      {{
        iconUrl: "chrome://branding/content/orbit-ai.svg",
        id: "orbitai",
        link1: "https://orbit.com.ai/terms/",
        link2: "https://orbit.com.ai/privacy/",
        maxLength: 32000,
        name: "Orbit AI",
        supportAutoSubmit: true,
      }},
    ],
"""


# -- the hand-written edits: the .patch files under patches/ -----------------------------


class PatchError(Exception):
    pass


@dataclass(frozen=True)
class StaticPatch:
    #: The .patch file.
    file: Path
    #: "browser" (browser/omni.ja) or "gre" (the omni.ja beside it): the first
    #: folder under patches/.
    jar: str
    #: The file inside that omni.ja the diff changes (from its "+++ b/…" line).
    path: str
    #: The builds the patch is for; all unless a "# platforms:" line narrows it.
    platforms: tuple[str, ...]
    #: Why, from the header comment, for the build and test messages.
    why: str
    #: The unified diff itself (from the first "--- " line on).
    body: str


def load_patches() -> list[StaticPatch]:
    """Every patches/**/*.patch, parsed. The header is the comment lines before
    the diff: "# platforms: mac windows" narrows the builds, the rest is why."""
    patches = []
    for file in sorted(PATCHES_DIR.rglob("*.patch")):
        rel = file.relative_to(PATCHES_DIR)
        jar = rel.parts[0]
        if jar not in ("browser", "gre"):
            raise PatchError(f"{file}: must be under patches/browser/ or patches/gre/.")
        # omni.ja is the same content on every desktop platform, so a patch with
        # no "# platforms:" line applies to all of them, Linux included. A patch
        # that touches platform-specific behaviour narrows itself with that line.
        platforms = ("mac", "windows", "linux")
        why = []
        lines = file.read_text().splitlines(keepends=True)
        start = next((i for i, line in enumerate(lines) if line.startswith("--- ")), None)
        if start is None:
            raise PatchError(f"{file}: has no unified diff (no '--- ' line).")
        for line in lines[:start]:
            text = line.lstrip("#").strip()
            if text.lower().startswith("platforms:"):
                platforms = tuple(text.split(":", 1)[1].split())
            elif text and not text.startswith("Orbit Browser patch"):
                why.append(text)
        body = "".join(lines[start:])
        plus = next(line for line in body.splitlines() if line.startswith("+++ "))
        path = plus[4:].strip().split("\t")[0]
        path = path[2:] if path.startswith("b/") else path
        patches.append(StaticPatch(file, jar, path, platforms, " ".join(why), body))
    return patches


def git_apply(patch: StaticPatch, text: str) -> str:
    """The patch applied to one file's text with `git apply` (strict: the
    context must still match). Raises PatchError, naming the file, if it doesn't."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / patch.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        result = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "-p1"],
            input=patch.body, text=True, cwd=tmp, capture_output=True,
        )
        if result.returncode != 0:
            raise PatchError(
                f"Patch {patch.file.relative_to(ROOT)} no longer applies to this Firefox.\n"
                f"  Change: {patch.why}\n"
                f"  git apply: {result.stderr.strip()}"
            )
        return target.read_text()


# -- the generated edits: Orbit's own data into a Mozilla file ---------------------------


@dataclass(frozen=True)
class Generated:
    #: "browser" or "gre".
    jar: str
    path: str
    #: The exact Mozilla text to replace; it must appear exactly once.
    old: str
    new: str
    why: str


GENERATED: list[Generated] = [
    Generated(
        "browser", "modules/GenAI.sys.mjs",
        "  chatProviders: new Map([\n", ORBIT_AI_PROVIDER,
        "Adds Orbit AI to the chatbot providers; the locked prefs make it the only one.",
    ),
    Generated(
        "browser", "chrome/browser/builtin-addons/newtab/lib/Wallpapers/WallpaperFeed.sys.mjs",
        "    const wallpapers = [\n      ...records.map(record => {\n", ORBIT_WALLPAPER_FEED,
        "The new tab offers Orbit's wallpapers (branding/content/wallpapers/) in place of the Firefox ones.",
    ),
    Generated(
        "browser", "localization/en-US/browser/newtab/newtab.ftl",
        "newtab-wallpaper-category-title-firefox = { -brand-product-name }\n", ORBIT_WALLPAPER_NAMES,
        "What a screen reader says for each of Orbit's wallpapers.",
    ),
]


def apply_generated(generated: Generated, text: str) -> str:
    count = text.count(generated.old)
    if count != 1:
        where = "is not in" if count == 0 else f"appears {count} times in"
        raise PatchError(
            f"Generated edit for {generated.jar}:{generated.path} no longer applies: its anchor {where} this Firefox.\n"
            f"  Change: {generated.why}\n  Looking for: {generated.old[:160]!r}"
        )
    return text.replace(generated.old, generated.new)


# -- the appends ------------------------------------------------------------------------

#: Styles added at the end of Mozilla's own stylesheets (they win over what
#: comes before them), by (jar, path).
APPENDED_STYLES = {
    ("browser", "chrome/browser/content/browser/genai/chat.css"): """
/* Orbit Browser: the sidebar holds Orbit AI alone, so its name is a title
   rather than a menu with one entry, and the panel takes Orbit's black and
   white accent rather than Firefox's purple (the Summarize button, focus). */
:root {
  --color-accent-primary: light-dark(#111111, #ffffff);
  --color-accent-primary-hover: light-dark(#2b2b2b, #e8e8e8);
  --color-accent-primary-active: light-dark(#000000, #d4d4d4);
  --focus-outline-color: light-dark(#111111, #ffffff);
}

#provider {
  appearance: none;
  pointer-events: none;
  background-color: transparent;
  background-image: none;
  border-color: transparent;
  padding-inline-end: var(--space-small);
  font-weight: var(--font-weight-bold);
}
""",
}

#: Lines appended to browser/omni.ja's components/components.manifest: Orbit
#: Browser's start-up module, called the way Firefox calls its own.
COMPONENT_CATEGORIES = (
    "category browser-before-ui-startup resource:///modules/OrbitBrowser.sys.mjs OrbitBrowser.init\n"
    "category browser-idle-startup resource:///modules/OrbitBrowser.sys.mjs OrbitBrowser.onIdle\n"
    "category browser-window-domcontentloaded resource:///modules/OrbitBrowser.sys.mjs OrbitBrowser.onWindow\n"
)


# -- applying everything to the two jars ------------------------------------------------


def apply_all(jars: dict, platform: str) -> None:
    """Change the two omni.ja jars (a {"browser": Jar, "gre": Jar} mapping) in
    place: the .patch files, then the generated edits, then the appends. Each
    step raises PatchError, naming what no longer fits, before a build ships
    without it."""
    for patch in load_patches():
        if platform not in patch.platforms:
            continue
        jar = jars[patch.jar]
        jar.replace(patch.path, git_apply(patch, jar.text(patch.path)))

    for generated in GENERATED:
        jar = jars[generated.jar]
        jar.replace(generated.path, apply_generated(generated, jar.text(generated.path)))

    for (jar_name, path), css in APPENDED_STYLES.items():
        jar = jars[jar_name]
        jar.replace(path, jar.text(path) + css)

    browser = jars["browser"]
    browser.replace(
        "components/components.manifest",
        browser.text("components/components.manifest") + COMPONENT_CATEGORIES,
    )
