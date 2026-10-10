"""Move Orbit Browser to a new Firefox: pin the release and check the patches.

    python3 scripts/update_firefox.py            # the newest release Mozilla ships
    python3 scripts/update_firefox.py 158.0      # a given release
    python3 scripts/update_firefox.py --check     # don't re-pin; just check the current one

firefox.json names the release and the SHA-512 of each build Orbit Browser is
made from, as Mozilla lists them in the release's SHA512SUMS. scripts/build.py
downloads only those files and refuses one whose checksum differs.

After pinning, this downloads the new Firefox and tries every patch in patches/
against it (with git apply, the way the build does) and every generated edit's
anchor, so a change Firefox moved is named here, before a build. A patch that no
longer applies is fixed by hand (see the README, "Moving to a new Firefox"):
dump the pristine file with scripts/firefox_file.py, edit a copy, and
`diff -u` the two into the patch. Never loosen a patch so it applies again
without the change it carries, or a feature Orbit removed comes back quietly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build  # noqa: E402
import omni_patches  # noqa: E402
from net import fetch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PIN = ROOT / "firefox.json"
VERSIONS = "https://product-details.mozilla.org/1.0/firefox_versions.json"
ARCHIVE = "https://archive.mozilla.org/pub/firefox/releases"

#: The builds Orbit Browser repacks, by platform: the path under the release
#: folder, with {v} for the version. Mac builds are universal (Apple silicon
#: and Intel); Windows and Linux have one per architecture. Mozilla names the
#: Linux tarballs in lower case with a hyphen (firefox-{v}.tar.xz), unlike the
#: Mac and Windows filenames.
BUILDS = {
    "mac": "mac/en-US/Firefox {v}.dmg",
    "win64": "win64/en-US/Firefox Setup {v}.exe",
    "win64-aarch64": "win64-aarch64/en-US/Firefox Setup {v}.exe",
    "linux": "linux-x86_64/en-US/firefox-{v}.tar.xz",
    "linux-aarch64": "linux-aarch64/en-US/firefox-{v}.tar.xz",
}


def latest() -> str:
    return json.loads(fetch(VERSIONS))["LATEST_FIREFOX_VERSION"]


def pin(version: str) -> dict:
    sums = {}
    for line in fetch(f"{ARCHIVE}/{version}/SHA512SUMS").decode().splitlines():
        digest, _, name = line.partition("  ")
        sums[name] = digest
    builds = {}
    for platform, template in BUILDS.items():
        path = template.format(v=version)
        if path not in sums:
            raise SystemExit(f"Firefox {version} has no {path} in its SHA512SUMS.")
        builds[platform] = {"path": path, "sha512": sums[path]}
    return {"version": version, "archive": f"{ARCHIVE}/{version}/", "builds": builds}


def check_patches() -> int:
    """Try every patch and generated edit against the pinned Firefox, the way
    the build does. Mac-only patches are checked only on a Mac (the Windows
    build unpacks anywhere; the Mac one needs a Mac). Returns the number that no
    longer apply."""
    jars = {"win64": build.read_jars("win64")}
    if sys.platform == "darwin":
        jars["mac"] = build.read_jars("mac")

    def entries_for(platforms: tuple[str, ...]):
        if "windows" in platforms:
            return jars["win64"], None
        if "mac" in platforms:
            return (jars["mac"], None) if "mac" in jars else (None, "mac-only, not on a Mac")
        return None, f"no build for {platforms}"

    applied = failed = skipped = 0
    for patch in omni_patches.load_patches():
        entries, why_skip = entries_for(patch.platforms)
        name = patch.file.relative_to(ROOT)
        if entries is None:
            print(f"  skip  {name}  ({why_skip})")
            skipped += 1
            continue
        try:
            if patch.path not in entries[patch.jar]:
                raise omni_patches.PatchError(f"{patch.jar}:{patch.path} isn't in this Firefox.")
            omni_patches.git_apply(patch, entries[patch.jar][patch.path].decode())
            applied += 1
        except omni_patches.PatchError as error:
            print(f"  FAIL  {name}\n        {str(error).replace(chr(10), chr(10) + '        ')}")
            failed += 1

    for generated in omni_patches.GENERATED:
        try:
            omni_patches.apply_generated(generated, jars["win64"][generated.jar][generated.path].decode())
            applied += 1
        except omni_patches.PatchError as error:
            print(f"  FAIL  generated {generated.jar}:{generated.path}\n        {error}")
            failed += 1

    print(f"\n{applied} applied, {failed} no longer apply" + (f", {skipped} skipped" if skipped else ""))
    if failed:
        print("Fix each failing patch by hand (see the README, 'Moving to a new Firefox');\n"
              "never loosen one so it applies without the change it carries.")
    return failed


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    argv = [a for a in argv if a != "--check"]

    if not check_only:
        version = argv[0] if argv else latest()
        current = json.loads(PIN.read_text())["version"] if PIN.exists() else None
        PIN.write_text(json.dumps(pin(version), indent=2) + "\n")
        print(f"firefox.json: Firefox {version}" + (f" (was {current})" if current and current != version else ""))

    print(f"Checking the patches against Firefox {json.loads(PIN.read_text())['version']}...")
    return 1 if check_patches() else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
