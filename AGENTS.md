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
  in Firefox. Keep it current when behaviour changes.
- Orbit Browser is Mozilla's own signed Firefox release, repacked: `firefox.json` pins the release
  and its checksums, `scripts/build.py` makes the apps from it. Never edit a downloaded build by
  hand; every change is made by the build, so moving to a new Firefox is
  `python3 scripts/update_firefox.py` and a rebuild.
### Hard rules for Orbit's changes to Firefox (do not break these)

Orbit Browser keeps every change it makes to Firefox apart from Mozilla's code, the way the Firefox
forks (Tor Browser, Mullvad, LibreWolf) do. These rules are not optional:

1. **Edit Mozilla's own omni.ja files only through `patches/`.** Each is a unified-diff `.patch`
   file, one per Mozilla file, at `patches/<jar>/<path>.patch` (`<jar>` is `browser` or `gre`),
   applied with `git apply`. To change what Orbit does to a Mozilla file, edit or add a patch there.
   Never edit a downloaded build, an unpacked `omni.ja`, or `work/` by hand — the build makes every
   change, so a hand-edit is lost and untracked.
2. **Never loosen a patch to make it apply.** When a new Firefox moves the code, `git apply` fails
   and names the patch and hunk. Fix the patch so it still carries Orbit's change — re-anchor it on
   the new surrounding code (dump the pristine file with `scripts/firefox_file.py`, re-make the edit,
   `diff -u`). Do not delete hunks, widen/blur context, or drop the change just to get a clean apply:
   a patch that applies but no longer carries its change silently brings back a feature Orbit removed.
3. **Add whole new Orbit files through `scripts/build.py`, not as patches.** New files (branding,
   `browser/modules/`, `browser/content/`, the launcher, `distribution/policies.json`) live in the
   repo as themselves; `build.py` drops them in. Patches are only for editing Mozilla's existing files.
4. **The only edits allowed outside `patches/` are the data-generated ones already in
   `scripts/omni_patches.py`** (the wallpapers from `ORBIT_WALLPAPERS`, the Orbit AI provider from
   `ORBIT_AI_URL`). Don't add new in-code string replacements there for things that could be a patch.
5. **A new or changed patch must apply cleanly before you hand work back.** Run
   `python3 scripts/update_firefox.py --check` (every patch against the pinned Firefox) and the tests
   below. If a patch can't be made to apply without dropping its change, stop and say so.
6. **Moving to a new Firefox is `python3 scripts/update_firefox.py` (it pins and checks the patches)
   then a rebuild.** Don't bump `firefox.json` by hand.
- Run `python3 -m unittest discover -s tests` before handing work back; it checks every patch,
  policy and locked pref against the pinned Firefox. After a Mac build, also run
  `python3 tests/smoke.py`, which starts the app and checks it from inside. Say plainly if anything
  fails.
- The logo comes from `scripts/orbitmark.swift` (the Orbit family's renderer, with the browser's
  mark added) through `scripts/build_icon.py`; edit those, never the files in `branding/`.
- Orbit AI's `/threads/start/` and its composer (`textarea#composer-input`, the "Send message"
  button) are what the sidebar relies on; Orbit Pass's server accepts the fixed extension UUID in
  `scripts/build.py`. Change those together with the other repository.
- Orbit Pass is built in from the sibling checkout (`../Orbit Pass/extension`, or
  `--orbit-pass`). Its Firefox manifest is made by that repository's
  `extension/scripts/package.mjs --firefox`; change the extension there, not here.
