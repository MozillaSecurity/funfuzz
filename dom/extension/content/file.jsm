"use strict";

/**********************
 * FILESYSTEM HELPERS *
 **********************/

function fileObject(path)
{
  var f = Components.classes["@mozilla.org/file/local;1"]
                    .createInstance(Components.interfaces.nsILocalFile);
  f.initWithPath(path);
  return f;
}


// readFile function from logan
// http://www.gozer.org/mozilla/userChrome.js/scripts/userScripts.uc.js
// |file| must be an nsIFile.
// Returns the contents of the file as a string.
function readFile(file)
{
  var content = '';

  var stream = Components.classes['@mozilla.org/network/file-input-stream;1']
                    .createInstance(Components.interfaces.nsIFileInputStream);
  stream.init(file, 0x01, 0, 0);

  var script = Components.classes['@mozilla.org/scriptableinputstream;1']
              .createInstance(Components.interfaces.nsIScriptableInputStream);
  script.init(stream);

  if (stream.available()) {
    var data = script.read(4096);

    while (data.length > 0) {
      content += data;
      data = script.read(4096);
    }
  }

  stream.close();
  script.close();

  return content;
}


function indir(dir, filename)
{
  var d = dir.clone();
  d.append(filename);
  return d;
}


/****************
 * MISC HELPERS *
 ****************/

function getEnv(key)
{
  var env = Components.classes["@mozilla.org/process/environment;1"]
                      .getService(Components.interfaces.nsIEnvironment);
  return env.get(key);
}

function dumpln(s) { dump(s + "\n"); }


var EXPORTED_SYMBOLS = [
  "fileObject",
  "profileDirectory",
  "extensionLocation",
  "readFile",
  "indir",
  "getEnv",
  "dumpln",
];
