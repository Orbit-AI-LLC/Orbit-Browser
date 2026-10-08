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
- Changes to Mozilla's own files inside omni.ja are exact text replacements in
  `scripts/omni_patches.py`, each of which must match exactly once. When a Firefox release moves
  the code, the build stops and names the patch; fix the anchor, don't loosen the check.
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
