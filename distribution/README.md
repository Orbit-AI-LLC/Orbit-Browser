# distribution/

What Orbit Browser ships beside the engine to make a running browser Orbit's,
without a compiler: the enterprise policies that **lock** features off, and the
first-run preferences that set the defaults a person can still change. The
split mirrors the Firefox build's: `policies/` is the hard lock, like the old
`policies.json`; `initial_preferences` is the soft default, like the old
`firefox-branding.js` prefs.

## `policies/orbit.json` — the locked policy

Chromium's enterprise policies, set for every profile and not changeable by the
person. This is the Chromium counterpart of the Firefox build's `AIControls` and
service lock-downs:

- **Google's AI off and locked.** `GenAiDefaultSettings: 2` disables every GenAI
  feature by default (so one Google adds later under the umbrella arrives off),
  with the individual GenAI policies (`TabOrganizerSettings`, `HelpMeWriteSettings`,
  `GeminiSettings`, `HistorySearchSettings`, `GenAILocalFoundationalModelSettings`,
  …) set off too. Orbit AI is the only assistant (the Orbit component), so no
  Chromium assistant is left available.
- **No Google account, Sync, metrics or background services.** `BrowserSignin: 0`,
  `SyncDisabled`, `MetricsReportingEnabled: false`,
  `UrlKeyedAnonymizedDataCollectionEnabled: false`, `BackgroundModeEnabled: false`,
  `ComponentUpdatesEnabled: false` (Orbit updates itself, not through Google's
  component feeds), `SafeBrowsingProtectionLevel: 0` (no Google Safe Browsing
  lookups; the build also ships no Google API keys).
- **Orbit Pass is the password manager.** Chromium's own is off
  (`PasswordManagerEnabled`, `AutofillAddressEnabled`, `AutofillCreditCardEnabled`
  all false), and Orbit Pass is **force-installed and un-removable**
  (`ExtensionSettings` → `force_installed`, `force_pinned`), served by Orbit
  Mission Control.
- **The Orbit apps** on the bookmarks bar (`ManagedBookmarks`).

Where it is placed (the installers and `scripts/build.py` do this):

| Platform | Managed-policy location |
| --- | --- |
| Windows | the registry under `HKLM\SOFTWARE\Policies\OrbitBrowser` (the installer writes it) |
| macOS | the `ai.com.orbit.browser` managed-preferences domain (a configuration profile) |

Keep the Orbit Pass id and the app list in step with `scripts/orbit_config.py`.

## `initial_preferences` — the first-run defaults

Chromium's master-preferences file, shipped in the install directory. It sets the
defaults a new profile starts with — the Orbit home page and new tab, the
bookmarks bar shown, no "make default browser" or Google import prompts, Google
Safe Browsing and the spelling service off — all of which a person may change
afterwards. The locked ones are in `policies/orbit.json`, not here.
