# chrome/browser/orbit — the Orbit browser component

Orbit's own behaviour in the browser, the Chromium counterpart of the Firefox
build's `browser/modules/Orbit*.sys.mjs`. In Firefox these were JavaScript
modules dropped into `omni.ja`; Chromium's browser UI is C++, so they are a
component compiled into the browser and wired in by patches
(see [`../../../../../patches/README.md`](../../../../../patches/README.md)).

Everything here is generated from or reads `orbit_generated.h`, which
`scripts/build.py` writes from `scripts/orbit_config.py` (version, build, the
Orbit apps, the account and AI URLs, the update feed and public key). Python and
C++ therefore never disagree about Orbit's data.

## What it provides (behaviour to preserve from the Firefox build)

- **The Orbit button.** A toolbar button, in place of Chromium's profile/avatar
  menu, opening a bubble with the person's Orbit account (from Mission Control,
  `ORBIT_ACCOUNT.accounts`) and each Orbit app (`ORBIT_APPS`), plus Sign in /
  Sign out. Orbit Pass opens its in-browser vault page, the others their URL.
- **Orbit AI.** The browser's only assistant: a side panel and "Ask Orbit AI" /
  "Summarize page" entries that open Orbit AI (`ORBIT_AI`). Chromium's own GenAI
  assistants are locked off by policy (`../../../../distribution/policies/`).
- **The new tab.** Orbit's wallpapers (`../../../../branding/content/wallpapers/`)
  and the Orbit apps as the shortcut tiles, in place of Chromium's Google ones.
- **Managed bookmarks.** The Orbit apps on the bookmarks bar for a new profile
  (also done by the `ManagedBookmarks` policy, so a profile gets them without the
  component).
- **Updates.** `update/` checks Orbit Mission Control half a minute after start
  and every four hours (and from Help › Check for Updates…), downloads a newer
  build, verifies its signature against `ORBIT_UPDATES.pubkey`
  (`scripts/sign_update.py` signs it, minisign/Blake2b, the version in the
  signature), and installs it when the browser quits — the same protocol as every
  other Orbit app (`src-tauri/src/updates.rs`; keep them alike). Chromium's own
  updater (Omaha/Keystone) is not built (`build/args/common.gn`), so this is the
  only updater.

## Files (added as overrides) and their wiring patches

| File (here → `src/chrome/browser/orbit/`) | Wired by patch |
| --- | --- |
| `orbit_browser.{h,cc}` — component entry, reads `orbit_generated.h` | `chrome/browser/BUILD.gn`, browser startup |
| `orbit_toolbar_button.{h,cc}` | `chrome/browser/ui/views/toolbar/BUILD.gn` + toolbar view |
| `orbit_ai_side_panel.{h,cc}` | `chrome/browser/ui/views/side_panel/BUILD.gn` + registry |
| `orbit_new_tab.{h,cc}` + wallpaper resources | `chrome/browser/new_tab_page/BUILD.gn` |
| `update/orbit_updates.{h,cc}`, `update/orbit_signature.{h,cc}` | `chrome/browser/BUILD.gn` + startup |
| `BUILD.gn` — the `//chrome/browser/orbit` target | referenced from `chrome/browser/BUILD.gn` |

These C++ files are authored against the synced Chromium tree (their APIs — Views,
SidePanelRegistry, the toolbar container — change between milestones), then added
here and their `BUILD.gn` wiring committed as patches. They are intentionally not
committed as stubs that would not compile.
