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

# global which is set in __main__, used to operate over ssh
remoteLoginAndMachine = None

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


def grabJob(relevantJobsDir, desiredJobType):
  while True:
    jobs = filter( (lambda s: s.endswith(desiredJobType)), runCommand("ls -1 " + relevantJobsDir).split("\n") )
    if len(jobs) > 0:
      oldNameOnServer = jobs[0]
      shortHost = socket.gethostname().split(".")[0]  # more portable than os.uname()[1]
      takenNameOnServer = relevantJobsDir + oldNameOnServer.split("_")[0] + "_taken_by_" + shortHost + "_at_" + timestamp()
      if tryCommand("mv " + relevantJobsDir + oldNameOnServer + " " + takenNameOnServer + ""):
        print "Grabbed " + oldNameOnServer + " by renaming it to " + takenNameOnServer
        job = copyFiles(remotePrefix + takenNameOnServer, ".")
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
  from optparse import OptionParser
  parser = OptionParser()
  parser.set_defaults(
      remote_host=None,
      basedir=os.path.join(os.path.expanduser("~"), "domfuzzjobs") + "/",
  )
  parser.add_option("--remote-host", dest="remote_host",
      help="Use remote host to store fuzzing data; format: user@host")
  parser.add_option("--basedir", dest="basedir",
      help="Base directory on remote machine to store fuzzing data")
  parser.add_option("--retest-all", dest="retestAll", action="store_true",
      help="Instead of fuzzing or reducing, take reduced testcases and retest them.")
  options, args = parser.parse_args()

  remoteLoginAndMachine = options.remote_host
  remoteBase = options.basedir
  # remotePrefix is used as a prefix for remoteBase when using scp
  remotePrefix = (remoteLoginAndMachine + ":") if remoteLoginAndMachine else ""
  relevantJobsDir = remoteBase + buildType() + "/"
  runCommand("mkdir -p " + relevantJobsDir)

  shouldLoop = True
  while shouldLoop:
    job = None
    oldjobname = None
    takenNameOnServer = None
    lithlog = None

    if os.path.exists("wtmp1"):
      print "wtmp1 shouldn't exist now. killing it."
      shutil.rmtree("wtmp1")

    if options.retestAll:
      print "Retesting time!"
      (job, oldjobname, takenNameOnServer) = grabJob(relevantJobsDir, "_reduced")
      if job:
        reducedFn = job + filter(lambda s: s.find("reduced") != -1, os.listdir(job))[0]
        print "reduced filename: " + reducedFn
        lithArgs = ["--strategy=check-only", "rundomfuzz.py", "build", reducedFn]
        (lithlog, ldfResult, lithDetails) = loopdomfuzz.runLithium(lithArgs, job, targetTime, "T")
      else:
        shouldLoop = False
    else:
      shouldLoop = False
      (job, oldjobname, takenNameOnServer) = grabJob(relevantJobsDir, "_needsreduction")
      if job:
        print "Reduction time!"
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
        (lithlog, ldfResult, lithDetails) = loopdomfuzz.many_timed_runs(targetTime, ["build"]) # xxx support --valgrind
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
      os.rename(job, newjobname)
      copyFiles(newjobname, remotePrefix + relevantJobsDir)
      shutil.rmtree(newjobname)
  
      # Remove the old *_taken directory from the server
      if takenNameOnServer:
        runCommand("rm -rf " + takenNameOnServer)
