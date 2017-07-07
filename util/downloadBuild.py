#!/usr/bin/env python

from __future__ import absolute_import

import ConfigParser
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from HTMLParser import HTMLParser

from optparse import OptionParser
import subprocesses as sps

# Use curl/wget rather than urllib because urllib can't check certs.
useCurl = False

# A terrible hack to work around a common configuration problem.
# (see bug 803764) (see bug 950256) -- (platform.system() == "Linux" and os.getenv("FUZZ_REMOTE_HOST") == "ffxbld@stage.mozilla.org")
# Another bug for Windows??
wgetMaybeNCC = ['--no-check-certificate']


def readFromURL(url):
    """Read in a URL and returns its contents as a list."""
    inpCmdList = ['curl', '--silent', url] if useCurl else ['wget'] + wgetMaybeNCC + ['-O', '-', url]
    p = subprocess.Popen(inpCmdList, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if not useCurl and p.returncode == 5:
        print 'Unable to read from URL. If you installed wget using MacPorts, you should put ' + \
              '"CA_CERTIFICATE=/opt/local/share/curl/curl-ca-bundle.crt" (without the quotes) ' + \
              'in ~/.wgetrc'
        raise Exception('Unable to read from URL. Please check your ~/.wgetrc file.')
    elif p.returncode != 0:
        print 'inpCmdList is: ' + sps.shellify(inpCmdList)
        print 'stdout: ' + repr(out)
        print 'stderr: ' + repr(err)
        raise Exception('The following exit code was returned: ' + str(p.returncode))
    else:
        # Ignore whatever verbose output wget spewed to stderr.
        return out


def downloadURL(url, dest):
    """Read in a URL and downloads it to a destination."""
    inpCmdList = ['curl', '--output', dest, url] if useCurl else ['wget'] + wgetMaybeNCC + ['-O', dest, url]
    out, retVal = sps.captureStdout(inpCmdList, combineStderr=True, ignoreExitCode=True)
    if retVal != 0:
        print out
        raise Exception('Return code is not 0, but is: ' + str(retVal))
    return dest


def parseOptions():
    usage = 'Usage: %prog [options]'
    parser = OptionParser(usage)
    parser.disable_interspersed_args()

    parser.set_defaults(
        compileType='dbg',
        downloadFolder=os.getcwdu(),
        repoName='mozilla-central',
        enableJsShell=False,
        wantTests=False,
    )

    parser.add_option('-c', '--compiletype', dest='compileType',
                      help='Sets the compile type to be downloaded. Must be "dbg" or "opt".' +
                      'Defaults to "%default".')
    parser.add_option('-a', '--architecture',
                      dest='arch',
                      type='choice',
                      choices=['32', '64'],
                      help='Test architecture. Only accepts "32" or "64"')
    parser.add_option('-w', '--downloadfolder', dest='downloadFolder',
                      help='Sets the folder to download builds in. Defaults to the current ' +
                      'working directory, which is "%default".')
    parser.add_option('-r', '--repoName', dest='repoName',
                      help='Sets the repository to be fuzzed. Defaults to "%default".')
    parser.add_option('-d', '--remotedir', dest='remoteDir',
                      help='Sets the remote directory from which the files are to be obtained ' +
                      'from. The default is to grab the latest from mozilla-central.')
    parser.add_option('-s', '--enable-jsshell', dest='enableJsShell', action='store_true',
                      help='Sets the compile type to be fuzzed. Defaults to "%default".')
    parser.add_option('-t', '--want-tests', dest='wantTests', action='store_true',
                      help='Download tests. Defaults to "%default".')

    options, args = parser.parse_args()
    assert options.compileType in ['dbg', 'opt']
    assert len(args) == 0
    return options


class MyHTMLParser(HTMLParser):

    def getHrefLinks(self, html, baseURI):
        thirdslash = find_nth(baseURI, "/", 0, 3)
        self.basepath = baseURI[thirdslash:]  # e.g. "/pub/firefox/tinderbox-builds/"

        self.hrefLinksList = []
        self.feed(html)
        return self.hrefLinksList

    def handle_starttag(self, tag, attrs):
        aTagFound = False
        if tag == 'a':
            aTagFound = True
        for attr in attrs:
            if not aTagFound:
                break
            if aTagFound and attr[0] == 'href':
                if attr[1][0] == '/':
                    # Convert site-relative URI to fully-relative URI
                    if attr[1].startswith(self.basepath):
                        self.hrefLinksList.append(attr[1][len(self.basepath):])
                elif attr[1][0] != '?':
                    # Already fully relative
                    self.hrefLinksList.append(attr[1])


def find_nth(haystack, needle, start, n):
    for _ in range(n):
        start = haystack.find(needle, start + 1)
        if start == -1:
            return -1
    return start


def httpDirList(directory):
    """Read an Apache-style directory listing and returns a list of its contents, as relative URLs."""
    print "Looking in " + directory + " ..."
    page = readFromURL(directory)
    sps.vdump('Finished reading from: ' + directory)

    parser = MyHTMLParser()
    fileList = parser.getHrefLinks(page, directory)
    return fileList


def unzip(fn, dest):
    """Extract .zip files to their destination."""
    sps.captureStdout(['unzip', fn, '-d', dest])


def untarbz2(fn, dest):
    """Extract .tar.bz2 files to their destination."""
    if not os.path.exists(dest):
        os.mkdir(dest)
    sps.captureStdout(['tar', '-C', dest, '-xjf', os.path.abspath(fn)])


def undmg(fn, dest, mountpoint):
    """Extract .dmg files to their destination via a mount point."""
    if os.path.exists(mountpoint):
        # If the mount point already exists, detach it first.
        sps.captureStdout(['hdiutil', 'detach', mountpoint, '-force'])
    sps.captureStdout(['hdiutil', 'attach', '-quiet', '-mountpoint', mountpoint, fn])
    try:
        apps = [x for x in os.listdir(mountpoint) if x.endswith('app')]
        assert len(apps) == 1
        shutil.copytree(mountpoint + '/' + apps[0], dest + '/' + apps[0])
    finally:
        sps.captureStdout(['hdiutil', 'detach', mountpoint])


def downloadBuild(httpDir, targetDir, jsShell=False, wantSymbols=True, wantTests=True):
    """Download the build specified, along with symbols and tests. Returns True when all are obtained."""
    wantSymbols = wantSymbols and not jsShell  # Bug 715365, js shell currently lacks native symbols
    wantTests = wantTests and not jsShell
    gotApp = False
    gotTests = False
    gotTxtFile = False
    gotSyms = False
    # Create build folder and a download subfolder.
    buildDir = os.path.abspath(sps.normExpUserPath(os.path.join(targetDir, 'build')))
    if os.path.exists(buildDir):
        print "Deleting old build..."
        shutil.rmtree(buildDir)
    os.mkdir(buildDir)
    downloadFolder = os.path.join(buildDir, 'download')
    os.mkdir(downloadFolder)

    with open(os.path.join(downloadFolder, "source-url.txt"), "w") as f:
        f.writelines([httpDir])

    # Hack #1 for making os.path.join(reftestScriptDir, automation.DEFAULT_APP) work is to:
    # Call this directory "dist".
    appDir = os.path.join(buildDir, 'dist') + os.sep
    testsDir = os.path.join(buildDir, 'tests') + os.sep
    symbolsDir = os.path.join(buildDir, 'symbols') + os.sep
    fileHttpRawList = httpDirList(httpDir)
    # We only want files, those with file extensions, not folders.
    fileHttpList = [httpDir + x for x in fileHttpRawList if '.' in x and 'mozilla.org' not in x]

    for remotefn in fileHttpList:
        localfn = os.path.join(downloadFolder, remotefn.split('/')[-1])
        if remotefn.endswith('.common.tests.zip') and wantTests:
            print 'Downloading common test files...',
            dlAction = downloadURL(remotefn, localfn)
            print 'extracting...',
            unzip(dlAction, testsDir)
            moveCrashInjector(testsDir)
            mIfyMozcrash(testsDir)
            print 'completed!'
            gotTests = True
        if remotefn.endswith('.reftest.tests.zip') and wantTests:
            print 'Downloading reftest files...',
            dlAction = downloadURL(remotefn, localfn)
            print 'extracting...',
            unzip(dlAction, testsDir)
            print 'completed!'
        if remotefn.split('/')[-1].endswith('.txt'):
            print 'Downloading text file...',
            downloadURL(remotefn, localfn)
            print 'completed!'
            gotTxtFile = True
        if jsShell:
            if remotefn.split('/')[-1].startswith('jsshell-'):
                print 'Downloading js shell...',
                dlAction = downloadURL(remotefn, localfn)
                print 'extracting...',
                unzip(dlAction, appDir)
                print 'completed!'
                gotApp = True  # Bug 715365 - note that js shell currently lacks native symbols
                writeDownloadedShellFMConf(remotefn, buildDir)
        else:
            if remotefn.endswith('.linux-i686.tar.bz2') or remotefn.endswith('.linux-x86_64.tar.bz2'):
                print 'Downloading application...',
                dlAction = downloadURL(remotefn, localfn)
                print 'extracting...',
                untarbz2(dlAction, appDir)
                print 'completed!'

                # Hack #2 to make os.path.join(reftestScriptDir, automation.DEFAULT_APP) work.
                shutil.move(os.path.join(appDir, 'firefox'), os.path.join(appDir, 'bin'))
                stackwalk = os.path.join(buildDir, 'minidump_stackwalk')
                stackwalkUrl = (
                    'https://hg.mozilla.org/build/tools/raw-file/default/breakpad/linux/minidump_stackwalk'
                    if remotefn.endswith('.linux-i686.tar.bz2') else
                    'https://hg.mozilla.org/build/tools/raw-file/default/breakpad/linux64/minidump_stackwalk'
                )
                downloadURL(stackwalkUrl, stackwalk)
                os.chmod(stackwalk, stat.S_IRWXU)
                gotApp = True
            if remotefn.endswith('.win32.zip') or remotefn.endswith('.win64.zip'):
                print 'Downloading application...',
                dlAction = downloadURL(remotefn, localfn)
                print 'extracting...',
                unzip(dlAction, appDir)
                print 'completed!'

                # Hack #2 for making os.path.join(reftestScriptDir, automation.DEFAULT_APP) work.
                shutil.move(os.path.join(appDir, 'firefox'), os.path.join(appDir, 'bin'))
                for filename in ['minidump_stackwalk.exe', 'cyggcc_s-1.dll',
                                 'cygstdc++-6.dll', 'cygwin1.dll']:
                    remoteURL = 'https://hg.mozilla.org/build/tools/raw-file/default/breakpad/win32/%s' % filename
                    localfile = os.path.join(buildDir, filename)
                    downloadURL(remoteURL, localfile)
                gotApp = True
            if remotefn.endswith('.mac.dmg') or remotefn.endswith('.mac64.dmg'):
                print 'Downloading application...',
                dlAction = downloadURL(remotefn, localfn)
                print 'extracting...',
                undmg(dlAction, appDir, os.path.join(buildDir, 'MOUNTEDDMG'))
                print 'completed!'
                downloadMDSW(buildDir, "macosx64")
                gotApp = True
            if remotefn.endswith('.crashreporter-symbols.zip') and wantSymbols:
                print 'Downloading crash reporter symbols...',
                dlAction = downloadURL(remotefn, localfn)
                print 'extracting...',
                unzip(dlAction, symbolsDir)
                print 'completed!'
                gotSyms = True
    return gotApp and gotTxtFile and (gotTests or not wantTests) and (gotSyms or not wantSymbols)


def downloadMDSW(buildDir, manifestPlatform):
    """Download the minidump_stackwalk[.exe] binary for this platform."""
    THIS_SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    TOOLTOOL_PY = os.path.join(THIS_SCRIPT_DIRECTORY, "tooltool", "tooltool.py")

    # Find the tooltool manifest for this platform
    manifestFilename = os.path.join(THIS_SCRIPT_DIRECTORY, "tooltool", manifestPlatform + ".manifest")

    # Download the binary (using tooltool)
    subprocess.check_call([sys.executable, TOOLTOOL_PY, "-m", manifestFilename, "fetch"], cwd=buildDir)

    # Mark the binary as executable
    if platform.system() != 'Windows':
        stackwalkBin = os.path.join(buildDir, "minidump_stackwalk")
        os.chmod(stackwalkBin, stat.S_IRWXU)


def moveCrashInjector(tests):
    # Hackaround for crashinject.exe not being a reliable way to kill firefox.exe (see bug 888748)
    testsBin = os.path.join(tests, "bin")
    crashinject = os.path.join(testsBin, "crashinject.exe")
    if os.path.exists(crashinject):
        shutil.move(crashinject, os.path.join(testsBin, "crashinject-disabled.exe"))


def mIfyMozcrash(testsDir):
    # Terrible hack to pass "-m" to breakpad through mozcrash
    mozcrashDir = os.path.join(testsDir, "mozbase", "mozcrash", "mozcrash")
    mozcrashPy = os.path.join(mozcrashDir, "mozcrash.py")
    # print mozcrashPy
    mozcrashPyBak = os.path.join(mozcrashDir, "mozcrash.py.bak")
    shutil.copyfile(mozcrashPy, mozcrashPyBak)
    with open(mozcrashPy, "w") as outfile:
        with open(mozcrashPyBak) as infile:
            for line in infile:
                outfile.write(line)
                if line.strip() == "self.stackwalk_binary,":
                    outfile.write("\"-m\",\n")


def isNumericSubDir(n):
    """Return True if input is a numeric directory, False if not. e.g. 1234/ returns True."""
    return re.match(r'^\d+$', n.split('/')[0])


def getBuildList(buildType, earliestBuild='default', latestBuild='default'):
    """Return the list of URLs of builds (e.g. 1386614507) that are present in tinderbox-builds/."""
    buildsHttpDir = 'https://archive.mozilla.org/pub/firefox/tinderbox-builds/' + \
                    buildType + '/'
    dirNames = httpDirList(buildsHttpDir)

    if earliestBuild != 'default':
        earliestBuild = earliestBuild + '/'
        if earliestBuild not in dirNames:
            raise Exception('Earliest build is not found in list of IDs.')
    else:
        earliestBuild = dirNames[0]

    # Earlier downloaded builds fail to start properly on macOS Sierra 10.12
    # First known working build is in:
    # https://archive.mozilla.org/pub/firefox/tinderbox-builds/mozilla-inbound-macosx64-debug/1468314445/
    # Note: if this gets more populated, we should move it to knownBrokenEarliestWorking
    if sps.isMac and int(earliestBuild[:-1]) < 1468314445:
        earliestBuild = '1468314445/'

    try:
        earliestBuildIndex = dirNames.index(earliestBuild)  # Set the start boundary
    except ValueError:
        # Sometimes 1468314445 is not found
        if sps.isMac and int(earliestBuild[:-1]) < 1468333601:
            earliestBuild = '1468333601/'
        earliestBuildIndex = dirNames.index(earliestBuild)  # Set the start boundary

    if latestBuild != 'default':
        latestBuild = latestBuild + '/'
        if latestBuild not in dirNames:
            raise Exception('Latest build is not found in list of IDs.')
    else:
        latestBuild = dirNames[-1]
    latestBuildIndex = dirNames.index(latestBuild)  # Set the end boundary

    dirNames = dirNames[earliestBuildIndex:latestBuildIndex + 1]

    buildDirs = [(buildsHttpDir + d) for d in dirNames if isNumericSubDir(d)]
    if len(buildDirs) < 1:
        print 'Warning: No builds in ' + buildsHttpDir + '!'
    return buildDirs


def downloadLatestBuild(buildType, workingDir, getJsShell=False, wantTests=False):
    """Download the latest build based on machine type, e.g. mozilla-central-macosx64-debug."""
    # Try downloading the latest build first.
    for buildURL in reversed(getBuildList(buildType)):
        if downloadBuild(buildURL, workingDir, jsShell=getJsShell, wantTests=wantTests):
            return buildURL
    raise Exception("No complete builds found.")


def mozPlatformDetails():
    """Determine the platform of the system and returns the RelEng-specific build type."""
    s = platform.system()
    if s == "Darwin":
        return ("macosx", "macosx64", platform.architecture()[0] == "64bit")
    elif s == "Linux":
        return ("linux", "linux64", platform.machine() == "x86_64")
    elif s == 'Windows':
        return ("win32", "win64", False)
    else:
        raise Exception("Unknown platform.system(): " + s)


def mozPlatform(arch):
    """Return the native build type of the current machine."""
    (name32, name64, native64) = mozPlatformDetails()
    if arch == "64":
        return name64
    elif arch == "32":
        return name32
    elif arch is None:
        # FIXME: Eventually, we should set 64-bit as native for Win64. We should also aim to test
        # both 32-bit and 64-bit Firefox builds on any platform that supports both. Let us make
        # sure Python detects 32-bit Windows vs 64-bit Windows correctly before changing this.
        return name64 if native64 else name32
    else:
        raise Exception("The arch passed to mozPlatform must be '64', '32', or None")


def defaultBuildType(repoName, arch, debug):
    """Return the default build type as per RelEng, e.g. mozilla-central-macosx-debug."""
    return repoName + '-' + mozPlatform(arch) + ('-debug' if debug else '')


def writeDownloadedShellFMConf(urlLink, bDir):
    """Writes an arbitrary .fuzzmanagerconf file for downloaded js shells."""
    downloadedShellCfg = ConfigParser.SafeConfigParser()
    downloadedShellCfg.add_section('Main')

    # Note that this does not differentiate between debug/asan/optimized builds
    if '-linux' in urlLink:
        osname = 'linux'
        if '-linux64' in urlLink:
            osname = 'linux64'
            archname = 'x86-64'
        else:
            archname = 'x86'
    elif '-win' in urlLink:
        osname = 'win32'
        if 'win64' in urlLink:
            osname = 'win64'
            archname = 'x86-64'
        else:
            archname = 'x86'
    elif '-macosx64' in urlLink:
        osname = 'macosx64'
        archname = 'x86-64'

    downloadedShellCfg.set('Main', 'platform', archname)
    if 'mozilla-central-' in urlLink:
        downloadedShellCfg.set('Main', 'product', 'mozilla-central')
    elif 'mozilla-inbound-' in urlLink:
        downloadedShellCfg.set('Main', 'product', 'mozilla-inbound')
    elif 'mozilla-aurora-' in urlLink:
        downloadedShellCfg.set('Main', 'product', 'mozilla-aurora')
    elif 'mozilla-beta-' in urlLink:
        downloadedShellCfg.set('Main', 'product', 'mozilla-beta')
    elif 'mozilla-release-' in urlLink:
        downloadedShellCfg.set('Main', 'product', 'mozilla-release')
    elif 'mozilla-esr52-' in urlLink:
        downloadedShellCfg.set('Main', 'product', 'mozilla-esr52')
    downloadedShellCfg.set('Main', 'os', osname)

    downloadedShellFMConfPath = os.path.join(bDir, 'dist', 'js.fuzzmanagerconf')
    if not os.path.isfile(downloadedShellFMConfPath):
        with open(downloadedShellFMConfPath, 'wb') as cfgfile:
            downloadedShellCfg.write(cfgfile)

    # Required pieces of the .fuzzmanagerconf file are platform, product and os
    cfg = ConfigParser.SafeConfigParser()
    cfg.read(downloadedShellFMConfPath)
    assert cfg.get('Main', 'platform')
    assert cfg.get('Main', 'product')
    assert cfg.get('Main', 'os')


def main():
    options = parseOptions()
    # On Windows, if a path surrounded by quotes ends with '\', the last quote is considered escaped and will be
    # part of the option. This is not what the user expects, so remove any trailing quotes from paths:
    options.remoteDir = options.remoteDir and options.remoteDir.rstrip('"')
    options.downloadFolder = options.downloadFolder and options.downloadFolder.rstrip('"')
    if options.remoteDir is not None:
        print downloadBuild(options.remoteDir, options.downloadFolder, jsShell=options.enableJsShell, wantTests=options.wantTests)
    else:
        buildType = defaultBuildType(options.repoName, options.arch, (options.compileType == 'dbg'))
        downloadLatestBuild(buildType, options.downloadFolder,
                            getJsShell=options.enableJsShell, wantTests=options.wantTests)


if __name__ == "__main__":
    main()
