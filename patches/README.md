# patches/

Orbit's edits to Chromium's **own existing source files**, as unified-diff
`.patch` files — one per Chromium file, at `patches/<path-in-src>.patch` (so
`patches/chrome/browser/ui/BUILD.gn.patch` edits `src/chrome/browser/ui/BUILD.gn`).
`scripts/patches.py` applies them with `git apply`, which is strict: the lines
around each change must still match, so a Chromium that moved the code stops the
build and names the patch. Each patch is a readable diff, reviewed like any other.

This is the only way to edit Chromium's existing files. **Whole new Orbit files**
go in [`../chromium_src/`](../chromium_src/) instead, copied into the tree as
themselves. A few build-time choices need no source edit at all and are GN
arguments in [`../build/args/`](../build/args/); what a running browser does by
policy is in [`../distribution/`](../distribution/).

## The rules (do not break these)

1. **Edit Chromium's files only through a patch here.** Never edit the checkout
   in `src/` by hand — `scripts/build.py` resets it to pristine Chromium every
   build, so a hand-edit is lost and untracked.
2. **Never loosen a patch to make it apply.** When a new Chromium moves the code,
   `git apply` fails and names the patch. Re-anchor it on the new surrounding
   code (see the README, "Moving to a new Chromium"); do not delete hunks, blur
   context, or drop the change to get a clean apply. A patch that applies but no
   longer carries its change silently brings back something Orbit removed.
3. **A `# platforms:` first line** limits a patch to some builds, e.g.
   `# platforms: mac` or `# platforms: win, linux`. Omitted, it applies everywhere.
4. **Check before handing work back:** `python3 scripts/update_chromium.py --check`
   applies every patch to the pinned Chromium.

## Authoring a patch against the synced tree

```bash
python3 scripts/sync.py                        # make src/ ready at the pinned Chromium
cd src
git diff chrome/browser/ui/foo.cc > /tmp/x     # after editing the file
# move the diff to patches/chrome/browser/ui/foo.cc.patch, then:
cd .. && python3 scripts/update_chromium.py --check
```

## The wiring patches Orbit needs

Branding, Google-stripping, the Orbit policies and Orbit Pass's force-install are
done without patching Chromium (GN args, `distribution/`, the branding copy in
`scripts/build.py`). The patches that remain are the ones that teach Chromium's
build and UI about Orbit's **new** source in `../chromium_src/chrome/browser/orbit/`:

- `chrome/browser/BUILD.gn` — add `//chrome/browser/orbit` to the browser target.
- `chrome/browser/ui/BUILD.gn` + the toolbar container — show the Orbit toolbar
  button (the Orbit account and apps) in place of Chromium's profile/avatar menu.
- `chrome/browser/ui/views/side_panel/` — register the Orbit AI side panel and
  the "Ask Orbit AI" / "Summarize page" context-menu items (Orbit AI's URLs,
  `scripts/orbit_config.py`).
- `chrome/browser/new_tab_page/` — Orbit's new-tab wallpapers and app shortcuts.
- `chrome/browser/BUILD.gn` + startup — start the Orbit update check
  (`chromium_src/chrome/browser/orbit/update/`), since Chromium's own updater is
  not built.

Each is authored against the synced tree as above. They are kept out of this repo
until written against a real Chromium, rather than committed as diffs that would
not apply.
