"""Pin Orbit Browser to a Firefox release: write firefox.json.

    python3 scripts/update_firefox.py            # the newest release Mozilla ships
    python3 scripts/update_firefox.py 158.0      # a given one

firefox.json names the release and the SHA-512 of each build Orbit Browser is
made from, as Mozilla lists them in the release's SHA512SUMS. scripts/build.py
downloads only those files and refuses one whose checksum differs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from net import fetch

ROOT = Path(__file__).resolve().parent.parent
PIN = ROOT / "firefox.json"
VERSIONS = "https://product-details.mozilla.org/1.0/firefox_versions.json"
ARCHIVE = "https://archive.mozilla.org/pub/firefox/releases"

#: The builds Orbit Browser repacks, by platform: the path under the release
#: folder, with {v} for the version. Mac builds are universal (Apple silicon
#: and Intel); Windows has one per architecture.
BUILDS = {
    "mac": "mac/en-US/Firefox {v}.dmg",
    "win64": "win64/en-US/Firefox Setup {v}.exe",
    "win64-aarch64": "win64-aarch64/en-US/Firefox Setup {v}.exe",
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


def main(argv: list[str]) -> int:
    version = argv[0] if argv else latest()
    current = json.loads(PIN.read_text())["version"] if PIN.exists() else None
    PIN.write_text(json.dumps(pin(version), indent=2) + "\n")
    print(f"firefox.json: Firefox {version}" + (f" (was {current})" if current and current != version else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
