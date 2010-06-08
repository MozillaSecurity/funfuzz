#!/usr/bin/env python

# bot.py runs domfuzz or lithium as needed, for a limited amount of time, storing jobs using ssh.

import sys, os, subprocess, time, socket, random, shutil
import build_downloader
import loopdomfuzz
devnull = open(os.devnull, "w")

targetTime = 15*60 # for build machines, use 20 minutes (20*60)

# Uses directory name 'mv' for synchronization.

# Possible ssh options:
#   -oStrictHostKeyChecking=no
#   -oUserKnownHostsFile=/dev/null

#remoteLoginAndMachine = "jruderman@jesse-arm-1"
#remoteBase = "/mnt/jruderman/domfuzzjobs/"

remoteLoginAndMachine = None
remoteBase = os.path.join(os.path.expanduser("~"), "domfuzzjobs") + "/" # since this is just for testing, assume we're on a system with forward slashes

remotePrefix = (remoteLoginAndMachine + ":") if remoteLoginAndMachine else "" # used as a prefix for remoteBase when using scp

def ensureTrailingSlash(d):
  if d[-1] != "/":
    return d + "/"
  return d

# Copies a directory (the directory itself, not just its contents)
# whose full name is |srcDir|, creating a subdirectory of |destParent| with the same short name.
def copyFiles(srcDir, destParent):
  srcDir = ensureTrailingSlash(srcDir)
  destParent = ensureTrailingSlash(destParent)
  if remoteLoginAndMachine == None:
    subprocess.check_call(["cp", "-R", srcDir[:-1], destParent])
  else:
    subprocess.check_call(["scp", "-r", srcDir, destParent], stdout=devnull)
    # XXX synchronize at destination, especially if destParent is the remote one, perhaps by using mktemp remotely
  return destParent + srcDir.split("/")[-2] + "/"

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


def grabReductionJob(relevantJobsDir):
  while True:
    jobs = filter( (lambda s: s.endswith("_needsreduction")), runCommand("ls -1 " + relevantJobsDir).split("\n") )
    if len(jobs) > 0:
      shortHost = socket.gethostname().split(".")[0]  # more portable than os.uname()[1]
      takenName = relevantJobsDir + jobs[0].split("_")[0] + "_taken_by_" + shortHost + "_at_" + timestamp()
      if tryCommand("mv " + relevantJobsDir + jobs[0] + " " + takenName + ""):
        print "Grabbed " + jobs[0] + " by renaming it to " + takenName
        return takenName
      else:
        print "Raced to grab " + relevantJobsDir + jobs[0] + ", trying again"
        continue
    else:
      return None


def readTinyFile(fn):
  f = open(fn)
  text = f.read()
  f.close()
  return text.strip()

def writeTinyFile(fn, text):
  f = open(fn, "w")
  f.write(text)
  f.close()

def timestamp():
  return str(int(time.time()))

def downloadLatestBuild():
  latestBuild = build_downloader.findLatestBuild(buildType())
  build_downloader.downloadBuild(latestBuild)
  return latestBuild

def buildType():
  return "mozilla-central-" + build_downloader.mozPlatform() + "-debug"

if __name__ == "__main__":
  relevantJobsDir = remoteBase + buildType() + "/"
  runCommand("mkdir -p " + relevantJobsDir)
  jobAsTaken = grabReductionJob(relevantJobsDir)
  job = jobAsTaken
  lithlog = None
  if os.path.exists("wtmp1"):
    print "wtmp1 shouldn't exist now. killing it."
    shutil.rmtree("wtmp1")

  if job:
    print "Reduction time!"
    job = copyFiles(remotePrefix + job, ".")
    oldjobname = job[2:] # cut off the "./"
    os.rename(job, "wtmp1") # so lithium gets the same filename as before
    job = "wtmp1/"
    preferredBuild = readTinyFile(job + "preferred-build.txt")
    if len(preferredBuild) > 7: # hack shortcut for local running and for 'haha' (see below)
      if not build_downloader.downloadBuild(preferredBuild):
        print "Preferred build for this reduction was missing, grabbing latest build"
        downloadLatestBuild()
    lithArgs = readTinyFile(job + "lithium-command.txt").strip().split(" ")
    (lithlog, ldfResult, lithDetails) = loopdomfuzz.runLithium(lithArgs, job, targetTime, "N")

  else:
    print "Fuzz time!"
    if not os.path.exists("build"): # shortcut for local running that i should probably remove
      buildUsed = downloadLatestBuild()
    else:
      buildUsed = "haha" # hack, see preferredBuild stuff above
    (lithlog, ldfResult, lithDetails) = loopdomfuzz.many_timed_runs("build", targetTime, []) # xxx support --valgrind for additionalArgs
    if ldfResult == loopdomfuzz.HAPPY:
      print "Happy happy! No bugs found!"
    else:
      job = "wtmp1/"
      writeTinyFile(job + "preferred-build.txt", buildUsed)
      # not really "oldjobname", but this is how i get newjobname to be what i want below
      # avoid putting underscores in this part, because those get split on
      oldjobname = "foundat" + timestamp() #+ "-" + str(random.randint(0, 1000000))
      os.rename("wtmp1", oldjobname)
      job = oldjobname + "/"
      lithlog = job + "lith1-out"

  if lithlog:
    statePostfix = ({
      loopdomfuzz.NO_REPRO_AT_ALL: "_no_repro",
      loopdomfuzz.NO_REPRO_EXCEPT_BY_URL: "_repro_url_only",
      loopdomfuzz.LITH_NO_REPRO: "_no_longer_reproducible",
      loopdomfuzz.LITH_FINISHED: "_reduced",
      loopdomfuzz.LITH_PLEASE_CONTINUE: "_needsreduction",
      loopdomfuzz.LITH_BUSTED: "_sad"
    })[ldfResult]

    if ldfResult == loopdomfuzz.LITH_PLEASE_CONTINUE:
      writeTinyFile(job + "lithium-command.txt", lithDetails)

    #print "oldjobname: " + oldjobname
    newjobname = oldjobname.split("_")[0] + statePostfix
    print "Uploading as: " + newjobname
    os.rename(job, newjobname)
    copyFiles(newjobname, remotePrefix + relevantJobsDir)
    shutil.rmtree(newjobname)

    # Remove the old _taken thing from the server
    if jobAsTaken:
      runCommand("rm -rf " + jobAsTaken)
