/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Orbit Browser's branding and its defaults, in place of Firefox's
// browser/branding/official/pref/firefox-branding.js (loaded after firefox.js,
// so these win). A person can change any of them; what they can't change
// (the AI features that are off, Orbit AI as the only chatbot) is locked in
// distribution/policies.json. scripts/build.py fills in the @…@ values.

// -- the build ---------------------------------------------------------------------------
// OrbitBrowser.sys.mjs reads these: Orbit Browser's own version (not
// Firefox's), the build number Mission Control orders releases by, and a
// stamp of this build's own files (when it changes, the browser drops caches
// made by the build before).
pref("orbitbrowser.version", "@ORBIT_VERSION@");
pref("orbitbrowser.build", @ORBIT_BUILD@);
pref("orbitbrowser.stamp", "@ORBIT_STAMP@");
// Updates, as the other Orbit apps get them: Mission Control's feed, where to
// download a build by hand (a copy that can't replace itself), and the public
// half of the key releases are signed with (scripts/sign_update.py; the
// browser reads it from these defaults only, never from a changed pref).
pref("orbitbrowser.updates.url", "https://control.orbit.com.ai/api/updates/orbit-browser/%TARGET%/%ARCH%/%VERSION%?build=%BUILD%");
pref("orbitbrowser.updates.download", "https://control.orbit.com.ai/download/orbit-browser/%OS%/");
pref("orbitbrowser.updates.pubkey", "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IEQ0MDRFQzM1REU3RDY1OTgKUldTWVpYM2VOZXdFMUtoTDdQNCtiUEFPdlFSeldaRTkvOW1DTlJFU2t3U3hOWW9EbUpmVHlIakoK");
pref("orbitbrowser.updates.enabled", true);

// -- pages Firefox's branding points at -------------------------------------------------
pref("startup.homepage_override_url", "");
pref("startup.homepage_welcome_url", "");
pref("startup.homepage_welcome_url.additional", "");
pref("app.update.url.manual", "https://orbit.com.ai/");
pref("app.update.url.details", "https://orbit.com.ai/");
// The engine is Firefox's, so its release notes are Firefox's: the About
// window links them beside the Firefox it is built on. Settings' What's new
// would sit beside Orbit Browser's own version, so it has none (about:blank).
pref("app.releaseNotesURL", "about:blank");
pref("app.releaseNotesURL.aboutDialog", "https://www.firefox.com/%LOCALE%/firefox/%VERSION%/releasenotes/");
pref("app.releaseNotesURL.prompt", "https://www.firefox.com/%LOCALE%/firefox/%VERSION%/releasenotes/");
pref("app.update.interval", 21600);
pref("app.update.promptWaitTime", 691200);
pref("app.update.checkInstallTime.days", 63);
pref("app.update.badgeWaitTime", 345600);
pref("devtools.selfxss.count", 0);

// -- Orbit Pass is the password manager --------------------------------------------------
// Firefox's own password manager, card and address autofill and form history
// are off and locked in distribution/policies.json; Orbit Pass fills instead.
// Firefox Relay (Mozilla's email masks): "unavailable" takes it out of the
// login menus and Settings ("disabled" would still offer it); locked in
// distribution/policies.json.
pref("signon.firefoxRelay.feature", "unavailable");
// Orbit Pass's own address (moz-extension://<uuid>/) is the same in every
// copy of Orbit Browser, so its server knows where a sign-in comes back to
// (ORBIT_PASS_EXTENSION_IDS in Orbit Pass). Firefox otherwise picks a random
// one per profile.
pref("extensions.webextensions.uuids", "{\"pass@orbit.com.ai\":\"@ORBIT_PASS_UUID@\"}");

// -- Orbit, not Mozilla's services ------------------------------------------------------
// Mozilla's account, Sync, Pocket, its VPN, its suggestions and stories are off
// in distribution/policies.json; these are the rest, and the Orbit apps in
// their place (the toolbar's Orbit menu is OrbitBrowser.sys.mjs).
// The new tab's shortcuts: the Orbit apps, not the list Mozilla sends
// (useRemoteSetting) or its sponsored tiles service (contile).
pref("browser.topsites.useRemoteSetting", false);
pref("browser.topsites.contile.enabled", false);
pref("browser.newtabpage.activity-stream.default.sites", "https://ai.orbit.com.ai/,https://mail.orbit.com.ai/,https://chat.orbit.com.ai/,https://pass.orbit.com.ai/vault/,https://control.orbit.com.ai/");
// The new tab is the one built in, which the build changes (Orbit's
// wallpapers, scripts/omni_patches.py). Mozilla otherwise swaps in a newer
// copy of it between releases (a "train-hop" add-on), and Firefox's wallpapers
// with it.
pref("browser.newtabpage.disableNewTabAsAddon", true);
// mozilla.org's pages driving the browser's menus and tours.
pref("browser.uitour.enabled", false);
// The sidebar's tools: Orbit AI first; no Synced Tabs, which needs a Mozilla
// account (scripts/omni_patches.py leaves it out of the sidebar altogether).
pref("sidebar.main.tools", "aichat,history,bookmarks");
// "Report Broken Site", which reports to Mozilla.
pref("ui.new-webcompat-reporter.enabled", false);
// Mozilla Monitor's breach alerts, and the protections page's Mozilla cards.
pref("signon.management.page.breach-alerts.enabled", false);
pref("browser.contentblocking.report.lockwise.enabled", false);
pref("browser.contentblocking.report.monitor.enabled", false);
pref("browser.contentblocking.report.show_mobile_app", false);
pref("browser.promo.relay.enabled", false);
pref("browser.promo.pin.enabled", false);
pref("browser.urlbar.suggest.weather", false);
// Mozilla's green "New" badges on the Summarize page button and menu item.
pref("browser.ml.chat.page.footerBadge", false);
pref("browser.ml.chat.page.menuBadge", false);
// Crash reports go nowhere (on the Mac, application.ini turns the reporter off too).
pref("browser.tabs.crashReporting.sendReport", false);
pref("breakpad.reportURL", "");

// -- no sponsored content, no Mozilla promotions -----------------------------------------
pref("browser.newtabpage.activity-stream.showSponsored", false);
pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false);
pref("browser.newtabpage.activity-stream.showSponsoredCheckboxes", false);
pref("browser.urlbar.suggest.quicksuggest.sponsored", false);
pref("browser.vpn_promo.enabled", false);
pref("browser.preferences.moreFromMozilla", false);
// Mozilla's first-run pages and tips feature its fox; Orbit Browser opens
// straight to a new tab.
pref("browser.aboutwelcome.enabled", false);
// The add-ons page opens on the extensions you have, not Mozilla's
// recommendations (and their fox).
pref("extensions.getAddons.showPane", false);
pref("extensions.htmlaboutaddons.recommendations.enabled", false);
