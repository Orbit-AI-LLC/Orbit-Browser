# Orbit Browser

Orbit's web browser for the Mac, Windows and Linux. Its engine is Chromium, the
newest stable release (pinned in `chromium.json`). Orbit Browser is a **source
fork**: it compiles Chromium with Orbit's changes, rather than repacking a
downloaded binary, so it can change anything — the engine, the UI, the services —
not only what a repack can reach.

| | What Orbit Browser does | Where |
| --- | --- | --- |
| **Name and logo** | "Orbit Browser" everywhere Chromium names itself; the Orbit family's mark, a globe with an orbit for its equator, on violet and magenta | `branding/BRANDING`, `branding/`, `scripts/build_icon.py`, `scripts/orbitmark.swift` |
| **Not Google Chrome** | Built un-Google-branded, with no Google API keys compiled in, so none of Chromium's calls to Google's sign-in, Sync, Safe Browsing or location services have credentials | `build/args/common.gn` |
| **Google's AI** | Every GenAI feature off and locked (`GenAiDefaultSettings` and each individual one), so Orbit AI is the only assistant | `distribution/policies/orbit.json` |
| **Orbit AI** | The only assistant: a side panel, "Ask Orbit AI" on selected text, "Summarize page" | `chromium_src/chrome/browser/orbit/`, Orbit AI's `/threads/start/` |
| **Orbit Pass** | Built in: force-installed and pinned to the toolbar from the first start, un-removable | `distribution/policies/orbit.json`, Orbit Pass's `extension/` |
| **Updates** | Chromium's own updater (Omaha/Keystone) not built; Orbit Browser updates itself from Orbit Mission Control as every other Orbit app does, with its own version (not Chromium's) | `build/args/common.gn`, `chromium_src/chrome/browser/orbit/update/` |
| **Google's services** | No Google account or Sync, no metrics, background services, component updates, spelling or prediction services, no Safe Browsing lookups | `distribution/policies/orbit.json` |
| **Orbit's instead** | An Orbit button on the toolbar: your Orbit account and the Orbit apps; the Orbit apps as managed bookmarks and the new tab's shortcuts | `chromium_src/chrome/browser/orbit/`, `distribution/policies/orbit.json` |
| **Autofill** | Orbit Pass's alone: Chromium's password manager, card and address autofill are off and locked | `distribution/policies/orbit.json` |

The engine itself (Blink, V8, the web platform, security fixes) is Chromium's:
Orbit Browser reports itself to websites as the Chromium it is built on.

## How it's made

`scripts/build.py` *compiles* Chromium. It:

1. fetches depot_tools and the Chromium source `chromium.json` pins
   (`scripts/sync.py`): a big, long first checkout (tens of GB) and `gclient
   sync` for every dependency the pinned tag's DEPS names;
2. applies Orbit's branding (`branding/`), patches (`patches/`) and new files
   (`chromium_src/`) onto a pristine tree (`scripts/patches.py`);
3. runs `gn gen` with Orbit's GN arguments (`build/args/`) and `autoninja` the
   browser;
4. packages per platform into `dist/`.

```bash
python3 scripts/build.py                                   # the host's default: Mac on a Mac, Linux on Linux, else Windows x64
python3 scripts/build.py --platform win64 --platform win64-aarch64
python3 scripts/build.py --platform linux --platform linux-aarch64
python3 scripts/build.py --no-sync                         # reuse the source tree as it is (faster iteration)
python3 -m unittest discover -s tests                      # the committed config and the update signatures
python3 scripts/update_chromium.py --check                 # every patch still applies to the pinned Chromium
```

A source fork is the heavy path a repack avoids: tens of GB of source and hours
per platform, and a rebuild for every Chromium security release. The trade is
reach — a repack can only change the files it can unpack; a fork can change the
browser itself, which is what the Orbit button, the Orbit AI side panel and the
Orbit updater (replacing Chromium's) need.

| Platform | Build on | Needs | Makes (in `dist/`) |
| --- | --- | --- | --- |
| `mac` | macOS | depot_tools' prerequisites, Xcode, Python 3, Node (for Orbit Pass) | `Orbit-Browser-<version>-macOS.dmg` (universal) and an `.app.tar.gz` update payload |
| `win64`, `win64-aarch64` | Windows | depot_tools' prerequisites (Visual Studio), Python 3, Node | `…-Windows-x64-Setup.exe` / `…-arm64-Setup.exe` and a portable `.zip` |
| `linux`, `linux-aarch64` | Linux | depot_tools' prerequisites (`build/install-build-deps.sh`), Python 3, Node | `…-Linux-x86_64.tar.xz` / `…-Linux-aarch64.tar.xz` |

Windows and Linux builds run on their own OS (Chromium's cross-compiles need the
host toolchain); the Mac build needs macOS. Orbit Pass comes from the Orbit Pass
checkout beside this one (`../Orbit Pass`, or `--orbit-pass <path>`): the build
runs its `extension/scripts/package.mjs --chrome`. Downloads and the source
checkout are kept in `.cache/` and `src/`. `--sign "Developer ID Application"`
signs the Mac app.

**Versions.** Orbit Browser has its own version, `VERSION` in
`scripts/orbit_config.py`, apart from the Chromium it is built on
(`chromium.json`): `0.1.0` for a release, `0.1.0-build.N` for a build on `main`,
`0.1.0-local` here (`--build N`, `--release`). People see it in the About window
and Settings, with "Built on Chromium …" under it. Raise `VERSION` for a release
(tag `v<VERSION>`); a new Chromium alone needs no new version, since every build
on `main` is newer by build number.

### Where Orbit's changes live

Everything Orbit Browser changes is kept apart from Google's code, the way the
Chromium forks (Brave, ungoogled-chromium, Vivaldi) keep theirs, so every change
is visible and nothing is quietly edited in place:

- **Branding data** — the name (`branding/BRANDING`) and the product icons
  (`branding/`) — is copied over Chromium's by `scripts/build.py` before the
  build. The mark is rendered by `scripts/orbitmark.swift` (the Orbit family's
  shared renderer) through `scripts/build_icon.py`; edit those, never the files
  in `branding/`.
- **Build-time choices** are **GN arguments** in `build/args/` (a `common.gn`
  and one file per platform): un-Google-branded, no Google API keys, proprietary
  codecs on, Chromium's updater not built.
- **Edits to Chromium's own files** are **unified-diff patches** in `patches/`,
  one per file (`patches/<path-in-src>.patch`), applied with `git apply` —
  strict, so a Chromium that moved the code stops the build and names the patch.
  See `patches/README.md`.
- **Whole new Orbit files** — the Orbit browser component — live in
  `chromium_src/`, copied into the source tree as themselves. See
  `chromium_src/README.md`.
- **What a running browser does by policy** — the locked features and the
  first-run defaults — is in `distribution/` (`policies/orbit.json` and
  `initial_preferences`). See `distribution/README.md`.

`scripts/patches.py` applies the patches and overrides; `scripts/build.py` does
the branding, the GN args and the packaging.

### Moving to a new Chromium

Google ships a new stable Chromium about every four weeks and security fixes
between them; Orbit Browser gets them only by being rebuilt. GitHub checks daily
(see [Builds on GitHub](#builds-on-github)). Then:

```bash
python3 scripts/update_chromium.py                   # pin the newest stable, then check every patch against it
python3 scripts/build.py                             # build
```

`update_chromium.py` pins the version in `chromium.json`, syncs the source to it,
and tries every patch in `patches/` (with `git apply --check`), printing which
still apply and which don't. Give it a version (`142.0.7444.52`) to pin that one;
`--check` alone re-checks the current pin. A patch that no longer applies is one
whose surrounding code Chromium moved; re-anchor it by hand:

```bash
python3 scripts/sync.py                              # src/ at the pinned Chromium
cd src && $EDITOR chrome/browser/…                   # make Orbit's change again
git diff chrome/browser/… > ../patches/chrome/browser/….patch
cd .. && python3 scripts/update_chromium.py --check
```

**Never loosen a patch so it applies without the change it carries**, or a
feature Orbit removed comes back quietly.

## Google's AI features, removed

Chromium's GenAI features are switched off and **locked** by enterprise policy
(`distribution/policies/orbit.json`), with the umbrella `GenAiDefaultSettings`
set to *disabled* (so a GenAI feature Google adds later under it arrives off) and
each individual one set off too: the tab organizer, "Help me write", themes
creation, history search, tab compare, DevTools AI, autofill prediction, Gemini,
and the on-device foundational model download. Orbit AI is the only assistant
(the Orbit browser component). `chrome://policy` lists every policy in force;
Settings says the browser is "managed by your organization" because of them.

## Orbit, not Google's services

Chromium leans on Google's services throughout. Orbit Browser turns them off
(`distribution/policies/orbit.json`) and puts Orbit's in their place: no Google
account or Sync (`BrowserSignin`, `SyncDisabled`), no usage metrics or anonymized
data collection, no background mode, no component updates (Orbit updates itself),
no Google Safe Browsing lookups, no spelling or network-prediction services. The
build also ships **no Google API keys** (`build/args/common.gn`), so even a
missed switch has no credentials to call Google with.

## Orbit Pass is the password manager

Chromium's own password manager and autofill are off and locked, and Orbit Pass
is **force-installed and un-removable** (`ExtensionSettings` →
`force_installed`, `force_pinned`), served by Orbit Mission Control. Its stable
extension id is the same in every copy of Orbit Browser, so Orbit Pass's server
knows the address a sign-in comes back to; keep it in step between this
repository (`scripts/orbit_config.py`) and Orbit Pass (`extension/`). Orbit
Pass's Chromium manifest is made by that repository's
`extension/scripts/package.mjs --chrome`; change the extension there, not here.

## Updates

Orbit Browser updates itself from Orbit Mission Control, the same as every other
Orbit app (`src-tauri/src/updates.rs` in each; keep them alike). Chromium's own
updater is not built (`build/args/common.gn`). Half a minute after start and
every four hours after (and from Help › Check for Updates…) the browser asks
Mission Control whether a newer build exists; a newer one is downloaded, its
signature checked against the public key the browser carries
(`scripts/orbit_config.py` `ORBIT_UPDATES`, the signature naming the version),
and installed when the browser quits. `scripts/sign_update.py` signs the payloads
(minisign/Blake2b, a Tauri signing key as in the other Orbit apps);
`.github/scripts/orbit_update_manifest.py` writes the release's
`orbit-update.json`. This behaviour is implemented in the Orbit browser component
(`chromium_src/chrome/browser/orbit/update/`).

## Builds on GitHub

`.github/workflows/build.yml`:

- **every push and pull request** runs the fast checks on a hosted runner: the
  committed config (`tests/test_config.py`) and the shared update-signature
  protocol (`tests/test_updates.py`);
- **daily** it checks that `chromium.json` is the newest stable Chromium and
  warns if not;
- **a `v*` tag or a manual run** builds each platform on a **self-hosted runner**
  (the Chromium compile is far past a hosted runner's disk and time), signs and
  notarizes the Mac app, signs the update payloads and publishes the release.

See the top of that file for the secrets (Developer ID, notarization, the update
signing key, the Orbit Pass token).

## Status

The pivot from the former Firefox repack to a Chromium source fork is in place:
the build pipeline, the pin and sync, the GN arguments, the branding, the
Chromium enterprise policies, the first-run preferences, Orbit Pass's
force-install, and the tests are complete and config-verified. What remains is
authored against a synced Chromium tree, because its C++ APIs (Views, the side
panel registry, the toolbar container) change between milestones and are not
committed as code that would not compile: the Orbit browser component
(`chromium_src/chrome/browser/orbit/` — the Orbit button, the Orbit AI side
panel, the new-tab wallpapers and the updater) and the few `patches/` that wire
it into Chromium's build and UI (listed in `patches/README.md` and
`chromium_src/chrome/browser/orbit/README.md`).
