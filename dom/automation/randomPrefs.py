# Random prefs (added by loopdomfuzz.py) to be combined with constant-prefs.js (added by domInteresting.py)

import os
import random

p0 = os.path.dirname(os.path.abspath(__file__))

def chance(p):
    return random.random() < p

def randomPrefs():
    p = []

    with open(os.path.join(p0, "bool-prefs.txt")) as f:
        for line in f:
            pref = line.strip()
            if len(pref) and pref[0] != "#":
                if 'enable' in pref:
                    t = chance(.8)
                elif 'disable' in pref:
                    t = chance(.2)
                else:
                    t = chance(.5)
                v = "true" if t else "false"
                p += ['user_pref("' + pref + '", ' + v + ');']

    if random.random() > 0.2:
        p += ['user_pref("ui.caretBlinkTime", -1);']
    if random.random() > 0.8:
        p += ['user_pref("font.size.inflation.minTwips", 120);']
    if random.random() > 0.8:
        p += ['user_pref("font.size.inflation.emPerLine", 15);']
    if random.random() > 0.8:
        p += ['user_pref("font.size.inflation.lineThreshold", ' + str(random.randrange(0, 400)) + ');']
        p += ['user_pref("font.size.inflation.maxRatio", ' + str(random.randrange(0, 400)) + ');']
        p += ['user_pref("browser.sessionhistory.max_entries", ' + str(random.randrange(2, 10)) + ');']
        p += ['user_pref("browser.sessionhistory.max_total_viewers", ' + str(random.randrange(0, 4)) + ');']
        p += ['user_pref("bidi.direction", ' + random.choice(["1", "2"]) + ');']
        p += ['user_pref("bidi.numeral", ' + random.choice(["0", "1", "2", "3", "4"]) + ');']
        p += ['user_pref("browser.display.use_document_fonts", ' + random.choice(["0", "1"]) + ');']
        p += ['user_pref("browser.history.maxStateObjectSize", ' + random.choice(["0", "100", "655360", "655360"]) + ');']
        p += ['user_pref("browser.sessionstore.interval", ' + random.choice(["100", "1000", "15000"]) + ');']
        p += ['user_pref("browser.sessionstore.max_tabs_undo", ' + random.choice(["0", "1", "10"]) + ');']
        p += ['user_pref("browser.sessionstore.browser.sessionstore.max_windows_undo", ' + random.choice(["0", "1", "10"]) + ');']
        p += ['user_pref("browser.sessionstore.postdata", ' + random.choice(["0", "-1", "1000"]) + ');']
        p += ['user_pref("layout.scrollbar.side", ' + random.choice(["0", "1", "2", "3"]) + ');']
        p += ['user_pref("permissions.default.image", ' + random.choice(["1", "2", "3"]) + ');']
        p += ['user_pref("accessibility.force_disabled", ' + random.choice(["-1", "0", "1"]) + ');']
        p += ['user_pref("gfx.font_rendering.harfbuzz.scripts", ' + random.choice(["-1", str(random.randrange(0, 0x80))]) + ');'] # gfx/thebes/gfxUnicodeProperties.h ShapingType bitfield
        p += ['user_pref("layout.css.devPixelsPerPx", ' + random.choice(["'-1.0'", "'1.0'", "'2.0'"]) + ');']
        p += ['user_pref("gfx.hidpi.enabled", ' + random.choice(["0", "1", "2"]) + ');']
    if random.random() > 0.9:
        p += ['user_pref("intl.uidirection.en", "rtl");']

    return "\n".join(p)
