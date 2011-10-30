#!/usr/bin/env python

import re, os, sys, shutil, subprocess, time, StringIO, stat
import platform
devnull = open(os.devnull, "w")

# Use curl/wget rather than urllib because urllib can't check certs.
# Want to move toward wget since it's in mozillabuild and on the build machines.  But wget on Mac has cert issues...
preferCurl = platform.system() == "Darwin"
def readFromURL(url):
  if preferCurl:
    p = subprocess.Popen(["curl", "--silent", url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  else:
    p = subprocess.Popen(["wget", "-q", "-O", "-", url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  (out, err) = p.communicate()
  return StringIO.StringIO(out)
def downloadURL(url, dest):
  if preferCurl:
    subprocess.check_call(["curl", "--output", dest, url])
  else:
    subprocess.check_call(["wget", "-O", dest, url])
  return dest

def httpDirList(dir):
  print "Looking in " + dir + "..."
  files = []
  page = readFromURL(dir)
  for line in page:
    if line.startswith("<tr>"):
      match = re.search("<a href=\"([^\"]*)\">", line)
      if match != None and match.group(1)[0] != "/":
        files.append(dir + match.group(1))
  page.close()
  return files


def unzip(fn, dest):
  subprocess.check_call(["unzip", fn, "-d", dest], stdout=devnull)

def untarbz2(fn, dest):
  os.mkdir(dest)
  subprocess.check_call(["tar", "-C", dest, "-xjf", os.path.abspath(fn)], stdout=devnull)

def undmg(fn, dest, mountpoint):
  if os.path.exists(mountpoint):
    subprocess.check_call(["hdiutil", "detach", mountpoint, "-force"], stdout=devnull)
  subprocess.check_call(["hdiutil", "attach", "-quiet", "-mountpoint", mountpoint, fn], stdout=devnull)
  try:
    apps = filter(lambda s: s.endswith(".app"), os.listdir(mountpoint))
    assert len(apps) == 1
    shutil.copytree(mountpoint + "/" + apps[0], dest + "/" + apps[0])
  finally:
    subprocess.check_call(["hdiutil", "detach", mountpoint], stdout=devnull)


def downloadBuild(httpDir, wantSymbols=True, wantTests=True):
  gotApp = False
  gotTests = False
  gotSyms = False
  if os.path.exists("build"):
    shutil.rmtree("build")
  os.mkdir("build")
  downloadDir = os.path.join("build", "download")
  os.mkdir(downloadDir)
  appDir = os.path.join("build", "dist") + os.sep # hack #1 for making os.path.join(reftestScriptDir, automation.DEFAULT_APP) work is calling this directory "dist"
  testsDir = os.path.join("build", "tests") + os.sep
  symbolsDir = os.path.join("build", "symbols") + os.sep
  for remotefn in httpDirList(httpDir):
    localfn = os.path.join(downloadDir, remotefn.split("/")[-1])
    if remotefn.endswith(".linux-i686.tar.bz2") or remotefn.endswith(".linux-x86_64.tar.bz2"):
      print "Downloading application..."
      untarbz2(downloadURL(remotefn, localfn), appDir)
      os.rename(os.path.join(appDir, "firefox"), os.path.join(appDir, "bin")) # hack #2 for making os.path.join(reftestScriptDir, automation.DEFAULT_APP) work
      stackwalk = os.path.join("build", "minidump_stackwalk")
      if remotefn.endswith(".linux-i686.tar.bz2"):
        downloadURL("http://hg.mozilla.org/build/tools/raw-file/default/breakpad/linux/minidump_stackwalk", stackwalk)
      else:
        downloadURL("http://hg.mozilla.org/build/tools/raw-file/default/breakpad/linux64/minidump_stackwalk", stackwalk)
      os.chmod(stackwalk, stat.S_IRWXU)
      gotApp = True
    if remotefn.endswith(".win32.zip"):
      print "Downloading application..."
      unzip(downloadURL(remotefn, localfn), appDir)
      os.rename(os.path.join(appDir, "firefox"), os.path.join(appDir, "bin")) # hack #2 for making os.path.join(reftestScriptDir, automation.DEFAULT_APP) work
      for filename in ['minidump_stackwalk.exe',
                       'cyggcc_s-1.dll',
                       'cygstdc++-6.dll',
                       'cygwin1.dll']:
          remoteURL = "http://hg.mozilla.org/build/tools/raw-file/default/breakpad/win32/%s" % filename
          localfile = os.path.join("build", filename)
          downloadURL(remoteURL, localfile)
      gotApp = True
    if remotefn.endswith(".mac.dmg") or remotefn.endswith(".mac64.dmg"):
      print "Downloading application..."
      undmg(downloadURL(remotefn, localfn), appDir, os.path.join("build", "MOUNTEDDMG"))
      stackwalk = os.path.join("build", "minidump_stackwalk")
      downloadURL("http://hg.mozilla.org/build/tools/raw-file/default/breakpad/osx/minidump_stackwalk", stackwalk)
      os.chmod(stackwalk, stat.S_IRWXU)
      gotApp = True
    if remotefn.endswith(".tests.zip") and wantTests:
      print "Downloading tests..."
      unzip(downloadURL(remotefn, localfn), testsDir)
      gotTests = True
    if remotefn.endswith(".crashreporter-symbols.zip") and wantSymbols:
      print "Downloading crash reporter symbols..."
      unzip(downloadURL(remotefn, localfn), symbolsDir)
      gotSyms = True
  return gotApp and gotTests and gotSyms

def isNumericDir(n):
  return re.match(r"^\d+$", n.split("/")[-2])

def downloadLatestBuild(buildType):
  """buildType can be e.g. mozilla-central-macosx-debug"""
  buildsDir = "https://ftp.mozilla.org/pub/mozilla.org/firefox/tinderbox-builds/" + buildType + "/"
  builds = filter(isNumericDir, httpDirList(buildsDir))
  for b in reversed(builds):
    if downloadBuild(b):
      return b
  raise Exception("No builds in " + buildsDir + "!")

def mozPlatform():
  s = platform.system()
  if s == "Darwin":
    a = platform.architecture()[0] # machine() depends on python version?
    if a == "64bit":
      return "macosx64"
    else:
      return "macosx"
  if s == "Linux":
    m = platform.machine()
    if m == "x86_64":
      return "linux64"
    else:
      return "linux"
  if s in ("Microsoft", "Windows"):
    return "win32"
  raise Exception("Unknown platform.system(): " + s)

def defaultBuildType():
  return "mozilla-central-" + mozPlatform() + "-debug"

if __name__ == "__main__":
  if len(sys.argv) > 1:
    downloadBuild(sys.argv[1])
  else:
    downloadLatestBuild(defaultBuildType())
