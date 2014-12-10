#!/usr/bin/env python

# bot.py runs domfuzz, jsfunfuzz, or Lithium for a limited amount of time.
# It stores jobs using ssh, using directory 'mv' for synchronization.

import os
import platform
import random
import shutil
import socket
import subprocess
import sys
import time
import uuid
import tempfile
import multiprocessing

from glob import iglob
from optparse import OptionParser
from tempfile import mkdtemp

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, 'util'))
sys.path.insert(0, path1)
import downloadBuild
import hgCmds
import lithOps
from subprocesses import captureStdout, dateStr, getFreeSpace
from subprocesses import isARMv7l, isLinux, isMac, isWin
from subprocesses import normExpUserPath, shellify
from LockDir import LockDir
path2 = os.path.abspath(os.path.join(path0, 'dom', 'automation'))
sys.path.append(path2)
import loopdomfuzz
import domInteresting
import randomPrefs
import buildBrowser
path3 = os.path.abspath(os.path.join(path0, 'js'))
sys.path.append(path3)
import buildOptions
import compileShell
import loopjsfunfuzz

localSep = "/" # even on windows, i have to use / (avoid using os.path.join) in bot.py! is it because i'm using bash?

# Possible ssh options:
#   -oStrictHostKeyChecking=no
#   -oUserKnownHostsFile=/dev/null

def splitSlash(d):
    return d.split("/" if "/" in d else "\\")

def assertTrailingSlash(d):
    assert d[-1] in ("/", "\\")

def adjustForScp(d):
    if platform.system() == "Windows" and d[1] == ":":
        # Turn "c:\foo\" into "/c/foo/" so scp doesn't think "c" is a hostname
        return "/" + d[0] + d[2:].replace("\\", "/")
    return d

# Copies a directory (the directory itself, not just its contents)
# whose full name is |srcDir|, creating a subdirectory of |destParent| with the same short name.
def copyFiles(remoteHost, srcDir, destParent):
    assertTrailingSlash(srcDir)
    assertTrailingSlash(destParent)
    if remoteHost == None:
        subprocess.check_call(["cp", "-R", srcDir[:-1], destParent])
    else:
        with open(os.devnull, "w") as devnull:
            subprocess.check_call(["scp", "-p", "-r", adjustForScp(srcDir), adjustForScp(destParent)], stdout=devnull)
    srcDirLeaf = splitSlash(srcDir)[-2]
    return destParent + srcDirLeaf + destParent[-1]

def tryCommand(remoteHost, cmd):
    if remoteHost == None:
        p = subprocess.Popen(["bash", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        p = subprocess.Popen(["ssh", remoteHost, cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.communicate()
    return p.returncode == 0

def runCommand(remoteHost, cmd):
    if remoteHost == None:
        p = subprocess.Popen(["bash", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        p = subprocess.Popen(["ssh", remoteHost, cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = p.communicate()
    if err != "":
        raise Exception("bot.py runCommand: stderr: " + repr(err))
    if p.returncode != 0:
        raise Exception("bot.py runCommand: unhappy exit code " + str(p.returncode) + " from " + cmd)
    return out


def grabJob(options, desiredJobType):
    while True:
        jobs = filter( (lambda s: s.endswith(desiredJobType)), runCommand(options.remote_host, "ls -t " + options.relevantJobsDir).split("\n") )
        if len(jobs) > 0:
            oldNameOnServer = jobs[0]
            shortHost = socket.gethostname().split(".")[0]  # more portable than os.uname()[1]
            takenNameOnServer = options.relevantJobsDir + oldNameOnServer.split("_")[0] + "_taken_by_" + shortHost + "_at_" + timestamp()
            if tryCommand(options.remote_host, "mv " + options.relevantJobsDir + oldNameOnServer + " " + takenNameOnServer + ""):
                print "Grabbed " + oldNameOnServer + " by renaming it to " + takenNameOnServer
                jobWithPostfix = copyFiles(options.remote_host, options.remote_prefix + takenNameOnServer + options.remoteSep, options.tempDir + localSep)
                oldjobname = oldNameOnServer[:len(oldNameOnServer) - len(desiredJobType)] # cut off the part after the "_"
                job = options.tempDir + localSep + oldjobname + localSep
                shutil.move(jobWithPostfix, job)
                print repr((job, oldjobname, takenNameOnServer))
                return (job, oldjobname, takenNameOnServer) # where it is for running lithium; what it should be named; and where to delete it from the server
            else:
                print "Raced to grab " + options.relevantJobsDir + oldNameOnServer + ", trying again"
                continue
        else:
            return (None, None, None)


def uploadJob(options, lithResult, lithDetails, job, oldjobname):
    statePostfix = ({
      lithOps.NO_REPRO_AT_ALL: "_no_repro",
      lithOps.NO_REPRO_EXCEPT_BY_URL: "_repro_url_only",
      lithOps.LITH_NO_REPRO: "_no_longer_reproducible",
      lithOps.LITH_FINISHED: "_reduced",
      lithOps.LITH_PLEASE_CONTINUE: "_needsreduction",
      lithOps.LITH_BUSTED: "_sad"
    })[lithResult]

    if lithResult == lithOps.LITH_PLEASE_CONTINUE:
        writeTinyFile(job + "lithium-command.txt", lithDetails)

    if lithResult == lithOps.LITH_FINISHED or (options.testType == 'js' and lithOps.LITH_NO_REPRO):
        # lithDetails should be a string like "11 lines"
        statePostfix = "_" + lithDetails.replace(" ", "_") + statePostfix
        summaryFile = job + filter(lambda s: s.find("summary") != -1, os.listdir(job))[0]
        with open(summaryFile) as f:
            summary = "\n\n" + f.read(50000)
        if options.testType == 'js':
            outFile = job + filter(lambda s: s.find("-out.txt") != -1 and '.gz' not in s, os.listdir(job))[0]
            if os.path.isfile(outFile):
                from itertools import islice
                with open(outFile) as f:
                    for line in islice(f, 0, 9):  # fuzzSeed is located near the top of *-out.txt
                        if line.startswith('fuzzSeed'):
                            summary = '\n\nfuzzSeed is: ' + line.split()[1] + summary
    else:
        summary = ""

    #print "oldjobname: " + oldjobname
    newjobname = oldjobname + statePostfix
    print "Uploading as: " + newjobname
    newjobnameTmp = newjobname + ".uploading"
    newjobTmp = options.tempDir + localSep + newjobnameTmp
    shutil.move(job, newjobTmp)
    copyFiles(options.remote_host, newjobTmp + localSep, options.remote_prefix + options.relevantJobsDir + options.remoteSep)
    runCommand(options.remote_host, "mv " + options.relevantJobsDir + newjobnameTmp + " " + options.relevantJobsDir + newjobname)
    shutil.rmtree(newjobTmp)

    if lithResult == lithOps.LITH_FINISHED or options.testType == 'js':
        recipients = []
        subject = "Reduced " + options.testType + " fuzz testcase"
        if options.remote_host:
            machineInfo = "This machine: " + platform.uname()[1] + "\n" + "Reporting to: " + options.remote_host + ":" + options.baseDir
            if options.baseDir == "//mnt/pvt_builds/fuzzing/":
                dirRef = "https://pvtbuilds.mozilla.org/fuzzing/" + options.relevantJobsDirName + "/" + newjobname + "/"
            else:
                dirRef = options.relevantJobsDirName + "/" + newjobname + "/"
        else:
            machineInfo = "This machine: " + platform.uname()[1] + "\n"
            dirRef = ''
        # no_longer_reproducible crashes do not have a summary file,
        # so check if summary is an actual local variable with a value.
        body = machineInfo + "\n\n" + dirRef + summary
        if options.testType == 'js':
            # Send jsfunfuzz emails to gkw
            recipients.append("gkwong")
        elif options.remote_host:
            # Send domfuzz emails to Jesse
            recipients.append("jruderman")
        print "Sending email..."
        for recipient in recipients:
            sendEmail(subject, body, recipient)
        print "Email sent!"


def readTinyFile(fn):
    with open(fn) as f:
        text = f.read()
    return text.strip()

def writeTinyFile(fn, text):
    with open(fn, "w") as f:
        f.write(text)

def timestamp():
    return str(int(time.time()))

def sendEmail(subject, body, receiver):
    import smtplib
    from email.mime.text import MIMEText

    assert receiver in ('jruderman', 'gkwong')
    if receiver == 'jruderman':
        fromAddr = 'jruderman+fuzzbot@mozilla.com'
        toAddr = 'jruderman@gmail.com'
    elif receiver == 'gkwong':
        fromAddr = 'gkwong+fuzzbot@mozilla.com'
        toAddr = 'swader@gmail.com'

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = fromAddr
    msg['To'] = toAddr

    server = smtplib.SMTP('mail.build.mozilla.org')
    server.sendmail(fromAddr, [toAddr], msg.as_string())
    server.quit()

def parseOpts():
    parser = OptionParser()
    parser.set_defaults(
        remote_host = None,
        baseDir = os.path.expanduser("~") + localSep + "fuzzingjobs" + localSep,
        repoName = 'mozilla-central',
        targetTime = 15*60,       # 15 minutes
        testType = "auto",
        existingBuildDir = None,
        retestRoot = None,
        disableRndFlags = False,
        noStart = False,
        timeout = 0,
        buildOptions = None,
        runLocalJsfunfuzz = False,
        useTinderboxShells = False,
        retestSkips = None
    )

    parser.add_option('-t', '--test-type', dest='testType', choices=['auto', 'js', 'dom'],
        help='Test type: "js", "dom", or "auto" (which is usually random).')

    parser.add_option("--delay", dest="localJsfunfuzzTimeDelay",
        help="Delay before local jsfunfuzz is run.")
    parser.add_option("--build", dest="existingBuildDir",
        help="Use an existing build directory.")
    parser.add_option("--retest", dest="retestRoot",
        help="Instead of fuzzing or reducing, take reduced testcases and retest them. Pass a directory such as ~/fuzzingjobs/ or an rsync'ed ~/fuzz-results/.")
    parser.add_option("--retest-skips", dest="retestSkips",
        help="File listing job names to skip when retesting.")

    parser.add_option('--repotype', dest='repoName',
        help='Sets the repository to be fuzzed. Defaults to "%default".')

    parser.add_option("--remote-host", dest="remote_host",
        help="Use remote host to store fuzzing jobs; format: user@host. If omitted, a local directory will be used instead.")
    parser.add_option("--basedir", dest="baseDir",
        help="Base directory on remote machine to store fuzzing data")
    parser.add_option("--target-time", dest="targetTime", type='int',
        help="Nominal amount of time to run, in seconds")

    #####
    parser.add_option('-j', '--local-jsfunfuzz', dest='runLocalJsfunfuzz', action='store_true',
                      help='Run local jsfunfuzz.')
    parser.add_option('-T', '--use-tinderbox-shells', dest='useTinderboxShells', action='store_true',
                      help='Fuzz js using tinderbox shells. Requires -j.')
    # From the old localjsfunfuzz file.
    parser.add_option('--disable-random-flags', dest='disableRndFlags', action='store_true',
                      help='Disable random flag fuzzing.')
    parser.add_option('--nostart', dest='noStart', action='store_true',
                      help='Compile shells only, do not start fuzzing.')

    # Specify how the shell will be built.
    # See js/buildOptions.py and dom/automation/buildBrowser.py for details.
    parser.add_option('-b', '--build-options',
                      dest='buildOptions',
                      help='Specify build options, e.g. -b "-c opt --arch=32" for js (python buildOptions.py --help)')

    parser.add_option('--timeout', type='int', dest='timeout',
                      help='Sets the timeout for loopjsfunfuzz.py. ' + \
                           'Defaults to taking into account the speed of the computer and ' + \
                           'debugger (if any).')

    options, args = parser.parse_args()
    if len(args) > 0:
        print "Warning: bot.py does not use positional arguments"

    if options.useTinderboxShells:
        if not options.runLocalJsfunfuzz:
            raise Exception('Turn on -j before using fuzzing using tinderbox js shells.')
        if options.buildOptions is not None:
            raise Exception('Do not use tinderbox shells if one needs to specify build parameters')

    if options.testType == 'auto' and not options.runLocalJsfunfuzz:
        if options.retestRoot or options.existingBuildDir:
            options.testType = 'dom'
        elif isLinux and platform.machine() != "x86_64":
            # Bug 855881
            options.testType = 'js'
        else:
            options.testType = random.choice(['js', 'dom'])
            print "Randomly fuzzing: " + options.testType

    if options.runLocalJsfunfuzz:
        options.testType = 'js'
        if options.buildOptions is None and not options.useTinderboxShells:
            options.buildOptions = ''

        if options.localJsfunfuzzTimeDelay is None:
            options.localJsfunfuzzTimeDelay = 0
        else:
            options.localJsfunfuzzTimeDelay = int(options.localJsfunfuzzTimeDelay)

    if options.remote_host and "/msys/" in options.baseDir:
        # Undo msys-bash damage that turns --basedir "/foo" into "C:/mozilla-build/msys/foo"
        # when we are trying to refer to a directory on another computer.
        options.baseDir = "/" + options.baseDir.split("/msys/")[1]

    # options.remote_prefix is used as a prefix for options.baseDir when using scp
    options.remote_prefix = (options.remote_host + ":") if options.remote_host else ""

    options.remoteSep = "/" if options.remote_host else localSep

    assert options.baseDir.endswith(options.remoteSep)
    return options


def main():
    botmain(parseOpts())

def botmain(options):
    #####
    # These only affect fuzzing the js shell on a local machine.
    if options.runLocalJsfunfuzz and not options.useTinderboxShells:
        if options.localJsfunfuzzTimeDelay != 0:
            time.sleep(options.localJsfunfuzzTimeDelay)

        options.buildOptions = buildOptions.parseShellOptions(options.buildOptions)
        options.timeout = options.timeout or machineTimeoutDefaults(options)

        with LockDir(compileShell.getLockDirPath(options.buildOptions.repoDir)):
            shell, fuzzPath, cList = localCompileFuzzJsShell(options)

        if options.noStart:
            print 'Exiting, --nostart is set.'
            sys.exit(0)

        # Commands to simulate bash's `tee`.
        tee = subprocess.Popen(['tee', 'log-jsfunfuzz.txt'], stdin=subprocess.PIPE, cwd=fuzzPath)

        # Start fuzzing the newly compiled builds.
        subprocess.call(cList, stdout=tee.stdin, cwd=fuzzPath)
    #####

    else:
        options.tempDir = tempfile.mkdtemp("fuzzbot")
        print options.tempDir

        if options.remote_host:
            printMachineInfo()
            #sendEmail("justInWhileLoop", "Platform details , " + platform.node() + " , Python " + sys.version[:5] + " , " +  " ".join(platform.uname()), "gkwong")

        buildDir, buildSrc, buildType, haveBuild = ensureBuild(options)
        if not haveBuild:
            return
        assert os.path.isdir(buildDir)

        if options.retestRoot:
            print "Retesting time!"
            retestAll(options, buildDir)
        else:
            options.relevantJobsDirName = options.testType + "-" + buildType
            options.relevantJobsDir = options.baseDir + options.relevantJobsDirName + options.remoteSep

            runCommand(options.remote_host, "mkdir -p " + options.baseDir) # don't want this created recursively, because "mkdir -p" is weird with modes
            runCommand(options.remote_host, "chmod og+rx " + options.baseDir)
            runCommand(options.remote_host, "mkdir -p " + options.relevantJobsDir)
            runCommand(options.remote_host, "chmod og+rx " + options.relevantJobsDir)

            (job, oldjobname, takenNameOnServer) = grabJob(options, "_needsreduction")
            if job:
                print "Reduction time!"
                lithArgs = readTinyFile(job + "lithium-command.txt").strip().split(" ")
                lithArgs[-1] = job + splitSlash(lithArgs[-1])[-1] # options.tempDir may be different
                if platform.system() == "Windows":
                    # Ensure both Lithium and Firefox understand the filename
                    lithArgs[-1] = lithArgs[-1].replace("/","\\")
                logPrefix = job + "reduce" + timestamp()
                (lithResult, lithDetails) = lithOps.runLithium(lithArgs, logPrefix, options.targetTime)
                uploadJob(options, lithResult, lithDetails, job, oldjobname)
                runCommand(options.remote_host, "rm -rf " + takenNameOnServer)

            else:
                print "Fuzz time!"
                #if options.testType == 'js':
                #    print "Sending email..."
                #    sendEmail("justFuzzTime", "Platform details (" + str(numProcesses) + " cores), " + platform.node() + " , Python " + sys.version[:5] + " , " +  " ".join(platform.uname()), "gkwong")
                #    print "Email sent!"

                numProcesses = multiprocessing.cpu_count()
                if "-asan" in buildDir:
                    # This should really be based on the amount of RAM available, but I don't know how to compute that in Python.
                    # I could guess 1 GB RAM per core, but that wanders into sketchyville.
                    numProcesses = max(numProcesses // 2, 1)

                forkJoin(numProcesses, fuzzUntilBug, [options, buildDir, buildSrc])

        # Remove build directory
        if not (options.retestRoot or options.existingBuildDir or options.buildOptions is not None):
            shutil.rmtree(buildDir)

        try:
            # Remove the main temp dir, which should be empty at this point
            os.rmdir(options.tempDir)
        except OSError as e:
            print repr(e)
            print options.tempDir + ' still has the following contents:'
            print os.listdir(options.tempDir)
            raise


def printMachineInfo():
    # Log information about the machine.
    print "Platform details: " + " ".join(platform.uname())
    print "hg version: " + captureStdout(['hg', '-q', 'version'])[0]

    # In here temporarily to see if mock Linux slaves on TBPL have gdb installed
    try:
        print "gdb version: " + captureStdout(['gdb', '--version'], combineStderr=True,
                                              ignoreStderr=True, ignoreExitCode=True)[0]
    except (KeyboardInterrupt, Exception) as e:
        print('Error involving gdb is: ' + repr(e))

    # FIXME: Should have if os.path.exists(path to git) or something
    #print "git version: " + captureStdout(['git', 'version'], combineStderr=True, ignoreStderr=True, ignoreExitCode=True)[0]
    print "Python version: " + sys.version[:5]
    print "Number of cores visible to OS: " +  str(multiprocessing.cpu_count())
    print 'Free space (GB): ' + str('%.2f') % getFreeSpace('/', 3)

    hgrcLocation = os.path.join(path0, '.hg', 'hgrc')
    if os.path.isfile(hgrcLocation):
        print 'The hgrc of this repository is:'
        with open(hgrcLocation, 'rb') as f:
            hgrcContentList = f.readlines()
        for line in hgrcContentList:
            print line.rstrip()

    if os.name == 'posix':
        # resource library is only applicable to Linux or Mac platforms.
        import resource
        print "Corefile size (soft limit, hard limit) is: " + \
                repr(resource.getrlimit(resource.RLIMIT_CORE))

def readSkips(filename):
    skips = {}
    if filename:
        with open(filename) as f:
            for line in f:
                jobname = line.split(" ")[0]
                skips[jobname] = True
    return skips

def retestAll(options, buildDir):
    '''
    Retest all testcases in options.retestRoot, starting with the newest,
    without modifying that subtree (because it might be rsync'ed).
    '''

    assert options.testType == "dom"

    testcases = []
    retestSkips = readSkips(options.retestSkips)

    # Find testcases to retest
    for jobTypeDir in (os.path.join(options.retestRoot, x) for x in os.listdir(options.retestRoot) if x.startswith(options.testType + "-")):
        for j in os.listdir(jobTypeDir):
            if j.split("_")[0] in retestSkips:
                print "Skipping " + j + " for " + j.split("_")[0]
            if "-asan" in buildDir and "-asan" not in jobTypeDir:
                pass
            elif "_0_lines" in j:
                print "Skipping a 0-line testcase"
            elif "_reduced" in j:
                job = os.path.join(jobTypeDir, j)
                testcase_leafs = filter(lambda s: s.find("reduced") != -1, os.listdir(job))
                if len(testcase_leafs) == 1:
                    testcase = os.path.join(job, testcase_leafs[0])
                    mtime = os.stat(testcase).st_mtime
                    testcases.append({'testcase': testcase, 'mtime': mtime})

    # Sort so the newest testcases are first
    print "Retesting " + str(len(testcases)) + " testcases..."
    testcases.sort(key=lambda t: t['mtime'], reverse=True)

    i = 0
    levelAndLines, domInterestingOptions = domInteresting.rdfInit([buildDir])
    tempDir = tempfile.mkdtemp("retesting")

    # Retest all the things!
    for t in testcases:
        testcase = t['testcase']
        print testcase
        i += 1
        logPrefix = os.path.join(tempDir, str(i))
        extraPrefs = randomPrefs.grabExtraPrefs(testcase)
        testcaseURL = loopdomfuzz.asFileURL(testcase)
        level, lines = levelAndLines(testcaseURL, logPrefix=logPrefix, extraPrefs=extraPrefs, quiet=True)

        #if level > domInteresting.DOM_FINE:
        #    print "Reproduced: " + testcase
        #    with open(logPrefix + "-summary.txt") as f:
        #        for line in f:
        #            print line,

        # Would it be easier to do it this way?

        #with open(os.devnull, "w") as devnull:
        #    p = subprocess.Popen([loopdomfuzz.domInterestingpy, "mozilla-central/obj-firefox-asan-debug/", testcase], stdout=devnull, stderr=subprocess.STDOUT)
        #    if p.wait() > 0:
        #        print "Still reproduces: " + testcase

        # Ideally we'd use something like "lithium-command.txt" to get the right --valgrind args, etc...
        # (but we don't want the --min-level option)

        # Or this way?

        #lithArgs = ["--strategy=check-only", loopdomfuzz.domInterestingpy, buildDir, testcase]
        #
        #(lithResult, lithDetails) = lithOps.runLithium(lithArgs, logPrefix, options.targetTime)
        #if lithResult == lithOps.LITH_RETESTED_STILL_INTERESTING:
        #   print "Reproduced: " + testcase

    shutil.rmtree(tempDir)


def ensureBuild(options):
    if options.existingBuildDir:
        buildDir = options.existingBuildDir
        buildType = 'local-build'
        buildSrc = buildDir
        success = True
    elif options.buildOptions is not None:
        # Compile from source
        if options.testType == "js":
            # options.buildOptions = buildOptions.parseShellOptions(options.buildOptions)
            # buildType = computeShellName(options.buildOptions, "x") ??
            raise Exception("For now, use 'localjsfunfuzz' mode to compile and fuzz local shells")
        else:
            options.buildOptions = buildBrowser.parseOptions(options.buildOptions.split())
            buildDir = options.buildOptions.objDir
            buildType = platform.system() + "-" + os.path.basename(options.buildOptions.mozconfig)
            buildSrc = repr(hgCmds.getRepoHashAndId(options.buildOptions.repoDir))
            success = buildBrowser.tryCompiling(options.buildOptions)
    else:
        # Download from Tinderbox and call it 'build'
        # FIXME: Put 'build' somewhere nicer, like ~/fuzzbuilds/. Don't re-download a build that's up to date.
        buildDir = 'build'
        buildType = downloadBuild.defaultBuildType(options.repoName, None, True)
        buildSrc = downloadBuild.downloadLatestBuild(buildType, './', getJsShell=(options.testType == 'js'))
        success = True
    return buildDir, buildSrc, buildType, success


# Call |fun| in a bunch of separate processes, then wait for them all to finish.
# fun is called with someArgs, plus an additional argument with a numeric ID.
def forkJoin(numProcesses, fun, someArgs):
    ps = []
    # Fork a bunch of processes
    print "Forking %d children..." % numProcesses
    for i in xrange(numProcesses):
        p = multiprocessing.Process(target=fun, args=(someArgs + [i + 1]), name="Parallel process " + str(i + 1))
        p.start()
        ps.append(p)
    # Wait for them all to finish
    for p in ps:
        p.join()
    print "All %d children have finished!" % numProcesses

def fuzzUntilBug(options, buildDir, buildSrc, i):
    # not really "oldjobname", but this is how i get newjobname to be what i want below
    # avoid putting underscores in this part, because those get split on
    oldjobname = uuid.uuid1(clock_seq = i).hex
    job = options.tempDir + localSep + oldjobname + localSep
    os.mkdir(job)

    if options.testType == 'js':
        shell = os.path.join(buildDir, "dist", "js.exe" if isWin else "js")
        # Not using compareJIT: bug 751700, and it's not fully hooked up
        # FIXME: randomize branch selection, download an appropriate build and use an appropriate known directory
        # FIXME: use the right timeout
        mtrArgs = ["--random-flags", "10", "mozilla-central", shell]
        (lithResult, lithDetails) = loopjsfunfuzz.many_timed_runs(options.targetTime, job, mtrArgs)
    else:
        # FIXME: support Valgrind
        (lithResult, lithDetails) = loopdomfuzz.many_timed_runs(options.targetTime, job, [buildDir])

    if lithResult == lithOps.HAPPY:
        print "Happy happy! No bugs found!"
    else:
        writeTinyFile(job + "build-source.txt", buildSrc)
        uploadJob(options, lithResult, lithDetails, job, oldjobname)


def cmdDump(shell, cmdList, log):
    '''Dump commands to file.'''
    with open(log, 'ab') as f:
        f.write('Command to be run is:\n')
        f.write(shellify(cmdList) + '\n')
        f.write('========================================================\n')
        f.write('|  Fuzzing %s js shell builds\n' %
                     (shell.getRepoName() ))
        f.write('|  DATE: %s\n' % dateStr())
        f.write('========================================================\n\n')


def fuzzingPathName(options, repoHash, repoId):
    '''Returns the path of the directory where fuzzing is going to take place.'''
    appendStr = ''
    if isMac:
        appendStr += '.noindex'  # Prevents Spotlight in Mac from indexing these folders.
    userDesktopFolder = normExpUserPath(os.path.join('~', 'Desktop'))
    if not os.path.isdir(userDesktopFolder):
        try:
            os.mkdir(userDesktopFolder)
        except OSError:
            raise Exception('Unable to create ~/Desktop folder.')

    buildId = '-'.join([hgCmds.getRepoNameFromHgrc(options.buildOptions.repoDir), repoHash, repoId])
    return mkdtemp(appendStr + os.sep,
                   buildOptions.computeShellName(options.buildOptions, buildId) + "-",
                   # WinXP has spaces in the user directory.
                   'c:\\' if platform.uname()[2] == 'XP' else userDesktopFolder)


def localCompileFuzzJsShell(options):
    '''Compiles and readies a js shell for fuzzing.'''
    print dateStr()
    (repoHash, repoId, isOnDefault) = hgCmds.getRepoHashAndId(options.buildOptions.repoDir)

    shell = compileShell.CompiledShell(options.buildOptions, repoHash)
    compileShell.compileStandalone(shell)

    fullPath = fuzzingPathName(options, repoHash, repoId)

    # Copy only files over to fullPath, not the objdir.
    # From http://stackoverflow.com/a/296184
    compiledFiles = iglob(os.path.join(shell.getShellCacheDir(), "*"))
    for cFile in compiledFiles:
        if os.path.isfile(cFile):
            shutil.copy2(cFile, fullPath)

    if not options.noStart:
        analysisPath = os.path.abspath(os.path.join(path0, 'experimental', 'js', 'analysis.py'))
        if os.path.exists(analysisPath):
            shutil.copy2(analysisPath, fullPath)

    # Construct a command-line for running loopjsfunfuzz.py
    cmdList = [sys.executable, '-u']
    cmdList.append(normExpUserPath(os.path.join(path0, 'js', 'loopjsfunfuzz.py')))
    cmdList.append('--repo=' + shell.getRepoDir())
    cmdList += ["--build", options.buildOptions.buildOptionsStr]
    if options.buildOptions.runWithVg:
        cmdList.append('--valgrind')
    if options.buildOptions.enableMoreDeterministic:
        cmdList.append('--comparejit')
    if not options.disableRndFlags:
        cmdList.append('--random-flags')
    cmdList.append(str(options.timeout))
    cmdList.append(lithOps.knownBugsDir(shell.getRepoName()))
    cmdList.append(normExpUserPath(os.path.join(fullPath, shell.getShellNameWithExt())))

    # Write log files describing commands to be run for fuzzing using jsfunfuzz.
    runLog = normExpUserPath(os.path.join(fullPath, 'log-localjsfunfuzz.txt'))
    cmdDump(shell, cmdList, runLog)

    # Display compilation parameter and fuzz command logs prior to fuzzing.
    compileLog = normExpUserPath(os.path.join(fullPath, 'compilation-parameters.txt'))
    if os.path.isfile(compileLog):
        with open(compileLog, 'rb') as f:
            for line in f:
                if 'Full environment is' not in line:
                    print line,

    with open(runLog, 'rb') as f:
        for line in f:
            print line,

    # FIXME: Randomize logic should be developed later, possibly together with target time in
    # loopjsfunfuzz.py. Randomize Valgrind runs too.

    return shell, fullPath, cmdList


def machineTimeoutDefaults(options):
    '''Sets different defaults depending on the machine type or debugger used.'''
    if options.buildOptions.runWithVg:
        return 300
    elif isARMv7l:
        return 180
    else:
        return 10  # If no timeout preference is specified, use 10 seconds.


if __name__ == "__main__":
    main()
