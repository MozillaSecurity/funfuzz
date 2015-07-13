var Platform = (function () {
  var version, webkitVersion, platform = {};

  var userAgent = (navigator.userAgent).toLowerCase();

  version = platform.version = (userAgent.match(/.*(?:rv|chrome|webkit|opera|ie)[\/: ](.+?)([ \);]|$)/) || [])[1];
  webkitVersion = (userAgent.match(/webkit\/(.+?) /) || [])[1];
  platform.windows = platform.isWindows = !!/windows/.test(userAgent);
  platform.mac = platform.isMac = !!/macintosh/.test(userAgent) || (/mac os x/.test(userAgent) && !/like mac os x/.test(userAgent));
  platform.lion = platform.isLion = !!(/mac os x 10_7/.test(userAgent) && !/like mac os x 10_7/.test(userAgent));
  platform.iPhone = platform.isiPhone = !!/iphone/.test(userAgent);
  platform.iPod = platform.isiPod = !!/ipod/.test(userAgent);
  platform.iPad = platform.isiPad = !!/ipad/.test(userAgent);
  platform.iOS = platform.isiOS = platform.iPhone || platform.iPod || platform.iPad;
  platform.android = platform.isAndroid = !!/android/.test(userAgent);
  platform.opera = /opera/.test(userAgent) ? version : 0;
  platform.isOpera = !!platform.opera;
  platform.msie = /msie/.test(userAgent) && !platform.opera ? version : 0;
  platform.isIE = !!platform.msie;
  platform.isIE8OrLower = !!(platform.msie && parseInt(platform.msie, 10) <= 8);
  platform.mozilla = /mozilla/.test(userAgent) && !/(compatible|webkit|msie)/.test(userAgent) ? version : 0;
  platform.isMozilla = !!platform.mozilla;
  platform.webkit = /webkit/.test(userAgent) ? webkitVersion : 0;
  platform.isWebkit = !!platform.webkit;
  platform.chrome = /chrome/.test(userAgent) ? version : 0;
  platform.isChrome = !!platform.chrome;
  platform.mobileSafari = /apple.*mobile/.test(userAgent) && platform.iOS ? webkitVersion : 0;
  platform.isMobileSafari = !!platform.mobileSafari;
  platform.iPadSafari = platform.iPad && platform.isMobileSafari ? webkitVersion : 0;
  platform.isiPadSafari = !!platform.iPadSafari;
  platform.iPhoneSafari = platform.iPhone && platform.isMobileSafari ? webkitVersion : 0;
  platform.isiPhoneSafari = !!platform.iphoneSafari;
  platform.iPodSafari = platform.iPod && platform.isMobileSafari ? webkitVersion : 0;
  platform.isiPodSafari = !!platform.iPodSafari;
  platform.isiOSHomeScreen = platform.isMobileSafari && !/apple.*mobile.*safari/.test(userAgent);
  platform.safari = platform.webkit && !platform.chrome && !platform.iOS && !platform.android ? webkitVersion : 0;
  platform.isSafari = !!platform.safari;
  platform.current =
    platform.msie ? "msie" :
      platform.mozilla ? "mozilla" :
        platform.chrome ? "chrome" :
          platform.safari ? "safari" :
            platform.opera ? "opera" :
              platform.mobileSafari ? "mobile-safari" :
                platform.android ? "android" : "unknown";

  function platformName(candidates) {
    for (var i = 0; i < candidates.length; i++) {
      if (candidates[i] in window) {
        return "window." + candidates[i];
      }
      if (candidates[i] in navigator) {
        return "navigator." + candidates[i];
      }
    }
    return undefined;
  }

  platform.GUM = platformName(['getUserMedia', 'webkitGetUserMedia', 'mozGetUserMedia', 'msGetUserMedia', 'getGUM']);
  platform.PeerConnection = platformName(['webkitRTCPeerConnection', 'mozRTCPeerConnection', 'msPeerConnection']);
  platform.IceCandidate = platformName(['mozRTCIceCandidate', 'RTCIceCandidate']);
  platform.SessionDescription = platformName(['mozRTCSessionDescription', 'RTCSessionDescription']);
  platform.URL = platformName(['URL', 'webkitURL']);
  platform.AudioContext = platformName(['AudioContext', 'webkitAudioContext']);
  platform.OfflineAudioContext = platformName(['OfflineAudioContext', 'webkitOfflineAudioContext']);
  platform.MediaSource = platformName(["MediaSource", "WebKitMediaSource"]);

  function findWebGLContextName(candidates) {
    var canvas = document.createElement("canvas");
    for (var i=0; i<candidates.length; i++) {
      var name = candidates[i];
      try {
        if (canvas.getContext(name)) {
          return name;
        }
      } catch (e) {}
    }
    return null;
  }

  //platform.WebGL = findWebGLContextName(["webgl", "experimental-webgl", "webkit-3d"]);
  //platform.WebGL2 = findWebGLContextName(["webgl2", "experimental-webgl2"]);
  // XXX move this into WebGL.js, and perhaps into generated code. Creating a context on every load is slow and may perturb results.
  // For now:
  platform.WebGL = "experimental-webgl";
  platform.WebGL2 = "experimental-webgl2";

  platform.captureStreamUntilEnded = "captureStreamUntilEnded";
  if (platform.isMozilla) { platform.captureStreamUntilEnded = "mozCaptureStreamUntilEnded"; }

  platform.srcObject = "srcObject";
  if (platform.isMozilla) { platform.srcObject = "mozSrcObject"; }

  return platform;
})();
