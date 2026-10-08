/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/**
 * Updates, as Orbit Mission Control hands them out: the same as the other
 * Orbit apps (src-tauri/src/updates.rs in each; keep them alike).
 *
 * Half a minute after start and every four hours after that (and from
 * Help > Check for Updates…, the About window or Settings) the browser asks
 * https://control.orbit.com.ai/api/updates/orbit-browser/{target}/{arch}/{version}?build={n}
 * (orbitbrowser.updates.url). Mission Control answers from Orbit Browser's
 * GitHub releases: 204 when this is the newest build, else the newer build's
 * version, download link and signature. The download is checked against the
 * public key in orbitbrowser.updates.pubkey before anything is installed
 * (OrbitSignature.sys.mjs), and the signature must name the version announced.
 *
 * Once a build is downloaded the browser asks whether to restart now; Later
 * installs it when Orbit Browser quits. On the Mac the new app
 * (Orbit-Browser-<v>-macOS.app.tar.gz, unpacked) takes the old one's place; on
 * Windows its installer (…-Setup.exe) runs silently over the old version.
 * Both happen once the browser has quit, by a helper that waits for it:
 * Firefox starts processes from its own files for as long as it runs.
 *
 * A copy that can't replace itself (on the Mac, one in a folder it can't
 * write to; on Windows, the portable zip) shows a bar with a Download button
 * instead. orbitbrowser.updates.enabled = false stops the checks in the
 * background; the menu still checks.
 */

import { AppConstants } from "resource://gre/modules/AppConstants.sys.mjs";
import {
  Blake2b,
  verifyUpdateSignature,
} from "resource:///modules/OrbitSignature.sys.mjs";

const lazy = {};

ChromeUtils.defineESModuleGetters(lazy, {
  BrowserWindowTracker: "resource:///modules/BrowserWindowTracker.sys.mjs",
  setInterval: "resource://gre/modules/Timer.sys.mjs",
  setTimeout: "resource://gre/modules/Timer.sys.mjs",
});

const APP_NAME = "Orbit Browser";
const ENABLED_PREF = "orbitbrowser.updates.enabled";
const URL_PREF = "orbitbrowser.updates.url";
const DOWNLOAD_PREF = "orbitbrowser.updates.download";
const PUBKEY_PREF = "orbitbrowser.updates.pubkey";
const FIRST_CHECK_MS = 30 * 1000;
const EVERY_MS = 4 * 60 * 60 * 1000;
const NOTIFICATION_ID = "orbit-browser-update";
/** Where a downloaded update waits, in the profile's local folder (caches). */
const UPDATE_FOLDER = "orbit-update";
/** Written to the disk as the download comes, in pieces about this big. */
const WRITE_EVERY = 8 * 1024 * 1024;
/** Windows: the installed copy, as the installer registers it. */
const UNINSTALL_KEY =
  "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\OrbitBrowser";

const MAC_INSTALL_SCRIPT = `#!/bin/sh
# Orbit Browser's update, finished once the browser has quit
# (OrbitUpdates.sys.mjs): the new app takes the old one's place.
pid="$1" app="$2" new="$3" relaunch="$4"
waited=0
while kill -0 "$pid" 2>/dev/null; do
  sleep 0.2
  waited=$((waited + 1))
  [ "$waited" -gt 3000 ] && exit 1
done
old="$(dirname "$app")/.$(basename "$app" .app)-replaced-$$"
if mv "$app" "$old"; then
  if mv "$new" "$app"; then
    rm -rf "$old"
  else
    mv "$old" "$app"
  fi
fi
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$app" >/dev/null 2>&1
[ "$relaunch" = 1 ] && /usr/bin/open "$app"
# The update's folder, this script's own.
rm -rf "$(dirname "$0")"
`;

function file(path) {
  const f = Cc["@mozilla.org/file/local;1"].createInstance(Ci.nsIFile);
  f.initWithPath(path);
  return f;
}

/** Runs a program to the end; resolves to its exit code. */
function run(executable, args) {
  const process = Cc["@mozilla.org/process/util;1"].createInstance(Ci.nsIProcess);
  process.init(file(executable));
  process.startHidden = true;
  process.noShell = true;
  return new Promise((resolve, reject) => {
    process.runwAsync(args, args.length, {
      observe(_subject, topic) {
        if (topic === "process-finished") {
          resolve(process.exitValue);
        } else {
          reject(new Error(`${executable} didn't run`));
        }
      },
    });
  });
}

/** Starts a program and leaves it running after the browser quits. */
function launch(executable, args) {
  const process = Cc["@mozilla.org/process/util;1"].createInstance(Ci.nsIProcess);
  process.init(file(executable));
  process.startHidden = true;
  process.noShell = true;
  process.runw(false, args, args.length);
}

export const OrbitUpdates = {
  /** A downloaded, verified build waiting to be installed: {version, path}. */
  _ready: null,
  /** Set while a check runs, so the timer and the menu never overlap. */
  _checking: false,
  /** Install when the browser quits (Later, or Restart Now), and open it again after? */
  _installAtQuit: false,
  _relaunch: false,
  _started: false,

  /** Orbit Browser's own version (not Firefox's), e.g. 0.1.0-build.12. */
  get version() {
    return Services.prefs.getStringPref("orbitbrowser.version", "");
  },

  /** Starts checking in the background (OrbitBrowser.onIdle). */
  start() {
    if (this._started) {
      return;
    }
    this._started = true;
    Services.obs.addObserver(this, "quit-application");
    // What an earlier run downloaded and didn't install is downloaded again.
    IOUtils.remove(this._folder(), { recursive: true, ignoreAbsent: true }).catch(console.error);
    if (!Services.prefs.getBoolPref(ENABLED_PREF, true)) {
      return;
    }
    lazy.setTimeout(() => {
      this.check(false).catch(console.error);
      lazy.setInterval(() => this.check(false).catch(console.error), EVERY_MS);
    }, FIRST_CHECK_MS);
  },

  /** Checks now. `manual` (from a menu or button) also says when there is nothing new or the check failed. */
  async check(manual = false) {
    if (this._checking) {
      return;
    }
    this._checking = true;
    let found = null;
    let error = null;
    try {
      if (this._ready) {
        // Already downloaded: the timer stays quiet, the menu asks again.
        found = manual ? { version: this._ready.version, ready: true } : null;
      } else {
        const offer = await this._offer();
        if (offer && this.canReplaceItself()) {
          await this._download(offer);
          found = { version: offer.version, ready: true };
        } else if (offer) {
          found = { version: offer.version, ready: false };
        }
      }
    } catch (e) {
      error = e;
    } finally {
      this._checking = false;
    }

    if (found?.ready) {
      this._askToRestart(found.version);
    } else if (found) {
      this._showDownloadBar(found.version);
    } else if (error) {
      console.warn("[updates]", error.message);
      if (manual) {
        Services.prompt.alert(
          this._window(),
          "Update check failed",
          `${APP_NAME} couldn't check for updates. Check your connection and try again.\n\n${error.message}`
        );
      }
    } else if (manual) {
      Services.prompt.alert(
        this._window(),
        "You're up to date",
        `${APP_NAME} ${this.version} is the newest version.`
      );
    }
  },

  /** Where this copy is, as Mission Control's update feed spells it. */
  platform() {
    if (AppConstants.platform === "macosx") {
      // One universal app for Apple silicon and Intel.
      return { target: "darwin", arch: "universal", os: "mac" };
    }
    const abi = Services.appinfo.XPCOMABI.split("-")[0];
    return {
      target: "windows",
      arch: abi === "aarch64" ? "aarch64" : "x86_64",
      os: "windows",
    };
  },

  /**
   * Whether this copy can put a new version in its own place: on the Mac, an
   * app in a folder it can write to (as the Orbit Installer and a drag from
   * the disk image leave it); on Windows, the copy the installer put in.
   */
  canReplaceItself() {
    try {
      if (AppConstants.platform === "macosx") {
        const app = this._macApp();
        return !!app && app.parent.isWritable() && app.isWritable();
      }
      if (AppConstants.platform === "win") {
        const key = Cc["@mozilla.org/windows-registry-key;1"].createInstance(Ci.nsIWindowsRegKey);
        key.open(Ci.nsIWindowsRegKey.ROOT_KEY_CURRENT_USER, UNINSTALL_KEY, Ci.nsIWindowsRegKey.ACCESS_READ);
        try {
          const installed = file(key.readStringValue("InstallLocation"));
          return installed.equals(Services.dirsvc.get("GreD", Ci.nsIFile));
        } finally {
          key.close();
        }
      }
    } catch {}
    return false;
  },

  /** The Mac app this runs from (…/Orbit Browser.app), or null. */
  _macApp() {
    // Contents/MacOS/firefox, the engine the launcher runs.
    const app = Services.dirsvc.get("XREExeF", Ci.nsIFile).parent.parent.parent;
    return app.leafName.endsWith(".app") ? app : null;
  },

  _folder() {
    return PathUtils.join(Services.dirsvc.get("ProfLD", Ci.nsIFile).path, UPDATE_FOLDER);
  },

  /** Mission Control's offer of a newer build, {version, url, signature}, or null. */
  async _offer() {
    const version = this.version;
    if (!version) {
      return null;
    }
    const build = Services.prefs.getIntPref("orbitbrowser.build", 0);
    const { target, arch } = this.platform();
    const url = Services.prefs
      .getStringPref(URL_PREF)
      .replace("%TARGET%", target)
      .replace("%ARCH%", arch)
      .replace("%VERSION%", encodeURIComponent(version))
      .replace("%BUILD%", String(build))
      // A local build has no build number; Mission Control then goes by the version.
      .replace(/\?build=0$/, "");
    const response = await fetch(url, { credentials: "omit", cache: "no-store" });
    if (response.status === 204 || response.status === 404) {
      return null;
    }
    if (!response.ok) {
      throw new Error(`Orbit Mission Control answered ${response.status}.`);
    }
    const offer = await response.json();
    // Mission Control only offers a build newer by build number, which the
    // version can't always tell (0.2.0-build.21 comes after 0.2.0).
    if (!offer?.version || offer.version === version) {
      return null;
    }
    if (!offer.url || !offer.signature) {
      throw new Error("Orbit Mission Control's answer has no download.");
    }
    return {
      version: String(offer.version),
      url: String(offer.url),
      signature: String(offer.signature),
    };
  },

  /** Downloads the offered build, checks its signature and makes it ready to install. */
  async _download(offer) {
    const folder = this._folder();
    await IOUtils.remove(folder, { recursive: true, ignoreAbsent: true });
    await IOUtils.makeDirectory(folder);
    const mac = AppConstants.platform === "macosx";
    const payload = PathUtils.join(folder, mac ? "update.app.tar.gz" : "Orbit-Browser-Setup.exe");

    const response = await fetch(offer.url, { credentials: "omit", cache: "no-store" });
    if (!response.ok) {
      throw new Error(`The download failed (HTTP ${response.status}).`);
    }
    const hash = new Blake2b();
    const reader = response.body.getReader();
    let pieces = [];
    let pending = 0;
    const flush = async () => {
      const bytes = new Uint8Array(pending);
      let at = 0;
      for (const piece of pieces) {
        bytes.set(piece, at);
        at += piece.length;
      }
      await IOUtils.write(payload, bytes, { mode: "appendOrCreate" });
      pieces = [];
      pending = 0;
    };
    for (;;) {
      const { done, value } = await reader.read();
      if (value?.length) {
        hash.update(value);
        pieces.push(value);
        pending += value.length;
      }
      if (pending >= WRITE_EVERY || (done && pending)) {
        await flush();
      }
      if (done) {
        break;
      }
    }

    const pubkey = Services.prefs.getDefaultBranch("").getStringPref(PUBKEY_PREF, "");
    const signed = await verifyUpdateSignature(hash.digest(), offer.signature, pubkey);
    if (signed.version !== offer.version) {
      throw new Error(`The download is signed for ${signed.version || "no version"}, not ${offer.version}.`);
    }

    let path = payload;
    if (mac) {
      const unpacked = PathUtils.join(folder, "new");
      await IOUtils.makeDirectory(unpacked);
      if ((await run("/usr/bin/tar", ["-xzf", payload, "-C", unpacked])) !== 0) {
        throw new Error("The download couldn't be unpacked.");
      }
      await IOUtils.remove(payload);
      path = PathUtils.join(unpacked, `${APP_NAME}.app`);
      if (!(await IOUtils.exists(PathUtils.join(path, "Contents", "Info.plist")))) {
        throw new Error(`The download holds no ${APP_NAME}.app.`);
      }
      // Its signature is checked; macOS needn't ask again.
      await run("/usr/bin/xattr", ["-dr", "com.apple.quarantine", path]);
      await IOUtils.writeUTF8(PathUtils.join(folder, "install.sh"), MAC_INSTALL_SCRIPT);
    }
    this._ready = { version: offer.version, path };
  },

  _window() {
    return lazy.BrowserWindowTracker.getTopWindow({ private: false }) || null;
  },

  _askToRestart(version) {
    const prompt = Services.prompt;
    const choice = prompt.confirmEx(
      this._window(),
      "Update ready",
      `${APP_NAME} ${version} is ready. Restart now to finish updating. Or keep working: it installs when you quit ${APP_NAME}.`,
      prompt.BUTTON_POS_0 * prompt.BUTTON_TITLE_IS_STRING +
        prompt.BUTTON_POS_1 * prompt.BUTTON_TITLE_IS_STRING +
        prompt.BUTTON_POS_0_DEFAULT,
      "Restart Now",
      "Later",
      null,
      null,
      {}
    );
    this._installAtQuit = true;
    if (choice === 0) {
      this._restart();
    }
  },

  /** Quits to install, opening the browser again (with its tabs) after. */
  _restart() {
    this._relaunch = true;
    Services.prefs.setBoolPref("browser.sessionstore.resume_session_once", true);
    Services.startup.quit(Ci.nsIAppStartup.eAttemptQuit);
    if (!Services.startup.shuttingDown) {
      // Something asked to keep the browser open (closing many tabs, a page
      // with unsaved changes) and the person chose to: install at the next quit.
      this._relaunch = false;
      Services.prefs.clearUserPref("browser.sessionstore.resume_session_once");
    }
  },

  observe(_subject, topic) {
    if (topic === "quit-application" && this._installAtQuit && this._ready) {
      try {
        this._installAfterQuit();
      } catch (error) {
        console.error("[updates] install failed:", error);
      }
    }
  },

  /** Hands the install to a helper that waits for this process to end. */
  _installAfterQuit() {
    const { path } = this._ready;
    const relaunch = this._relaunch;
    if (AppConstants.platform === "macosx") {
      const app = this._macApp();
      const script = PathUtils.join(this._folder(), "install.sh");
      // Detached (nohup, in the background), so it outlives the browser.
      launch("/bin/sh", [
        "-c",
        'nohup /bin/sh "$0" "$@" >/dev/null 2>&1 &',
        script,
        String(Services.appinfo.processID),
        app.path,
        path,
        relaunch ? "1" : "0",
      ]);
    } else {
      // The installer waits for the browser to close (/UPDATE), installs
      // without a window (/S) where the browser is, and opens it again if asked.
      launch(path, ["/S", "/UPDATE", ...(relaunch ? ["/RELAUNCH"] : [])]);
    }
  },

  /** For a copy that can't replace itself: a bar with a link to the new version. */
  _showDownloadBar(version) {
    const window = this._window();
    if (!window?.gNotificationBox) {
      return;
    }
    const box = window.gNotificationBox;
    if (box.getNotificationWithValue(NOTIFICATION_ID)) {
      return;
    }
    const download = Services.prefs.getStringPref(DOWNLOAD_PREF).replace("%OS%", this.platform().os);
    box.appendNotification(
      NOTIFICATION_ID,
      {
        label: `${APP_NAME} ${version} is ready. Download it, then open it to replace this version; your tabs and settings stay.`,
        priority: box.PRIORITY_INFO_MEDIUM,
      },
      [
        {
          label: "Download",
          accessKey: "D",
          callback() {
            window.openTrustedLinkIn(download, "tab");
          },
        },
      ]
    );
  },

  QueryInterface: ChromeUtils.generateQI(["nsIObserver"]),
};
