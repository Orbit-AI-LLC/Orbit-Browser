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
- Orbit Browser *repacks* a prebuilt **ungoogled-chromium** rather than compiling it: `chromium.json`
  pins the version and each platform's download URL and SHA-256, and `scripts/build.py` makes Orbit
  Browser from it. Never edit a downloaded build by hand; every change is made by the build, so
  moving to a new Chromium is `python3 scripts/update_chromium.py` (with the new per-platform URLs)
  and a rebuild.

### Hard rules for Orbit's changes (do not break these)

A repack can only change what it can unpack and re-pack, so everything Orbit does is configuration,
not compiled code. Keep it that way:

1. **No compiler, no source tree.** Orbit Browser is a repack, not a source fork. Don't add a
   Chromium checkout, GN args, or source patches; if something seems to need them, it belongs in a
   force-installed extension or is out of scope for the repack (say so).
2. **Locked behaviour is enterprise policy** (`distribution/policies/orbit.json`). This is where
   Google's AI and services are turned off and Orbit Pass is force-installed. Prefer a policy over
   anything that edits the unpacked browser's files.
3. **First-run defaults are `distribution/initial_preferences`** (Chromium's master preferences),
   shipped inside the app — a person can still change these. This is where ungoogled-chromium's
   "clear site data on exit" default is turned off (cookies content setting back to 1 = Allow);
   don't let it regress (there is a test for it).
4. **Branding is the app name and icon only.** The deep in-UI strings stay "Chromium" (a repack
   can't recompile them). Set branding in `branding/` and `scripts/build.py`, not by editing a build.
5. **Orbit's data lives in `scripts/orbit_config.py`** (version, apps, account, update feed, Orbit
   Pass id). Don't scatter copies of these values.
6. **Pin by checksum.** A new URL is pinned with `python3 scripts/update_chromium.py`, which records
   the SHA-256; the build refuses a download that doesn't match. Don't hand-edit `chromium.json`.

- Run `python3 -m unittest discover -s tests` before handing work back; it checks the committed
  config (the pin's shape, the branding assets, the locked policies and the first-run preferences)
  and the shared update signatures. It needs no download. Say plainly if anything fails.
- The logo comes from `scripts/orbitmark.swift` (the Orbit family's shared renderer) through
  `scripts/build_icon.py`; edit those, never the files in `branding/`.
- Orbit AI's URLs and Orbit Pass's fixed extension id (`scripts/orbit_config.py`) are what Orbit
  relies on; Orbit Pass's server accepts the same id. Change those together with the other repository.
- Orbit Pass is **not bundled** into the app. It is force-installed and un-removable by policy
  (`distribution/policies/orbit.json` → `ExtensionSettings`), served from Orbit Mission Control at
  runtime. Change the extension in the Orbit Pass repository; keep its extension id in step with
  `scripts/orbit_config.py` (`ORBIT_PASS_ID`) and Mission Control's force-install update URL.
