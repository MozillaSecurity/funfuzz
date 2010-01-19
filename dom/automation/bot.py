#!/usr/bin/env python

# bot.py runs domfuzz or lithium as needed, for a limited amount of time, storing jobs using ssh.

import sys, os, subprocess, time, socket, random, shutil
import build_downloader
import loopdomfuzz
devnull = open(os.devnull, "w")

targetTime = 60 # for build machines, use 20 minutes (20*60)

# Uses directory name 'mv' for synchronization.

# Possible ssh options:
#   -oStrictHostKeyChecking=no
#   -oUserKnownHostsFile=/dev/null

remoteLoginAndMachine = "jruderman@jesse-arm-1"
remoteBase = "/mnt/jruderman/domfuzzjobs/"

#remoteLoginAndMachine = None
#remoteBase = "/Users/jruderman/domfuzzjobs/"

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


if __name__ == "__main__":
  relevantJobsDir = remoteBase + "mozilla-central-macosx-debug/"
  runCommand("mkdir -p " + relevantJobsDir)
  job = grabReductionJob(relevantJobsDir)
  lithlog = None

  if job:
    print "Reduction time!"
    # We could be cool and call loopdomfuzz.runLithium()
    job = copyFiles(remotePrefix + job, ".")
    oldjobname = job[2:] # cut off the "./"
    os.rename(job, "wtmp1") # so lithium gets the same filename as before
    job = "wtmp1/"
    preferredBuild = readTinyFile(job + "preferred-build.txt")
    if len(preferredBuild) > 7: # shortcut for local running that i should probably remove
      build_downloader.downloadBuild(preferredBuild)
    lithargs = loopdomfuzz.lithiumpy + ["--maxruntime=" + str(targetTime)] + readTinyFile(job + "lithium-command.txt").strip().split(" ")
    print repr(lithargs)
    subprocess.call(lithargs, stdout=open("lithiumlog", "w"), stderr=subprocess.STDOUT)
    lithlog = "lithiumlog"

  else:
    print "Fuzz time!"
    if not os.path.exists("build"): # shortcut for local running that i should probably remove
      latestBuild = build_downloader.findLatestBuild("mozilla-central", "macosx")
      build_downloader.downloadBuild(latestBuild)
    else:
      latestBuild = "haha"
    r = loopdomfuzz.many_timed_runs("build", targetTime, []) # xxx support --valgrind for additionalArgs
    if r:
      job = "wtmp1/"
      writeTinyFile(job + "preferred-build.txt", latestBuild)
      # not really "oldjobname", but this is how i get newjobname to be what i want below
      # avoid putting underscores in this part, because those get split on
      oldjobname = "foundat" + timestamp() #+ "-" + str(random.randint(0, 1000000))
      os.rename("wtmp1", oldjobname)
      job = oldjobname + "/"
      lithlog = job + "lith1-out"
    else:
      print "Happy happy! No bugs found!"

  if lithlog:
    # We could be cool and move some of this code into loopdomfuzz.runLithium()
    for line in open(lithlog):
      if line.startswith("Lithium result: the original testcase is not"):
        # Unfortunately, this single state can mean three things: never reproducible, reproducible with url only, lithium made it nonrepro
        statePostfix = "_nolongerreproducible"
        break
      if line.startswith("Lithium result: succeeded"):
        statePostfix = "_reduced"
        break
      if line.startswith("Lithium result: please continue using: "):
        statePostfix = "_needsreduction"
        lithiumHint = line[len("Lithium result: please continue using: "):]
        writeTinyFile(job + "lithium-command.txt", lithiumHint)
        break
    else:
      os.rename("lithiumlog", job + "sad-lithium-log.txt") # only in this case do we save a lithium log
      statePostfix = "_sad"
    #print "oldjobname: " + oldjobname
    newjobname = oldjobname.split("_")[0] + statePostfix
    print "Uploading as: " + newjobname
    os.rename(job, newjobname)
    copyFiles(newjobname, remotePrefix + relevantJobsDir)
    shutil.rmtree(newjobname)
