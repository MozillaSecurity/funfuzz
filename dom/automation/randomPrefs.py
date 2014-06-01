# Random prefs (added by loopdomfuzz.py) to be combined with constant-prefs.js (added by domInteresting.py)

import os
import random
import re

p0 = os.path.dirname(os.path.abspath(__file__))


intPrefs = {
    "ui.caretBlinkTime":                          lambda: 120,
    "font.size.inflation.minTwips":               lambda: 120,
    "font.size.inflation.emPerLine":              lambda: 15,
    "font.size.inflation.lineThreshold":          lambda: random.randrange(0, 400),
    "font.size.inflation.maxRatio":               lambda: random.randrange(0, 400),
    "browser.sessionhistory.max_entries":         lambda: random.randrange(2, 10),
    "browser.sessionhistory.max_total_viewers":   lambda: random.randrange(0, 4),
    "bidi.direction":                             lambda: random.choice([1, 2]),
    "bidi.numeral":                               lambda: random.choice([0, 1, 2, 3, 4]),
    "browser.display.use_document_fonts":         lambda: random.choice([0, 1]),
    "browser.history.maxStateObjectSize":         lambda: random.choice([0, 100, 655360, 655360]),
    "browser.sessionstore.interval":              lambda: random.choice([100, 1000, 15000]),
    "browser.sessionstore.max_tabs_undo":         lambda: random.choice([0, 1, 10]),
    "browser.sessionstore.browser.sessionstore.max_windows_undo": lambda: random.choice([0, 1, 10]),
    "browser.sessionstore.postdata":              lambda: random.choice([0, -1, 1000]),
    "layout.scrollbar.side":                      lambda: random.choice([0, 1, 2, 3]),
    "permissions.default.image":                  lambda: random.choice([1, 2, 3]),
    "accessibility.force_disabled":               lambda: random.choice([-1, 0, 1]),
    "gfx.hidpi.enabled":                          lambda: random.choice([0, 1, 2]),
    "image.mem.hard_limit_decoded_image_kb":      lambda: random.randrange(0, 66560),
    "dom.max_script_run_time":                    lambda: random.choice([0, 5, 60, 60, 60, 60]), # NB: constant-prefs.js also usually sets it to 60
}

strPrefs = {
    "layout.css.devPixelsPerPx":                  lambda: random.choice(["-1.0", "1.0", "2.0"]), # float prefs are string prefs
    "intl.uidirection.en":                        lambda: "rtl",
    "gfx.canvas.azure.backends":                  lambda: "skia", # cg, direct2d, skia, cairo
}



def chance(p):
    return random.random() < p

def loadBoolPrefs():
    prefs = []

    with open(os.path.join(p0, "bool-prefs.txt")) as f:
        for line in f:
            line = line.strip()
            if len(line) and line[0] != "#":
                prefs.append(line)

    return prefs

cachedBoolPrefs = None
def boolPrefs():
    global cachedBoolPrefs
    if not cachedBoolPrefs:
        print "Loading bool prefs"
        cachedBoolPrefs = loadBoolPrefs()
    return cachedBoolPrefs

def randomPrefs():
    s = ""

    # Usually only modify a few prefs, but sometimes modify a lot
    prefiness = .1 if chance(.9) else .8

    for pref in boolPrefs():
        if chance(prefiness):
            if 'enable' in pref:
                t = chance(.8)
            elif 'disable' in pref:
                t = chance(.2)
            else:
                t = chance(.5)
            s += 'user_pref("' + pref + '", ' + ("true" if t else "false") + ');\n'
    for pref in intPrefs:
        if chance(prefiness):
            s += 'user_pref("' + pref + '", ' + str(intPrefs.get(pref)()) + ');\n'
    for pref in strPrefs:
        if chance(prefiness):
            s += 'user_pref("' + pref + '", "' + strPrefs.get(pref)() + '");\n'

    return s


prefRE = re.compile(r'^user_pref\("([a-zA-Z0-9_\-\.]*)", (false|true|[\-0-9\.]*|"[a-zA-Z0-9_\-\.]*")\);$')
def grabExtraPrefs(testcaseFilename):
    prefs = ""

    for fn in findPrefsFiles(testcaseFilename):
        with open(fn) as f:
            for line in f:
                if line.startswith("user_pref("):
                    line = line.rstrip()
                    m = prefRE.match(line)
                    if m:
                        prefName = m.group(1)
                        prefValue = m.group(2)
                        if (prefName in boolPrefs()) or (prefName in intPrefs) or (prefName in strPrefs):
                            prefs += 'user_pref("%s", %s);\n' % (prefName, prefValue)
                        else:
                            print "Warning: user_pref line has disallowed pref name: " + line
                    else:
                        print "Warning: user_pref line has disallowed syntax: " + line

    return prefs

def findPrefsFiles(testcaseFilename):
    # If the testcase is a-1.html, we will look for prefs in a-1.html and a-prefs.txt.
    fns = []
    basename = os.path.basename(testcaseFilename)
    if os.path.exists(testcaseFilename):
        fns.append(testcaseFilename)
        hyphen = basename.find("-")
        if hyphen != -1:
            prefsFile = os.path.join(os.path.dirname(testcaseFilename), basename[0:hyphen] + "-prefs.txt")
            #print "Looking for prefsFile: " + prefsFile
            if os.path.exists(prefsFile):
                fns.append(prefsFile)
    return fns
