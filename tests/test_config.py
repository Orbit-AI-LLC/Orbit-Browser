"""Orbit Browser's configuration is consistent and carries its guarantees.

No network, no source tree, no compiler: these check the committed files that
make a Chromium build Orbit Browser's — the pin, the GN arguments, the branding,
the locked policies and the first-run defaults — so a mistake is caught before a
long build. The build itself (scripts/build.py) and the patches
(scripts/update_chromium.py --check) are checked against real Chromium elsewhere.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import orbit_config as cfg  # noqa: E402
import patches  # noqa: E402


def gn_assignments(text: str) -> dict[str, str]:
    """The key = value assignments in a GN args fragment (ignoring comments)."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        m = re.match(r"^([a-z0-9_]+)\s*=\s*(.+)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


class PinTest(unittest.TestCase):
    def test_chromium_pin(self):
        pin = json.loads((ROOT / "chromium.json").read_text())
        self.assertRegex(pin["version"], r"^\d+\.\d+\.\d+\.\d+$")
        self.assertEqual(pin["milestone"], int(pin["version"].split(".")[0]))
        self.assertTrue(pin["src"].startswith("https://"))
        self.assertTrue(pin["depot_tools"].startswith("https://"))

    def test_no_firefox_pin_left(self):
        self.assertFalse((ROOT / "firefox.json").exists(), "firefox.json should be gone")
        self.assertFalse((ROOT / "scripts" / "omni_patches.py").exists())
        self.assertFalse(list((ROOT / "patches").rglob("*.patch")), "no Firefox .patch files should remain")


class OrbitConfigTest(unittest.TestCase):
    def test_version(self):
        self.assertRegex(cfg.VERSION, r"^\d+\.\d+\.\d+$")
        self.assertEqual(cfg.orbit_version(0, False), f"{cfg.VERSION}-local")
        self.assertEqual(cfg.orbit_version(7, False), f"{cfg.VERSION}-build.7")
        self.assertEqual(cfg.orbit_version(7, True), cfg.VERSION)

    def test_apps(self):
        for app in cfg.ORBIT_APPS:
            self.assertTrue(app["url"].startswith("https://"))
            self.assertTrue((ROOT / "branding" / "content" / "apps" / f"{app['id']}.svg").exists())
        pass_app = next(a for a in cfg.ORBIT_APPS if a["id"] == "pass")
        self.assertIn(cfg.ORBIT_PASS_ID, pass_app["open"])

    def test_update_feed(self):
        self.assertIn("%VERSION%", cfg.ORBIT_UPDATES["url"])
        self.assertTrue(cfg.ORBIT_UPDATES["pubkey"])


class GnArgsTest(unittest.TestCase):
    def test_common_args(self):
        common = gn_assignments((ROOT / "build" / "args" / "common.gn").read_text())
        self.assertEqual(common["is_chrome_branded"], "false")
        self.assertEqual(common["is_official_build"], "true")
        self.assertEqual(common["use_official_google_api_keys"], "false")
        self.assertEqual(common["google_api_key"], '""')

    def test_no_duplicate_or_conflicting_keys(self):
        common_text = (ROOT / "build" / "args" / "common.gn").read_text()
        # A duplicate assignment in one file is a GN error; check each file.
        for gn in (ROOT / "build" / "args").glob("*.gn"):
            keys = [m.group(1) for m in re.finditer(r"(?m)^([a-z0-9_]+)\s*=", gn.read_text())]
            self.assertEqual(len(keys), len(set(keys)), f"duplicate key in {gn.name}: {keys}")
        # common + each platform file are concatenated by build.py: no overlap.
        common = set(gn_assignments(common_text))
        for platform in ("mac", "win64", "win64-aarch64", "linux", "linux-aarch64"):
            per = set(gn_assignments((ROOT / "build" / "args" / f"{platform}.gn").read_text()))
            self.assertFalse(common & per, f"{platform}.gn re-assigns {common & per}")


class BrandingTest(unittest.TestCase):
    def test_branding_file(self):
        fields = dict(
            line.split("=", 1)
            for line in (ROOT / "branding" / "BRANDING").read_text().splitlines()
            if "=" in line and not line.startswith("#")
        )
        self.assertEqual(fields["PRODUCT_FULLNAME"], "Orbit Browser")
        self.assertEqual(fields["MAC_BUNDLE_ID"], cfg.MAC_BUNDLE_ID)

    def test_icons_present(self):
        for path in ("branding/mac/app.icns", "branding/windows/app.ico",
                     "branding/content/icon128.png", "branding/content/icon16.png"):
            self.assertTrue((ROOT / path).exists(), f"missing {path}")


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((ROOT / "distribution" / "policies" / "orbit.json").read_text())

    def test_google_ai_locked_off(self):
        self.assertEqual(self.policy["GenAiDefaultSettings"], 2)
        self.assertEqual(self.policy["GeminiSettings"], 1)

    def test_no_google_services(self):
        self.assertEqual(self.policy["BrowserSignin"], 0)
        self.assertTrue(self.policy["SyncDisabled"])
        self.assertFalse(self.policy["MetricsReportingEnabled"])

    def test_orbit_pass_is_the_password_manager(self):
        self.assertFalse(self.policy["PasswordManagerEnabled"])
        self.assertFalse(self.policy["AutofillAddressEnabled"])
        self.assertFalse(self.policy["AutofillCreditCardEnabled"])
        forced = self.policy["ExtensionSettings"][cfg.ORBIT_PASS_ID]
        self.assertEqual(forced["installation_mode"], "force_installed")

    def test_orbit_apps_bookmarked(self):
        urls = {b.get("url") for b in self.policy["ManagedBookmarks"]}
        for app in cfg.ORBIT_APPS:
            self.assertIn(app["url"], urls)

    def test_initial_preferences_valid(self):
        prefs = json.loads((ROOT / "distribution" / "initial_preferences").read_text())
        self.assertFalse(prefs["distribution"]["make_chrome_default"])


class PatchesTest(unittest.TestCase):
    def test_patches_load(self):
        # No fabricated patches are committed; the loader must still work and the
        # platform parsing accept the real set (possibly empty).
        for patch in patches.load_patches():
            self.assertTrue(patch.target)
            self.assertTrue(set(patch.platforms) <= set(patches.ALL_PLATFORMS))


if __name__ == "__main__":
    unittest.main()
