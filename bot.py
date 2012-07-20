#!/usr/bin/env python

# bot.py runs domfuzz or lithium as needed, for a limited amount of time, storing jobs using ssh.

from __future__ import with_statement

import os
import platform
import random
import shutil
import socket
import subprocess
import sys
import time

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
path3 = os.path.abspath(os.path.join(path0, 'js'))
sys.path.append(path3)
import loopjsfunfuzz

devnull = open(os.devnull, "w")

targetTime = 15*60 # for build machines, use 15 minutes (15*60)
localSep = "/" # even on windows, i have to use / (avoid using os.path.join) in bot.py! is it because i'm using bash?

# Uses directory name 'mv' for synchronization.

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


def grabJob(remoteHost, remotePrefix, remoteSep, relevantJobsDir, desiredJobType):
    while True:
        jobs = filter( (lambda s: s.endswith(desiredJobType)), runCommand(remoteHost, "ls -1 " + relevantJobsDir).split("\n") )
        if len(jobs) > 0:
            oldNameOnServer = jobs[0]
            shortHost = socket.gethostname().split(".")[0]  # more portable than os.uname()[1]
            takenNameOnServer = relevantJobsDir + oldNameOnServer.split("_")[0] + "_taken_by_" + shortHost + "_at_" + timestamp()
            if tryCommand(remoteHost, "mv " + relevantJobsDir + oldNameOnServer + " " + takenNameOnServer + ""):
                print "Grabbed " + oldNameOnServer + " by renaming it to " + takenNameOnServer
                job = copyFiles(remoteHost, remotePrefix + takenNameOnServer + remoteSep, "." + localSep)
                oldjobname = oldNameOnServer[:len(oldNameOnServer) - len(desiredJobType)] # cut off the part that will be redundant
                os.rename(job, "wtmp1") # so lithium gets the same filename as before
                print repr(("wtmp1/", oldjobname, takenNameOnServer))
                return ("wtmp1/", oldjobname, takenNameOnServer) # where it is for running lithium; what it should be named; and where to delete it from the server
            else:
                print "Raced to grab " + relevantJobsDir + oldNameOnServer + ", trying again"
                continue
        else:
            return (None, None, None)


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
        basedir = os.path.expanduser("~") + localSep + "fuzzingjobs" + localSep,
        repoName = 'mozilla-central',
        compileType = 'dbg',
        runJsfunfuzz = False,
    )
    parser.add_option("--reuse-build", dest="reuse_build", default=False, action="store_true",
        help="Use the existing 'build' directory.")
    parser.add_option("--remote-host", dest="remote_host",
        help="Use remote host to store fuzzing jobs; format: user@host. If omitted, a local directory will be used instead.")
    parser.add_option("--basedir", dest="basedir",
        help="Base directory on remote machine to store fuzzing data")
    parser.add_option("--retest-all", dest="retestAll", action="store_true",
        help="Instead of fuzzing or reducing, take reduced testcases and retest them.")
    parser.add_option('--repotype', dest='repoName',
        help='Sets the repository to be fuzzed. Defaults to "%default".')
    parser.add_option('--compiletype', dest='compileType',
        help='Sets the compile type to be fuzzed. Defaults to "%default".')
    parser.add_option('-a', '--architecture',
                      dest='arch',
                      type='choice',
                      choices=['32', '64'],
                      help='Test architecture. Only accepts "32" or "64"')
    parser.add_option('-j', '--jsfunfuzz', dest='runJsfunfuzz', action='store_true',
        help='Fuzz jsfunfuzz instead of DOM fuzzer. Defaults to "%default".')
    options, args = parser.parse_args()

    if options.remote_host and "/msys/" in options.basedir:
        # Undo msys-bash damage that turns --basedir "/foo" into "C:/mozilla-build/msys/foo"
        # when we are trying to refer to a directory on another computer.
        options.basedir = "/" + options.basedir.split("/msys/")[1]

    if not options.runJsfunfuzz and not options.retestAll and random.choice([True, False]):
        print "Randomly fuzzing JS!"
        options.runJsfunfuzz = True

    if options.retestAll:
        options.reuse_build = True

    return options

def main():
    options = parseOpts()

    buildType = downloadBuild.defaultBuildType(options)
    remoteHost = options.remote_host
    remoteBase = options.basedir
    # remotePrefix is used as a prefix for remoteBase when using scp
    remotePrefix = (remoteHost + ":") if remoteHost else ""
    remoteSep = "/" if remoteHost else localSep
    assert remoteBase.endswith(remoteSep)
    testType = "js" if options.runJsfunfuzz else "dom"
    relevantJobsDirName = testType + "-" + (buildType if not options.retestAll else "all")
    relevantJobsDir = remoteBase + relevantJobsDirName + remoteSep
    runCommand(remoteHost, "mkdir -p " + remoteBase) # don't want this created recursively, because "mkdir -p" is weird with modes
    runCommand(remoteHost, "chmod og+rx " + remoteBase)
    runCommand(remoteHost, "mkdir -p " + relevantJobsDir)
    runCommand(remoteHost, "chmod og+rx " + relevantJobsDir)

    if remoteHost:
        # Log information about the machine.
        print "Platform details: " + " ".join(platform.uname())
        print "Python version: " + sys.version[:5]
        print "Number of cores visible to OS: " +  str(cpuCount())
        print 'Free space (MB): ' + str(getFreeSpace('/', 2))
        if os.name == 'posix':
            # resource library is only applicable to Linux or Mac platforms.
            import resource
            print "Corefile size (soft limit, hard limit) is: " + \
                    repr(resource.getrlimit(resource.RLIMIT_CORE))

    shouldLoop = True
    while shouldLoop:
        job = None
        oldjobname = None
        takenNameOnServer = None
        lithResult = None
        # FIXME: Put 'build' somewhere nicer, like ~/fuzzbuilds/. Don't re-download a build that's up to date.
        buildDir = 'build'
        #if remoteHost:
        #  sendEmail("justInWhileLoop", "Platform details , " + platform.node() + " , Python " + sys.version[:5] + " , " +  " ".join(platform.uname()), "gkwong")

        # FIXME: Put 'wtmp1' somewhere nicer, like ~/fuzztemp/. Make it possible to parallelize.
        if os.path.exists("wtmp1"):
            print "wtmp1 shouldn't exist now. killing it."
            shutil.rmtree("wtmp1")

        if options.retestAll:
            print "Retesting time!"
            (job, oldjobname, takenNameOnServer) = grabJob(remoteHost, remotePrefix, remoteSep, relevantJobsDir, "_reduced")
            if job:
                if ("1339201819" in oldjobname or # Bug 763126
                    "1338835174" in oldjobname or # Bug 763126
                    "1339379020" in oldjobname or # Bug 763560
                    "1339573949" in oldjobname or # Bug 767279
                    "1339589159" in oldjobname or # Bug 765109
                    "1339599262" in oldjobname or # lol mv
                    "1341082845" in oldjobname or # hang that should have been ignored
                    "1340073462" in oldjobname or # Bug 767233
                    "1338621034" in oldjobname or # Bug 761422
                    "1340814313" in oldjobname or # Bug 769015
                    "1340815388" in oldjobname or # Bug 769015
                    "1340808789" in oldjobname or # Bug 769015
                    "1340809470" in oldjobname or # Bug 769015
                    "1340801456" in oldjobname or # Bug 769015
                    "1340802472" in oldjobname or # Bug 769021
                    "1339516108" in oldjobname or # Nasty OOM behavior
                    "1338878206" in oldjobname or # Nasty OOM behavior
                    "1338698829" in oldjobname or # Nasty OOM behavior
                    "1339959377" in oldjobname or # Bug 766075 (also copied to whenfixed)
                    "1339728406" in oldjobname or # Bug 766430 (nondeterministic crash)
                    "1341133958" in oldjobname or # grr. bug 735081 or bug 735082.
                    "1341815616" in oldjobname or # grr. bug 735081 or bug 735082.
                    "1340246538" in oldjobname):  # Bug 767273
                    # These testcases cause random crashes, or rely on internal blacklists.
                    print "Skipping retesting of " + job
                    (lithResult, lithDetails) = (lithOps.LITH_NO_REPRO, "Skipping retest")
                else:
                    reducedFn = job + filter(lambda s: s.find("reduced") != -1, os.listdir(job))[0]
                    print "reduced filename: " + reducedFn
                    lithArgs = ["--strategy=check-only", loopdomfuzz.domInterestingpy, "build", reducedFn]
                    logPrefix = job + "retest"
                    (lithResult, lithDetails) = lithOps.runLithium(lithArgs, logPrefix, targetTime)
            else:
                shouldLoop = False
        else:
            shouldLoop = False
            (job, oldjobname, takenNameOnServer) = grabJob(remoteHost, remotePrefix, remoteSep, relevantJobsDir, "_needsreduction")
            if job:
                print "Reduction time!"
                if not options.reuse_build:
                    preferredBuild = readTinyFile(job + "preferred-build.txt")
                    if not downloadBuild.downloadBuild(preferredBuild, './', jsShell=options.runJsfunfuzz):
                        print "Preferred build for this reduction was missing, grabbing latest build"
                        downloadBuild.downloadLatestBuild(buildType, './', getJsShell=options.runJsfunfuzz)
                lithArgs = readTinyFile(job + "lithium-command.txt").strip().split(" ")
                logPrefix = job + "reduce" + timestamp()
                (lithResult, lithDetails) = lithOps.runLithium(lithArgs, logPrefix, targetTime)

            else:
                print "Fuzz time!"
                #if remoteHost:
                #  sendEmail("justFuzzTime", "Platform details , " + platform.node() + " , Python " + sys.version[:5] + " , " +  " ".join(platform.uname()), "gkwong")
                if options.reuse_build and os.path.exists(buildDir):
                    buildSrc = buildDir
                else:
                    if os.path.exists(buildDir):
                        print "Deleting old build..."
                        shutil.rmtree(buildDir)
                    os.mkdir(buildDir)
                    buildSrc = downloadBuild.downloadLatestBuild(buildType, './', getJsShell=options.runJsfunfuzz)
                if options.runJsfunfuzz:
                    shell = os.path.join(buildDir, "dist", "js.exe" if isWin else "js")
                    # Not using compareJIT: bug 751700, and it's not fully hooked up
                    # FIXME: randomize branch selection, download an appropriate build and use an appropriate known directory
                    mtrArgs = ["--random-flags", "10", os.path.join(path0, "known", "mozilla-central"), shell]
                    (lithResult, lithDetails) = loopjsfunfuzz.many_timed_runs(targetTime, mtrArgs)
                else:
                    (lithResult, lithDetails) = loopdomfuzz.many_timed_runs(targetTime, [buildDir]) # xxx support --valgrind
                if lithResult == lithOps.HAPPY:
                    print "Happy happy! No bugs found!"
                else:
                    job = "wtmp1" + localSep
                    writeTinyFile(job + "preferred-build.txt", buildSrc)
                    # not really "oldjobname", but this is how i get newjobname to be what i want below
                    # avoid putting underscores in this part, because those get split on
                    oldjobname = "foundat" + timestamp() #+ "-" + str(random.randint(0, 1000000))
                    os.rename("wtmp1", oldjobname)
                    job = oldjobname + localSep

        if lithResult != lithOps.HAPPY:
            statePostfix = ({
              lithOps.NO_REPRO_AT_ALL: "_no_repro",
              lithOps.NO_REPRO_EXCEPT_BY_URL: "_repro_url_only",
              lithOps.LITH_NO_REPRO: "_no_longer_reproducible",
              lithOps.LITH_FINISHED: "_reduced",
              lithOps.LITH_RETESTED_STILL_INTERESTING: "_retested",
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
            copyFiles(remoteHost, newjobnameTmp + localSep, remotePrefix + relevantJobsDir + remoteSep)
            runCommand(remoteHost, "mv " + relevantJobsDir + newjobnameTmp + " " + relevantJobsDir + newjobname)
            shutil.rmtree(newjobnameTmp)

            # Remove the old *_taken directory from the server
            if takenNameOnServer:
                runCommand(remoteHost, "rm -rf " + takenNameOnServer)

            # Remove build directory
            if not options.reuse_build and os.path.exists(buildDir):
                shutil.rmtree(buildDir)

            if remoteHost and (lithResult == lithOps.LITH_FINISHED or options.runJsfunfuzz):
                recipients = []
                subject = "Reduced " + testType + " fuzz testcase"
                dirRef = "https://pvtbuilds.mozilla.org/fuzzing/" + relevantJobsDirName + "/" + newjobname + "/"
                body = dirRef + "\n\n" + summary[0:50000]
                if options.runJsfunfuzz:
                    # Send jsfunfuzz emails to gkw
                    recipients.append("gkwong")
                else:
                    # Send domfuzz emails to Jesse
                    recipients.append("jruderman")
                print "Sending email..."
                for recipient in recipients:
                    sendEmail(subject, body, recipient)
                print "Email sent!"

if __name__ == "__main__":
    main()
