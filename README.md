# Orbit Browser

Orbit's web browser for the Mac and Windows. Its engine is Mozilla's Firefox, the newest release
(pinned in `firefox.json`, now **157.0.1**). Orbit Browser takes Mozilla's own signed release
builds and makes them Orbit's:

| | What Orbit Browser does | Where |
| --- | --- | --- |
| **Name and logo** | "Orbit Browser" everywhere Firefox names itself; the Orbit family's mark, a globe with an orbit for its equator, on violet and magenta | `branding/`, `scripts/build_icon.py`, `scripts/orbitmark.swift` |
| **Colours** | Orbit's in the window instead of Firefox's violet and orange: a night-sky slate, Orbit teal and indigo | `browser/content/orbit-browser.css` |
| **Wallpapers** | The new tab's Firefox wallpapers (foxes, promotions) replaced by Orbit's own: space in Orbit teal | `scripts/wallpapers.swift`, `branding/content/wallpapers/`, `scripts/omni_patches.py` |
| **Mozilla's AI** | Every AI feature off and locked, the settings page for them gone, the on-device AI libraries not shipped | `distribution/policies.json`, `scripts/build.py` |
| **Orbit AI** | The only chatbot: in the sidebar, "Ask Orbit AI" on selected text, "Summarize page" | `scripts/omni_patches.py`, Orbit AI's `/threads/start/` |
| **Orbit Pass** | Built in: on the toolbar from the first start, listed under Add-ons, can be turned off but not removed | `browser/modules/OrbitBrowser.sys.mjs`, Orbit Pass's `extension/` |
| **Updates** | Firefox's updater removed (it would install Mozilla's Firefox over Orbit Browser); Orbit Browser updates itself from Orbit Mission Control as every other Orbit app does, with its own version (not Firefox's) | `browser/modules/OrbitUpdates.sys.mjs` |
| **Mozilla's services** | No Mozilla account or Sync, no Firefox Suggest, Pocket stories, VPN, Relay or Monitor, no telemetry, studies, crash reports, sponsored content, promotions or fox-themed onboarding | `distribution/policies.json`, `branding/firefox-branding.js` |
| **Orbit's instead** | An Orbit button on the toolbar: your Orbit account and the Orbit apps; the Orbit apps on the bookmarks toolbar and as the new tab's shortcuts | `browser/modules/OrbitBrowser.sys.mjs`, `scripts/build.py` (`ORBIT_APPS`) |
| **Autofill** | Orbit Pass's alone: Firefox's password manager, card and address autofill and form history are off and locked | `distribution/policies.json` |

The engine itself (XUL, the web platform, the JavaScript engine, security fixes) is Mozilla's,
unchanged: Orbit Browser reports itself to websites as the Firefox it is built on.

## How it's made

`scripts/build.py` *repacks* Firefox rather than compiling it: it downloads the release
`firefox.json` pins (checking Mozilla's SHA-512), unpacks it and changes what can be changed
without a compiler: the front-end code, strings and images in `omni.ja`, the default prefs, the
enterprise policies, the executables' icons and details, and which files ship. That keeps Mozilla's
optimised, tested builds, and moves to a new Firefox in minutes; a compiled fork needs about 40 GB
and hours per platform, and would have to rebuild every Firefox security release.

```bash
python3 scripts/build.py                                   # the Mac app (on a Mac)
python3 scripts/build.py --platform win64 --platform win64-aarch64
python3 -m unittest discover -s tests                      # every change still applies to the pinned Firefox
python3 tests/smoke.py --shots work/smoke                  # start the Mac app and check it from inside
```

| Platform | Build on | Needs | Makes (in `dist/`) |
| --- | --- | --- | --- |
| `mac` | macOS | Python 3, Node, clang (Xcode's command line tools) | `Orbit-Browser-<version>-macOS.dmg`, one app for Apple silicon and Intel |
| `win64`, `win64-aarch64` | macOS or Linux | Python 3, Node (`npm ci` once), bsdtar (`libarchive-tools` on Linux), makensis (`nsis`) for the installer | `…-Windows-x64-Setup.exe` / `…-arm64-Setup.exe`, and a portable `.zip` of each |

Orbit Pass comes from the Orbit Pass checkout beside this one (`../Orbit Pass`, or
`--orbit-pass <path>`): the build runs its `extension/scripts/package.mjs --firefox`. Downloads
are kept in `.cache/`, unpacked builds in `work/<platform>/`. `--sign "Developer ID Application"`
signs the Mac app with a Developer ID (see [The Mac app](#the-mac-app)).

**Versions.** Orbit Browser has its own version, `VERSION` in `scripts/build.py` (now
**0.1.0**), apart from the Firefox it is built on: `0.1.0` for a release, `0.1.0-build.N` for a
build on `main`, `0.1.0-local` here (`--build N`, `--release`). People see it in the About window
and Settings, with "Built on Firefox 157.0.1" under it; the Mac app's `CFBundleShortVersionString`
and the Windows executables' product version are it too. The engine keeps Firefox's (its
`application.ini`, the user agent, add-ons). Raise `VERSION` for a release (tag `v<VERSION>`); a
new Firefox alone needs no new version, since every build on `main` is newer by build number.

### Moving to a new Firefox

Mozilla ships a release about every four weeks and security fixes between them; Orbit Browser gets
them only by being rebuilt. GitHub checks daily and goes red when a newer Firefox is out (see
[Builds on GitHub](#builds-on-github)). Then:

```bash
python3 scripts/update_firefox.py              # pins the newest release in firefox.json
python3 -m unittest discover -s tests          # every patch, policy and locked pref still fits
python3 scripts/build.py && python3 tests/smoke.py
```

A test that fails names the change that no longer fits: a patch whose text Firefox moved, a policy
or pref it renamed, a file it moved. Fix that change (in `scripts/omni_patches.py`,
`distribution/policies.json` or `scripts/build.py`); never loosen the check, or a feature that was
removed comes back quietly.

## Mozilla's AI features, removed

Firefox's AI features are switched off and **locked** by the enterprise policy Mozilla made for
the purpose, `AIControls`, with everything blocked by default (so an AI feature Mozilla adds later
under the same switch arrives blocked) and the sidebar chatbot kept for Orbit AI alone:

- **Translations** (on-device machine translation). Mozilla counts it among its AI features. To
  bring it back, add `"Translations": {"Value": "available", "Locked": true}` to `AIControls`.
- **Smart Window**: Mozilla's AI window, its agent and the memories it builds from history and
  conversations (`browser.smartwindow.*`, also locked off by pref, since an experiment or the
  window's own launcher would otherwise turn it on).
- **Smart tab groups**: AI-suggested tab groups and names.
- **Link previews**: AI summaries of linked pages.
- **PDF alt text**: generated image descriptions in the PDF editor, and its model download.
- **On-device speech recognition**.
- **The chatbot providers** (Claude, ChatGPT, Copilot, Gemini, HuggingChat, Mistral, localhost):
  hidden; Orbit AI is the only one and can't be changed.

And, locked by pref in the same file: the ML engine itself (`browser.ml.enable`), the trial ML API
for extensions (`extensions.ml.enabled`), semantic history search, ML field detection in form
autofill, the address bar's ML suggestions, Google Lens image search, and the new tab page's
inferred interests. Settings' **AI Controls** page is hidden (`browser.preferences.aiControls`).

The native libraries only these features use aren't shipped at all: `libmozinference` (llama.cpp
and the Parakeet speech model) and `libonnxruntime` on the Mac, `mozinference.dll` and
`onnxruntime.dll` on Windows (Windows on Arm has only the first). The engine loads them only on
demand, and starts fine without them. `about:policies` lists every policy in force; Settings says
the browser is "managed by your organization" because of them.

## Orbit, not Mozilla's services

Firefox signs people in to a Mozilla account and leans on Mozilla's services throughout. Orbit
Browser turns them off and puts Orbit's in their place.

Off, by policy (`distribution/policies.json`): the Mozilla account and everything on it (Sync,
Send Tab, the toolbar's account button, the Sync settings), Firefox Suggest's online suggestions,
the home page's stories and weather, Mozilla's built-in VPN (IP Protection), the feedback commands,
studies and telemetry. Off by default (`branding/firefox-branding.js`): mozilla.org's control of
the browser's tours (UITour), "Report Broken Site", Mozilla Monitor's breach alerts, the
protections page's Mozilla cards, Relay and pinning promotions, weather in the address bar, crash
reports, sponsored tiles and suggestions, Mozilla's list of new-tab shortcuts and its tiles
service, and "More from Mozilla". Firefox Relay is locked to `unavailable` (Firefox still offers
it when it is merely "disabled"). Pocket is gone from Firefox itself.

Where the policies only grey things out, `scripts/omni_patches.py` takes them away: the Help menu's
Share Ideas and Feedback, Report Broken Site, Report Deceptive Site and Switching to a New Device
(also in the Mac's windowless menu bar, with the Smart Window items); Settings' first page loses
Mozilla's account, Sync and "Share Firefox" groups and is called General.

**Autofill is Orbit Pass's alone.** Firefox's own password manager (saving, filling, the password
generator, the Passwords page and its sidebar), its card and address autofill and its form history
are off and locked (`PasswordManagerEnabled`, `AutofillCreditCardEnabled`,
`AutofillAddressEnabled`, `DisableFormHistory`, and `signon.autofillForms` and
`signon.generation.enabled`), so login, card and address fields show only Orbit Pass's menu.
Settings has no "Passwords and autofill" page and the app menu no "Passwords". (The address bar
still completes addresses you've visited; that's navigation, not form filling.) The sidebar's tools are Orbit AI, History and Bookmarks: Synced Tabs needs a Mozilla account, so
it isn't registered at all while accounts are off (not in the launcher, its Customize panel or the
View menu, whatever an older profile's saved list says).

In their place:

- **The Orbit button** (the family's planet, where Mozilla's account button was) opens a panel: your
  Orbit account (the name of the account you're signed in to in Mission Control, from
  `/a/api/accounts/` with this browser's session, and "Manage your Orbit account"; or "Sign in to
  Orbit"), the Orbit apps (Orbit AI, Mail, Calendar, Chat, and Orbit Pass's own vault page inside
  the browser), and "Sign out of Orbit" (Mission Control's sign-out, which ends every Orbit app's
  session). It's built in `OrbitBrowser.sys.mjs` with Firefox's own toolbar-panel parts, styled by
  `browser/content/orbit-browser.css`; the apps' marks are in `branding/content/apps/`.
- **Bookmarks**: a new profile starts with the Orbit apps on the bookmarks toolbar
  (`default-bookmarks.html`, written by the build from `ORBIT_APPS`) instead of Firefox's
  "Mozilla Firefox" folder; a profile made before has Firefox's taken out and the Orbit apps added,
  once, leaving everything else alone.
- **The new tab's shortcuts** default to the Orbit apps.

What stays Mozilla's, because the engine depends on it: add-ons come from addons.mozilla.org (the
only place Firefox accepts signed add-ons from); Safe Browsing, certificate revocation and the
blocklists come through Mozilla's servers; "Learn more" links and Help go to Mozilla's support
pages, which describe this engine.

## Colours

Firefox's new look is violet and orange: a violet-to-orange edge on the selected tab, a
violet-to-peach wash across the tab strip, violet greys and a violet accent.
`browser/content/orbit-browser.css` gives the window Orbit's instead, by setting Firefox's own
design tokens:

- **The selected tab** has a teal-to-indigo edge.
- **The tab strip** runs from indigo into teal, over white, or over deep navy in dark mode.
- **The greys** (text, icons, hovers, borders) are Firefox's, cooled to slate.
- **The accent** (focus rings, primary buttons, the loading tab) is Orbit teal.

Only the default, Light and Dark themes change. A theme the person installs, private windows
and high contrast keep their own colours. The smoke test checks the selected tab and the tab
strip, so a Firefox that renames these tokens fails it rather than bringing the orange back.

## Wallpapers

Firefox keeps a category of its own among the new tab's wallpapers. The page names it after the
browser, so it said "Orbit Browser" over pictures of foxes, and Mozilla uses it for promotions too
(World Cup teams, a football club). Orbit Browser puts its own there instead: eight space scenes in
Orbit teal, with the family's tilted orbit and its moon.

- **Planet**: the mark as a world. A banded teal planet, its orbit passing behind it above and in
  front of it below, the moon riding it at the top right.
- **Nebula**, **Horizon** (a planet's edge at night, its air lit by a rising sun), **Eclipse** and
  **Comet**.
- **Orbits**: the mark drawn out flat, dark and light. **Daybreak**, light: the day side of a teal
  planet, a moon's orbit across the sky.

`scripts/wallpapers.swift` draws them from code into `branding/content/wallpapers/`, each at
3840 × 2160 with a 480 × 270 thumbnail for the picker. Its seeds are fixed, so a run makes the same
files:

```bash
xcrun swiftc -O -o /tmp/wallpapers scripts/wallpapers.swift
/tmp/wallpapers preview /tmp/previews              # quick 1600 × 900 PNGs
/tmp/wallpapers write branding/content/wallpapers
```

They're JPEG: ImageIO writes an AVIF over 512 pixels as a grid of tiles, which Firefox won't
decode. The build ships them at `chrome://branding/content/wallpapers/`, and a patch to the new
tab's wallpaper feed (`ORBIT_WALLPAPERS` in `scripts/omni_patches.py`) offers them in place of the
Firefox category, each with a name for screen readers. Mozilla's other categories (abstract,
celestial, photographs, solid colours) stay, and still come from Mozilla's servers. Someone who had
picked one of the Firefox wallpapers has none until they choose again.

Between releases Mozilla can swap the new tab for a newer copy of its own (a "train-hop" add-on),
which would bring the Firefox wallpapers back. `branding/firefox-branding.js` turns that off
(`browser.newtabpage.disableNewTabAsAddon`), so the new tab is always the one the build changed.

## Orbit AI

Firefox's sidebar chatbot, pointed at Orbit AI and nothing else:

- `scripts/omni_patches.py` adds Orbit AI to the providers in `GenAI.sys.mjs` (named "Orbit AI",
  Orbit AI's own violet mark from `branding/content/orbit-ai.svg`), and names it in the sidebar's
  and menus' strings.
- `distribution/policies.json` locks `browser.ml.chat.provider` to
  `https://ai.orbit.com.ai/threads/start/` and `browser.ml.chat.providers` to it alone.
- The sidebar opens that address: a fresh New Orbit (Orbit AI's README, "Orbit AI in Orbit
  Browser"). For "Ask Orbit AI" (selected text: summarize, explain, quiz, proofread) and
  "Summarize page", Firefox types the request into Orbit AI's composer and sends it
  (`supportAutoSubmit`); a patch to `GenAIChild.sys.mjs` lets it find `textarea#composer-input`.
  The request never goes in an address. It goes to Orbit AI only when the person asks.

Signed out, the sidebar shows Orbit's sign-in (Mission Control) and comes back. The sidebar's
own frame is styled to match (`APPENDED_STYLES` in `scripts/omni_patches.py`): "Orbit AI" is a
title, not a menu with one entry, the frame takes Orbit's black-and-white accent instead of
Firefox's purple, and Mozilla's "New" badges are off. The sidebar is about 400 px wide; Orbit AI's
composer fits it (its narrow-screen styles keep the model's name and show the thinking level and
Web as icons).

## Orbit Pass

Orbit Pass is a *built-in* add-on: its files sit inside `omni.ja`
(`resource://builtin-addons/orbit-pass/`), and `OrbitBrowser.sys.mjs` installs it from there at
every start (`AddonManager.maybeInstallBuiltinAddon`, the way Firefox installs its built-in themes),
so it needs no Mozilla signature, isn't downloaded, and can't be removed, only turned off. The build:

- takes Orbit Pass's Firefox package and stamps its version with a checksum of its files
  (`1.0.0.37488415`, say), so a profile replaces its copy exactly when Orbit Pass changes;
- adds `granted_host_permissions`, so it may fill on every site from the start (built-in add-ons
  are privileged; it also runs in private windows);
- gives it a fixed address, `moz-extension://cabce947-8111-49e9-a61f-0224b07a4dfd/`
  (`extensions.webextensions.uuids` in `branding/firefox-branding.js`), which Orbit Pass's server
  always accepts for sign-in (`ORBIT_BROWSER_PASS_UUID` there). Change one, change both.

On a new profile it opens its welcome page ("Sign in with Orbit"), and its button is on the toolbar.

## The start-up module

`browser/modules/OrbitBrowser.sys.mjs` is added to `omni.ja` and called from Firefox's own start-up
categories (two lines the build appends to `components/components.manifest`):

- **Before the first window**: installs the built-in add-ons; adds the Orbit button; and drops compiled-script caches
  made by a different Orbit Browser build. Firefox throws those away only when *Firefox's* version
  changes, so each build stamps itself (`orbitbrowser.stamp`, a default pref) and a new stamp asks
  for fresh caches at the next start.
- **When idle**: swaps Mozilla's default bookmarks for the Orbit apps in a profile made before
  Orbit Browser had them (once), and starts the updates (below).
- **Each window**: Orbit Browser's styles, and **Help › Check for Updates…** (on Windows it is in
  the app menu's Help too).

## Updates

Orbit Browser updates itself the way every other Orbit app does on the Mac and Windows (their
`src-tauri/src/updates.rs`; `browser/modules/OrbitUpdates.sys.mjs` here, kept alike):

- **When**: half a minute after it starts and every four hours after that, and from **Help ›
  Check for Updates…**, the About window's **Check for updates** and the one in Settings' **About
  Orbit Browser**. It asks Orbit Mission Control
  (`/api/updates/orbit-browser/<darwin|windows>/<universal|x86_64|aarch64>/<version>?build=<n>`,
  `orbitbrowser.updates.url`), which answers from this repository's GitHub releases.
- **What**: a newer build downloads quietly and is checked before anything is installed
  (`browser/modules/OrbitSignature.sys.mjs`): Ed25519 over the download's BLAKE2b-512, minisign's
  form, as the Tauri updater checks the other apps, with the public key in
  `orbitbrowser.updates.pubkey` (read from the build's defaults only), and the signature must name
  the version announced. Then one prompt: **Restart Now**, or **Later**, and it installs when Orbit
  Browser quits. From the menu it also says when it's up to date or the check failed.
- **How**: once the browser has quit, a helper that waits for it finishes the job (Firefox starts
  processes from its own files the whole time it runs). On the Mac the new app
  (`Orbit-Browser-<v>-macOS.app.tar.gz`, unpacked) takes the old one's place and opens again after
  Restart Now, tabs and all. On Windows the new version's installer runs over the old one with
  `/S /UPDATE` (and `/RELAUNCH`), waiting for the browser to close.
- **A copy that can't replace itself** (on the Mac, one in a folder it can't write to; on Windows,
  the portable zip, not the copy the installer registered) shows a bar with a **Download** button
  (`/download/orbit-browser/<mac|windows>/`) instead. The Orbit Installer and a drag from the disk
  image leave the app the person's own, so it can.
- `orbitbrowser.updates.enabled = false` stops the checks in the background; the menu still checks.

Releases are signed by `scripts/sign_update.py`, as the Tauri CLI signs the other apps' (the CLI's
own `signer sign` doesn't put the version in, which Mission Control requires), with a Tauri
signing key: `TAURI_SIGNING_PRIVATE_KEY` (and `_PASSWORD`) in the workflow; it was made with
`cargo tauri signer generate` and is kept at `~/.tauri/orbit-browser.key` on the Mac it was made on.
Mission Control's catalog (`apps/releases/catalog.py`) has `orbit-browser` with
`Orbit-Browser-*-macOS.app.tar.gz` as the Mac update (the `.dmg` stays the download) and the
`-Setup.exe` installers on Windows; a release is offered once it carries `orbit-update.json`.

## The Mac app

- **Its own data folder.** Firefox keeps its data in `~/Library/Application Support/Firefox`, and
  recent macOS guards that folder for Firefox alone (seen on macOS 27), so Orbit Browser couldn't open it on a
  Mac that has Firefox. The app's executable is a small launcher (`browser/launcher/orbit-browser.c`)
  that runs the engine (`Contents/MacOS/firefox`) with Orbit Browser's own
  `Contents/Resources/browser/application.ini` (through `XUL_APP_FILE`, which Firefox's `-app`
  sets): the same engine, `Name=Firefox` still (the user agent and add-ons go by it), but
  `Profile=Orbit Browser`, so its data is in `~/Library/Application Support/Orbit Browser` and
  `~/Library/Caches/Orbit Browser`. Crash reports don't go to Mozilla (`[Crash Reporter]
  Enabled=0`).
- **Its icon in the Dock.** `ditto` keeps Mozilla's dates on everything it copies, and macOS keeps
  showing whatever icon it first saw for an app whose date hasn't changed; a bundle that was once
  Firefox.app went on showing the fox as it launched. The build dates the app afresh and registers
  it with Launch Services (`register_mac_app`). It won't replace an app that is running
  (`--work work-test` builds elsewhere).
- **Info.plist**: name, `ai.com.orbit.browser`, the launcher, Orbit's icons (`firefox.icns`, and no
  `Assets.car`, which held Firefox's macOS 26 icon), permission prompts that name Orbit Browser.
- **Signing.** The engine and the app are signed again (their contents changed), with Mozilla's
  entitlements less the two only Mozilla can hold: its application identifier, and
  `com.apple.developer.web-browser.public-key-credential`, which Apple grants per browser through a
  provisioning profile. Without it, **passkeys stored in iCloud Keychain aren't offered**; security
  keys and Orbit Pass's passkeys still work. Ad hoc (locally), Mozilla's signatures on XUL, the
  libraries and the helper apps are left as they are. With a Developer ID, everything is signed
  again, innermost first, each helper app keeping its entitlements, since notarization accepts only
  an app whose code is all the team's. (Don't sign everything ad hoc: the helper processes, under
  the hardened runtime, then refuse to load XUL.)

## Windows

- **Executables**: every icon in `firefox.exe` (the app, documents, PDF, the jump list's, and the
  alternative icons Firefox lets people pick, a picker Orbit Browser turns off) and
  `private_browsing.exe` becomes Orbit Browser's, and their details name it
  (`scripts/win_resources.mjs`, with `resedit`). Editing them drops Mozilla's Authenticode
  signature; the installers are unsigned, so SmartScreen warns on first run until a code-signing
  certificate is added.
- **The installer** (`installer/windows/OrbitBrowser.nsi`) installs for the person running it, with
  no administrator, in `%LOCALAPPDATA%\Programs\Orbit Browser`; adds Start menu and desktop
  shortcuts and an Apps & features entry; registers Orbit Browser with Windows as a browser under
  its own name, and offers to open Default apps at the end. A new version replaces the old files;
  the uninstaller leaves profiles alone. For an update (`/S /UPDATE`, from the browser as it quits)
  it waits up to a minute for the browser to close instead of asking, leaves a deleted desktop
  shortcut deleted, and with `/RELAUNCH` opens the browser again.
- **Firefox's own "make default"** is turned off on Windows (`DefaultBrowserSettingEnabled`): it
  registers the browser under Firefox's name. So are the default-browser agent and the desktop
  launcher (which reinstalls Mozilla's Firefox).
- **Data** stays where Firefox keeps it, `%APPDATA%\Mozilla\Firefox`, in a profile of Orbit
  Browser's own: Firefox gives every installation its own profile. Windows doesn't guard the
  folder, and pinning a running window to the taskbar launches `firefox.exe` directly, which a
  launcher like the Mac's would miss.

## Tests

| Suite | Command | Covers |
| --- | --- | --- |
| Build | `python3 -m unittest discover -s tests` | Against the pinned Firefox (its Windows installer, unpacked anywhere): every patch matches exactly once, the files the build replaces are there, the start-up hooks it relies on exist, every policy is one this Firefox has and implements and every locked pref one it knows; Orbit's wallpapers drawn, loadable by the new tab and named apart from Mozilla's, and the built-in new tab kept; Orbit Browser's own version; the Mac app's `application.ini`; update signatures: what `scripts/sign_update.py` signs, the browser's own check accepts (run under Node by `tests/verify_signature.mjs`), as it does a file the Tauri CLI signed (`tests/fixtures/`, a throwaway key), and a changed download or another key is refused (18 tests; needs `cryptography` and Node 25 or later, for `Uint8Array.fromBase64`) |
| Mac app | `python3 tests/smoke.py [--shots work/smoke]` | Starts `work/mac/Orbit Browser.app` headless in a fresh profile over Marionette (`tests/marionette.py`) and checks from inside: the name, the data folder, the policies, every AI pref off and locked and every AI control blocked, the AI libraries and updater gone, Orbit AI the only chatbot and opening in the sidebar, Orbit Pass built in at its address with every site and private windows, no Mozilla account, the Orbit button and its apps, the Orbit bookmarks and no Mozilla ones, the Help menu (with Check for Updates), File menu and sidebar without Mozilla's items, Orbit Browser's version and the Firefox under it in the About window and Settings with a working Check for updates, Relay and Mozilla's shortcuts, stories and weather off, Firefox's password manager, card and address autofill and form history off and locked (its Passwords page blocked, no autofill page in Settings, no Passwords in the app menu), no "Firefox" or Mozilla account in the home page, Settings and Add-ons, and the new tab built in, offering Orbit's wallpapers first (each loading) and not the Firefox ones |

The Windows builds are checked on a Mac by inspection (icons and details of the executables,
imports, the removed files, the policies); they haven't been run on Windows here.

## Builds on GitHub

`.github/workflows/build.yml` runs on every push to `main`, every `v*` tag (`v0.1.0`, which must
be `VERSION` in `scripts/build.py`), pull requests and on demand: the tests on Ubuntu, both Windows
builds on Ubuntu, the Mac build on macOS (then the smoke test), and a release: a pre-release for
each push to `main`, a release for a tag. Every day it checks Mozilla's newest Firefox and fails
when Orbit Browser is behind.

| Secret | What |
| --- | --- |
| `ORBIT_PASS_TOKEN` | A fine-grained token with read-only Contents on `Orbit-AI-LLC/Orbit-Pass` (private), to build Orbit Pass in |
| `TAURI_SIGNING_PRIVATE_KEY`, `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | Orbit Browser's update key (`~/.tauri/orbit-browser.key`, no password), to sign the updates (see [Updates](#updates)). Without it releases are made but installed browsers aren't offered them |
| `MACOS_CERTIFICATE_P12`, `MACOS_CERTIFICATE_PASSWORD`, `APPLE_TEAM_ID`, `NOTARY_APPLE_ID`, `NOTARY_PASSWORD` | As in Orbit Pass: a Developer ID to sign the Mac app, and notarytool to notarize the disk image. Without them the app is signed ad hoc, and macOS blocks it when downloaded until it's opened with Control-click > Open |

## Layout

```
firefox.json              the Firefox release and the checksums of its builds
scripts/build.py          the build: fetch, unpack, change, sign, package (VERSION: Orbit Browser's own)
scripts/sign_update.py    sign the update payloads for Mission Control, as the Tauri apps' are
scripts/omni_patches.py   the changes to Mozilla's own files in omni.ja, each matched exactly
scripts/update_firefox.py pin a Firefox release
scripts/build_icon.py     every form of the logo, from scripts/orbitmark.swift (the family renderer)
scripts/wallpapers.swift  the new tab's wallpapers, into branding/content/wallpapers/
scripts/win_resources.mjs icons and details of the Windows executables
browser/modules/          OrbitBrowser.sys.mjs, the start-up module; OrbitUpdates.sys.mjs and
                          OrbitSignature.sys.mjs, the updates and their signature check
browser/launcher/         the Mac app's launcher
branding/                 the logo in every form, the names (locales/), the default prefs (firefox-branding.js)
distribution/policies.json  the locked policies (AI off, Orbit AI, no updater, no telemetry)
installer/windows/        the NSIS installer
tests/                    the build tests, the smoke test and its Marionette client, the
                          signature check under Node and its fixtures
.github/                  the build and release workflow, the update manifest script (shared)
```

## The logo

`scripts/orbitmark.swift` is the Orbit family's mark renderer, the same file in Orbit AI, Chat, IDE,
Mail, Mission Control, Pass and the Website. Orbit Browser's mark is a globe drawn in line, its rim,
one meridian and a latitude ring, with the family's tilted orbit and moon for its equator, white on
violet and magenta (`#b07cff` → `#e0379a`). It is the family's only open globe, so it doesn't read as the solid planet of Orbit's
own mark. At 16 px, where the family drops the orbit, the globe draws an equator of its own.
`scripts/build_icon.py` renders the Mac icon, the Windows icons and tiles, the browser's own logo
pages and the toolbar's mark from it, and Orbit AI's mark for the sidebar. The wordmark is "Orbit
Browser" in Inter Display SemiBold, outlined. After changing `orbitmark.swift`, copy it to the other
repositories, re-run the Website's `scripts/build_icon.py` (it writes the `orbit-browser` entry the
other apps' `orbit_icons.py` copy) and run Orbit Mission Control's `scripts/check_shared.py`.

## Limitations

- **Streaming video protected by Widevine** may be refused or played at lower quality by services
  that check the browser's binaries: Mozilla's host signatures (`*.sig`) cover `firefox.exe` and
  the Mac engine, which Orbit Browser edits or signs again.
- **iCloud Keychain passkeys** on the Mac (above). Windows Hello passkeys are unaffected.
- **English (US)** only: the repack starts from Mozilla's en-US builds.
- **Crash reports on Windows**: Mozilla's crash reporter is compiled into `firefox.exe` with
  Mozilla's address; Orbit Browser turns off sending reports from the browser, but after a crash
  the reporter's own window can still offer to send one to Mozilla. (On the Mac it's off in
  `application.ini`.)
- **The home page** wasn't checked visually: in the headless test, Firefox's new tab page stays
  blank (Mozilla's build does the same; the page's feeds never start), so its text check finds
  nothing to read. The wallpapers are checked through the new tab's own feed instead.
- **Mozilla's AI code is still inside `omni.ja`**, switched off and locked; only its native
  libraries are gone. Taking the code out too would mean editing Mozilla's modules wholesale and
  breaking with every Firefox release.
- **Sync** uses a Mozilla account, as in Firefox; it hasn't been tried here.

## Licence

Firefox is Mozilla's, under the Mozilla Public License 2.0; the files Orbit Browser changes in
`omni.ja` are source code and stay under it (this repository holds every change). "Firefox" and
its logos are Mozilla's trademarks, which is why Orbit Browser carries its own name and logo and
says, where Firefox credits itself, that it is built on Firefox.
