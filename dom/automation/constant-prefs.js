// Disable slow script dialogs.
user_pref("dom.max_script_run_time", 0);
user_pref("dom.max_chrome_script_run_time", 0);

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
user_pref("security.warn_submit_insecure", false);
user_pref("security.warn_viewing_mixed", false);
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

// Looking up the system proxy settings can cause problems (see bug 794174, see bug 793016)
user_pref("network.proxy.type", 0);

// Prefs from Christoph (?)
user_pref("network.jar.open-unsafe-types", true);
user_pref("gfx.color_management.mode", 2);
user_pref("gfx.canvas.azure.backends", "skia"); //direct2d, skia, cairo
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
