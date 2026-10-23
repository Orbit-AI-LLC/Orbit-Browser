# chromium_src/

Orbit's **whole new files**, copied into the Chromium source tree before the
build (`scripts/patches.py` → `copy_overrides`). The path under `chromium_src/`
is the path under `src/`: `chromium_src/chrome/browser/orbit/foo.cc` is copied to
`src/chrome/browser/orbit/foo.cc`. The build's `BUILD.gn` files — edited by a
patch in [`../patches/`](../patches/) — pull these into the compile.

Use this for files that are Orbit's own. To **edit** one of Chromium's existing
files, use a patch, not an override here: a copy of a whole Chromium file would
silently fall out of date as Chromium changes it, which is exactly what the
Firefox fork's `patches/`-only rule existed to prevent. An override of an
existing file is allowed only when a diff would be unreadable, and is reviewed
with that in mind.

A file whose path contains a platform directory (`mac/`, `win/`, `linux/`) or a
`.<platform>.` segment in its name is copied only for that platform's build.

## What lives here

- `chrome/browser/orbit/` — the Orbit browser component: the toolbar's Orbit
  button (account + apps), the Orbit AI side panel and menu items, the new-tab
  Orbit shortcuts and wallpapers, and the update check against Orbit Mission
  Control. It is built from `orbit_generated.h`, which `scripts/build.py` writes
  from `scripts/orbit_config.py`, so the C++ and the Python never disagree. See
  that directory's README for the file list and the wiring patches it needs.

Orbit Pass is **not** here: it is force-installed and un-removable by policy
(`../distribution/policies/`), built from the sibling Orbit Pass checkout by
`scripts/build.py`.
