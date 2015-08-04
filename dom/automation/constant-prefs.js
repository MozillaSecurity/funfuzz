// Not ready for e10s
user_pref("browser.tabs.remote.autostart", false);
user_pref("browser.tabs.remote.autostart.1", false);
user_pref("browser.tabs.remote.autostart.2", false);

// Allow installing the DOMFuzz Helper extension.
user_pref("extensions.enabledScopes", 5);
user_pref("extensions.autoDisableScopes", 0);
user_pref("extensions.update.notifyUser", false);
user_pref("extensions.installDistroAddons", false);
user_pref("xpinstall.signatures.required", false);

// Extend the time before slow script dialogs appear.
user_pref("dom.max_chrome_script_run_time", 75);
user_pref("dom.max_script_run_time", 60);

// Set additional prefs for fuzzing.
user_pref("browser.dom.window.dump.enabled", true);
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("browser.addon-watch.interval", -1);
user_pref("layout.debug.enable_data_xbl", true);
user_pref("dom.disable_window_status_change", false);
user_pref("dom.disable_window_move_resize", false);
user_pref("dom.disable_open_during_load", false);
user_pref("dom.disable_window_flip", false);
user_pref("security.fileuri.strict_origin_policy", false);
user_pref("dom.min_background_timeout_value", 4);
user_pref("dom.successive_dialog_time_limit", 0);
user_pref("network.manage-offline-status", false);
user_pref("layout.spammy_warnings.enabled", false);

// Disable a timer-based drawWindow call in favor of fuzzPriv.callDrawWindow.
user_pref("browser.pageThumbs.enabled", false);
user_pref("browser.pagethumbnails.capturing_disabled", true);

// Reset things (on each startup) that might be set by fuzzing
user_pref("javascript.options.gczeal", 0);

// Disable first-run annoyances.
user_pref("browser.newtabpage.updateIntroShown", true);
user_pref("browser.tabs.warnOnClose", false);
user_pref("browser.warnOnQuit", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.EULA.override", true);
user_pref("toolkit.telemetry.prompted", 2);
user_pref("browser.rights.3.shown", true);
user_pref("browser.rights.override", true);
user_pref("browser.firstrun.show.localepicker", false);
user_pref("browser.firstrun.show.uidiscovery", false);
user_pref("browser.startup.page", 0); // use about:blank, not browser.startup.homepage
user_pref("general.warnOnAboutConfig", false);
user_pref("browser.displayedE10SPrompt.1", 5);
user_pref("browser.newtabpage.introShown", true);
user_pref("browser.reader.detectedFirstArticle", true);
user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);

// Suppress automatic safe mode after crashes.
user_pref("toolkit.startup.max_resumed_crashes", -1);

// Turn off various things in firefox that try to contact servers,
// to improve performance and sanity.
// http://support.mozilla.com/en-US/kb/Firefox+makes+unrequested+connections
user_pref("browser.aboutHomeSnippets.updateUrl", "nonexistent://test");
user_pref("browser.newtabpage.enhanced", false);
user_pref("browser.newtabpage.directory.ping", "");
user_pref("browser.newtabpage.directory.source", 'data:application/json,{"testing":1}');
user_pref("browser.safebrowsing.enabled", false);
user_pref("browser.safebrowsing.malware.enabled", false);
user_pref("browser.search.update", false);
user_pref("browser.webapps.checkForUpdates", 0);
user_pref("app.update.enabled", false);
user_pref("app.update.stage.enabled", false);
user_pref("app.update.staging.enabled", false);
user_pref("app.update.url.android", "");
user_pref("extensions.update.enabled", false);
user_pref("extensions.getAddons.cache.enabled", false);
user_pref("extensions.blocklist.enabled", false);
user_pref("extensions.showMismatchUI", false);
user_pref("extensions.testpilot.runStudies", false);
user_pref("lightweightThemes.update.enabled", false);
user_pref("browser.microsummary.enabled", false);
user_pref("toolkit.telemetry.server", "");
user_pref("toolkit.telemetry.unified", false);
user_pref("plugins.update.url", "");
user_pref("datareporting.healthreport.service.enabled", false);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("browser.urlbar.suggest.searches", false);
user_pref("browser.snippets.enabled", false);
user_pref("browser.snippets.firstrunHomepage.enabled", false);
user_pref("browser.snippets.syncPromo.enabled", false);
user_pref("general.useragent.updates.enabled", false);

// Prevent the fuzzer from accidentally contacting servers.
//   Note: Since we are not actually running a proxy on port 6,
//     Firefox will show the error message "The proxy server is refusing connections"
//   Note: I'm not sure why localhost / 127.0.0.1 even calls the PAC (see https://bugzilla.mozilla.org/show_bug.cgi?id=31510)
//   Note: If I want to make a real proxy, look at:
//     https://hg.mozilla.org/mozilla-central/file/f78e532e8a10/testing/mochitest/runtests.py#l984
//     https://hg.mozilla.org/mozilla-central/file/f78e532e8a10/testing/mozbase/mozprofile/mozprofile/permissions.py#l284
//   Note: If I remove the proxy entirely, network.proxy.type should be set to 0 because
//     looking up the system proxy settings can cause problems (see bug 794174, see bug 793016)
user_pref("network.proxy.share_proxy_settings", true);
user_pref("network.proxy.type", 2);
user_pref("network.proxy.autoconfig_url", "data:text/plain,function FindProxyForURL(url, host) { if (host == 'localhost' || host == '127.0.0.1') { return 'DIRECT'; } else { return 'PROXY 127.0.0.1:6'; } }");

// Prefs from Christoph (?)
user_pref("network.jar.open-unsafe-types", true);
user_pref("gfx.color_management.mode", 2);
user_pref("media.peerconnection.aec", 1);
user_pref("media.peerconnection.aec_enabled", true);
user_pref("media.peerconnection.agc", 1);
user_pref("media.peerconnection.agc_enabled", false);
user_pref("media.peerconnection.default_iceservers", '[{"url": "stun:23.21.150.121"}]');
user_pref("media.peerconnection.noise", 1);
user_pref("media.peerconnection.noise_enabled", false);
user_pref("media.peerconnection.use_document_iceservers", true);
user_pref("media.peerconnection.turn.disable", false);
user_pref("browser.ssl_override_behavior", 1);
