"""Build Orbit Browser from Mozilla's Firefox release.

    python3 scripts/build.py                          # the Mac app (on a Mac) or Windows x64
    python3 scripts/build.py --platform win64 --platform win64-aarch64
    python3 scripts/build.py --platform mac --sign "Developer ID Application: …"

Downloads the release firefox.json pins (checking Mozilla's SHA-512), and
makes Orbit Browser from it, in work/<platform>/ with the packages in dist/:

- the name and logo everywhere Firefox shows its own (branding/);
- Mozilla's AI features off and locked (distribution/policies.json) and the
  on-device inference libraries removed;
- Orbit AI as the only chatbot, in the sidebar and the menus;
- Orbit Pass built in, from the Orbit Pass checkout (--orbit-pass);
- Firefox's updater removed (it would install Mozilla's Firefox over Orbit
  Browser); OrbitBrowser.sys.mjs installs new Orbit Browsers instead.

Orbit Browser has its own version (VERSION below), apart from the Firefox
it is built on (firefox.json): 0.1.0 for a release, 0.1.0-build.N for a build
on main, 0.1.0-local here.

Mac builds need macOS (hdiutil, codesign). Windows builds run anywhere with
bsdtar (macOS's tar; libarchive-tools on Linux) and Node; the installer also
needs makensis (NSIS).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from net import download  # noqa: E402
import omni_patches  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
WORK = ROOT / "work"
DIST = ROOT / "dist"
BRANDING = ROOT / "branding"
PLATFORMS = ("mac", "win64", "win64-aarch64")
WINDOWS_ARCH = {"win64": "x64", "win64-aarch64": "arm64"}

APP_NAME = "Orbit Browser"
#: Orbit Browser's own version, as people see it and Orbit Mission Control
#: orders it; the Firefox it is built on is firefox.json's. Raise it for a
#: release (a v<VERSION> tag); builds on main are newer by build number alone,
#: so a new Firefox doesn't need one.
VERSION = "0.1.0"
BUNDLE_ID = "ai.com.orbit.browser"
#: Orbit Pass's ID, and the moz-extension:// address it has in every copy of
#: Orbit Browser (firefox-branding.js). Orbit Pass's server lists the same.
ORBIT_PASS_ID = "pass@orbit.com.ai"
ORBIT_PASS_UUID = "cabce947-8111-49e9-a61f-0224b07a4dfd"

#: The Orbit apps: in the toolbar's Orbit menu (OrbitBrowser.sys.mjs) and on
#: a new profile's bookmarks toolbar, in place of Mozilla's bookmarks. id is
#: the mark (branding/content/apps/<id>.svg); open, where the menu opens it
#: if not the address (Orbit Pass: its vault page, inside the browser).
ORBIT_APPS = [
    {"id": "ai", "name": "Orbit AI", "url": "https://ai.orbit.com.ai/"},
    {"id": "mail", "name": "Orbit Mail", "url": "https://mail.orbit.com.ai/"},
    {"id": "calendar", "name": "Orbit Calendar", "url": "https://mail.orbit.com.ai/calendar/"},
    {"id": "chat", "name": "Orbit Chat", "url": "https://chat.orbit.com.ai/"},
    {"id": "pass", "name": "Orbit Pass", "url": "https://pass.orbit.com.ai/vault/",
     "open": f"moz-extension://{ORBIT_PASS_UUID}/src/vault/vault.html"},
]

#: Native code that only Mozilla's on-device AI uses: llama.cpp and the
#: speech model (mozinference) and ONNX Runtime. Nothing loads them with the
#: AI features off; Orbit Browser doesn't ship them at all.
AI_LIBRARIES = {
    "mac": ["Contents/MacOS/libmozinference.dylib", "Contents/MacOS/libonnxruntime.dylib"],
    "windows": ["mozinference.dll", "onnxruntime.dll"],
}

#: Firefox's updater and what serves it. Left in, it would replace Orbit
#: Browser with Mozilla's Firefox at the next Firefox update.
UPDATER = {
    "mac": ["Contents/MacOS/updater.app", "Contents/Library/LaunchServices"],
    "windows": [
        "updater.exe",
        "maintenanceservice.exe",
        "maintenanceservice_installer.exe",
        # Re-installs Mozilla's Firefox from a desktop shortcut.
        "desktop-launcher",
        # Firefox's scheduled task that nags about the default browser.
        "default-browser-agent.exe",
    ],
}

#: Entitlements of Mozilla's main executable that Orbit Browser can't keep:
#: the application identifier names Mozilla's team, and passkeys through the
#: system need a provisioning profile Apple grants per browser.
DROPPED_ENTITLEMENTS = {
    "com.apple.application-identifier",
    "com.apple.developer.team-identifier",
    "com.apple.developer.web-browser.public-key-credential",
}


def log(message: str) -> None:
    print(f"==> {message}", flush=True)


def run(*args, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


# -- versions -------------------------------------------------------------------------


def firefox_pin() -> dict:
    return json.loads((ROOT / "firefox.json").read_text())


def orbit_version(build: int, release: bool, base: str = VERSION) -> str:
    """Orbit Browser's version for this build: VERSION for a release,
    VERSION-build.N for a build on main, VERSION-local for one made here."""
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", base):
        raise SystemExit(f"VERSION {base!r} isn't a version of three numbers.")
    if release:
        return base
    return f"{base}-build.{build}" if build else f"{base}-local"


# -- fetching Firefox -------------------------------------------------------------------


def fetch_firefox(platform: str) -> Path:
    pin = firefox_pin()
    build = pin["builds"][platform]
    target = CACHE / "firefox" / pin["version"] / build["path"].replace("/", "_")
    if not target.exists() or sha512(target) != build["sha512"]:
        log(f"Downloading Firefox {pin['version']} ({platform})")
        download(pin["archive"] + build["path"].replace(" ", "%20"), target)
    digest = sha512(target)
    if digest != build["sha512"]:
        target.unlink()
        raise SystemExit(f"{build['path']}: SHA-512 {digest} is not the one Mozilla lists. Download deleted.")
    return target


def sha512(path: Path) -> str:
    h = hashlib.sha512()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# -- omni.ja --------------------------------------------------------------------------


class Jar:
    """An omni.ja, read whole, changed in memory and written back as a zip
    Firefox reads (deflated entries, no data descriptors)."""

    def __init__(self, path: Path):
        self.path = path
        self.entries = read_jar(path)

    def text(self, name: str) -> str:
        return self.entries[name].decode("utf-8")

    def replace(self, name: str, data: bytes | str) -> None:
        if name not in self.entries:
            raise SystemExit(f"{self.path.name} has no {name} to replace; has Firefox moved it?")
        self.entries[name] = data.encode("utf-8") if isinstance(data, str) else data

    def add(self, name: str, data: bytes | str) -> None:
        if name in self.entries:
            raise SystemExit(f"{self.path.name} already has {name}.")
        self.entries[name] = data.encode("utf-8") if isinstance(data, str) else data

    def put(self, name: str, data: bytes | str) -> None:
        self.entries[name] = data.encode("utf-8") if isinstance(data, str) else data

    def save(self) -> None:
        partial = self.path.with_suffix(".ja.part")
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for name, data in self.entries.items():
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, data)
        partial.replace(self.path)


def read_jar(path: Path) -> dict[str, bytes]:
    """The files in an omni.ja. Mozilla writes them "optimized": a 4-byte
    header, then the central directory, then the files, which Python's
    zipfile can't follow, so this reads it the way Firefox does, from the end
    of central directory record."""
    data = path.read_bytes()
    end = data.rfind(b"PK\x05\x06")
    if end < 0:
        raise SystemExit(f"{path} is not a zip.")
    count, _, offset = struct.unpack("<HII", data[end + 10:end + 20])
    entries = {}
    for _ in range(count):
        if data[offset:offset + 4] != b"PK\x01\x02":
            raise SystemExit(f"{path}: damaged central directory.")
        method, = struct.unpack("<H", data[offset + 10:offset + 12])
        crc, size = struct.unpack("<II", data[offset + 16:offset + 24])
        name_len, extra_len, comment_len = struct.unpack("<HHH", data[offset + 28:offset + 34])
        local, = struct.unpack("<I", data[offset + 42:offset + 46])
        name = data[offset + 46:offset + 46 + name_len].decode("utf-8")
        offset += 46 + name_len + extra_len + comment_len
        if data[local:local + 4] != b"PK\x03\x04":
            raise SystemExit(f"{path}: {name} has no local header.")
        local_name, local_extra = struct.unpack("<HH", data[local + 26:local + 30])
        start = local + 30 + local_name + local_extra
        raw = data[start:start + size]
        if method == 0:
            content = raw
        elif method == 8:
            content = zlib.decompress(raw, -15)
        else:
            raise SystemExit(f"{path}: {name} uses compression method {method}.")
        if zlib.crc32(content) != crc:
            raise SystemExit(f"{path}: {name} fails its checksum.")
        if not name.endswith("/"):
            entries[name] = content
    return entries


def orbit_pass_files(checkout: Path) -> dict[str, bytes]:
    """Orbit Pass's Firefox package, made by its own packager, as the files
    of a built-in add-on: privileged, so its host permissions are granted at
    install, and versioned by its contents so a changed Orbit Pass replaces
    the one a profile already has."""
    packager = checkout / "extension" / "scripts" / "package.mjs"
    if not packager.exists():
        raise SystemExit(f"No Orbit Pass at {checkout} (expected extension/scripts/package.mjs). Pass --orbit-pass.")
    with tempfile.TemporaryDirectory() as tmp:
        package = Path(tmp) / "orbit-pass-firefox.zip"
        run("node", packager, "--firefox", package, stdout=subprocess.DEVNULL)
        with zipfile.ZipFile(package) as z:
            files = {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}
    manifest = json.loads(files["manifest.json"])
    gecko_id = manifest.get("browser_specific_settings", {}).get("gecko", {}).get("id")
    if gecko_id != ORBIT_PASS_ID:
        raise SystemExit(f"Orbit Pass's Firefox package has the ID {gecko_id!r}, not {ORBIT_PASS_ID}.")
    content = zlib.crc32(b"".join(name.encode() + files[name] for name in sorted(files)))
    manifest["version"] = f"{manifest['version']}.{content % 100_000_000}"
    manifest["granted_host_permissions"] = True
    files["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    return files


def customize_omni(resources: Path, *, platform: str, version: str, build: int, orbit_pass: dict[str, bytes]) -> str:
    """Make browser/omni.ja and omni.ja Orbit Browser's. Returns the build's stamp."""
    browser = Jar(resources / "browser" / "omni.ja")
    gre = Jar(resources / "omni.ja")

    for patch in omni_patches.PATCHES:
        if platform not in patch.platforms:
            continue
        jar = browser if patch.jar == "browser" else gre
        try:
            jar.replace(patch.path, omni_patches.apply(patch, jar.text(patch.path)))
        except omni_patches.PatchError as error:
            raise SystemExit(str(error))

    for (jar_name, path), css in omni_patches.APPENDED_STYLES.items():
        jar = browser if jar_name == "browser" else gre
        jar.replace(path, jar.text(path) + css)

    branding = "chrome/browser/content/branding/"
    for source in sorted((BRANDING / "content").rglob("*")):
        if source.is_file():
            browser.put(branding + source.relative_to(BRANDING / "content").as_posix(), source.read_bytes())
    browser.replace("localization/en-US/branding/brand.ftl", (BRANDING / "locales" / "brand.ftl").read_bytes())
    browser.replace("chrome/en-US/locale/branding/brand.properties", (BRANDING / "locales" / "brand.properties").read_bytes())
    browser.replace("chrome/browser/skin/classic/browser/sidebar/firefox.svg", (BRANDING / "skin" / "sidebar-firefox.svg").read_bytes())
    browser.add("chrome/browser/skin/classic/browser/orbit-button.svg", (BRANDING / "skin" / "orbit-button.svg").read_bytes())
    browser.add("chrome/browser/content/browser/orbit-browser.css", (ROOT / "browser" / "content" / "orbit-browser.css").read_bytes())
    browser.replace("chrome/browser/content/browser/default-bookmarks.html", orbit_default_bookmarks())

    addon_root = "chrome/browser/builtin-addons/orbit-pass/"
    for name, data in orbit_pass.items():
        browser.add(addon_root + name, data)
    pass_version = json.loads(orbit_pass["manifest.json"])["version"]
    builtins = [{"id": ORBIT_PASS_ID, "version": pass_version, "url": "resource://builtin-addons/orbit-pass/"}]
    module = (ROOT / "browser" / "modules" / "OrbitBrowser.sys.mjs").read_text()
    module = module.replace("/* @BUILTIN_ADDONS@ */ []", json.dumps(builtins), 1)
    module = module.replace("/* @ORBIT_APPS@ */ []", json.dumps(ORBIT_APPS), 1)
    if "@BUILTIN_ADDONS@" in module or "@ORBIT_APPS@" in module:
        raise SystemExit("OrbitBrowser.sys.mjs has a placeholder the build doesn't fill.")
    browser.add("modules/OrbitBrowser.sys.mjs", module)
    # Its updates (as the other Orbit apps get them) and their signature check.
    for name in ("OrbitUpdates.sys.mjs", "OrbitSignature.sys.mjs"):
        browser.add(f"modules/{name}", (ROOT / "browser" / "modules" / name).read_bytes())
    browser.replace(
        "components/components.manifest",
        browser.text("components/components.manifest") + omni_patches.COMPONENT_CATEGORIES,
    )

    # The stamp covers everything this build put in, so it changes exactly
    # when Orbit Browser's own files do (OrbitBrowser.dropCachesFromOtherBuilds).
    h = hashlib.sha256(f"{version}/{build}".encode())
    for jar in (browser, gre):
        for name in sorted(jar.entries):
            h.update(name.encode() + b"\0" + jar.entries[name])
    stamp = h.hexdigest()[:16]
    prefs = (BRANDING / "firefox-branding.js").read_text()
    for key, value in {
        "@ORBIT_VERSION@": version,
        "@ORBIT_BUILD@": str(build),
        "@ORBIT_STAMP@": stamp,
        "@ORBIT_PASS_UUID@": ORBIT_PASS_UUID,
    }.items():
        prefs = prefs.replace(key, value)
    if re.search(r"@[A-Z_]+@", prefs):
        raise SystemExit("firefox-branding.js has a placeholder the build doesn't fill.")
    browser.replace("defaults/preferences/firefox-branding.js", prefs)

    browser.save()
    gre.save()
    return stamp


def orbit_default_bookmarks() -> str:
    """A new profile's bookmarks, in place of Firefox's "Mozilla Firefox"
    folder: the Orbit apps on the bookmarks toolbar, each with its mark."""
    import base64
    from html import escape

    rows = []
    for app in ORBIT_APPS:
        icon = base64.b64encode((BRANDING / "content" / "apps" / f"{app['id']}-32.png").read_bytes()).decode()
        rows.append(f'            <dt><a href="{escape(app["url"])}" icon="data:image/png;base64,{icon}">{escape(app["name"])}</a></dt>')
    return "\n".join([
        "<!-- This Source Code Form is subject to the terms of the Mozilla Public",
        "   - License, v. 2.0. If a copy of the MPL was not distributed with this",
        "   - file, You can obtain one at http://mozilla.org/MPL/2.0/. -->",
        "<!-- Orbit Browser's default bookmarks, written by scripts/build.py. -->",
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
        "<html>",
        "<head>",
        '    <meta charset="UTF-8">',
        "    <meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none';\">",
        "    <title>Bookmarks</title>",
        "</head>",
        "<body>",
        "<h1>Bookmarks</h1>",
        "<dl><p>",
        '    <dt><h3 PERSONAL_TOOLBAR_FOLDER="true">Bookmarks Toolbar</h3></dt>',
        "        <dl><p>",
        *rows,
        "        </dl><p>",
        "</dl>",
        "</body>",
        "</html>",
        "",
    ])


def write_policies(distribution: Path, platform: str) -> None:
    policies = json.loads((ROOT / "distribution" / "policies.json").read_text())
    if platform != "mac":
        # Firefox's own way of becoming the default browser on Windows
        # registers it under Firefox's name; the installer registers Orbit
        # Browser, and Windows' Default apps settings choose it.
        policies["policies"].update({
            "DisableDefaultBrowserAgent": True,
            "DefaultBrowserSettingEnabled": False,
            "DontCheckDefaultBrowser": True,
        })
    distribution.mkdir(parents=True, exist_ok=True)
    (distribution / "policies.json").write_text(json.dumps(policies, indent=2) + "\n")


def remove_ai_libraries(base: Path, platform: str) -> None:
    """The on-device AI libraries this build of Firefox has (not every one
    has each: Windows on Arm has no ONNX Runtime), and then a check that
    nothing else by those names is left."""
    found = [name for name in AI_LIBRARIES[platform] if (base / name).exists()]
    if not found:
        raise SystemExit("None of Firefox's AI libraries are where they were; have they moved? (scripts/build.py)")
    remove(base, found)
    folder = (base / AI_LIBRARIES[platform][0]).parent
    left = [p.name for p in folder.iterdir() if re.search(r"inference|onnx", p.name, re.I)]
    if left:
        raise SystemExit(f"Firefox has AI libraries the build doesn't know: {left} (scripts/build.py, AI_LIBRARIES)")


def remove(base: Path, relative: list[str]) -> None:
    for name in relative:
        target = base / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        else:
            raise SystemExit(f"Expected {name} in Firefox; has it moved? (scripts/build.py)")


# -- the Mac app ------------------------------------------------------------------------


def build_mac(args, version: str, orbit_pass: dict[str, bytes]) -> list[Path]:
    dmg = fetch_firefox("mac")
    work = args.work / "mac"
    app = work / f"{APP_NAME}.app"
    refuse_if_running(app)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    log("Unpacking Firefox.app")
    with tempfile.TemporaryDirectory() as mount:
        run("hdiutil", "attach", "-nobrowse", "-readonly", "-noautoopen", "-mountpoint", mount, dmg, stdout=subprocess.DEVNULL)
        try:
            run("ditto", Path(mount) / "Firefox.app", app)
        finally:
            run("hdiutil", "detach", mount, "-quiet")
    contents = app / "Contents"
    resources = contents / "Resources"
    entitlements = mozilla_entitlements(app)

    log("Rebranding and changing omni.ja")
    stamp = customize_omni(resources, platform="mac", version=version, build=args.build, orbit_pass=orbit_pass)
    write_policies(resources / "distribution", "mac")
    # Firefox's own icon for macOS 26 (Assets.car) and Mozilla's provisioning
    # profile (it names Mozilla's team) go too.
    remove_ai_libraries(app, "mac")
    remove(app, UPDATER["mac"] + ["Contents/Resources/Assets.car", "Contents/embedded.provisionprofile"])
    shutil.copyfile(BRANDING / "mac" / "firefox.icns", resources / "firefox.icns")
    shutil.copyfile(BRANDING / "mac" / "document.icns", resources / "document.icns")
    (resources / "browser" / "application.ini").write_text(orbit_application_ini((resources / "application.ini").read_text()))
    build_launcher(contents / "MacOS" / LAUNCHER)
    rename_mac_bundle(contents, version)

    log("Signing")
    sign_mac(app, entitlements, args.sign)
    register_mac_app(app)
    log("Making the disk image")
    DIST.mkdir(exist_ok=True)
    out = DIST / f"Orbit-Browser-{version}-macOS.dmg"
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / APP_NAME
        stage.mkdir()
        run("ditto", app, stage / app.name)
        (stage / "Applications").symlink_to("/Applications")
        if out.exists():
            out.unlink()
        run("hdiutil", "create", "-quiet", "-volname", APP_NAME, "-srcfolder", stage, "-format", "ULMO", "-fs", "HFS+", out)
    if args.sign:
        run("codesign", "--force", "--timestamp", "--sign", args.sign, out)
    # The update payload: the app alone, which an installed Orbit Browser
    # unpacks and puts in its own place (OrbitBrowser.sys.mjs), as the Tauri
    # apps' .app.tar.gz. No AppleDouble (._) files: the app's signature covers
    # everything in it.
    payload = DIST / f"Orbit-Browser-{version}-macOS.app.tar.gz"
    run("tar", "--no-mac-metadata", "-czf", payload, "-C", work, app.name)
    print(f"stamp {stamp}")
    return [out, payload]


#: The Mac app's executable, browser/launcher/orbit-browser.c: it starts the
#: engine (Contents/MacOS/firefox) with Orbit Browser's application.ini.
LAUNCHER = "orbit-browser"


def orbit_application_ini(firefox_ini: str) -> str:
    """The engine's application data, as Firefox's build wrote it, with Orbit
    Browser's own folders (~/Library/Application Support/Orbit Browser and
    ~/Library/Caches/Orbit Browser): Profile names them, while Name stays
    "Firefox", which the user agent and add-ons go by. Crash reports don't go
    to Mozilla, whose build this no longer is."""
    import configparser

    ini = configparser.ConfigParser(interpolation=None)
    ini.optionxform = str
    ini.read_string(firefox_ini)
    app = dict(ini["App"])
    app["RemotingName"] = "orbit-browser"
    app["Profile"] = APP_NAME
    out = ["; Orbit Browser's application data, written by scripts/build.py from Firefox's.", "; The launcher (Contents/MacOS/orbit-browser) hands it to the engine.", "[App]"]
    out += [f"{key}={value}" for key, value in app.items()]
    for section in ("Gecko", "XRE"):
        out += ["", f"[{section}]"] + [f"{key}={value}" for key, value in ini[section].items()]
    out += ["", "[Crash Reporter]", "Enabled=0", ""]
    return "\n".join(out)


def build_launcher(target: Path) -> None:
    run(
        "clang", "-O2", "-Wall", "-Werror", "-arch", "arm64", "-arch", "x86_64", "-mmacosx-version-min=10.15",
        "-o", target, ROOT / "browser" / "launcher" / "orbit-browser.c",
    )


def register_mac_app(app: Path) -> None:
    """Date the app now and tell Launch Services about it. ditto keeps the
    dates of Mozilla's Firefox.app, and macOS keeps an app's icon (in the
    Dock, as it launches) for as long as its date says it hasn't changed: a
    rebuilt Orbit Browser would show whatever icon macOS first saw there."""
    for path in (app, app / "Contents", app / "Contents" / "Info.plist", app / "Contents" / "Resources" / "firefox.icns"):
        os.utime(path)
    lsregister = Path("/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister")
    if lsregister.exists():
        subprocess.run([str(lsregister), "-f", str(app)], check=False)


def refuse_if_running(app: Path) -> None:
    """Replacing an app while it runs pulls its files from under it."""
    running = subprocess.run(["pgrep", "-f", str(app / "Contents" / "MacOS")], capture_output=True, text=True).stdout.split()
    if running:
        raise SystemExit(f"{app} is running. Quit it first, or build elsewhere with --work.")


def mozilla_entitlements(app: Path) -> dict:
    out = subprocess.run(["codesign", "-d", "--entitlements", "-", "--xml", str(app)], capture_output=True, check=True).stdout
    entitlements = plistlib.loads(out) if out.strip() else {}
    return {k: v for k, v in entitlements.items() if k not in DROPPED_ENTITLEMENTS}


def rename_mac_bundle(contents: Path, version: str) -> None:
    info_path = contents / "Info.plist"
    info = plistlib.loads(info_path.read_bytes())
    info.update({
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleGetInfoString": f"{APP_NAME} {version}",
        # Orbit Browser's version (Finder's Get Info); CFBundleVersion stays
        # Firefox's build, the engine's.
        "CFBundleShortVersionString": version,
        "CFBundleExecutable": LAUNCHER,
    })
    # Firefox's icon on macOS 26 lives in Assets.car (removed); the .icns is Orbit's.
    info.pop("CFBundleIconName", None)
    # Mozilla's privileged updater helpers, removed with the updater.
    info.pop("SMPrivilegedExecutables", None)
    for key, value in list(info.items()):
        if key.endswith("UsageDescription") and isinstance(value, str):
            info[key] = value.replace("Firefox", APP_NAME)
    info_path.write_bytes(plistlib.dumps(info))
    for strings in contents.glob("Resources/*.lproj/InfoPlist.strings"):
        raw = strings.read_bytes()
        encoding = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
        text = raw.decode(encoding)
        text = re.sub(r'CFBundleName = "[^"]*";', f'CFBundleName = "{APP_NAME}";', text)
        strings.write_bytes(text.encode(encoding))


def sign_mac(app: Path, entitlements: dict, identity: str | None, *, everything: bool | None = None) -> None:
    """Sign the engine (Contents/MacOS/firefox: the launcher becomes it, so it
    carries the entitlements, less the ones only Mozilla can hold) and the
    app itself again (its executable, Info.plist and resources changed).

    Ad hoc (no identity), Mozilla's own signatures on XUL, the libraries and
    the helper apps stay as they are. With a Developer ID (or everything=True)
    all the code inside is signed again, innermost first, each helper app
    keeping its own entitlements: notarization only accepts an app whose code
    is all the team's."""
    def sign(path: Path, ents: dict | None = None, *extra: str) -> None:
        args = ["codesign", "--force", "--sign", identity or "-", "--options", "runtime"]
        if identity:
            args.append("--timestamp")
        with tempfile.NamedTemporaryFile(suffix=".plist", delete=False) as f:
            f.write(plistlib.dumps(ents or {}))
        try:
            run(*args, *(["--entitlements", f.name] if ents else []), *extra, path)
        finally:
            os.unlink(f.name)

    contents = app / "Contents"
    if identity if everything is None else everything:
        helpers = list(contents.rglob("*.app"))
        for path in sorted(contents.rglob("*")):
            if (path.is_file() and not path.is_symlink() and path.name not in ("firefox", LAUNCHER)
                    and not any(helper in path.parents for helper in helpers) and is_macho(path)):
                sign(path)
        for helper in sorted(helpers, key=lambda p: -len(p.parts)):
            sign(helper, mozilla_entitlements(helper))
    sign(contents / "MacOS" / "firefox", entitlements, "--identifier", f"{BUNDLE_ID}.engine")
    sign(app, entitlements)
    run("codesign", "--verify", "--strict", "--deep", app)


def is_macho(path: Path) -> bool:
    with path.open("rb") as f:
        magic = f.read(4)
    return magic in (b"\xca\xfe\xba\xbe", b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf")


# -- Windows ------------------------------------------------------------------------------


def build_windows(args, platform: str, version: str, orbit_pass: dict[str, bytes]) -> list[Path]:
    installer = fetch_firefox(platform)
    arch = WINDOWS_ARCH[platform]
    work = args.work / platform
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    log(f"Unpacking Firefox for Windows ({arch})")
    # The installer is 7-Zip's self-extractor in front of a 7z archive.
    data = installer.read_bytes()
    start = data.find(b"7z\xbc\xaf\x27\x1c")
    if start < 0:
        raise SystemExit(f"{installer.name} doesn't hold a 7z archive.")
    archive = work / "payload.7z"
    archive.write_bytes(data[start:])
    run(bsdtar(), "-xf", archive, "-C", work, "core")
    archive.unlink()
    app = work / APP_NAME
    (work / "core").rename(app)

    log("Rebranding and changing omni.ja")
    stamp = customize_omni(app, platform="windows", version=version, build=args.build, orbit_pass=orbit_pass)
    write_policies(app / "distribution", platform)
    remove_ai_libraries(app, "windows")
    remove(app, UPDATER["windows"])
    windows = BRANDING / "windows"
    for name in ("VisualElements_150.png", "VisualElements_70.png", "PrivateBrowsing_150.png", "PrivateBrowsing_70.png"):
        shutil.copyfile(windows / name, app / "browser" / "VisualElements" / name)
    tile_colour = (windows / "tile-colour.txt").read_text().strip()
    for manifest, colour, text in (("firefox", tile_colour, "light"), ("private_browsing", "#16181d", "light")):
        path = app / f"{manifest}.VisualElementsManifest.xml"
        xml = path.read_text()
        xml = re.sub(r"BackgroundColor='[^']*'", f"BackgroundColor='{colour}'", xml)
        xml = re.sub(r"ForegroundText='[^']*'", f"ForegroundText='{text}'", xml)
        path.write_text(xml)

    log("Icons and details of the executables")
    run("node", ROOT / "scripts" / "win_resources.mjs", app, version, cwd=ROOT)

    DIST.mkdir(exist_ok=True)
    outputs = []
    portable = DIST / f"Orbit-Browser-{version}-Windows-{arch}.zip"
    if portable.exists():
        portable.unlink()
    with zipfile.ZipFile(portable, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(app.rglob("*")):
            if path.is_file():
                z.write(path, Path(APP_NAME) / path.relative_to(app))
    outputs.append(portable)
    makensis = shutil.which("makensis")
    if makensis:
        log("Making the installer")
        setup = DIST / f"Orbit-Browser-{version}-Windows-{arch}-Setup.exe"
        run(
            makensis, "-V2", "-INPUTCHARSET", "UTF8",
            f"-DVERSION={version}", f"-DARCH={arch}", f"-DSOURCE={app}", f"-DOUTFILE={setup}",
            f"-DICON={windows / 'firefox.ico'}",
            "-DFILEVERSION=" + ".".join((re.findall(r"\d+", version.split("-")[0]) + ["0"] * 4)[:3] + [str(args.build)]),
            ROOT / "installer" / "windows" / "OrbitBrowser.nsi",
        )
        outputs.append(setup)
    else:
        print("makensis not found: made the zip only (install NSIS for the installer).")
    print(f"stamp {stamp}")
    return outputs


def bsdtar() -> str:
    for name in ("bsdtar", "tar"):
        path = shutil.which(name)
        if path and "bsdtar" in subprocess.run([path, "--version"], capture_output=True, text=True).stdout:
            return path
    raise SystemExit("Unpacking Firefox for Windows needs bsdtar (libarchive-tools on Linux).")


# -------------------------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--platform", action="append", choices=PLATFORMS, help="mac, win64 or win64-aarch64 (repeatable)")
    parser.add_argument("--orbit-pass", type=Path, default=ROOT.parent / "Orbit Pass", help="the Orbit Pass checkout")
    parser.add_argument("--build", type=int, default=0, help="the build number (CI's run number)")
    parser.add_argument("--release", action="store_true", help="a release: the version without -build.N")
    parser.add_argument("--sign", help="a Developer ID identity for the Mac app (ad hoc when left out)")
    parser.add_argument("--work", type=Path, default=WORK, help="where the unpacked builds go (default work/)")
    args = parser.parse_args(argv)
    args.work = args.work.resolve()
    platforms = args.platform or (["mac"] if sys.platform == "darwin" else ["win64"])

    firefox = firefox_pin()["version"]
    version = orbit_version(args.build, args.release)
    log(f"Orbit Browser {version} on Firefox {firefox}")
    orbit_pass = orbit_pass_files(args.orbit_pass.resolve())
    outputs = []
    for platform in platforms:
        if platform == "mac":
            if sys.platform != "darwin":
                raise SystemExit("The Mac app is built on macOS.")
            outputs += build_mac(args, version, orbit_pass)
        else:
            outputs += build_windows(args, platform, version, orbit_pass)
    for out in outputs:
        print(out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
