"""Build Orbit Browser by repacking ungoogled-chromium.

    python3 scripts/build.py                       # the host's default (Mac on a Mac, else Windows)
    python3 scripts/build.py --platform win64
    python3 scripts/build.py --platform mac-arm64 --platform mac-x64

Orbit Browser *repacks* a prebuilt Chromium rather than compiling it: it
downloads the ungoogled-chromium build chromium.json pins (checking its
SHA-256), unpacks it, and changes what can be changed without a compiler — the
app's name and icon, the enterprise policies and the first-run preferences. That
keeps builds small and fast (minutes on a standard GitHub runner), the trade for
a source fork's deeper reach. Orbit Pass is not bundled: it is force-installed by
policy from Orbit Mission Control (distribution/policies/orbit.json).

ungoogled-chromium already has Google's web services, sign-in and reporting
removed; Orbit's policies (distribution/) lock the rest off and put Orbit's
services in their place.

What a repack cannot do (it would need the source): rename "Chromium" in the
compiled UI strings, add the Orbit toolbar button / Orbit AI side panel as
built-in UI (these ship as a force-installed Orbit extension instead), or embed
an in-app self-updater. Orbit Browser's name and icon are set at the app-bundle
level; its behaviour comes from policy and extensions.

Orbit Browser has its own version (orbit_config.VERSION), apart from the
Chromium it is built on (chromium.json).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import orbit_config as cfg  # noqa: E402
from net import download  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "chromium"
WORK = ROOT / "work"
DIST = ROOT / "dist"
BRANDING = ROOT / "branding"
#: ungoogled-chromium ships official Windows and macOS builds only; there is no
#: official generic Linux binary, so Orbit Browser's repack does not build Linux.
PLATFORMS = ("win64", "mac-x64", "mac-arm64")
#: How a platform names itself for Mission Control's update feed (target, arch, os).
UPDATE_TARGET = {
    "win64": ("windows", "x86_64", "windows"),
    "mac-x64": ("darwin", "x86_64", "mac"),
    "mac-arm64": ("darwin", "aarch64", "mac"),
}


def log(message: str) -> None:
    print(f"==> {message}", flush=True)


def run(*args, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def pin() -> dict:
    return json.loads((ROOT / "chromium.json").read_text())


# -- fetching ungoogled-chromium ----------------------------------------------------------


def fetch_chromium(platform: str) -> Path:
    info = pin()
    build = info["builds"][platform]
    if not info.get("version") or not build.get("url") or not build.get("sha256"):
        raise SystemExit(
            f"chromium.json has no pinned build for {platform}. "
            "Run `python3 scripts/update_chromium.py` to pin the latest ungoogled-chromium and its checksums."
        )
    target = CACHE / info["version"] / Path(build["url"]).name
    if not target.exists() or sha256(target) != build["sha256"]:
        log(f"Downloading ungoogled-chromium {info['version']} ({platform})")
        download(build["url"], target)
    digest = sha256(target)
    if digest != build["sha256"]:
        target.unlink()
        raise SystemExit(f"{target.name}: SHA-256 {digest} is not the one chromium.json pins. Download deleted.")
    return target


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# -- shared staging -----------------------------------------------------------------------


def stage_initial_preferences(dest: Path) -> None:
    """Chromium's first-run defaults, inside the app. The locked policy
    (distribution/policies/) is placed by the installer at the OS managed-policy
    location (distribution/README.md), which a repack cannot write from here."""
    (dest / "initial_preferences").write_text((ROOT / "distribution" / "initial_preferences").read_text())


def stage_policy_file(package_dir: Path) -> None:
    """Ship the locked policy in the package so the installer can place it. Kept
    beside the app as orbit-policy.json; the installer copies it to the managed
    location (Linux /etc/..., Windows registry, macOS managed prefs)."""
    shutil.copyfile(ROOT / "distribution" / "policies" / "orbit.json", package_dir / "orbit-policy.json")


# Orbit Pass is not bundled into the app: it is force-installed and un-removable
# by policy (distribution/policies/orbit.json -> ExtensionSettings), served from
# Orbit Mission Control at runtime. That is the standard Chromium way to ship a
# built-in extension, and it needs no Chrome packaging step at build time.


# -- macOS --------------------------------------------------------------------------------


def build_mac(args, platform: str, version: str) -> list[Path]:
    if sys.platform != "darwin":
        raise SystemExit("The Mac app is repacked on macOS (hdiutil).")
    dmg = fetch_chromium(platform)
    work = args.work / platform
    reset_dir(work)
    app = work / f"{cfg.APP_NAME}.app"
    log("Unpacking ungoogled-chromium")
    with tempfile.TemporaryDirectory() as mount:
        run("hdiutil", "attach", "-nobrowse", "-readonly", "-noautoopen", "-mountpoint", mount, dmg, stdout=subprocess.DEVNULL)
        try:
            src_app = next(Path(mount).glob("*.app"))
            run("ditto", src_app, app)
        finally:
            run("hdiutil", "detach", mount, "-quiet")

    log("Rebranding")
    rename_mac_bundle(app / "Contents", version)
    resources = app / "Contents" / "Resources"
    # Chromium's app and document icons are app.icns and document.icns; replace
    # each in place with Orbit's (match by exact name, so the app icon and the
    # document icon never cross over).
    for icon in ("app.icns", "document.icns"):
        source = BRANDING / "mac" / icon
        target = resources / icon
        if source.exists() and target.exists():
            shutil.copyfile(source, target)
    stage_initial_preferences(resources)

    if args.sign:
        log("Signing")
        run("codesign", "--force", "--deep", "--timestamp", "--options", "runtime", "--sign", args.sign, app)
        run("codesign", "--verify", "--strict", "--deep", app)

    DIST.mkdir(exist_ok=True)
    arch = "Intel" if platform == "mac-x64" else "AppleSilicon"
    out = DIST / f"Orbit-Browser-{version}-macOS-{arch}.dmg"
    make_dmg(app, out, args.sign)
    payload = DIST / f"Orbit-Browser-{version}-macOS-{arch}.app.tar.gz"
    run("tar", "--no-mac-metadata", "-czf", payload, "-C", work, app.name)
    stage_policy_file(DIST)
    return [out, payload]


def rename_mac_bundle(contents: Path, version: str) -> None:
    info_path = contents / "Info.plist"
    info = plistlib.loads(info_path.read_bytes())
    info.update({
        "CFBundleName": cfg.APP_NAME,
        "CFBundleDisplayName": cfg.APP_NAME,
        "CFBundleIdentifier": cfg.MAC_BUNDLE_ID,
        "CFBundleShortVersionString": version,
    })
    info_path.write_bytes(plistlib.dumps(info))


def make_dmg(app: Path, out: Path, sign: str | None) -> None:
    log("Making the disk image")
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / cfg.APP_NAME
        stage.mkdir()
        run("ditto", app, stage / app.name)
        (stage / "Applications").symlink_to("/Applications")
        if out.exists():
            out.unlink()
        run("hdiutil", "create", "-quiet", "-volname", cfg.APP_NAME, "-srcfolder", stage, "-format", "UDZO", "-fs", "HFS+", out)
    if sign:
        run("codesign", "--force", "--timestamp", "--sign", sign, out)


# -- Windows ------------------------------------------------------------------------------


def build_windows(args, platform: str, version: str) -> list[Path]:
    archive = fetch_chromium(platform)
    work = args.work / platform
    reset_dir(work)
    log("Unpacking ungoogled-chromium")
    with zipfile.ZipFile(archive) as z:
        z.extractall(work)
    inner = _single_dir(work)
    app = work / cfg.APP_NAME
    inner.rename(app)

    log("Rebranding")
    stage_initial_preferences(app)

    DIST.mkdir(exist_ok=True)
    portable = DIST / f"Orbit-Browser-{version}-Windows-x64.zip"
    if portable.exists():
        portable.unlink()
    with zipfile.ZipFile(portable, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(app.rglob("*")):
            if path.is_file():
                z.write(path, Path(cfg.APP_NAME) / path.relative_to(app))
    stage_policy_file(DIST)
    # The installer (which writes the HKLM policy and the Start-menu entry) is
    # out of scope of the repack itself; the portable zip is the artifact.
    return [portable]


# -- helpers ------------------------------------------------------------------------------


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _single_dir(parent: Path) -> Path:
    dirs = [p for p in parent.iterdir() if p.is_dir()]
    if len(dirs) != 1:
        raise SystemExit(f"Expected one directory in the unpacked build, found {[p.name for p in dirs]}.")
    return dirs[0]


# -----------------------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--platform", action="append", choices=PLATFORMS, help="repeatable")
    parser.add_argument("--build", type=int, default=0, help="the build number (CI's run number)")
    parser.add_argument("--release", action="store_true", help="a release: the version without -build.N")
    parser.add_argument("--sign", help="a Developer ID identity for the Mac app (ad hoc when left out)")
    parser.add_argument("--work", type=Path, default=WORK, help="where the unpacked builds go (default work/)")
    args = parser.parse_args(argv)
    args.work = args.work.resolve()

    if args.platform:
        platforms = args.platform
    elif sys.platform == "darwin":
        platforms = ["mac-arm64"]
    else:
        platforms = ["win64"]

    version = cfg.orbit_version(args.build, args.release)
    log(f"Orbit Browser {version} repacking ungoogled-chromium {pin().get('version') or '(unpinned)'}")
    outputs = []
    for platform in platforms:
        if platform.startswith("mac"):
            outputs += build_mac(args, platform, version)
        else:
            outputs += build_windows(args, platform, version)
    for out in outputs:
        print(out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
