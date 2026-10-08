/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/**
 * Orbit Browser's own start-up work, run from the browser's start-up
 * categories (components.manifest, added by scripts/build.py):
 *
 * - init (browser-before-ui-startup): installs the built-in Orbit add-ons
 *   from the browser's own files, drops caches made by a different build, and
 *   adds the toolbar's Orbit button (in place of Mozilla's account button): the
 *   person's Orbit account and the Orbit apps.
 * - onIdle (browser-idle-startup): swaps Mozilla's default bookmarks for the
 *   Orbit apps in a profile made before it had them; and starts Orbit
 *   Browser's updates (OrbitUpdates.sys.mjs), which work as the other Orbit
 *   apps' do. Firefox's own updater is off (it would install Mozilla's
 *   Firefox over Orbit Browser).
 */

const lazy = {};

ChromeUtils.defineESModuleGetters(lazy, {
  AddonManager: "resource://gre/modules/AddonManager.sys.mjs",
  CustomizableUI:
    "moz-src:///browser/components/customizableui/CustomizableUI.sys.mjs",
  OrbitUpdates: "resource:///modules/OrbitUpdates.sys.mjs",
  PlacesUtils: "resource://gre/modules/PlacesUtils.sys.mjs",
});

/**
 * The add-ons built into Orbit Browser, from scripts/build.py: each one's ID,
 * version and the resource:// folder in omni.ja that holds it.
 */
const BUILTIN_ADDONS = /* @BUILTIN_ADDONS@ */ [];

/**
 * The Orbit apps, from scripts/build.py (ORBIT_APPS): each one's mark
 * (chrome://branding/content/apps/<id>.svg), name, address, and where the
 * browser opens it (Orbit Pass: its own vault page, inside the browser).
 */
const ORBIT_APPS = /* @ORBIT_APPS@ */ [];

/** The person's Orbit account, in Orbit Mission Control. */
const ORBIT_ACCOUNT = {
  manage: "https://control.orbit.com.ai/a/settings/",
  signIn: "https://control.orbit.com.ai/accounts/login/",
  // Signs out of every Orbit app at once.
  signOut: "https://control.orbit.com.ai/sso/logout/",
  // The signed-in person's accounts, as JSON; signed out, a redirect to sign in.
  accounts: "https://control.orbit.com.ai/a/api/accounts/",
};

const BUTTON_ID = "orbit-button";
const VIEW_ID = "PanelUI-orbit";
const STYLESHEET = "chrome://browser/content/orbit-browser.css";

/** Firefox's default bookmarks, which a profile made by an earlier build has. */
const MOZILLA_BOOKMARKS = [
  "https://support.mozilla.org/products/firefox",
  "https://support.mozilla.org/kb/customize-firefox-controls-buttons-and-toolbars?utm_source=firefox-browser&utm_medium=default-bookmarks&utm_campaign=customize",
  "https://www.mozilla.org/contribute/",
  "https://www.mozilla.org/about/",
];
const BOOKMARKS_DONE_PREF = "orbitbrowser.bookmarks.version";
const BOOKMARKS_VERSION = 1;

const STAMP_PREF = "orbitbrowser.stamp";
const SEEN_STAMP_PREF = "orbitbrowser.stamp.seen";
/** Help > Check for Updates…, as in the other Orbit apps. */
const CHECK_ITEM_ID = "orbit-checkForUpdates";

export const OrbitBrowser = {
  init() {
    for (const { id, version, url } of BUILTIN_ADDONS) {
      lazy.AddonManager.maybeInstallBuiltinAddon(id, version, url).catch(
        console.error
      );
    }
    this.dropCachesFromOtherBuilds();
    this.createOrbitButton();
  },

  /**
   * Each browser window (browser-window-domcontentloaded): Orbit Browser's own
   * styles, and Check for Updates… in the Help menu.
   */
  onWindow(window) {
    window.windowUtils.loadSheetUsingURIString(
      STYLESHEET,
      window.windowUtils.AUTHOR_SHEET
    );
    this.addCheckForUpdates(window);
  },

  /**
   * Help > Check for Updates…, above About Orbit Browser. The app menu's Help
   * view (where Windows keeps Help) copies the Help menu each time it opens,
   * giving the copy the id appMenu_<id>, so one listener serves both.
   */
  addCheckForUpdates(window) {
    const doc = window.document;
    const popup = doc.getElementById("menu_HelpPopup");
    if (!popup || doc.getElementById(CHECK_ITEM_ID)) {
      return;
    }
    const item = doc.createXULElement("menuitem");
    item.id = CHECK_ITEM_ID;
    item.setAttribute("label", "Check for Updates…");
    popup.insertBefore(item, doc.getElementById("aboutName"));
    window.addEventListener("command", event => {
      const id = event.target?.id;
      if (id === CHECK_ITEM_ID || id === `appMenu_${CHECK_ITEM_ID}`) {
        lazy.OrbitUpdates.check(true).catch(console.error);
      }
    });
  },

  // -- the Orbit button -----------------------------------------------------------------

  createOrbitButton() {
    lazy.CustomizableUI.createWidget({
      id: BUTTON_ID,
      type: "view",
      viewId: VIEW_ID,
      label: "Orbit",
      tooltiptext: "Your Orbit account and apps",
      defaultArea: lazy.CustomizableUI.AREA_NAVBAR,
      onBeforeCreated: doc => {
        this.preparePanel(doc);
        return true;
      },
      onViewShowing: event => {
        this.fillPanel(event.target).catch(console.error);
      },
    });
  },

  /** The (empty) panel, in the window's cache of panels, and its styles. */
  preparePanel(doc) {
    const cache = doc.getElementById("appMenu-viewCache");
    if (!cache || cache.content.querySelector(`#${VIEW_ID}`) || doc.getElementById(VIEW_ID)) {
      return;
    }
    const view = doc.createXULElement("panelview");
    view.id = VIEW_ID;
    view.className = "PanelUI-subView";
    const body = doc.createXULElement("vbox");
    body.className = "panel-subview-body";
    view.append(body);
    cache.content.append(view);
  },

  /** Fills the panel each time it opens: the account, then the apps. */
  async fillPanel(view) {
    const doc = view.ownerDocument;
    const win = doc.defaultView;
    const body = view.querySelector(".panel-subview-body");
    const open = url => {
      win.openTrustedLinkIn(url, "tab");
      lazy.CustomizableUI.hidePanelForNode(view);
    };
    const button = (label, { image, subtitle, className, onCommand }) => {
      const item = doc.createXULElement("toolbarbutton");
      item.className = `subviewbutton ${className || ""}`.trim();
      if (subtitle) {
        // With children of its own, a toolbarbutton draws no icon: the
        // account's goes in as a child too, as in Firefox's account panel.
        item.setAttribute("align", "center");
        if (image) {
          const avatar = doc.createXULElement("image");
          avatar.className = "orbit-panel-avatar";
          avatar.setAttribute("src", image);
          avatar.setAttribute("role", "presentation");
          item.append(avatar);
        }
        const text = doc.createXULElement("vbox");
        text.setAttribute("flex", "1");
        const title = doc.createXULElement("label");
        title.className = "orbit-panel-title";
        title.setAttribute("crop", "end");
        title.setAttribute("value", label);
        const sub = doc.createXULElement("label");
        sub.className = "orbit-panel-subtitle";
        sub.setAttribute("crop", "end");
        sub.setAttribute("value", subtitle);
        text.append(title, sub);
        item.append(text);
      } else {
        item.setAttribute("label", label);
      }
      if (image && !subtitle) {
        item.classList.add("subviewbutton-iconic");
        item.setAttribute("image", image);
      }
      item.addEventListener("command", onCommand);
      return item;
    };

    const account = await this.orbitAccount();
    const items = [];
    if (account) {
      items.push(
        button(account.name, {
          subtitle: "Manage your Orbit account",
          className: "orbit-panel-account",
          image: account.logo || "chrome://branding/content/apps/control.svg",
          onCommand: () => open(ORBIT_ACCOUNT.manage),
        })
      );
    } else {
      items.push(
        button("Sign in to Orbit", {
          subtitle: "One account for every Orbit app",
          className: "orbit-panel-account",
          image: "chrome://branding/content/apps/control.svg",
          onCommand: () => open(ORBIT_ACCOUNT.signIn),
        })
      );
    }
    items.push(doc.createXULElement("toolbarseparator"));
    for (const app of ORBIT_APPS) {
      items.push(
        button(app.name, {
          image: `chrome://branding/content/apps/${app.id}.svg`,
          onCommand: () => open(app.open || app.url),
        })
      );
    }
    if (account) {
      items.push(doc.createXULElement("toolbarseparator"));
      items.push(
        button("Sign out of Orbit", {
          onCommand: () => open(ORBIT_ACCOUNT.signOut),
        })
      );
    }
    body.replaceChildren(...items);
  },

  /**
   * The signed-in person's active Orbit account ({name, logo}), from Mission
   * Control's session in this browser; null when signed out or unreachable.
   */
  async orbitAccount() {
    try {
      const response = await fetch(ORBIT_ACCOUNT.accounts, {
        credentials: "include",
        redirect: "manual",
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        return null;
      }
      const data = await response.json();
      const accounts = data.accounts || [];
      const active =
        accounts.find(a => a.id === data.active_account_id) || accounts[0];
      return active ? { name: active.name, logo: active.logo_url || "" } : null;
    } catch {
      return null;
    }
  },

  // -- bookmarks ---------------------------------------------------------------------------

  /**
   * A new profile gets the Orbit apps on its bookmarks toolbar
   * (default-bookmarks.html, from scripts/build.py). A profile made before
   * that has Firefox's instead: once, they go and the Orbit apps come in,
   * leaving every bookmark the person made alone.
   */
  async replaceMozillaBookmarks() {
    if (Services.prefs.getIntPref(BOOKMARKS_DONE_PREF, 0) >= BOOKMARKS_VERSION) {
      return;
    }
    const { bookmarks } = lazy.PlacesUtils;
    const folders = new Set();
    for (const url of MOZILLA_BOOKMARKS) {
      const found = [];
      await bookmarks.fetch({ url }, b => found.push(b));
      for (const b of found) {
        folders.add(b.parentGuid);
        await bookmarks.remove(b.guid);
      }
    }
    for (const guid of folders) {
      const folder = await bookmarks.fetch(guid);
      const left = await bookmarks.fetch({ parentGuid: guid, index: 0 });
      if (folder?.title === "Mozilla Firefox" && !left) {
        await bookmarks.remove(guid);
      }
    }
    for (const app of ORBIT_APPS) {
      if (!(await bookmarks.fetch({ url: app.url }))) {
        await bookmarks.insert({
          parentGuid: bookmarks.toolbarGuid,
          url: app.url,
          title: app.name,
        });
      }
    }
    Services.prefs.setIntPref(BOOKMARKS_DONE_PREF, BOOKMARKS_VERSION);
  },

  /**
   * Firefox keeps compiled scripts between runs and only throws them away
   * when Firefox's version changes. Orbit Browser can change its own files
   * without Firefox changing, so each build stamps itself (a default pref,
   * read afresh from omni.ja on every start) and a new stamp drops the caches
   * on the next start.
   */
  dropCachesFromOtherBuilds() {
    const stamp = Services.prefs.getDefaultBranch("").getStringPref(STAMP_PREF, "");
    const seen = Services.prefs.getStringPref(SEEN_STAMP_PREF, "");
    if (!stamp || stamp === seen) {
      return;
    }
    if (seen) {
      Services.appinfo.invalidateCachesOnRestart();
    }
    Services.prefs.setStringPref(SEEN_STAMP_PREF, stamp);
  },

  async onIdle() {
    await this.replaceMozillaBookmarks().catch(console.error);
    lazy.OrbitUpdates.start();
  },
};
