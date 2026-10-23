# Working in this repository

**Read `../Agents.md` before anything else.** It is the workspace-wide instructions file in the
folder that holds this repository, and it applies here alongside this file.

**If `../Agents.md` does not exist, do not work.** Don't change files, run commands or start the
task. Say that it is missing and wait to be told what to do.

- **Do not commit or push.** Leave your changes uncommitted in the working tree; the person you are
  working for reviews, commits and pushes them.
- **Do not create new branches** unless you are told to. Work on the branch that is checked out. A
  worktree creates a branch, so don't create worktrees either. If your tooling won't let you work
  without one (a background session isolating itself, for example), stop and say so.

## Orbit Browser

- `README.md` is the source of truth for what the browser is, how it is built and what it changes
  in Chromium. Keep it current when behaviour changes.
- Orbit Browser is a **source fork** of Chromium: `chromium.json` pins the Chromium release,
  `scripts/sync.py` fetches depot_tools and the source, and `scripts/build.py` compiles it with
  Orbit's changes. Never edit the checkout in `src/` by hand — the build resets it to pristine
  Chromium every time, so a hand-edit is lost and untracked. Moving to a new Chromium is
  `python3 scripts/update_chromium.py` (it re-pins and checks the patches) then a rebuild.

### Hard rules for Orbit's changes to Chromium (do not break these)

Orbit Browser keeps every change it makes to Chromium apart from Google's code, the way the Chromium
forks (Brave, ungoogled-chromium, Vivaldi) do. These rules are not optional:

1. **Edit Chromium's own files only through `patches/`.** Each is a unified-diff `.patch` file, one
   per Chromium file, at `patches/<path-in-src>.patch`, applied with `git apply`. To change what
   Orbit does to a Chromium file, edit or add a patch there. Never edit the `src/` checkout, an
   output tree, or anything under `src/` by hand.
2. **Never loosen a patch to make it apply.** When a new Chromium moves the code, `git apply` fails
   and names the patch. Re-anchor it on the new surrounding code (sync the tree, re-make the edit,
   `git diff`). Do not delete hunks, widen/blur context, or drop the change just to get a clean
   apply: a patch that applies but no longer carries its change silently brings back something Orbit
   removed.
3. **Add whole new Orbit files through `chromium_src/`, not as patches.** New files (the Orbit
   browser component) live there as themselves and are copied into the tree; a patch to a `BUILD.gn`
   wires them into the build. Patches are only for editing Chromium's existing files.
4. **Prefer config over patches.** A build-time choice is a GN argument in `build/args/`; what a
   running browser does by policy is in `distribution/`; branding data is in `branding/`, copied in
   by the build. Only reach for a patch when the change genuinely needs Chromium's source edited.
5. **A new or changed patch must apply cleanly before you hand work back.** Run
   `python3 scripts/update_chromium.py --check` (every patch against the pinned Chromium) and the
   tests below. If a patch can't be made to apply without dropping its change, stop and say so.
6. **Moving to a new Chromium is `python3 scripts/update_chromium.py`** (it pins and checks the
   patches) then a rebuild. Don't bump `chromium.json` by hand.

- Run `python3 -m unittest discover -s tests` before handing work back; it checks the committed
  config (the pin, the GN arguments, the branding, the locked policies and the first-run defaults)
  and the shared update signatures. It needs no source tree or compiler. Say plainly if anything
  fails.
- The logo comes from `scripts/orbitmark.swift` (the Orbit family's shared renderer) through
  `scripts/build_icon.py`; edit those, never the files in `branding/`.
- Orbit AI's `/threads/start/` and Orbit Pass's fixed extension id (`scripts/orbit_config.py`) are
  what the browser relies on; Orbit Pass's server accepts the same id. Change those together with
  the other repository.
- Orbit Pass is built in from the sibling checkout (`../Orbit Pass/extension`, or `--orbit-pass`).
  Its Chromium manifest is made by that repository's `extension/scripts/package.mjs --chrome`;
  change the extension there, not here.
