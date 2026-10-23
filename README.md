# Orbit Browser

Orbit's web browser for the Mac, Windows and Linux. Its engine is Chromium, by
way of **ungoogled-chromium** — Chromium with Google's web services, sign-in and
reporting already removed. Orbit Browser *repacks* a pinned ungoogled-chromium
build (in `chromium.json`) and makes it Orbit's, without a compiler.

| | What Orbit Browser does | Where |
| --- | --- | --- |
| **Base** | ungoogled-chromium, whose builds have Google's services, sign-in, Safe Browsing lookups and reporting removed upstream | `chromium.json` |
| **Name and icon** | "Orbit Browser" as the app's name, the Orbit family's mark as its icon (the deep in-UI strings stay "Chromium" — a repack can't recompile them) | `branding/`, `scripts/build_icon.py`, `scripts/orbitmark.swift` |
| **Google's AI** | Every GenAI feature off and locked by policy, so no Chromium assistant is offered | `distribution/policies/orbit.json` |
| **Orbit AI, the Orbit button** | Orbit's assistant, account and apps, delivered as a force-installed Orbit extension (a repack adds UI through extensions, not built-in C++) | `distribution/policies/orbit.json` |
| **Orbit Pass** | Built in: force-installed and pinned, un-removable; bundled from the Orbit Pass checkout | `distribution/policies/orbit.json`, Orbit Pass's `extension/` |
| **Google's services** | No Google account/Sync, metrics, background services, component updates, spelling or prediction services | `distribution/policies/orbit.json` |
| **Orbit's instead** | The Orbit apps as managed bookmarks, the Orbit home page and new tab | `distribution/policies/orbit.json`, `distribution/initial_preferences` |
| **Site data** | ungoogled-chromium deletes site data when you close all windows by default; Orbit sets it back to "Allow sites to save data" | `distribution/initial_preferences` |
| **Autofill** | Orbit Pass's alone: Chromium's password manager, card and address autofill off and locked | `distribution/policies/orbit.json` |

## How it's made

`scripts/build.py` *repacks* a prebuilt Chromium rather than compiling it: it
downloads the ungoogled-chromium build `chromium.json` pins (checking its
SHA-256), unpacks it, and changes what can be changed without a compiler — the
app's name and icon, the enterprise policies, the first-run preferences, and
Orbit Pass built in — then repackages. That keeps builds small and fast (minutes
on a standard GitHub runner).

```bash
python3 scripts/build.py                              # the host's default (Mac on a Mac, Linux on Linux, else Windows)
python3 scripts/build.py --platform mac-arm64 --platform mac-x64
python3 scripts/build.py --platform win64
python3 scripts/build.py --platform linux
python3 -m unittest discover -s tests                 # the committed config and the update signatures
```

| Platform | Build on | Makes (in `dist/`) |
| --- | --- | --- |
| `mac-arm64`, `mac-x64` | macOS | `Orbit-Browser-<version>-macOS-AppleSilicon.dmg` / `…-Intel.dmg` and an `.app.tar.gz` update payload each |
| `win64` | Windows | a portable `…-Windows-x64.zip` |
| `linux` | Linux | `…-Linux-x86_64.tar.xz` |

ungoogled-chromium ships per-architecture macOS builds (no universal), so the Mac
app is two builds. Orbit Pass comes from the Orbit Pass checkout beside this one
(`../Orbit Pass`, or `--orbit-pass <path>`): the build runs its
`extension/scripts/package.mjs --chrome`. Downloads are kept in `.cache/`,
unpacked trees in `work/`. `--sign "Developer ID Application"` signs the Mac app.

**Versions.** Orbit Browser has its own version, `VERSION` in
`scripts/orbit_config.py`, apart from the Chromium it is built on
(`chromium.json`): `0.1.0` for a release, `0.1.0-build.N` for a build on `main`,
`0.1.0-local` here. Raise `VERSION` for a release (tag `v<VERSION>`).

### Where Orbit's changes live

A repack can only change what it can unpack and re-pack, so everything Orbit does
is configuration, not compiled code:

- **Branding** — the app name and icon — in `branding/`, applied by
  `scripts/build.py` (the bundle name/Info.plist on macOS, the folder and `.desktop`
  on Linux). The mark is rendered by `scripts/orbitmark.swift` (the Orbit family's
  shared renderer) through `scripts/build_icon.py`; edit those, not `branding/`.
- **Locked behaviour** — `distribution/policies/orbit.json`, Chromium's enterprise
  policy, placed at the OS managed-policy location by the installer.
- **First-run defaults** — `distribution/initial_preferences`, shipped inside the
  app (this is where the ungoogled "clear site data on exit" default is turned off).
- **Orbit's data** (version, apps, account, update feed, Orbit Pass id) — one file,
  `scripts/orbit_config.py`.

See `distribution/README.md` for the policy/preferences split and where each is placed.

### What a repack cannot do

A repack can't recompile Chromium, so some things the former source-fork plan could
do are out of reach and handled differently:

- **Deep rebranding.** "Chromium" in the compiled UI strings (About, menus) stays;
  only the app's name and icon are Orbit's.
- **Built-in Orbit UI.** The Orbit toolbar button and the Orbit AI side panel ship
  as a **force-installed Orbit extension**, not built-in browser code.
- **An in-app self-updater.** See [Updates](#updates).

### Moving to a new Chromium

ungoogled-chromium publishes a new build after each Chromium release; Orbit Browser
gets it by re-pinning. The binaries are built and hosted by ungoogled-chromium's
contributors (linked from the [binaries page][bin]), so the per-platform URLs are
passed in:

```bash
python3 scripts/update_chromium.py                    # prints the newest version and what to pass
python3 scripts/update_chromium.py <version> \
    --url win64=<url> --url mac-x64=<url> --url mac-arm64=<url> --url linux=<url>
python3 scripts/build.py                               # build
```

`update_chromium.py` downloads each build, computes its SHA-256, and writes
`chromium.json`; `build.py` refuses a download whose checksum differs.

[bin]: https://ungoogled-software.github.io/ungoogled-chromium-binaries/

## Google's AI and services, removed

ungoogled-chromium removes Google's web services, sign-in, Safe Browsing lookups
and reporting at the source. Orbit locks the rest off by enterprise policy
(`distribution/policies/orbit.json`): the umbrella `GenAiDefaultSettings` disables
every GenAI feature (and each individual one — Gemini, the tab organizer, "Help me
write", history search, the on-device model), and `BrowserSignin`, `SyncDisabled`,
`MetricsReportingEnabled: false`, `BackgroundModeEnabled: false` and
`ComponentUpdatesEnabled: false` keep the browser off Google's services. `chrome://policy`
lists them; Settings says the browser is managed.

## Orbit Pass is the password manager

Chromium's own password manager and autofill are off and locked, and Orbit Pass is
**force-installed and un-removable** (`ExtensionSettings` → `force_installed`,
`force_pinned`), served by Orbit Mission Control. Its stable extension id is the
same in every copy (keep it in step between `scripts/orbit_config.py` and Orbit
Pass's `extension/`). Orbit Pass's Chromium manifest is made by that repository's
`extension/scripts/package.mjs --chrome`; change the extension there, not here.

## Updates

Orbit Browser is meant to update itself from Orbit Mission Control, as every other
Orbit app does (`scripts/sign_update.py` signs the payloads, minisign/Blake2b, the
version in the signature; `.github/scripts/orbit_update_manifest.py` writes the
release manifest). A repack can't embed an in-app updater the way a source fork
could, so the update **client** (checking the feed, verifying the signature,
replacing the app) ships as part of the force-installed Orbit extension / a small
companion, not built into the browser. The release side (signing, the manifest) is
in place; the client is the remaining piece.

## Builds on GitHub

`.github/workflows/build.yml`, all on **standard** GitHub-hosted runners (the
repack is fast):

- **every push and pull request** runs the config and update-signature tests;
- **daily** it checks `chromium.json` against the newest ungoogled-chromium;
- **every push to main (prerelease) and every `v*` tag (release)**, plus manual
  runs, repacks each platform, signs and notarizes the Mac app, signs the update
  payloads and publishes.

See the top of that file for the secrets.
