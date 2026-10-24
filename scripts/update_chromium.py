"""Pin the ungoogled-chromium build Orbit Browser repacks.

    python3 scripts/update_chromium.py            # pin the newest Windows + macOS release
    python3 scripts/update_chromium.py --check     # just report the pinned vs newest version

chromium.json pins the version and, per platform, the download URL and its
SHA-256. ungoogled-software ships official builds for Windows and macOS (each in
its own release repo); this reads the newest release of each from GitHub and
takes the download URL and the SHA-256 GitHub records for every asset, so no
download is needed. There is no official generic Linux binary, so Linux is not
pinned or built (Linux users install ungoogled-chromium from their distro).

scripts/build.py refuses any download whose checksum differs from the pin.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from net import fetch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PIN = ROOT / "chromium.json"
API = "https://api.github.com/repos/ungoogled-software/{repo}/releases/latest"
#: Each platform: the release repo, and the suffix of the asset to take.
SOURCES = {
    "win64": ("ungoogled-chromium-windows", "_windows_x64.zip"),
    "mac-x64": ("ungoogled-chromium-macos", "_x86_64-macos.dmg"),
    "mac-arm64": ("ungoogled-chromium-macos", "_arm64-macos.dmg"),
}


def latest_release(repo: str) -> dict:
    # curl (net.fetch), as the other build scripts do: it uses the system's
    # certificates, where Python's own may not be set up.
    return json.loads(fetch(API.format(repo=repo)))


def asset_for(release: dict, suffix: str) -> dict:
    for asset in release["assets"]:
        if asset["name"].endswith(suffix):
            digest = asset.get("digest", "")
            if not digest.startswith("sha256:"):
                raise SystemExit(f"{asset['name']} has no sha256 digest from GitHub; cannot pin without downloading.")
            return {"url": asset["browser_download_url"], "sha256": digest.split(":", 1)[1]}
    raise SystemExit(f"No asset ending in {suffix!r} in {release['tag_name']}.")


def repin() -> str:
    releases: dict[str, dict] = {}
    builds = {}
    version = None
    for platform, (repo, suffix) in SOURCES.items():
        if repo not in releases:
            releases[repo] = latest_release(repo)
        tag = releases[repo]["tag_name"]
        version = version or tag
        if tag != version:
            print(f"::warning::{repo} is {tag}, not {version}; the platforms are out of step.")
        builds[platform] = asset_for(releases[repo], suffix)

    info = json.loads(PIN.read_text())
    was = info.get("version")
    info["version"] = version
    info["builds"] = builds
    PIN.write_text(json.dumps(info, indent=2) + "\n")
    print(f"chromium.json: ungoogled-chromium {version}" + (f" (was {was})" if was and was != version else ""))
    for platform, build in builds.items():
        print(f"  {platform:10} {build['sha256']}")
    return version


def main(argv: list[str]) -> int:
    if "--check" in argv:
        pinned = json.loads(PIN.read_text()).get("version") or "(none)"
        newest = latest_release("ungoogled-chromium-windows")["tag_name"]
        print(f"pinned: {pinned}\nnewest: {newest}")
        return 0 if pinned == newest else 1
    repin()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
