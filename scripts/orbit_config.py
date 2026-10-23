"""Orbit Browser's own data, in one place.

The Chromium fork's build (scripts/build.py), its generated config
(distribution/, the GN branding) and its Orbit source component
(chromium_src/orbit/) all read these: Orbit Browser's version, the Orbit apps,
the Orbit account, Orbit's update feed and Orbit Pass's identity. Nothing here
is Chromium's; it is what makes a Chromium build Orbit Browser's.

`python3 scripts/orbit_config.py` prints it all as JSON (what the C++ in
chromium_src/orbit/ is generated from, so Python and C++ never disagree).
"""

from __future__ import annotations

import json
import re

#: Orbit Browser's own version, as people see it and Orbit Mission Control
#: orders it, apart from the Chromium it is built on (chromium.json). Raise it
#: for a release (a v<VERSION> tag); builds on main are newer by build number
#: alone, so a new Chromium doesn't need one.
VERSION = "0.1.0"

APP_NAME = "Orbit Browser"
COMPANY = "Orbit"
#: macOS bundle id and the base id the engine's helpers extend.
MAC_BUNDLE_ID = "ai.com.orbit.browser"
#: Linux package / wm-class / profile directory name.
LINUX_NAME = "orbit-browser"
#: Windows install registry name (OrbitUpdates and the installer agree on it).
WINDOWS_APP_ID = "OrbitBrowser"

#: Orbit Pass is built in: force-installed and un-removable. Its stable
#: extension id is the same in every copy of Orbit Browser, so Orbit Pass's
#: server knows the address a sign-in comes back to. For a Chromium (MV3)
#: build the id is the one derived from Orbit Pass's packaging key; Orbit Pass's
#: own repo (extension/scripts/package.mjs --chrome) produces the .crx and
#: reports this id. Keep the two in step (see ../Orbit Pass).
ORBIT_PASS_ID = "cabceppaohijjjeghpmbnojliinelphd"
#: Where Orbit Mission Control serves the force-install update manifest for it.
ORBIT_PASS_UPDATE_URL = "https://control.orbit.com.ai/extensions/orbit-pass/updates.xml"

#: The Orbit apps: Orbit's managed bookmarks, the new tab's shortcuts, and the
#: toolbar's Orbit menu (chromium_src/orbit/). id is the mark
#: (branding/content/apps/<id>.svg); open, where the menu opens it if not the
#: address (Orbit Pass: its vault page, inside the browser).
ORBIT_APPS = [
    {"id": "ai", "name": "Orbit AI", "url": "https://ai.orbit.com.ai/"},
    {"id": "mail", "name": "Orbit Mail", "url": "https://mail.orbit.com.ai/"},
    {"id": "calendar", "name": "Orbit Calendar", "url": "https://mail.orbit.com.ai/calendar/"},
    {"id": "chat", "name": "Orbit Chat", "url": "https://chat.orbit.com.ai/"},
    {"id": "pass", "name": "Orbit Pass", "url": "https://pass.orbit.com.ai/vault/",
     "open": f"chrome-extension://{ORBIT_PASS_ID}/src/vault/vault.html"},
]

#: Orbit AI is the browser's assistant: its side panel and "Ask Orbit AI" open
#: these, in place of any Google/Gemini assistant (which the GenAI policies in
#: distribution/ lock off).
ORBIT_AI = {
    "chat": "https://ai.orbit.com.ai/threads/start/",
    "summarize": "https://ai.orbit.com.ai/threads/start/?action=summarize",
}

#: The person's Orbit account, in Orbit Mission Control (the toolbar's Orbit
#: menu). The same endpoints the other Orbit apps use.
ORBIT_ACCOUNT = {
    "manage": "https://control.orbit.com.ai/a/settings/",
    "signIn": "https://control.orbit.com.ai/accounts/login/",
    "signOut": "https://control.orbit.com.ai/sso/logout/",
    "accounts": "https://control.orbit.com.ai/a/api/accounts/",
}

#: Orbit Browser updates itself from Orbit Mission Control, as every other Orbit
#: app does (Chromium's own updater is not built or shipped). The feed, the
#: by-hand download, and the public half of the key releases are signed with
#: (scripts/sign_update.py). %TOKENS% are filled by the update component.
ORBIT_UPDATES = {
    "url": "https://control.orbit.com.ai/api/updates/orbit-browser/%TARGET%/%ARCH%/%VERSION%?build=%BUILD%",
    "download": "https://control.orbit.com.ai/download/orbit-browser/%OS%/",
    "pubkey": "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IEQ0MDRFQzM1REU3RDY1OTgKUldTWVpYM2VOZXdFMUtoTDdQNCtiUEFPdlFSeldaRTkvOW1DTlJFU2t3U3hOWW9EbUpmVHlIakoK",
}


def check_version(base: str = VERSION) -> str:
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", base):
        raise SystemExit(f"VERSION {base!r} isn't a version of three numbers.")
    return base


def orbit_version(build: int, release: bool, base: str = VERSION) -> str:
    """Orbit Browser's version for this build: VERSION for a release,
    VERSION-build.N for a build on main, VERSION-local for one made here."""
    check_version(base)
    if release:
        return base
    return f"{base}-build.{build}" if build else f"{base}-local"


def as_dict() -> dict:
    return {
        "version": VERSION,
        "app_name": APP_NAME,
        "company": COMPANY,
        "mac_bundle_id": MAC_BUNDLE_ID,
        "linux_name": LINUX_NAME,
        "windows_app_id": WINDOWS_APP_ID,
        "orbit_pass_id": ORBIT_PASS_ID,
        "orbit_pass_update_url": ORBIT_PASS_UPDATE_URL,
        "apps": ORBIT_APPS,
        "orbit_ai": ORBIT_AI,
        "account": ORBIT_ACCOUNT,
        "updates": ORBIT_UPDATES,
    }


if __name__ == "__main__":
    print(json.dumps(as_dict(), indent=2))
