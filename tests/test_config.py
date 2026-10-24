"""Orbit Browser's configuration is consistent and carries its guarantees.

No network and no download: these check the committed files that make a repack of
ungoogled-chromium into Orbit Browser — the pin's shape, the branding assets, the
locked policies and the first-run preferences — so a mistake is caught before a
build. The actual repack (scripts/build.py) downloads and is checked in CI.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import orbit_config as cfg  # noqa: E402

PLATFORMS = ("win64", "mac-x64", "mac-arm64")


class PinTest(unittest.TestCase):
    def test_chromium_pin_shape(self):
        pin = json.loads((ROOT / "chromium.json").read_text())
        self.assertEqual(pin["source"], "ungoogled-chromium")
        self.assertEqual(set(pin["builds"]), set(PLATFORMS))
        for platform, build in pin["builds"].items():
            self.assertIn("url", build, platform)
            self.assertIn("sha256", build, platform)

    def test_no_firefox_or_source_fork_left(self):
        self.assertFalse((ROOT / "firefox.json").exists())
        self.assertFalse((ROOT / "scripts" / "sync.py").exists(), "source-fork sync.py should be gone")
        self.assertFalse((ROOT / "patches").exists(), "source patches/ should be gone")
        self.assertFalse((ROOT / "chromium_src").exists(), "chromium_src/ should be gone")


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


class BrandingTest(unittest.TestCase):
    def test_icons_present(self):
        for path in ("branding/mac/app.icns", "branding/mac/document.icns",
                     "branding/windows/app.ico",
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


class PreferencesTest(unittest.TestCase):
    def setUp(self):
        self.prefs = json.loads((ROOT / "distribution" / "initial_preferences").read_text())

    def test_valid_and_not_default_browser_prompt(self):
        self.assertFalse(self.prefs["distribution"]["make_chrome_default"])

    def test_site_data_is_allowed_not_cleared_on_exit(self):
        # ungoogled-chromium defaults cookies to SESSION_ONLY (4): "delete site
        # data when you close all windows". Orbit must ship Allow (1) so this is
        # never left enabled.
        self.assertEqual(
            self.prefs["profile"]["default_content_setting_values"]["cookies"], 1,
            "cookies default must be 1 (Allow), not 4 (clear on exit)",
        )


if __name__ == "__main__":
    unittest.main()
