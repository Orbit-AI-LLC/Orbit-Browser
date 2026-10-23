"""Move Orbit Browser to a new Chromium: pin the release and check the patches.

    python3 scripts/update_chromium.py                 # the newest stable Google ships
    python3 scripts/update_chromium.py 142.0.7444.52    # a given version
    python3 scripts/update_chromium.py --check          # don't re-pin; just check the current one

chromium.json names the Chromium version Orbit Browser is forked from. Unlike a
binary repack, there is no checksum to pin: the source is a git tag, verified by
git when scripts/sync.py checks it out.

With --check (or after pinning), this syncs the source to the pin and tries every
patch in patches/ against it (with `git apply --check`, the way the build does),
printing which still apply and which don't. A patch that no longer applies is one
whose surrounding code Chromium moved; fix it by hand (see the README, "Moving to
a new Chromium"). Never loosen a patch so it applies again without the change it
carries, or a feature Orbit removed comes back quietly.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import patches as patchlib  # noqa: E402
import sync  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PIN = ROOT / "chromium.json"
#: ChromiumDash: the current release versions per channel and platform.
RELEASES = "https://chromiumdash.appspot.com/fetch_releases?channel=Stable&platform=Mac&num=1"


def latest() -> str:
    with urllib.request.urlopen(RELEASES, timeout=60) as response:
        data = json.loads(response.read())
    if not data:
        raise SystemExit("ChromiumDash returned no stable release.")
    return data[0]["version"]


def repin(version: str) -> None:
    info = json.loads(PIN.read_text())
    was = info.get("version")
    info["version"] = version
    info["milestone"] = int(version.split(".")[0])
    PIN.write_text(json.dumps(info, indent=2) + "\n")
    print(f"chromium.json: Chromium {version}" + (f" (was {was})" if was and was != version else ""))


def check_patches() -> int:
    """Sync the source to the pin and try every patch against it. Returns the
    number that no longer apply."""
    sync.ensure_depot_tools()
    src = sync.ensure_source()
    host = "mac" if sys.platform == "darwin" else "linux" if sys.platform.startswith("linux") else "win"

    applied = failed = skipped = 0
    for patch in patchlib.load_patches():
        name = patch.file.relative_to(ROOT)
        if host not in patch.platforms:
            print(f"  skip  {name}  (not for {host})")
            skipped += 1
            continue
        try:
            patchlib.git_apply(patch, src, check_only=True)
            applied += 1
        except patchlib.PatchError as error:
            print(f"  FAIL  {name}\n        {str(error).replace(chr(10), chr(10) + '        ')}")
            failed += 1

    print(f"\n{applied} apply, {failed} no longer apply" + (f", {skipped} skipped" if skipped else ""))
    if failed:
        print("Fix each failing patch by hand (see the README, 'Moving to a new Chromium');\n"
              "never loosen one so it applies without the change it carries.")
    return failed


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    argv = [a for a in argv if a != "--check"]
    if not check_only:
        repin(argv[0] if argv else latest())
    print(f"Checking the patches against Chromium {json.loads(PIN.read_text())['version']}...")
    return 1 if check_patches() else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
