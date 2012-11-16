#!/usr/bin/env python

# bot.py runs domfuzz, jsfunfuzz, or Lithium for a limited amount of time.
# It stores jobs using ssh, using directory 'mv' for synchronization.

from __future__ import with_statement

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

from optparse import OptionParser

path0 = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.abspath(os.path.join(path0, 'util'))
sys.path.insert(0, path1)
import downloadBuild
import lithOps
from countCpus import cpuCount
from subprocesses import getFreeSpace, isWin
path2 = os.path.abspath(os.path.join(path0, 'dom', 'automation'))
sys.path.append(path2)
import loopdomfuzz
import domInteresting
path3 = os.path.abspath(os.path.join(path0, 'js'))
sys.path.append(path3)
import loopjsfunfuzz

localSep = "/" # even on windows, i have to use / (avoid using os.path.join) in bot.py! is it because i'm using bash?

# Possible ssh options:
#   -oStrictHostKeyChecking=no
#   -oUserKnownHostsFile=/dev/null

def assertTrailingSlash(d):
    assert d[-1] in ("/", "\\")

# Copies a directory (the directory itself, not just its contents)
# whose full name is |srcDir|, creating a subdirectory of |destParent| with the same short name.
def copyFiles(remoteHost, srcDir, destParent):
    assertTrailingSlash(srcDir)
    assertTrailingSlash(destParent)
    if remoteHost == None:
        subprocess.check_call(["cp", "-R", srcDir[:-1], destParent])
    else:
        with open(os.devnull, "w") as devnull:
            subprocess.check_call(["scp", "-p", "-r", srcDir, destParent], stdout=devnull)
    srcDirLeaf = srcDir.split("/" if "/" in srcDir else "\\")[-2]
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
                os.rename(jobWithPostfix, job) # so lithium gets the same filename as before
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

    if lithResult == lithOps.LITH_FINISHED:
        # lithDetails should be a string like "11 lines"
        statePostfix = "_" + lithDetails.replace(" ", "_") + statePostfix
        summaryFile = job + filter(lambda s: s.find("summary") != -1, os.listdir(job))[0]
        with open(summaryFile) as f:
            summary = f.read()

    #print "oldjobname: " + oldjobname
    newjobname = oldjobname + statePostfix
    print "Uploading as: " + newjobname
    newjobnameTmp = newjobname + ".uploading"
    os.rename(job, newjobnameTmp)
    copyFiles(options.remote_host, newjobnameTmp + localSep, options.remote_prefix + options.relevantJobsDir + options.remoteSep)
    runCommand(options.remote_host, "mv " + options.relevantJobsDir + newjobnameTmp + " " + options.relevantJobsDir + newjobname)
    shutil.rmtree(newjobnameTmp)

    if options.remote_host and (lithResult == lithOps.LITH_FINISHED or (options.testType == 'js')):
        recipients = []
        subject = "Reduced " + options.testType + " fuzz testcase"
        dirRef = "https://pvtbuilds.mozilla.org/fuzzing/" + options.relevantJobsDirName + "/" + newjobname + "/"
        # FIXME: The if condition is present here because for no_longer_reproducible
        # testcases, the -summary file is apparently absent, so this needs reconfirmation.
        body = dirRef + "\n\n" + summary[0:50000] if summary else dirRef
        if options.testType == 'js':
            # Send jsfunfuzz emails to gkw
            recipients.append("gkwong")
        else:
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
        toAddr = 'gary@rumblingedge.com'

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
        compileType = 'dbg',
        targetTime = 15*60,       # 15 minutes
        tempDir = "fuzztemp",
        testType = "auto",
        existingBuildDir = None,
        retestRoot = None,
    )

    parser.add_option('-t', '--test-type', dest='testType', choices=['auto', 'js', 'dom'],
        help='Test type: "js", "dom", or "auto" (which is usually random).')

    parser.add_option("--build", dest="existingBuildDir",
        help="Use an existing build directory.")
    parser.add_option("--retest", dest="retestRoot",
        help="Instead of fuzzing or reducing, take reduced testcases and retest them. Pass a directory such as ~/fuzzingjobs/ or an rsync'ed ~/fuzz-results/.")

    parser.add_option('--repotype', dest='repoName',
        help='Sets the repository to be fuzzed. Defaults to "%default".')
    parser.add_option('--compiletype', dest='compileType',
        help='Sets the compile type to be fuzzed. Defaults to "%default".')
    parser.add_option('-a', '--architecture',
                      dest='arch',
                      type='choice',
                      choices=['32', '64'],
                      help='Test architecture. Only accepts "32" or "64"')

    parser.add_option("--remote-host", dest="remote_host",
        help="Use remote host to store fuzzing jobs; format: user@host. If omitted, a local directory will be used instead.")
    parser.add_option("--basedir", dest="baseDir",
        help="Base directory on remote machine to store fuzzing data")
    parser.add_option("--target-time", dest="targetTime", type='int',
        help="Nominal amount of time to run, in seconds")
    parser.add_option("--tempdir", dest="tempDir",
        help="Temporary directory for fuzzing. Will be blown away and re-created. Should be a name that can be reused.")

    options, args = parser.parse_args()

    if options.remote_host and "/msys/" in options.baseDir:
        # Undo msys-bash damage that turns --basedir "/foo" into "C:/mozilla-build/msys/foo"
        # when we are trying to refer to a directory on another computer.
        options.baseDir = "/" + options.baseDir.split("/msys/")[1]

    # options.remote_prefix is used as a prefix for options.baseDir when using scp
    options.remote_prefix = (options.remote_host + ":") if options.remote_host else ""

    options.remoteSep = "/" if options.remote_host else localSep

    if options.testType == 'auto':
        if options.retestRoot or options.existingBuildDir:
            options.testType = 'dom'
        else:
            options.testType = random.choice(['js', 'dom'])
            print "Randomly fuzzing: " + options.testType

    options.buildType = 'local-build' if options.existingBuildDir else downloadBuild.defaultBuildType(options)
    options.relevantJobsDirName = options.testType + "-" + options.buildType
    options.relevantJobsDir = options.baseDir + options.relevantJobsDirName + options.remoteSep

    assert options.baseDir.endswith(options.remoteSep)
    return options


def main():
    options = parseOpts()

    runCommand(options.remote_host, "mkdir -p " + options.baseDir) # don't want this created recursively, because "mkdir -p" is weird with modes
    runCommand(options.remote_host, "chmod og+rx " + options.baseDir)
    runCommand(options.remote_host, "mkdir -p " + options.relevantJobsDir)
    runCommand(options.remote_host, "chmod og+rx " + options.relevantJobsDir)

    if options.remote_host:
        # Log information about the machine.
        print "Platform details: " + " ".join(platform.uname())
        print "Python version: " + sys.version[:5]
        print "Number of cores visible to OS: " +  str(cpuCount())
        print 'Free space (GB): ' + str('%.2f') % getFreeSpace('/', 3)
        if os.name == 'posix':
            # resource library is only applicable to Linux or Mac platforms.
            import resource
            print "Corefile size (soft limit, hard limit) is: " + \
                    repr(resource.getrlimit(resource.RLIMIT_CORE))

    # FIXME: Put 'build' somewhere nicer, like ~/fuzzbuilds/. Don't re-download a build that's up to date.
    buildDir = options.existingBuildDir or 'build'
    #if options.remote_host:
    #  sendEmail("justInWhileLoop", "Platform details , " + platform.node() + " , Python " + sys.version[:5] + " , " +  " ".join(platform.uname()), "gkwong")

    if os.path.exists(options.tempDir):
        shutil.rmtree(options.tempDir)
    os.mkdir(options.tempDir)

    if options.retestRoot:
        print "Retesting time!"
        ensureBuild(options, buildDir, None)
        retestAll(options, buildDir)
    else:
        (job, oldjobname, takenNameOnServer) = grabJob(options, "_needsreduction")
        if job:
            print "Reduction time!"
            ensureBuild(options, buildDir, readTinyFile(job + "preferred-build.txt"))
            lithArgs = readTinyFile(job + "lithium-command.txt").strip().split(" ")
            logPrefix = job + "reduce" + timestamp()
            (lithResult, lithDetails) = lithOps.runLithium(lithArgs, logPrefix, options.targetTime)
            uploadJob(options, lithResult, lithDetails, job, oldjobname)
            runCommand(options.remote_host, "rm -rf " + takenNameOnServer)

        else:
            print "Fuzz time!"
            #if options.remote_host:
            #  sendEmail("justFuzzTime", "Platform details , " + platform.node() + " , Python " + sys.version[:5] + " , " +  " ".join(platform.uname()), "gkwong")
            buildSrc = ensureBuild(options, buildDir, None)
            multiFuzzUntilBug(options, buildDir, buildSrc)

    # Remove build directory
    if not (options.retestRoot or options.existingBuildDir) and os.path.exists(buildDir):
        shutil.rmtree(buildDir)

    # Remove the main temp dir, which should be empty at this point
    os.rmdir(options.tempDir)


def retestAll(options, buildDir):
    '''
    Retest all testcases in options.retestRoot, starting with the newest,
    without modifying that subtree (because it might be rsync'ed).
    '''

    assert options.testType == "dom"

    testcases = []

    # Find testcases to retest
    for jobTypeDir in (os.path.join(options.retestRoot, x) for x in os.listdir(options.retestRoot) if x.startswith(options.testType + "-")):
        for job in (os.path.join(jobTypeDir, x) for x in os.listdir(jobTypeDir) if "_reduced" in x and not skipJobNamed(x)):
            testcase = os.path.join(job, filter(lambda s: s.find("reduced") != -1, os.listdir(job))[0])
            testcases.append({'testcase': testcase, 'mtime': os.stat(testcase).st_mtime})

    # Sort so the newest testcases are first
    print "Reteseting " + str(len(testcases)) + " testcases..."
    testcases.sort(key=lambda t: t['mtime'], reverse=True)

    i = 0
    levelAndLines, deleteProfile, domInterestingOptions = domInteresting.rdfInit([buildDir])
    tempDir = tempfile.mkdtemp("retesting")

    # Retest all the things!
    for t in testcases:
        testcase = t['testcase']
        print testcase
        i += 1
        logPrefix = os.path.join(tempDir, str(i))
        extraPrefs = domInteresting.grabExtraPrefs(testcase)
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

    deleteProfile()
    shutil.rmtree(tempDir)

def skipJobNamed(j):
    # These testcases cause random crashes, or rely on internal blacklists.

    return (
        "b826f91e0c8511e280083c0754725936" in j or # Bug 797065
        "e9a41a6b16c311e280033c0754725936" in j or # Bug 801914, in its manifestation as a "hang"
        "623986e119f511e280063c0754724cee" in j or # A fixed bug in the fuzzer
        "27fed8d11a9111e280053c0754725891" in j or # Another fixed bug in the fuzzer
        "d18c1bc21ab611e28007406c8f39f8b7" in j or # Ditto
        "91b3a56810ac11e280053c0754724fc3" in j or # makeCommand threw an exception
        "e441bd47108511e280083c07547257fa" in j or # makeCommand threw an exception
        "951f93f3103f11e280023c07547257ed" in j or # makeCommand threw an exception
        "c4f5c9d4103011e280083c07547237b0" in j or # makeCommand threw an exception
        "63f907230ffc11e280043c075472548a" in j or # makeCommand threw an exception
        "2d406fc70ff811e280083c07547237b0" in j or # makeCommand threw an exception
        "5f30be210fee11e280063c07547237b0" in j or # makeCommand threw an exception
        "913531bd0fe911e280063c075472877d" in j or # makeCommand threw an exception
        "274db34f0fe611e280063c07547237b0" in j or # makeCommand threw an exception
        "274d72bd0fe611e280043c07547237b0" in j or # makeCommand threw an exception
        "ccd24e300fe411e280043c07547257fa" in j or # makeCommand threw an exception
        "ccd2ccb50fe411e280073c07547257fa" in j or # makeCommand threw an exception
        "5d9762170fe311e280043c07547286ad" in j or # makeCommand threw an exception
        "e03fa4f30fdf11e280023c07547237b0" in j or # makeCommand threw an exception
        "e03fd1730fdf11e280033c07547237b0" in j or # makeCommand threw an exception
        "9918e5351c1911e280023c075472528a" in j or # bug 804083
        "2dfb799c2eb511e280033c075472500f" in j or # bug 812641
        "1342637058" in j or # fuzzer bug, fixed in fuzzer rev 784e6fe8f808
        "1343538581" in j or # probably a nasty variant of bug 728632
        "1344266896" in j or # bug 798829, bug 802982, bug 798323
        "1345481534" in j or # bug 798829, bug 802982, bug 798323
        "1339201819" in j or # Bug 763126
        "1338835174" in j or # Bug 763126
        "1339379020" in j or # Bug 763560
        "1339573949" in j or # Bug 767279
        "1339589159" in j or # Bug 765109
        "1339599262" in j or # lol mv
        "1341082845" in j or # hang that should have been ignored
        "1340073462" in j or # Bug 767233
        "1338621034" in j or # Bug 761422
        "1340814313" in j or # Bug 769015
        "1340815388" in j or # Bug 769015
        "1340808789" in j or # Bug 769015
        "1340809470" in j or # Bug 769015
        "1340801456" in j or # Bug 769015
        "1340802472" in j or # Bug 769021
        "1339516108" in j or # Nasty OOM behavior
        "1338878206" in j or # Nasty OOM behavior
        "1338698829" in j or # Nasty OOM behavior
        "1339959377" in j or # Bug 766075 (also copied to whenfixed)
        "1339728406" in j or # Bug 766430 (nondeterministic crash)
        "1341133958" in j or # grr. bug 735081 or bug 735082.
        "1341815616" in j or # grr. bug 735081 or bug 735082.
        "1344134705" in j or # Bug 780790 (plus mysterious bad local stack walking)
        "1340246538" in j)   # Bug 767273


def ensureBuild(options, buildDir, preferredBuild):
    '''Returns a string indicating the source of the build we got.'''
    if options.existingBuildDir:
        assert os.path.exists(buildDir)
        return buildDir
    if preferredBuild:
        gotPreferred = downloadBuild.downloadBuild(preferredBuild, './', jsShell=(options.testType == 'js'))
        if gotPreferred:
            return gotPreferred # is this the right type?
        else:
            print "Preferred build for this reduction was missing, grabbing latest build"
    return downloadBuild.downloadLatestBuild(options.buildType, './', getJsShell=(options.testType == 'js'))


def multiFuzzUntilBug(options, buildDir, buildSrc):
    if sys.version_info < (2, 6):
        # The multiprocessing module was added in Python 2.6
        fuzzUntilBug(options, buildDir, buildSrc, 0)
    else:
        from multiprocessing import Process
        ps = []
        # Fork a bunch of processes
        numProcesses = cpuCount()
        if "-asan" in buildDir:
            # This should really be based on the amount of RAM available, but I don't know how to compute that in Python.
            numProcesses = max(numProcesses // 2, 1)
        print "Forking %d children..." % numProcesses
        for i in xrange(numProcesses):
            p = Process(target=fuzzUntilBug, args=(options, buildDir, buildSrc, i + 1), name="Fuzzing process " + str(i + 1))
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
        mtrArgs = ["--random-flags", "10", os.path.join(path0, "known", "mozilla-central"), shell]
        (lithResult, lithDetails) = loopjsfunfuzz.many_timed_runs(options.targetTime, job, mtrArgs)
    else:
        # FIXME: support Valgrind
        (lithResult, lithDetails) = loopdomfuzz.many_timed_runs(options.targetTime, job, [buildDir])

    if lithResult == lithOps.HAPPY:
        print "Happy happy! No bugs found!"
    else:
        writeTinyFile(job + "preferred-build.txt", buildSrc)
        uploadJob(options, lithResult, lithDetails, job, oldjobname)

if __name__ == "__main__":
    main()
