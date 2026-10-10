"""The changes Orbit Browser makes to Mozilla's own files inside omni.ja.

Each one replaces an exact piece of text that must appear exactly once in the
pinned Firefox; when a new Firefox moves it, the build stops and names the
patch (and tests/test_patches.py fails). Fix the anchor then, never loosen the
check: a patch that quietly stops applying would quietly bring a feature back.

Files Orbit Browser adds or replaces whole (the branding, its prefs, its
start-up module, the built-in add-ons) are listed in scripts/build.py instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

#: Orbit AI's address for the browser: a fresh New Orbit each time (see
#: Orbit AI's README, "Orbit AI in Orbit Browser"). distribution/policies.json
#: locks browser.ml.chat.provider to the same address.
ORBIT_AI_URL = "https://ai.orbit.com.ai/threads/start/"

#: The new tab's own wallpapers, in place of Firefox's: space in the teal of
#: the mark, drawn by scripts/wallpapers.swift into branding/content/wallpapers/
#: (so chrome://branding/content/wallpapers/, which the new tab's content
#: security policy lets it load). They fill the category Firefox keeps for its
#: own, which the page names after the browser ({ -brand-product-name }), first
#: in the list. position is the CSS background-position: what stays in view
#: when the window crops the picture. name is what a screen reader says.
ORBIT_WALLPAPERS = [
    {"title": "orbit-planet", "file": "planet", "theme": "dark", "position": "right",
     "name": "A teal planet circled by its orbit, its moon at the top right"},
    {"title": "orbit-nebula", "file": "nebula", "theme": "dark", "position": "left",
     "name": "A teal and indigo nebula across a field of stars"},
    {"title": "orbit-horizon", "file": "horizon", "theme": "dark", "position": "bottom",
     "name": "The edge of a planet at night, lit teal by a rising sun"},
    {"title": "orbit-eclipse", "file": "eclipse", "theme": "dark", "position": "right",
     "name": "A planet in front of its star, ringed in teal light"},
    {"title": "orbit-comet", "file": "comet", "theme": "dark", "position": "top right",
     "name": "A comet with a long teal tail"},
    {"title": "orbit-orbits", "file": "orbits", "theme": "dark", "position": "bottom left",
     "name": "A teal planet and its moons on their orbits, on a dark background"},
    {"title": "orbit-orbits-light", "file": "orbits-light", "theme": "light", "position": "bottom left",
     "name": "A teal planet and its moons on their orbits, on a light background"},
    {"title": "orbit-daybreak", "file": "daybreak", "theme": "light", "position": "bottom right",
     "name": "Morning over a teal planet, a moon on its orbit in a pale sky"},
]


def orbit_wallpaper_records() -> list[dict]:
    """ORBIT_WALLPAPERS as the new tab's wallpaper feed hands them to the page,
    the way it hands on Mozilla's Remote Settings records."""
    base = "chrome://branding/content/wallpapers/"
    return [
        {
            "id": w["title"],
            "title": w["title"],
            "category": "firefox",
            "theme": w["theme"],
            "background_position": w["position"],
            "order": (i + 1) * 10,
            "fluent_id": f"newtab-wallpaper-{w['title']}",
            "wallpaperUrl": f"{base}{w['file']}.jpg",
            "thumbnail": f"{base}{w['file']}-thumb.jpg",
        }
        for i, w in enumerate(ORBIT_WALLPAPERS)
    ]


ORBIT_WALLPAPER_FEED = """    // Orbit Browser: its own wallpapers, shipped in the browser
    // (scripts/omni_patches.py, ORBIT_WALLPAPERS), in place of the Firefox
    // ones and the promotions Mozilla sends in their category. Mozilla's
    // other categories stay as they are.
    const orbitWallpapers = %s;
    records = [
      ...orbitWallpapers,
      ...records.filter(record => record.category !== "firefox"),
    ];

    const wallpapers = [
      ...records.map(record => {
""" % json.dumps(orbit_wallpaper_records(), indent=2).replace("\n", "\n    ")

ORBIT_WALLPAPER_NAMES = "newtab-wallpaper-category-title-firefox = { -brand-product-name }\n\n" + "".join(
    f"newtab-wallpaper-{w['title']} = {w['name']}\n" for w in ORBIT_WALLPAPERS
)


@dataclass(frozen=True)
class Patch:
    #: "browser" (browser/omni.ja) or "gre" (the omni.ja beside it).
    jar: str
    path: str
    old: str
    new: str
    why: str
    #: The builds the file is in ("mac", "windows"): some are one platform's.
    platforms: tuple[str, ...] = ("mac", "windows")


ORBIT_AI_PROVIDER = f"""  chatProviders: new Map([
    // Orbit Browser: Orbit AI, the only chatbot it offers (browser.ml.chat.providers
    // is locked to "orbitai", which hides the others). The prompt is typed into
    // Orbit AI's composer and sent (supportAutoSubmit), never put in the address.
    [
      "{ORBIT_AI_URL}",
      {{
        iconUrl: "chrome://branding/content/orbit-ai.svg",
        id: "orbitai",
        link1: "https://orbit.com.ai/terms/",
        link2: "https://orbit.com.ai/privacy/",
        maxLength: 32000,
        name: "Orbit AI",
        supportAutoSubmit: true,
      }},
    ],
"""

PATCHES: list[Patch] = [
    # -- Orbit AI in the sidebar --------------------------------------------------------
    Patch(
        "browser",
        "modules/GenAI.sys.mjs",
        "  chatProviders: new Map([\n",
        ORBIT_AI_PROVIDER,
        "Adds Orbit AI to the chatbot providers; the locked prefs make it the only one.",
    ),
    Patch(
        "browser",
        "actors/GenAIChild.sys.mjs",
        """'#prompt-textarea, [contenteditable], [role="textbox"]'""",
        """'#composer-input, #prompt-textarea, [contenteditable], [role="textbox"]'""",
        "Lets the sidebar type a prompt into Orbit AI's composer (textarea#composer-input).",
    ),
    # The sidebar's and menus' names for the chatbot when they don't name the
    # provider. With the provider locked they mostly say "Orbit AI" already.
    Patch("browser", "localization/en-US/browser/sidebar.ftl",
          "menu-view-genai-chat =\n  .label = AI Chatbot\n",
          "menu-view-genai-chat =\n  .label = Orbit AI\n",
          "View > Sidebar names Orbit AI."),
    Patch("browser", "localization/en-US/browser/sidebar.ftl",
          "sidebar-menu-genai-chat-label =\n  .label = AI chatbot\n",
          "sidebar-menu-genai-chat-label =\n  .label = Orbit AI\n",
          "The sidebar's tool names Orbit AI."),
    Patch("browser", "localization/en-US/browser/sidebar.ftl",
          "sidebar-menu-open-ai-chatbot-tooltip-generic = Open AI chatbot ({ $shortcut })\n",
          "sidebar-menu-open-ai-chatbot-tooltip-generic = Open Orbit AI ({ $shortcut })\n",
          "Tooltip."),
    Patch("browser", "localization/en-US/browser/sidebar.ftl",
          "sidebar-menu-close-ai-chatbot-tooltip-generic = Close AI chatbot ({ $shortcut })\n",
          "sidebar-menu-close-ai-chatbot-tooltip-generic = Close Orbit AI ({ $shortcut })\n",
          "Tooltip."),
    Patch("browser", "localization/en-US/browser/genai.ftl",
          "genai-menu-ask-generic-2 =\n    .label = Ask AI Chatbot\n",
          "genai-menu-ask-generic-2 =\n    .label = Ask Orbit AI\n",
          "Context menu."),
    Patch("browser", "localization/en-US/browser/genai.ftl",
          "genai-menu-no-provider-2 =\n    .label = Ask an AI Chatbot\n",
          "genai-menu-no-provider-2 =\n    .label = Ask Orbit AI\n",
          "Context menu."),
    Patch("browser", "localization/en-US/browser/genai.ftl",
          "genai-menu-open-generic =\n    .label = Open AI Chatbot\n",
          "genai-menu-open-generic =\n    .label = Open Orbit AI\n",
          "Context menu."),
    Patch("browser", "localization/en-US/browser/genai.ftl",
          "genai-input-ask-generic =\n    .placeholder = Ask AI chatbot…\n",
          "genai-input-ask-generic =\n    .placeholder = Ask Orbit AI…\n",
          "The selection shortcut's box."),
    Patch("browser", "localization/en-US/browser/genai.ftl",
          "genai-chatbot-title = AI chatbot\n",
          "genai-chatbot-title = Orbit AI\n",
          "The sidebar's heading."),
    Patch("browser", "localization/en-US/browser/genai.ftl",
          "genai-options-reload-generic =\n    .label = Reload AI chatbot\n",
          "genai-options-reload-generic =\n    .label = Reload Orbit AI\n",
          "Sidebar menu."),
    # -- the about dialog: who makes what ---------------------------------------------------
    Patch(
        "browser",
        "localization/en-US/browser/aboutDialog.ftl",
        'community-exp = <label data-l10n-name="community-exp-mozillaLink">{ -vendor-short-name }</label> is a <label data-l10n-name="community-exp-creditsLink">global community</label> working together to keep the Web open, public and accessible to all.\n',
        'community-exp = { -brand-short-name } is built on Firefox, made by <label data-l10n-name="community-exp-mozillaLink">Mozilla</label> and a <label data-l10n-name="community-exp-creditsLink">global community</label> working together to keep the Web open, public and accessible to all.\n',
        "With the vendor renamed, Firefox's line would credit Orbit with Mozilla's work.",
    ),
    Patch(
        "browser",
        "localization/en-US/browser/aboutDialog.ftl",
        'community-2 = { -brand-short-name } is designed by <label data-l10n-name="community-mozillaLink">{ -vendor-short-name }</label>, a <label data-l10n-name="community-creditsLink">global community</label> working together to keep the Web open, public and accessible to all.\n',
        'community-2 = { -brand-short-name } is made by Orbit on Firefox, which is designed by <label data-l10n-name="community-mozillaLink">Mozilla</label>, a <label data-l10n-name="community-creditsLink">global community</label> working together to keep the Web open, public and accessible to all.\n',
        "The same, in the other form of the line.",
    ),
    # -- versions and updates: Orbit Browser's own, as in the other Orbit apps -------------
    # Firefox's updater is off on purpose (it would install Mozilla's Firefox);
    # OrbitUpdates.sys.mjs updates the browser instead. The About window and
    # Settings show Orbit Browser's version, the Firefox it is built on under
    # it, and a Check for Updates button that asks Orbit Mission Control.
    Patch(
        "browser",
        "chrome/browser/content/browser/aboutDialog.xhtml",
        """              <hbox align="baseline">
                <label id="version" class="update"/>
                <label id="releasenotes" is="text-link" hidden="true" data-l10n-id="releaseNotes-link"/>
              </hbox>
""",
        """              <!-- Orbit Browser: its version, and under it the Firefox it is built on
                   with Firefox's release notes; one box, as #updateInfo is a
                   grid of three rows. -->
              <vbox>
                <hbox align="baseline">
                  <label id="version" class="update"/>
                </hbox>
                <hbox align="baseline">
                  <label id="orbitFirefoxVersion" data-l10n-id="aboutdialog-orbit-firefox-version"/>
                  <label id="releasenotes" is="text-link" hidden="true" data-l10n-id="releaseNotes-link"/>
                </hbox>
              </vbox>
""",
        "The About window: the Firefox Orbit Browser is built on, under Orbit Browser's own version.",
    ),
    Patch(
        "browser",
        "chrome/browser/content/browser/aboutDialog.xhtml",
        """                <description id="policyDisabled" data-l10n-id="update-policy-disabled"/>
""",
        """                <!-- Orbit Browser: Firefox's updater is off; this asks Orbit Mission Control. -->
                <description id="policyDisabled">
                  <button id="orbitCheckForUpdatesButton"
                          data-l10n-id="update-checkForUpdatesButton"/>
                </description>
""",
        "The About window's Check for updates button, where Firefox says its updates are off.",
    ),
    Patch(
        "browser",
        "chrome/browser/content/browser/aboutDialog.js",
        """  let versionAttributes = {
    version: AppConstants.MOZ_APP_VERSION_DISPLAY,
  };
""",
        """  // Orbit Browser: its own version, and the Firefox it is built on below it.
  let versionAttributes = {
    version: Services.prefs.getStringPref(
      "orbitbrowser.version",
      AppConstants.MOZ_APP_VERSION_DISPLAY
    ),
  };
  document.l10n.setArgs(document.getElementById("orbitFirefoxVersion"), {
    version: AppConstants.MOZ_APP_VERSION_DISPLAY,
  });
  document
    .getElementById("orbitCheckForUpdatesButton")
    .addEventListener("command", () => {
      ChromeUtils.importESModule(
        "resource:///modules/OrbitUpdates.sys.mjs"
      ).OrbitUpdates.check(true);
    });
""",
        "The About window shows Orbit Browser's version (not Firefox's) and checks for Orbit Browser updates.",
    ),
    Patch("browser", "localization/en-US/browser/aboutDialog.ftl",
          "aboutdialog-version-arch-nightly = { $version } ({ $isodate }) ({ $arch })\n",
          "aboutdialog-version-arch-nightly = { $version } ({ $isodate }) ({ $arch })\n"
          "aboutdialog-orbit-firefox-version = Built on Firefox { $version }\n",
          "The About window's line naming the Firefox Orbit Browser is built on."),
    Patch("browser", "localization/en-US/browser/aboutDialog.ftl",
          "settings-update-policy-disabled =\n    .label = Updates disabled by your organization\n",
          "settings-update-policy-disabled =\n    .label = { -brand-short-name } downloads new versions itself and asks before it restarts\n",
          "Settings' update section: Firefox's updater is off, Orbit Browser's own is on."),
    Patch(
        "browser",
        "chrome/browser/content/browser/preferences/widgets/update-state.mjs",
        """  policyDisabled: {
    l10nId: "settings-update-policy-disabled",
    buttonL10nId: "update-checkForUpdatesButton",
    buttonDisabled: true,
  },
""",
        """  policyDisabled: {
    // Orbit Browser: Firefox's updater is off; the button asks Orbit Mission
    // Control instead (OrbitUpdates.sys.mjs).
    l10nId: "settings-update-policy-disabled",
    buttonL10nId: "update-checkForUpdatesButton",
    buttonId: "checkForUpdatesButton",
    buttonAction: "orbit",
  },
""",
        "Settings' Check for updates button works, for Orbit Browser's updates.",
    ),
    Patch(
        "browser",
        "chrome/browser/content/browser/preferences/widgets/update-state.mjs",
        """    let { buttonAction } = updateStatusToMetadata[this.value];
    if (!buttonAction || !window.gAppUpdater) {
""",
        """    let { buttonAction } = updateStatusToMetadata[this.value];
    if (buttonAction === "orbit") {
      ChromeUtils.importESModule(
        "resource:///modules/OrbitUpdates.sys.mjs"
      ).OrbitUpdates.check(true);
      return;
    }
    if (!buttonAction || !window.gAppUpdater) {
""",
        "What that button does.",
    ),
    Patch(
        "browser",
        "chrome/browser/content/browser/preferences/config/about-firefox.mjs",
        """    let version = AppConstants.MOZ_APP_VERSION_DISPLAY;
    let distribution;
""",
        """    // Orbit Browser: its own version, and the Firefox it is built on below
    // it, where a distribution's name would go.
    let version = Services.prefs.getStringPref(
      "orbitbrowser.version",
      AppConstants.MOZ_APP_VERSION_DISPLAY
    );
    let distribution = `Built on Firefox ${AppConstants.MOZ_APP_VERSION_DISPLAY}`;
""",
        "Settings' update section shows Orbit Browser's version and the Firefox under it.",
    ),
    # -- the add-ons page: Mozilla, not the browser, runs the recommended extensions ---------
    Patch("gre", "localization/en-US/toolkit/about/aboutAddons.ftl",
          '    a selection Firefox <a data-l10n-name="learn-more-trigger">recommends</a> for\n',
          '    a selection Mozilla <a data-l10n-name="learn-more-trigger">recommends</a> for\n',
          "Mozilla's Recommended Extensions program, named for who runs it."),
    Patch("gre", "localization/en-US/toolkit/about/aboutAddons.ftl",
          "  .title = Firefox only recommends extensions that meet standards for security and performance\n",
          "  .title = Mozilla only recommends extensions that meet standards for security and performance\n",
          "The same program's badge."),
    # -- Mozilla's account, feedback and device moving: gone from the menus ---------------
    # The feedback policy only greys these out, and the Help menu shows them
    # again every time it opens; the app menu's Help view copies what's shown.
    Patch(
        "browser",
        "chrome/browser/content/browser/utilityOverlay.js",
        """  document.getElementById("feedbackPage").disabled =
    !Services.policies.isAllowed("feedbackCommands");
""",
        """  document.getElementById("feedbackPage").disabled =
    !Services.policies.isAllowed("feedbackCommands");
  // Orbit Browser: no feedback to Mozilla while the policy is off, and no
  // moving a Mozilla account to a new device.
  document.getElementById("feedbackPage").hidden =
    !Services.policies.isAllowed("feedbackCommands");
  document.getElementById("helpSwitchDevice").hidden = true;
""",
        "Hides Share Ideas and Feedback, and Switching to a New Device, in the Help menu and the app menu.",
    ),
    Patch(
        "browser",
        "chrome/browser/content/browser/browser-safebrowsing.js",
        "    reportMenu.hidden = isPhishingPage;\n",
        '    reportMenu.hidden =\n      isPhishingPage || !Services.policies.isAllowed("feedbackCommands");\n',
        "Report Deceptive Site goes with the other feedback commands rather than staying greyed out.",
    ),
    Patch(
        "browser",
        "chrome/browser/content/browser/browser-safebrowsing.js",
        "    reportErrorMenu.hidden = !isPhishingPage;\n",
        '    reportErrorMenu.hidden =\n      !isPhishingPage || !Services.policies.isAllowed("feedbackCommands");\n',
        "And its This Isn't a Deceptive Site.",
    ),
    # The Mac's menu bar when no window is open has no script to hide these.
    *[
        Patch("browser", "chrome/browser/content/browser/hiddenWindowMac.xhtml",
              f'      <menuitem id="{item}"\n', f'      <menuitem id="{item}" hidden="true"\n',
              f"{item}, hidden in the Mac's windowless menu bar.", platforms=("mac",))
        for item in ("menu_newAIWindow", "menu_newClassicWindow", "feedbackPage", "helpSwitchDevice", "help_reportBrokenSite")
    ],
    # Report Broken Site (to Mozilla) is hidden when the feedback policy is off,
    # but only once a tab changes; until then the menu's own markup shows it.
    Patch("browser", "chrome/browser/content/browser/browser.xhtml",
          '      <menuitem id="help_reportBrokenSite"\n', '      <menuitem id="help_reportBrokenSite" hidden="true"\n',
          "Report Broken Site starts hidden; Firefox shows it again only if feedback is allowed."),
    # -- the sidebar: no Synced Tabs, which needs a Mozilla account ---------------------------
    # Left out of the sidebar's tools altogether while accounts are off (they are
    # locked off), so neither the launcher, its Customize panel nor the View
    # menu offers it, whatever a profile's saved list of tools says.
    Patch(
        "browser",
        "chrome/browser/content/browser/sidebar/browser-sidebar.js",
        """      [
        "viewTabsSidebar",
        this.makeSidebar({
""",
        """      // Orbit Browser: Synced Tabs only with a Mozilla account.
      ...(Services.prefs.getBoolPref("identity.fxaccounts.enabled", true) ? [[
        "viewTabsSidebar",
        this.makeSidebar({
""",
        "Synced Tabs is registered only when Mozilla accounts are on.",
    ),
    Patch(
        "browser",
        "chrome/browser/content/browser/sidebar/browser-sidebar.js",
        """          gleanClickEvent: Glean.sidebar.syncedTabsIconClick,
        }),
      ],
""",
        """          gleanClickEvent: Glean.sidebar.syncedTabsIconClick,
        }),
      ]] : []),
""",
        "The end of that entry.",
    ),
    # -- Settings: the landing page without Mozilla's account ------------------------------
    Patch(
        "browser",
        "chrome/browser/content/browser/preferences/preferences.js",
        """  sync: {
    l10nId: "account-sync-section",
    iconSrc: "chrome://browser/skin/fxa/avatar-empty.svg",
    groupIds: [
      "defaultBrowserSync",
      "accountDisabled",
      "account",
      "sync",
      "importBrowserData",
      "profiles",
      "backup",
      "referrals",
    ],""",
        """  sync: {
    l10nId: "account-sync-section",
    // Orbit Browser: the page keeps the default browser, importing, profiles
    // and backup; Mozilla's account, Sync and "Share Firefox" go.
    iconSrc: "chrome://global/skin/icons/settings.svg",
    groupIds: ["defaultBrowserSync", "importBrowserData", "profiles", "backup"],""",
        "Settings' first page without Mozilla's account, Sync and referral groups.",
    ),
    Patch("browser", "localization/en-US/browser/preferences/preferences.ftl",
          "account-sync-section =\n    .heading = Account and sync\n",
          "account-sync-section =\n    .heading = General\n",
          "Its heading."),
    Patch("browser", "localization/en-US/browser/preferences/preferences.ftl",
          "pane-account-sync-title2 = Account and sync\n    .title = Account and sync\n",
          "pane-account-sync-title2 = General\n    .title = General\n",
          "Its name in Settings' list."),
    Patch(
        "browser",
        "chrome/browser/content/browser/preferences/preferences.js",
        """    groupIds: ["passwords", "payments", "addresses", "personalInfo"],
    module:
      "chrome://browser/content/preferences/config/passwords-autofill.mjs",
    visible: () => srdSectionEnabled("passwordsAutofill"),""",
        """    groupIds: ["passwords", "payments", "addresses", "personalInfo"],
    module:
      "chrome://browser/content/preferences/config/passwords-autofill.mjs",
    // Orbit Browser: Firefox's passwords, cards and addresses are off and
    // locked (distribution/policies.json); Orbit Pass fills instead.
    visible: () => false,""",
        "Settings has no Passwords and autofill page: everything on it is Firefox's own autofill, which is off.",
    ),
    # -- the new tab's wallpapers: Orbit's, not the Firefox ones --------------------------------
    # The category Firefox keeps for its own wallpapers (foxes, and promotions
    # such as World Cup teams) is named after the browser, so it said "Orbit
    # Browser" over pictures of foxes. branding/firefox-branding.js keeps the
    # built-in new tab, which these patches change, from being swapped for
    # Mozilla's newer copy.
    Patch(
        "browser",
        "chrome/browser/builtin-addons/newtab/lib/Wallpapers/WallpaperFeed.sys.mjs",
        """    const wallpapers = [
      ...records.map(record => {
""",
        ORBIT_WALLPAPER_FEED,
        "The new tab offers Orbit's wallpapers (branding/content/wallpapers/) in place of the Firefox ones.",
    ),
    Patch("browser", "localization/en-US/browser/newtab/newtab.ftl",
          "newtab-wallpaper-category-title-firefox = { -brand-product-name }\n",
          ORBIT_WALLPAPER_NAMES,
          "What a screen reader says for each of Orbit's wallpapers."),
    # -- Firefox product names in the toolkit's brand terms ------------------------------------
    Patch("gre", "localization/en-US/toolkit/branding/brandings.ftl",
          "-firefox-home-brand-name = Firefox Home\n",
          "-firefox-home-brand-name = Orbit Browser Home\n",
          "The home page's name."),
    Patch("gre", "localization/en-US/toolkit/branding/brandings.ftl",
          "-firefoxview-brand-name = Firefox View\n",
          "-firefoxview-brand-name = Tab Overview\n",
          "Firefox View, under a name that isn't Firefox's."),
    Patch("gre", "localization/en-US/toolkit/branding/brandings.ftl",
          "-firefox-suggest-brand-name = Firefox Suggest\n",
          "-firefox-suggest-brand-name = Address Bar Suggestions\n",
          "Firefox Suggest, under a name that isn't Firefox's."),
    # -- the startup profile selector: open the chosen profile through the bundle ---------------
    # Mac only. Choosing a profile in the selector shown at start-up normally
    # returns launchWithProfile to Firefox's native start-up code, which
    # relaunches the engine (Contents/MacOS/firefox) directly. That path skips
    # the launcher (Contents/MacOS/orbit-browser), the only thing that sets
    # XUL_APP_FILE and so makes the engine Orbit Browser rather than Firefox; the
    # relaunched instance looks for its data in ~/Library/Application Support/
    # Firefox (which macOS guards for Firefox alone), finds no profile and quits
    # before a window opens -- "the app closes after opening a profile", and only
    # from the start-up selector (the in-browser profiles panel already launches
    # through the bundle and works). So launch the chosen profile the panel's way
    # (launchInstance -> launchAppBundle -> the launcher runs and sets
    # XUL_APP_FILE), then tell the start-up code to just exit this selector
    # process. Windows runs firefox.exe directly with no launcher, so its native
    # relaunch is already Orbit Browser; this patch is the Mac's alone.
    Patch("browser", "chrome/browser/content/browser/profiles/profile-selector.mjs",
          """  async launchProfile(profile, url) {
    if (this.isStartupUI) {
      await this.setLaunchArguments(profile, url ? ["-url", url] : []);
      await this.selectableProfileService.uninit();
    } else {
      this.selectableProfileService.launchInstance(profile, url ? [url] : []);
    }

    window.close();
  }""",
          """  async launchProfile(profile, url) {
    // Orbit Browser: launch through the app bundle (so the launcher runs and
    // sets XUL_APP_FILE) instead of the native launchWithProfile relaunch,
    // which runs the engine directly and loses Orbit Browser's data folder.
    this.selectableProfileService.launchInstance(profile, url ? [url] : []);
    if (this.isStartupUI) {
      if (this.#startupParams) {
        this.#startupParams.SetInt(0, Ci.nsIToolkitProfileService.exit);
        this.#startupParams.SetInt(1, 0);
        this.#startupParams.SetInt(2, 0);
      }
      await this.selectableProfileService.uninit();
    }

    window.close();
  }""",
          "The start-up profile selector opens the chosen profile through the app bundle.",
          platforms=("mac",)),
]

#: Styles added at the end of Mozilla's own stylesheets (they win over what
#: comes before them), by (jar, path).
APPENDED_STYLES = {
    ("browser", "chrome/browser/content/browser/genai/chat.css"): """
/* Orbit Browser: the sidebar holds Orbit AI alone, so its name is a title
   rather than a menu with one entry, and the panel takes Orbit's black and
   white accent rather than Firefox's purple (the Summarize button, focus). */
:root {
  --color-accent-primary: light-dark(#111111, #ffffff);
  --color-accent-primary-hover: light-dark(#2b2b2b, #e8e8e8);
  --color-accent-primary-active: light-dark(#000000, #d4d4d4);
  --focus-outline-color: light-dark(#111111, #ffffff);
}

#provider {
  appearance: none;
  pointer-events: none;
  background-color: transparent;
  background-image: none;
  border-color: transparent;
  padding-inline-end: var(--space-small);
  font-weight: var(--font-weight-bold);
}
""",
}

#: Lines appended to browser/omni.ja's components/components.manifest: Orbit
#: Browser's start-up module, called the way Firefox calls its own.
COMPONENT_CATEGORIES = (
    "category browser-before-ui-startup resource:///modules/OrbitBrowser.sys.mjs OrbitBrowser.init\n"
    "category browser-idle-startup resource:///modules/OrbitBrowser.sys.mjs OrbitBrowser.onIdle\n"
    "category browser-window-domcontentloaded resource:///modules/OrbitBrowser.sys.mjs OrbitBrowser.onWindow\n"
)


class PatchError(Exception):
    pass


def apply(patch: Patch, text: str) -> str:
    count = text.count(patch.old)
    if count != 1:
        where = "is not in" if count == 0 else f"appears {count} times in"
        raise PatchError(
            f"Patch for {patch.jar}:{patch.path} no longer applies: its text {where} this Firefox.\n"
            f"  Patch: {patch.why}\n  Looking for: {patch.old[:160]!r}"
        )
    return text.replace(patch.old, patch.new)
