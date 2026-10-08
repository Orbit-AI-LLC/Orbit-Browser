"""Start a built Orbit Browser and check it is what it should be.

    python3 tests/smoke.py                          # work/mac/Orbit Browser.app, headless
    python3 tests/smoke.py --shots work/smoke       # also save screenshots there
    python3 tests/smoke.py --app "/Applications/Orbit Browser.app"

Runs the app in a fresh profile, over Marionette (tests/marionette.py), and
checks from inside it: the name, the policies, every AI feature off and
locked, Orbit AI the only chatbot (and its sidebar opening), Orbit Pass built
in at its fixed address, Firefox's updater gone and Orbit Browser's own
version (and the Firefox under it) in the About window and Settings, no
"Firefox" left in the pages people see first, Orbit's wallpapers on the new tab. Exits non-zero on
the first thing that's wrong.
Mac only for now (the app has to run here).
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from marionette import Browser, MarionetteError  # noqa: E402
from omni_patches import ORBIT_WALLPAPERS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ORBIT_PASS_UUID = "cabce947-8111-49e9-a61f-0224b07a4dfd"

# The new tab's wallpaper feed, handed one of Mozilla's Firefox wallpapers and
# one from its other categories in place of Remote Settings, so the check
# doesn't wait on the network. Then each wallpaper it offers is loaded.
WALLPAPERS = """
const done = arguments[arguments.length - 1];
(async () => {
  const { WallpaperFeed } = ChromeUtils.importESModule("resource://newtab/lib/Wallpapers/WallpaperFeed.sys.mjs");
  const { AboutNewTabResourceMapping } = ChromeUtils.importESModule("resource:///modules/AboutNewTabResourceMapping.sys.mjs");
  const feed = new WallpaperFeed();
  const sent = [];
  feed.store = { dispatch: action => sent.push(action), getState: () => ({ Prefs: { values: {} } }) };
  feed.wallpaperClient = { get: async () => [
    { title: "firefox-a", category: "firefox", theme: "dark", attachment: { location: "a.svg" } },
    { title: "starry-sky", category: "celestial", theme: "dark", attachment: { location: "b.avif" } },
  ] };
  await feed.updateWallpapers();
  const list = sent.find(a => a.type == "WALLPAPERS_SET")?.data || [];
  const first = list.filter(w => w.category == "firefox");
  const failed = [];
  for (const url of first.flatMap(w => [w.wallpaperUrl, w.thumbnail])) {
    const image = new Image();
    image.src = url;
    await image.decode().catch(() => failed.push(url));
  }
  done({ titles: list.map(w => w.title), first: first.map(w => w.title), failed, xpi: AboutNewTabResourceMapping.addonIsXPI });
})().catch(e => done({ error: String(e) + "\\n" + e.stack }));
"""

# The About window, opened as Help > About opens it, once it has its strings.
ABOUT = """
const done = arguments[arguments.length - 1];
(async () => {
  window.openAboutDialog();
  let doc;
  for (let i = 0; i < 100; i++) {
    doc = Services.wm.getMostRecentWindow("Browser:About")?.document;
    if (doc?.getElementById("version")?.textContent && doc.getElementById("orbitFirefoxVersion")?.textContent) {
      break;
    }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  const button = doc.getElementById("orbitCheckForUpdatesButton");
  const about = {
    version: doc.getElementById("version").textContent,
    firefox: doc.getElementById("orbitFirefoxVersion").textContent,
    engine: AppConstants.MOZ_APP_VERSION_DISPLAY,
    button: !!button && button.getBoundingClientRect().width > 0,
  };
  doc.defaultView.close();
  done(about);
})().catch(e => done({ error: String(e) }));
"""

STATE = """
const done = arguments[arguments.length - 1];
(async () => {
  const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
  const { GenAI } = ChromeUtils.importESModule("resource:///modules/GenAI.sys.mjs");
  const pref = name => {
    const type = Services.prefs.getPrefType(name);
    const value = type == Services.prefs.PREF_STRING ? Services.prefs.getStringPref(name)
      : type == Services.prefs.PREF_INT ? Services.prefs.getIntPref(name)
      : type == Services.prefs.PREF_BOOL ? Services.prefs.getBoolPref(name) : null;
    return { value, locked: Services.prefs.prefIsLocked(name) };
  };
  const names = arguments[0];
  const prefs = Object.fromEntries(names.map(n => [n, pref(n)]));
  const pass = await AddonManager.getAddonByID("pass@orbit.com.ai");
  const policy = WebExtensionPolicy.getByID("pass@orbit.com.ai");
  const brand = Services.strings.createBundle("chrome://branding/locale/brand.properties");
  const l10n = new Localization(["branding/brand.ftl", "browser/genai.ftl", "browser/sidebar.ftl"], true);
  const binDir = Services.dirsvc.get("GreBinD", Ci.nsIFile);
  const profileRoot = Services.dirsvc.get("DefProfRt", Ci.nsIFile).path;
  done({
    brand: brand.GetStringFromName("brandShortName"),
    trademark: l10n.formatValueSync("trademarkInfo"),
    chatTitle: l10n.formatValueSync("genai-chatbot-title"),
    policies: Object.keys(Services.policies.getActivePolicies() || {}),
    prefs,
    pass: pass && { version: pass.version, active: pass.isActive, hidden: pass.hidden, builtin: pass.isBuiltin,
                    canUninstall: !!(pass.permissions & AddonManager.PERM_CAN_UNINSTALL),
                    host: policy?.mozExtensionHostname, privateBrowsing: policy?.privateBrowsingAllowed,
                    allUrls: !!policy?.allowedOrigins?.subsumes(new MatchPattern("https://example.com/*")) },
    providers: [...GenAI.chatProviders].filter(([, v]) => !v.hidden).map(([url, v]) => ({ url, name: v.name })),
    chatEntrypoints: GenAI.canShowChatEntrypoint,
    files: Object.fromEntries(["libmozinference.dylib", "libonnxruntime.dylib", "updater.app"].map(f => {
      const file = binDir.clone(); file.append(f); return [f, file.exists()];
    })),
    profileRoot,
  });
})().catch(e => done({ error: String(e) + "\\n" + e.stack }));
"""

ORBIT_MENU = """
const done = arguments[arguments.length - 1];
(async () => {
  const { CustomizableUI } = ChromeUtils.importESModule("moz-src:///browser/components/customizableui/CustomizableUI.sys.mjs");
  const { PlacesUtils } = ChromeUtils.importESModule("resource://gre/modules/PlacesUtils.sys.mjs");
  const area = CustomizableUI.getPlacementOfWidget("orbit-button")?.area;
  const fxa = document.getElementById("fxa-toolbar-menu-button");
  const mozillaAccountButton = !!fxa && !fxa.hidden && fxa.checkVisibility();
  document.getElementById("orbit-button").click();
  let text = "";
  for (let i = 0; i < 40 && !text.includes("Orbit Pass"); i++) {
    await new Promise(r => setTimeout(r, 250));
    text = document.getElementById("PanelUI-orbit")?.textContent || "";
    const labels = [...(document.getElementById("PanelUI-orbit")?.querySelectorAll("[label], [value]") || [])]
      .map(n => n.getAttribute("label") || n.getAttribute("value"));
    text += " " + labels.join(" | ");
  }
  // Default bookmarks are imported after start-up, then Mozilla's are swapped when idle.
  let toolbar = [], all = [];
  for (let i = 0; i < 40; i++) {
    const tree = await PlacesUtils.promiseBookmarksTree(PlacesUtils.bookmarks.toolbarGuid);
    toolbar = (tree.children || []).map(c => c.uri).filter(Boolean);
    if (toolbar.length) break;
    await new Promise(r => setTimeout(r, 250));
  }
  const root = await PlacesUtils.promiseBookmarksTree(PlacesUtils.bookmarks.rootGuid);
  (function walk(n) { if (n.uri) all.push(n.uri); (n.children || []).forEach(walk); })(root);
  done({ area, mozillaAccountButton, panel: text, toolbarBookmarks: toolbar, allBookmarks: all });
})().catch(e => done({ error: String(e) + "\\n" + e.stack }));
"""

MOZILLA_LEFTOVERS = """
  buildHelpMenu();
  const help = [...document.getElementById("menu_HelpPopup").children]
    .filter(n => n.localName == "menuitem" && !n.hidden).map(n => n.id);
  const { AIWindow } = ChromeUtils.importESModule("moz-src:///browser/components/aiwindow/ui/modules/AIWindow.sys.mjs");
  const prefs = {};
  for (const name of ["signon.firefoxRelay.feature", "browser.topsites.useRemoteSetting", "browser.topsites.contile.enabled",
                      "browser.newtabpage.activity-stream.feeds.section.topstories", "browser.newtabpage.activity-stream.showWeather"]) {
    const type = Services.prefs.getPrefType(name);
    prefs[name] = type == Services.prefs.PREF_STRING ? Services.prefs.getStringPref(name) : Services.prefs.getBoolPref(name);
  }
  const sidebarTools = SidebarController.getTools().filter(t => !t.hidden).map(t => t.name).join(",");
  return { help, smartWindow: AIWindow.isAIWindowEnabled(), sidebarTools, syncedTabs: SidebarController.sidebars.has("viewTabsSidebar"), prefs };
"""

# What Firefox's own rules paint with Orbit's colours (orbit-browser.css): the
# selected tab's edge, and the gradient on the tab strip (the body's, or the
# toolbox's when a theme puts it there).
COLOURS = """
  const tab = gBrowser.selectedTab.querySelector(".tab-background");
  const strip = [document.body, document.getElementById("navigator-toolbox")]
    .map(n => getComputedStyle(n).backgroundImage).find(image => image != "none") || "none";
  return { tab: getComputedStyle(tab).backgroundImage, strip };
"""

LOCKED_OFF = [
    "browser.ml.enable", "browser.ml.linkPreview.enabled", "browser.ml.pageAssist.enabled",
    "browser.smartwindow.enabled", "browser.tabs.groups.smart.enabled", "browser.tabs.groups.smart.userEnabled",
    "browser.translations.enable", "pdfjs.enableAltText", "pdfjs.enableGuessAltText", "extensions.ml.enabled",
    "extensions.formautofill.useml", "places.semanticHistory.featureGate", "browser.search.visualSearch.featureGate",
    "browser.preferences.aiControls", "browser.urlbar.quicksuggest.mlEnabled",
    # Firefox's own autofill: Orbit Pass fills instead.
    "signon.rememberSignons", "signon.autofillForms", "signon.generation.enabled",
    "extensions.formautofill.addresses.enabled", "extensions.formautofill.creditCards.enabled",
    "browser.formfill.enable", "browser.contextual-password-manager.enabled",
]
BLOCKED_CONTROLS = [
    "browser.ai.control.default", "browser.ai.control.translations", "browser.ai.control.pdfjsAltText",
    "browser.ai.control.smartTabGroups", "browser.ai.control.linkPreviewKeyPoints",
    "browser.ai.control.smartWindow", "browser.ai.control.speechRecognition",
]


class Failed(Exception):
    pass


def check(condition, message):
    if not condition:
        raise Failed(message)
    print(f"  ok  {message}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--app", type=Path, default=ROOT / "work" / "mac" / "Orbit Browser.app")
    parser.add_argument("--shots", type=Path, help="save screenshots in this folder")
    parser.add_argument("--headed", action="store_true", help="show the window")
    args = parser.parse_args(argv)
    executable = args.app / "Contents" / "MacOS" / "orbit-browser"
    if not executable.exists():
        print(f"No Orbit Browser at {args.app}: run scripts/build.py first.")
        return 2
    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)

    def shot(browser, name):
        if args.shots:
            browser.screenshot(args.shots / f"{name}.png")

    browser = Browser(executable, headless=not args.headed)
    try:
        browser.chrome()
        time.sleep(3)  # built-in add-ons install as the first window opens
        state = browser.js(STATE, LOCKED_OFF + BLOCKED_CONTROLS + [
            "browser.ai.control.sidebarChatbot", "browser.ml.chat.enabled", "browser.ml.chat.provider",
            "signon.rememberSignons", "orbitbrowser.version", "orbitbrowser.stamp", "identity.fxaccounts.enabled",
        ], asynchronous=True)
        if "error" in state:
            raise Failed(state["error"])
        prefs = state["prefs"]
        print("Orbit Browser", prefs["orbitbrowser.version"]["value"])

        check(state["brand"] == "Orbit Browser" and state["trademark"].startswith("Orbit Browser is built on Mozilla Firefox"), "named Orbit Browser")
        check(state["profileRoot"].rstrip("/").endswith("/Orbit Browser") or "Orbit Browser" in state["profileRoot"],
              f"keeps its data apart from Firefox's ({state['profileRoot']})")
        for policy in ("AIControls", "DisableAccounts", "DisableAppUpdate", "DisableFirefoxStudies",
                       "DisableTelemetry", "FirefoxSuggest", "IPProtectionAvailable", "Preferences",
                       "PasswordManagerEnabled", "AutofillAddressEnabled", "AutofillCreditCardEnabled", "DisableFormHistory"):
            check(policy in state["policies"], f"policy {policy} is in force")
        for name in LOCKED_OFF:
            check(prefs[name]["value"] is False and prefs[name]["locked"], f"{name} is off and locked")
        for name in BLOCKED_CONTROLS:
            check(prefs[name]["value"] == "blocked" and prefs[name]["locked"], f"{name} is blocked and locked")
        for name, present in state["files"].items():
            check(not present, f"{name} is not shipped")

        check(prefs["browser.ai.control.sidebarChatbot"]["value"] == "available", "the sidebar chatbot stays, for Orbit AI")
        check(state["providers"] == [{"url": prefs["browser.ml.chat.provider"]["value"], "name": "Orbit AI"}],
              "Orbit AI is the only chatbot")
        check(prefs["browser.ml.chat.provider"]["locked"], "and it can't be swapped for another")
        check(state["chatEntrypoints"], "Orbit AI's menus and sidebar are shown")
        check(state["chatTitle"] == "Orbit AI", "the sidebar calls it Orbit AI")

        pass_ = state["pass"]
        check(pass_ and pass_["active"], "Orbit Pass is installed and running")
        check(pass_["builtin"] and not pass_["canUninstall"] and not pass_["hidden"], "built in: listed, can be turned off, not removed")
        check(pass_["host"] == ORBIT_PASS_UUID, "at its fixed address (moz-extension://cabce947-…)")
        check(pass_["allUrls"] and pass_["privateBrowsing"], "with every site and private windows")
        check(not browser.js("const b = document.getElementById('appMenu-passwords-button'); return !!b && getComputedStyle(b).display != 'none'"),
              "the app menu has no Passwords (Firefox's password manager is off)")
        check(prefs["identity.fxaccounts.enabled"]["value"] is False and prefs["identity.fxaccounts.enabled"]["locked"],
              "no Mozilla account or Sync")
        colours = browser.js(COLOURS)
        check(any(teal in colours["tab"] for teal in ("rgb(46, 191, 177)", "rgb(63, 224, 207)")),
              f"the selected tab is edged in Orbit's teal, not Firefox's orange ({colours['tab']})")
        # The strip's stops compute as oklab(L a b / alpha): a < 0 leans teal, Firefox's peach has a > 0.
        stops = re.findall(r"oklab\(([-\d.e]+) ([-\d.e]+) ([-\d.e]+)", colours["strip"])
        check(stops and float(stops[-1][1]) < 0, f"the tab strip fades into teal, not Firefox's peach ({colours['strip']})")

        orbit = browser.js(ORBIT_MENU, asynchronous=True)
        if "error" in orbit:
            raise Failed(orbit["error"])
        check(orbit["area"] == "nav-bar", "the Orbit button is on the toolbar")
        check(not orbit["mozillaAccountButton"], "Mozilla's account button isn't")
        for name in ("Orbit AI", "Orbit Mail", "Orbit Calendar", "Orbit Chat", "Orbit Pass"):
            check(name in orbit["panel"], f"the Orbit menu opens {name}")
        check("Sign in to Orbit" in orbit["panel"] or "Manage your Orbit account" in orbit["panel"], "and the Orbit account")
        shot(browser, "orbit-menu")
        browser.js("PanelUI.panel.hidePopup(); document.getElementById('customizationui-widget-panel')?.hidePopup();")
        check(all(url in orbit["toolbarBookmarks"] for url in ("https://ai.orbit.com.ai/", "https://mail.orbit.com.ai/")),
              "the bookmarks toolbar has the Orbit apps")
        check(not [u for u in orbit["allBookmarks"] if "mozilla.org" in u], "and no Mozilla bookmarks")
        menus = browser.js(MOZILLA_LEFTOVERS)
        check(menus["help"] == ["menu_openHelp", "helpSafeMode", "troubleShooting", "orbit-checkForUpdates", "aboutName"],
              f"the Help menu has Check for Updates and no Mozilla feedback or device moving ({menus['help']})")
        check(not menus["smartWindow"], "the File menu has no Smart Window")
        check("syncedtabs" not in menus["sidebarTools"] and not menus["syncedTabs"],
              f"the sidebar has no Synced Tabs ({menus['sidebarTools']})")
        for name, value in menus["prefs"].items():
            check(value is False or value == "unavailable", f"{name} is off")
        about = browser.js(ABOUT, asynchronous=True)
        if "error" in about:
            raise Failed(about["error"])
        version = prefs["orbitbrowser.version"]["value"]
        check(about["version"].startswith(f"{version} ("), f"the About window shows Orbit Browser's version ({about['version']})")
        check(about["firefox"] == f"Built on Firefox {about['engine']}", f"and the Firefox it is built on ({about['firefox']})")
        check(about["button"], "and a Check for updates button")

        # The pages people see first.
        browser.content()
        for url, name in (("about:home", "home"), ("about:preferences", "settings"), ("about:addons", "addons"), ("about:policies", "policies")):
            browser.command("WebDriver:Navigate", {"url": url})
            time.sleep(1.5)
            text = browser.js("return document.body.innerText")
            # about:policies lists Mozilla's policy names (DisableFirefoxStudies…), which are identifiers.
            if url != "about:policies":
                mentions = [line.strip() for line in text.splitlines() if "Firefox" in line]
                check(not mentions, f"{url} doesn't say Firefox" + (f" (it says: {mentions[:3]})" if mentions else ""))
            if url == "about:addons":
                check("Orbit Pass" in text, "about:addons opens on the extensions, Orbit Pass among them")
            if url == "about:preferences":
                check(not browser.js("return !!document.querySelector('#category-ai-features:not([hidden])')"), "Settings has no AI controls page")
                check("Account and sync" not in text and "Sign in" not in text, "Settings has no Mozilla account")
                check(not browser.js("return !!document.querySelector('#category-passwords-autofill')?.checkVisibility()"),
                      "Settings has no Passwords and autofill page")
                updates = browser.js("""
                  const info = document.querySelector("update-information")?.shadowRoot;
                  const button = document.querySelector("update-state")?.shadowRoot?.querySelector("moz-button");
                  return { version: info?.querySelector("#label")?.textContent.trim() || "",
                           firefox: info?.querySelector("#distribution")?.textContent.trim() || "",
                           button: !!button && !button.disabled };
                """)
                check(updates["version"].startswith(f"Version {version} "), f"Settings shows Orbit Browser's version ({updates['version']})")
                check(updates["firefox"].startswith("Built on Firefox "), "and the Firefox under it")
                check(updates["button"], "and its Check for updates button works")
            shot(browser, name)

        try:
            browser.command("WebDriver:Navigate", {"url": "about:logins"})
            blocked = "blockedByPolicy" in browser.js("return document.documentURI")
        except MarionetteError as error:
            # Marionette reports landing on the "blocked" page as an error.
            blocked = "blockedByPolicy" in str(error)
        check(blocked, "Firefox's Passwords page is blocked")

        # The new tab's wallpapers, from its own feed: headless, the page itself
        # stays blank (its feeds never start), so it can't be asked.
        browser.chrome()
        walls = browser.js(WALLPAPERS, asynchronous=True)
        if "error" in walls:
            raise Failed(walls["error"])
        check(not walls["xpi"], "the new tab is the built-in one, with the build's changes")
        check(walls["first"] == [w["title"] for w in ORBIT_WALLPAPERS], f"the new tab's first wallpapers are Orbit's ({walls['first']})")
        check("firefox-a" not in walls["titles"] and "starry-sky" in walls["titles"],
              "the Firefox ones are gone; Mozilla's other wallpapers stay")
        check(not walls["failed"], f"each wallpaper and its thumbnail loads ({walls['failed']})")

        opened = browser.js("""
          const done = arguments[arguments.length - 1];
          SidebarController.show("viewGenaiChatSidebar").then(async () => {
            const win = SidebarController.browser.contentWindow;
            const inner = await win.browserPromise;
            for (let i = 0; i < 40 && (!inner.currentURI || inner.currentURI.spec == "about:blank" || inner.webProgress.isLoadingDocument); i++) {
              await new Promise(r => setTimeout(r, 250));
            }
            done({ open: SidebarController.isOpen, id: SidebarController.currentID, url: inner.currentURI.spec });
          }).catch(e => done({ error: String(e) }));
        """, asynchronous=True)
        check(opened.get("open") and opened.get("id") == "viewGenaiChatSidebar", "Orbit AI opens in the sidebar")
        check("orbit.com.ai" in opened.get("url", ""), f"and loads Orbit AI ({opened.get('url')})")
        time.sleep(2)
        shot(browser, "orbit-ai-sidebar")
        print("All good.")
        return 0
    except Failed as failure:
        print(f"FAIL {failure}")
        shot(browser, "failure")
        return 1
    finally:
        browser.quit()


if __name__ == "__main__":
    sys.exit(main())
