"""Apply Orbit's changes to the Chromium source tree.

Orbit keeps every change it makes to Chromium apart from Google's code, the way
the Chromium forks (Brave, ungoogled-chromium, Vivaldi) do, so every change is
visible and nothing is quietly edited in place. Two kinds, both applied here:

1. patches/ -- unified-diff .patch files, one per Chromium file, at
   patches/<path-in-src>.patch (so patches/chrome/browser/foo.cc.patch edits
   src/chrome/browser/foo.cc). Applied with `git apply`, which is strict: the
   lines around each change must still match, so a Chromium that moved the code
   stops the build and names the patch. This is the only way to edit Chromium's
   own existing files. A `# platforms:` first line limits a patch to some builds.

2. chromium_src/ -- whole Orbit files (new source, branding data, the Orbit
   component) copied into the matching path under src/. This is how new files
   are added (Chromium's BUILD.gn files, edited by patch, pull them into the
   build). Overriding an existing Chromium file wholesale is allowed here only
   when a diff would be unreadable; prefer a patch.

Never loosen a patch so it applies without the change it carries, or a feature
Orbit removed comes back quietly. A patch that no longer applies is re-anchored
by hand against the new Chromium (see the README, "Moving to a new Chromium").
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATCHES = ROOT / "patches"
OVERRIDES = ROOT / "chromium_src"

#: The platforms a patch or override can be limited to, matched against the
#: build's platform (mac, win, linux). None means every platform.
ALL_PLATFORMS = ("mac", "win", "linux")


class PatchError(RuntimeError):
    pass


@dataclass
class Patch:
    file: Path
    #: The src-relative file it edits (patches/<rel>.patch -> src/<rel>).
    target: str
    platforms: tuple[str, ...]


def load_patches() -> list[Patch]:
    patches = []
    for path in sorted(PATCHES.rglob("*.patch")):
        rel = path.relative_to(PATCHES).with_suffix("")  # drop .patch
        platforms = _platforms(path)
        patches.append(Patch(file=path, target=rel.as_posix(), platforms=platforms))
    return patches


def _platforms(path: Path) -> tuple[str, ...]:
    first = path.read_text().splitlines()[:1]
    if first and first[0].startswith("# platforms:"):
        names = tuple(first[0].split(":", 1)[1].replace(",", " ").split())
        unknown = [n for n in names if n not in ALL_PLATFORMS]
        if unknown:
            raise PatchError(f"{path.name}: unknown platform(s) {unknown}; use {ALL_PLATFORMS}.")
        return names
    return ALL_PLATFORMS


def git_apply(patch: Patch, src: Path, *, check_only: bool = False) -> None:
    """Apply one patch to the Chromium checkout with `git apply`, the strict way
    the build does. Raises PatchError (naming the patch) if it no longer fits."""
    target = src / patch.target
    if not target.exists():
        raise PatchError(f"{patch.target} isn't in this Chromium; has it moved or been renamed? ({patch.file.relative_to(ROOT)})")
    args = ["git", "-C", str(src), "apply", "--whitespace=nowarn"]
    if check_only:
        args.append("--check")
    result = subprocess.run(args + [str(patch.file)], capture_output=True, text=True)
    if result.returncode != 0:
        raise PatchError(f"{patch.file.relative_to(ROOT)} no longer applies:\n{result.stderr.strip()}")


def copy_overrides(src: Path, platform: str) -> int:
    """Copy chromium_src/ into the source tree. A file whose path has a
    `.<platform>.` segment, or that sits under a platform directory, is only
    copied for that platform. Returns the number copied."""
    if not OVERRIDES.exists():
        return 0
    copied = 0
    for source in sorted(OVERRIDES.rglob("*")):
        if not source.is_file() or source.name == "README.md":
            continue
        rel = source.relative_to(OVERRIDES)
        if not _override_applies(rel, platform):
            continue
        target = src / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied += 1
    return copied


def _override_applies(rel: Path, platform: str) -> bool:
    parts = set(rel.parts[:-1])
    for other in ALL_PLATFORMS:
        if other != platform and (other in parts or f".{other}." in rel.name):
            return False
    return True


def apply_all(src: Path, platform: str) -> None:
    """Every patch and override for this platform, onto a pristine tree."""
    for patch in load_patches():
        if platform in patch.platforms:
            git_apply(patch, src)
    copy_overrides(src, platform)
