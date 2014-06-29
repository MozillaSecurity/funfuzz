// Extend the time before slow script dialogs appear.
user_pref("dom.max_chrome_script_run_time", 75);
user_pref("dom.max_script_run_time", 60);

// Set additional prefs for fuzzing.
user_pref("browser.dom.window.dump.enabled", true);
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("layout.debug.enable_data_xbl", true);
user_pref("dom.disable_window_status_change", false);
user_pref("dom.disable_window_move_resize", false);
user_pref("dom.disable_open_during_load", false);
user_pref("dom.disable_window_flip", false);
user_pref("extensions.enabledScopes", 3);
user_pref("extensions.autoDisableScopes", 10);
user_pref("extensions.update.notifyUser", false);
user_pref("security.fileuri.strict_origin_policy", false);
user_pref("dom.min_background_timeout_value", 4);
user_pref("dom.successive_dialog_time_limit", 0);

// Disable a timer-based drawWindow call in favor of fuzzPriv.callDrawWindow.
user_pref("browser.pageThumbs.enabled", false);

// Reset things (on each startup) that might be set by fuzzing
user_pref("javascript.options.gczeal", 0);

// Disable first-run annoyances.
user_pref("browser.tabs.warnOnClose", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.EULA.override", true);
user_pref("toolkit.telemetry.prompted", 2);
user_pref("browser.rights.3.shown", true);
user_pref("browser.firstrun.show.localepicker", false);
user_pref("browser.firstrun.show.uidiscovery", false);
user_pref("browser.startup.page", 0); // use about:blank, not browser.startup.homepage
user_pref("general.warnOnAboutConfig", false);
//user_pref("datareporting.policy.dataSubmissionPolicyBypassAcceptance", true);

// Suppress automatic safe mode after crashes.
user_pref("toolkit.startup.max_resumed_crashes", -1);

// Turn off various things in firefox that try to contact servers,
// to improve performance and sanity.
// http://support.mozilla.com/en-US/kb/Firefox+makes+unrequested+connections
user_pref("browser.safebrowsing.enabled", false);
user_pref("browser.safebrowsing.malware.enabled", false);
user_pref("browser.search.update", false);
user_pref("browser.webapps.checkForUpdates", 0);
user_pref("app.update.enabled", false);
user_pref("app.update.stage.enabled", false);
user_pref("app.update.staging.enabled", false);
user_pref("extensions.update.enabled", false);
user_pref("extensions.getAddons.cache.enabled", false);
user_pref("extensions.blocklist.enabled", false);
user_pref("extensions.showMismatchUI", false);
user_pref("extensions.testpilot.runStudies", false);
user_pref("lightweightThemes.update.enabled", false);
user_pref("browser.microsummary.enabled", false);
user_pref("toolkit.telemetry.server", "");
user_pref("plugins.update.url", "");
user_pref("datareporting.healthreport.service.enabled", false);

// Prevent the fuzzer from accidentally contacting servers.
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
