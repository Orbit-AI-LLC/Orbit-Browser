"""The build against the pinned Firefox: every change still lands.

    python3 -m unittest discover -s tests

Reads Firefox's own omni.ja files from the pinned Windows x64 installer
(downloaded into .cache/ the first time, checked against Mozilla's SHA-512;
any platform can unpack it) and checks that each patch in patches/ still
applies, that the files the build replaces are still there, and that every policy and
locked pref in distribution/policies.json is one this Firefox knows. A new
Firefox that moves any of these fails here, by name, before a build ships
without it.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build  # noqa: E402
import omni_patches  # noqa: E402
import sign_update  # noqa: E402

_JARS: dict = {}


def firefox_jars() -> dict:
    """browser/omni.ja and omni.ja of the pinned Firefox, read once."""
    if not _JARS:
        _JARS.update(build.read_jars("win64"))
    return _JARS


class PatchTests(unittest.TestCase):
    def test_every_patch_applies_to_this_firefox(self):
        """Each patches/**/*.patch still applies with git apply (context and
        all); a new Firefox that moved the code fails here, by name."""
        jars = firefox_jars()
        patches = omni_patches.load_patches()
        self.assertTrue(patches, "no patches found under patches/")
        # The pinned Windows build: patches for the Mac alone are checked by the Mac build.
        for patch in (p for p in patches if "windows" in p.platforms):
            with self.subTest(patch=str(patch.file.relative_to(ROOT)), why=patch.why):
                self.assertIn(patch.path, jars[patch.jar])
                omni_patches.git_apply(patch, jars[patch.jar][patch.path].decode())

    def test_every_generated_edit_applies_to_this_firefox(self):
        """The edits built from Orbit's data (the Orbit AI provider, the
        wallpapers) still find their anchor exactly once."""
        jars = firefox_jars()
        for generated in omni_patches.GENERATED:
            with self.subTest(edit=f"{generated.jar}:{generated.path}", why=generated.why):
                self.assertIn(generated.path, jars[generated.jar])
                omni_patches.apply_generated(generated, jars[generated.jar][generated.path].decode())

    def test_the_appended_stylesheets_are_still_there(self):
        jars = firefox_jars()
        for (jar, path) in omni_patches.APPENDED_STYLES:
            with self.subTest(path=path):
                self.assertIn(path, jars[jar])

    def test_the_files_the_build_replaces_are_still_there(self):
        browser = firefox_jars()["browser"]
        for name in (
            "localization/en-US/branding/brand.ftl",
            "chrome/en-US/locale/branding/brand.properties",
            "defaults/preferences/firefox-branding.js",
            "chrome/browser/skin/classic/browser/sidebar/firefox.svg",
            "components/components.manifest",
            "chrome/browser/content/branding/about-logo.png",
            "chrome/browser/content/branding/about-wordmark.svg",
        ):
            with self.subTest(name=name):
                self.assertIn(name, browser)

    def test_start_up_categories_and_built_in_add_ons_work_as_relied_on(self):
        browser = firefox_jars()["browser"]
        manifest = browser["components/components.manifest"].decode()
        # The way Orbit Browser's module is called is the way Firefox calls its own.
        self.assertIn("category browser-before-ui-startup resource:///modules/BuiltInThemes.sys.mjs", manifest)
        self.assertIn("category browser-idle-startup", manifest + browser["modules/BrowserGlue.sys.mjs"].decode())
        self.assertIn("resource builtin-addons browser/builtin-addons/", browser["chrome/chrome.manifest"].decode())
        for name in ("OrbitBrowser", "OrbitUpdates", "OrbitSignature"):
            self.assertNotIn(f"modules/{name}.sys.mjs", browser)
        self.assertFalse(any(name.startswith("chrome/browser/builtin-addons/orbit-pass/") for name in browser))
        xpi = firefox_jars()["gre"]["modules/addons/XPIProvider.sys.mjs"].decode()
        self.assertIn("async maybeInstallBuiltinAddon(aID, aVersion, aBase)", xpi)


class WallpaperTests(unittest.TestCase):
    FOLDER = ROOT / "branding" / "content" / "wallpapers"

    def test_every_wallpaper_is_drawn_and_nothing_else(self):
        """scripts/wallpapers.swift draws each one and its picker thumbnail."""
        wallpapers = omni_patches.ORBIT_WALLPAPERS
        self.assertEqual(len({w["title"] for w in wallpapers}), len(wallpapers))
        offered = {f"{w['file']}{end}" for w in wallpapers for end in (".jpg", "-thumb.jpg")}
        self.assertEqual({p.name for p in self.FOLDER.iterdir()}, offered)
        for w in wallpapers:
            with self.subTest(wallpaper=w["title"]):
                self.assertIn(w["theme"], ("dark", "light"))
                self.assertTrue(w["title"].startswith("orbit-"))

    def test_no_mozilla_wallpaper_shares_a_name(self):
        """A person's choice is kept by name; one of Mozilla's with the same name would take its place."""
        records = json.loads(firefox_jars()["browser"]["defaults/settings/main/newtab-wallpapers-v2.json"])["data"]
        self.assertFalse({r["title"] for r in records} & {w["title"] for w in omni_patches.ORBIT_WALLPAPERS})

    def test_the_new_tab_can_load_them(self):
        browser = firefox_jars()["browser"]
        # chrome://branding/content/ is branding/content/, and the page's policy allows chrome: images.
        self.assertIn("content branding browser/content/branding/ contentaccessible=yes", browser["chrome/chrome.manifest"].decode())
        page = browser["chrome/browser/builtin-addons/newtab/prerendered/activity-stream.html"].decode()
        self.assertIn("chrome:", re.search(r"img-src ([^;]*);", page).group(1).split())

    def test_the_built_in_new_tab_stays(self):
        """The patches change the built-in new tab; Mozilla's train-hop copy would bring Firefox's wallpapers back."""
        mapping = firefox_jars()["browser"]["modules/AboutNewTabResourceMapping.sys.mjs"].decode()
        self.assertIn('"browser.newtabpage.disableNewTabAsAddon"', mapping)
        prefs = (ROOT / "branding" / "firefox-branding.js").read_text()
        self.assertIn('pref("browser.newtabpage.disableNewTabAsAddon", true);', prefs)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.policies = json.loads((ROOT / "distribution" / "policies.json").read_text())["policies"]

    def test_every_policy_is_one_this_firefox_has(self):
        """In the schema and implemented: a policy can outlive its feature in
        the schema (DisablePocket did) and then quietly does nothing."""
        browser = firefox_jars()["browser"]
        schema = json.loads(browser["modules/policies/policies-schema.json"])["properties"]
        code = browser["modules/policies/Policies.sys.mjs"].decode()
        for name in list(self.policies) + ["DisableDefaultBrowserAgent", "DefaultBrowserSettingEnabled", "DontCheckDefaultBrowser"]:
            with self.subTest(policy=name):
                self.assertIn(name, schema)
                self.assertIn(f"\n  {name}: {{", code)
        for name in self.policies["AIControls"]:
            with self.subTest(ai_control=name):
                self.assertIn(name, schema["AIControls"]["properties"])

    def test_every_locked_pref_exists_in_this_firefox(self):
        """Named in Firefox's prefs files or read by its code (some prefs, such
        as browser.ml.chat.providers, take their default from the code)."""
        known = set()
        for jar in firefox_jars().values():
            for name, data in jar.items():
                if name.endswith((".js", ".mjs", ".json")):
                    known.update(re.findall(r'"([a-z][\w.-]*\.[\w.-]+)"', data.decode(errors="ignore")))
        for name in self.policies["Preferences"]:
            short = name.removeprefix("browser.newtabpage.activity-stream.")
            with self.subTest(pref=name):
                self.assertTrue(name in known or short in known, f"{name} isn't in this Firefox")

    def test_orbit_ai_is_the_locked_provider(self):
        prefs = self.policies["Preferences"]
        self.assertEqual(prefs["browser.ml.chat.provider"]["Value"], omni_patches.ORBIT_AI_URL)
        self.assertEqual(self.policies["AIControls"]["Default"], {"Value": "blocked", "Locked": True})
        self.assertEqual(self.policies["AIControls"]["SidebarChatbot"]["Value"], "available")


class VersionTests(unittest.TestCase):
    def test_orbit_browser_has_its_own_version(self):
        """Not Firefox's: VERSION, with -build.N on main and -local here."""
        self.assertRegex(build.VERSION, r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
        self.assertNotEqual(build.VERSION, build.firefox_pin()["version"])
        self.assertEqual(build.orbit_version(0, False, "0.1.0"), "0.1.0-local")
        self.assertEqual(build.orbit_version(12, False, "0.1.0"), "0.1.0-build.12")
        self.assertEqual(build.orbit_version(12, True, "0.1.0"), "0.1.0")
        with self.assertRaises(SystemExit):
            build.orbit_version(12, True, "157.0")

    def test_application_ini_keeps_the_engine_and_moves_the_data(self):
        firefox = "[App]\nVendor=Mozilla\nName=Firefox\nRemotingName=firefox\nVersion=157.0.1\nBuildID=1\nID={ec8030f7-c20a-464f-9b0e-13a3a9e97384}\n\n[Gecko]\nMinVersion=157.0.1\nMaxVersion=157.0.1\n\n[XRE]\nEnableProfileMigrator=1\n\n[Crash Reporter]\nEnabled=1\nServerURL=https://crash-reports.mozilla.com/\n\n[AppUpdate]\nURL=https://aus5.mozilla.org/\n"
        ini = build.orbit_application_ini(firefox)
        self.assertIn("Name=Firefox\n", ini)
        self.assertIn("Profile=Orbit Browser\n", ini)
        self.assertIn("RemotingName=orbit-browser\n", ini)
        self.assertIn("[Crash Reporter]\nEnabled=0", ini)
        self.assertNotIn("AppUpdate", ini)
        self.assertNotIn("mozilla.com", ini)


FIXTURES = ROOT / "tests" / "fixtures"


class UpdateSignatureTests(unittest.TestCase):
    """Updates are signed as the Tauri apps' are (scripts/sign_update.py) and
    checked by the browser's own code (OrbitSignature.sys.mjs, run under Node
    by tests/verify_signature.mjs). fixtures/ holds a throwaway key, with the
    password below, and a file the Tauri CLI signed with it."""

    PASSWORD = "orbit-browser-tests"

    def setUp(self):
        self.public_key = (FIXTURES / "update-test.key.pub").read_text().strip()
        self.key_id, self.seed = sign_update.load_secret_key((FIXTURES / "update-test.key").read_text(), self.PASSWORD)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def browser_verifies(self, payload: Path, signature: str) -> dict | str:
        """The trusted comment's fields, as the browser reads them, or its error message."""
        sig = self.tmp / "signature"
        sig.write_text(signature)
        out = subprocess.run(
            ["node", ROOT / "tests" / "verify_signature.mjs", "verify", payload, sig, self.public_key],
            capture_output=True, text=True,
        )
        return json.loads(out.stdout) if out.returncode == 0 else out.stdout.strip()

    def test_the_build_signs_what_the_browser_accepts(self):
        payload = self.tmp / "Orbit-Browser-0.1.0-build.3-macOS.app.tar.gz"
        payload.write_bytes(bytes(range(256)) * 1000 + b"end")
        signature = sign_update.sign(payload, "0.1.0-build.3", self.key_id, self.seed)
        fields = sign_update.verify(payload, signature, self.public_key)
        self.assertEqual((fields["version"], fields["file"]), ("0.1.0-build.3", payload.name))
        if shutil.which("node"):
            self.assertEqual(self.browser_verifies(payload, signature)["version"], "0.1.0-build.3")

    def test_a_changed_download_is_refused(self):
        payload = self.tmp / "payload"
        payload.write_bytes(b"x" * 5000)
        signature = sign_update.sign(payload, "0.1.0", self.key_id, self.seed)
        payload.write_bytes(b"x" * 4999 + b"y")
        with self.assertRaises(sign_update.SignatureError):
            sign_update.verify(payload, signature, self.public_key)
        if shutil.which("node"):
            self.assertEqual(self.browser_verifies(payload, signature), "The update's signature doesn't match the download.")

    def test_another_key_is_refused(self):
        payload = self.tmp / "payload"
        payload.write_bytes(b"x")
        signature = sign_update.sign(payload, "0.1.0", b"\x01" * 8, b"\x02" * 32)
        with self.assertRaises(sign_update.SignatureError):
            sign_update.verify(payload, signature, self.public_key)
        if shutil.which("node"):
            self.assertEqual(self.browser_verifies(payload, signature), "The update is signed with another key.")

    def test_signatures_the_tauri_cli_makes_verify(self):
        """The same format as the other Orbit apps' updates, byte for byte."""
        payload = FIXTURES / "tauri-signed.bin"
        signature = (FIXTURES / "tauri-signed.bin.sig").read_text()
        self.assertEqual(sign_update.verify(payload, signature, self.public_key)["file"], payload.name)
        if shutil.which("node"):
            self.assertEqual(self.browser_verifies(payload, signature)["file"], payload.name)

    def test_the_browsers_hash_is_blake2b(self):
        if not shutil.which("node"):
            self.skipTest("needs Node")
        data = self.tmp / "data"
        for size in (0, 1, 127, 128, 129, 256, 257, 100_003):
            data.write_bytes(bytes((i * 7 + size) % 256 for i in range(size)))
            for piece in (1, 128, 65536):
                with self.subTest(size=size, piece=piece):
                    out = subprocess.run(["node", ROOT / "tests" / "verify_signature.mjs", "hash", data, str(piece)],
                                         capture_output=True, text=True, check=True).stdout.strip()
                    self.assertEqual(out, hashlib.blake2b(data.read_bytes()).hexdigest())

    def test_the_browser_carries_a_signing_key(self):
        prefs = (ROOT / "branding" / "firefox-branding.js").read_text()
        key = re.search(r'pref\("orbitbrowser\.updates\.pubkey", "([^"]+)"\);', prefs).group(1)
        text = base64.b64decode(key).decode()
        self.assertTrue(text.startswith("untrusted comment: minisign public key: "))
        raw = base64.b64decode(text.splitlines()[1])
        self.assertEqual((len(raw), raw[:2]), (42, b"Ed"))


if __name__ == "__main__":
    unittest.main()
