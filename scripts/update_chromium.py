"""Pin the ungoogled-chromium build Orbit Browser repacks.

    python3 scripts/update_chromium.py                         # show the newest version and what to pass
    python3 scripts/update_chromium.py 141.0.7390.65-1 \\
        --url win64=https://.../ungoogled-chromium_..._windows_x64.zip \\
        --url mac-x64=https://.../ungoogled-chromium_..._x86-64-macos.dmg \\
        --url mac-arm64=https://.../ungoogled-chromium_..._arm64-macos.dmg \\
        --url linux=https://.../ungoogled-chromium_..._linux.tar.xz

chromium.json pins the version and, per platform, the download URL and its
SHA-256. ungoogled-chromium's binaries are built and hosted by its contributors
(linked from https://ungoogled-software.github.io/ungoogled-chromium-binaries/),
so the URLs differ per platform and version and are passed in; this downloads
each, computes its SHA-256, and writes chromium.json. scripts/build.py then
refuses any download whose checksum differs.

With no version it prints the newest ungoogled-chromium release tag, so you can
fetch that version's URLs from the binaries page and pass them back.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build  # noqa: E402
from net import download  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PIN = ROOT / "chromium.json"
TAGS = "https://api.github.com/repos/ungoogled-software/ungoogled-chromium/tags"
PLATFORMS = ("win64", "mac-x64", "mac-arm64", "linux")


def latest() -> str:
    req = urllib.request.Request(TAGS, headers={"Accept": "application/vnd.github+json", "User-Agent": "Orbit Browser build"})
    with urllib.request.urlopen(req, timeout=60) as response:
        tags = json.loads(response.read())
    if not tags:
        raise SystemExit("No ungoogled-chromium tags found.")
    return tags[0]["name"]


def pin_version(version: str, urls: dict[str, str]) -> None:
    info = json.loads(PIN.read_text())
    info["version"] = version
    with tempfile.TemporaryDirectory() as tmp:
        for platform, url in urls.items():
            target = Path(tmp) / Path(url).name
            print(f"Downloading {platform}: {url}")
            download(url, target)
            digest = build.sha256(target)
            info["builds"][platform] = {"url": url, "sha256": digest}
            print(f"  sha256 {digest}")
    PIN.write_text(json.dumps(info, indent=2) + "\n")
    print(f"chromium.json: ungoogled-chromium {version} ({', '.join(urls)})")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("version", nargs="?", help="the ungoogled-chromium version to pin")
    parser.add_argument("--url", action="append", default=[], metavar="PLATFORM=URL",
                        help="a download URL for a platform (repeatable)")
    args = parser.parse_args(argv)

    if not args.version:
        print(f"Newest ungoogled-chromium: {latest()}")
        print("Get this version's per-platform download URLs from")
        print("  https://ungoogled-software.github.io/ungoogled-chromium-binaries/")
        print("and re-run with the version and --url PLATFORM=URL for each of:", ", ".join(PLATFORMS))
        return 0

    urls = {}
    for item in args.url:
        platform, _, url = item.partition("=")
        if platform not in PLATFORMS or not url:
            parser.error(f"--url must be PLATFORM=URL with PLATFORM in {PLATFORMS}: got {item!r}")
        urls[platform] = url
    missing = [p for p in PLATFORMS if p not in urls]
    if missing:
        parser.error(f"missing --url for: {', '.join(missing)}")
    pin_version(args.version, urls)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
