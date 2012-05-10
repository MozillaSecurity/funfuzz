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
sys.path.append(path1)
import downloadBuild
path2 = os.path.abspath(os.path.join(path0, 'dom', 'automation'))
sys.path.append(path2)
import loopdomfuzz

devnull = open(os.devnull, "w")

targetTime = 15*60 # for build machines, use 15 minutes (15*60)
localSep = "/" # even on windows, i have to use / (avoid using os.path.join) in bot.py! is it because i'm using bash?

# Uses directory name 'mv' for synchronization.

# Possible ssh options:
#   -oStrictHostKeyChecking=no
#   -oUserKnownHostsFile=/dev/null

# global which is set in __main__, used to operate over ssh
remoteLoginAndMachine = None

def assertTrailingSlash(d):
    assert d[-1] in ("/", "\\")

# Copies a directory (the directory itself, not just its contents)
# whose full name is |srcDir|, creating a subdirectory of |destParent| with the same short name.
def copyFiles(srcDir, destParent):
    assertTrailingSlash(srcDir)
    assertTrailingSlash(destParent)
    if remoteLoginAndMachine == None:
        subprocess.check_call(["cp", "-R", srcDir[:-1], destParent])
    else:
        subprocess.check_call(["scp", "-p", "-r", srcDir, destParent], stdout=devnull)
    srcDirLeaf = srcDir.split("/" if "/" in srcDir else "\\")[-2]
    return destParent + srcDirLeaf + destParent[-1]

def tryCommand(cmd):
    if remoteLoginAndMachine == None:
        p = subprocess.Popen(["bash", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        p = subprocess.Popen(["ssh", remoteLoginAndMachine, cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.communicate()
    return p.returncode == 0

def runCommand(cmd):
    if remoteLoginAndMachine == None:
        p = subprocess.Popen(["bash", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        p = subprocess.Popen(["ssh", remoteLoginAndMachine, cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = p.communicate()
    if err != "":
        raise Exception("bot.py runCommand: stderr: " + repr(err))
    if p.returncode != 0:
        raise Exception("bot.py runCommand: unhappy exit code " + str(p.returncode) + " from " + cmd)
    return out


def grabJob(relevantJobsDir, desiredJobType):
    while True:
        jobs = filter( (lambda s: s.endswith(desiredJobType)), runCommand("ls -1 " + relevantJobsDir).split("\n") )
        if len(jobs) > 0:
            oldNameOnServer = jobs[0]
            shortHost = socket.gethostname().split(".")[0]  # more portable than os.uname()[1]
            takenNameOnServer = relevantJobsDir + oldNameOnServer.split("_")[0] + "_taken_by_" + shortHost + "_at_" + timestamp()
            if tryCommand("mv " + relevantJobsDir + oldNameOnServer + " " + takenNameOnServer + ""):
                print "Grabbed " + oldNameOnServer + " by renaming it to " + takenNameOnServer
                job = copyFiles(remotePrefix + takenNameOnServer + remoteSep, "." + localSep)
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
        basedir = os.path.expanduser("~") + localSep + "domfuzzjobs" + localSep,
        repoName = 'mozilla-central',
        compileType = 'dbg',
        runJsfunfuzz = False,
    )
    parser.add_option("--reuse-build", dest="reuse_build", default=False, action="store_true",
        help="Use the existing 'build' directory.")
    parser.add_option("--remote-host", dest="remote_host",
        help="Use remote host to store fuzzing data; format: user@host")
    parser.add_option("--basedir", dest="basedir",
        help="Base directory on remote machine to store fuzzing data")
    parser.add_option("--retest-all", dest="retestAll", action="store_true",
        help="Instead of fuzzing or reducing, take reduced testcases and retest them.")
    parser.add_option('--repotype', dest='repoName',
        help='Sets the repository to be fuzzed. Defaults to "%default".')
    parser.add_option('--compiletype', dest='compileType',
        help='Sets the compile type to be fuzzed. Defaults to "%default".')
    parser.add_option('-j', '--jsfunfuzz', dest='runJsfunfuzz', action='store_true',
        help='Fuzz jsfunfuzz instead of DOM fuzzer. Defaults to "%default".')
    options, args = parser.parse_args()

    if options.retestAll:
        options.reuse_build = True

    return options

def main():
    options = parseOpts()

    buildType = downloadBuild.defaultBuildType(options)
    remoteLoginAndMachine = options.remote_host
    remoteBase = options.basedir
    # remotePrefix is used as a prefix for remoteBase when using scp
    remotePrefix = (remoteLoginAndMachine + ":") if remoteLoginAndMachine else ""
    remoteSep = "/" if remoteLoginAndMachine else localSep
    relevantJobsDir = remoteBase + buildType + remoteSep
    runCommand("mkdir -p " + remoteBase) # don't want this created recursively, because "mkdir -p" is weird with modes
    runCommand("chmod og+r " + remoteBase)
    runCommand("mkdir -p " + relevantJobsDir)
    runCommand("chmod og+r " + relevantJobsDir)

    shouldLoop = True
    while shouldLoop:
        job = None
        oldjobname = None
        takenNameOnServer = None
        lithlog = None
        buildDir = relevantJobsDir + 'build'
        #if remoteLoginAndMachine:
        #  sendEmail("justInWhileLoop", "Platform details , " + platform.node() + " , Python " + sys.version[:5] + " , " +  " ".join(platform.uname()), "gkwong")

        if os.path.exists(relevantJobsDir + "wtmp1"):
            print "wtmp1 shouldn't exist now. killing it."
            shutil.rmtree(relevantJobsDir + "wtmp1")

        if options.retestAll:
            print "Retesting time!"
            (job, oldjobname, takenNameOnServer) = grabJob(relevantJobsDir, "_reduced")
            if job:
                reducedFn = job + filter(lambda s: s.find("reduced") != -1, os.listdir(job))[0]
                print "reduced filename: " + reducedFn
                lithArgs = ["--strategy=check-only", loopdomfuzz.domInterestingpy, "build", reducedFn]
                (lithlog, ldfResult, lithDetails) = loopdomfuzz.runLithium(lithArgs, job, targetTime, "T")
            else:
                shouldLoop = False
        else:
            shouldLoop = False
            (job, oldjobname, takenNameOnServer) = grabJob(relevantJobsDir, "_needsreduction")
            if job:
                print "Reduction time!"
                if not options.reuse_build:
                    preferredBuild = readTinyFile(job + "preferred-build.txt")
                    if not downloadBuild.downloadBuild(preferredBuild, relevantJobsDir, jsShell=options.runJsfunfuzz):
                        print "Preferred build for this reduction was missing, grabbing latest build"
                        downloadBuild.downloadLatestBuild(buildType, relevantJobsDir, getJsShell=options.runJsfunfuzz)
                lithArgs = readTinyFile(job + "lithium-command.txt").strip().split(" ")
                (lithlog, ldfResult, lithDetails) = loopdomfuzz.runLithium(lithArgs, job, targetTime, "N")

            else:
                print "Fuzz time!"
                #if remoteLoginAndMachine:
                #  sendEmail("justFuzzTime", "Platform details , " + platform.node() + " , Python " + sys.version[:5] + " , " +  " ".join(platform.uname()), "gkwong")
                if options.reuse_build and os.path.exists(buildDir):
                    buildSrc = buildDir
                else:
                    if os.path.exists(buildDir):
                        print "Deleting old build"
                        shutil.rmtree(buildDir)
                    os.mkdir(buildDir)
                    buildSrc = downloadBuild.downloadLatestBuild(buildType, relevantJobsDir, getJsShell=options.runJsfunfuzz)
                if options.runJsfunfuzz:
                    assert False, 'jsfunfuzz support is not yet completed.'
                (lithlog, ldfResult, lithDetails) = loopdomfuzz.many_timed_runs(targetTime, [buildDir]) # xxx support --valgrind
                if ldfResult == loopdomfuzz.HAPPY:
                    print "Happy happy! No bugs found!"
                else:
                    job = relevantJobsDir + "wtmp1" + localSep
                    writeTinyFile(job + "preferred-build.txt", buildSrc)
                    # not really "oldjobname", but this is how i get newjobname to be what i want below
                    # avoid putting underscores in this part, because those get split on
                    oldjobname = relevantJobsDir + "foundat" + timestamp() #+ "-" + str(random.randint(0, 1000000))
                    os.rename(relevantJobsDir + "wtmp1", oldjobname)
                    job = oldjobname + localSep
                    lithlog = job + "lith1-out"

        if lithlog:
            statePostfix = ({
              loopdomfuzz.NO_REPRO_AT_ALL: "_no_repro",
              loopdomfuzz.NO_REPRO_EXCEPT_BY_URL: "_repro_url_only",
              loopdomfuzz.LITH_NO_REPRO: "_no_longer_reproducible",
              loopdomfuzz.LITH_FINISHED: "_reduced",
              loopdomfuzz.LITH_RETESTED_STILL_INTERESTING: "_retested",
              loopdomfuzz.LITH_PLEASE_CONTINUE: "_needsreduction",
              loopdomfuzz.LITH_BUSTED: "_sad"
            })[ldfResult]

            if ldfResult == loopdomfuzz.LITH_PLEASE_CONTINUE:
                writeTinyFile(job + "lithium-command.txt", lithDetails)

            if ldfResult == loopdomfuzz.LITH_FINISHED:
                # lithDetails should be a string like "11 lines"
                statePostfix = "_" + lithDetails.replace(" ", "_") + statePostfix

            #print "oldjobname: " + oldjobname
            newjobname = oldjobname + statePostfix
            print "Uploading as: " + newjobname
            newjobnameTmp = newjobname + ".uploading"
            os.rename(job, newjobnameTmp)
            copyFiles(newjobnameTmp + localSep, remotePrefix + relevantJobsDir + remoteSep)
            runCommand("mv " + relevantJobsDir + newjobnameTmp + " " + relevantJobsDir + newjobname)
            shutil.rmtree(newjobnameTmp)

            # Remove the old *_taken directory from the server
            if takenNameOnServer:
                runCommand("rm -rf " + takenNameOnServer)

            # Remove build directory
            if not options.reuse_build and os.path.exists(buildDir):
                shutil.rmtree(buildDir)

            if remoteLoginAndMachine and ldfResult == loopdomfuzz.LITH_FINISHED:
                print "Sending email..."
                sendEmail("Reduced fuzz testcase", "https://pvtbuilds.mozilla.org/fuzzing/" + buildType + "/" + newjobname + "/", "jruderman")
                #sendEmail("Reduced fuzz testcase", "https://pvtbuilds.mozilla.org/fuzzing/" + buildType + "/" + newjobname + "/ " + \
                #          " - " + platform.node() + " - Python " + sys.version[:5] + " - " +  " ".join(platform.uname()), "gkwong")
                print "Email sent!"

if __name__ == "__main__":
    main()
