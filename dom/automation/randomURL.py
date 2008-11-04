#!/usr/bin/env python -u

# http://www.python.org/doc/2.5.2/lib/module-urllib2.html
# http://delicious.com/recent
# http://diveintopython.org/http_web_services/index.html

import random
import urllib
import urllib2
import socket
import httplib
import re


# In particular, we don't want URLs containing #, because those won't work
# (Not sure what delicious is thinking including those in a redirect response, but whatever)
saneURLs = re.compile("^https?\\:\\/\\/[a-zA-Z0-9/%&-_+=~?]*$")
if not saneURLs.match("http://www.google.com/"):
   raise "Yikes"
if saneURLs.match("http://www.google.com/#123"):
   raise "Yikes, we don't want to let # through"
if not saneURLs.match("http://www.google.com/123"):
   raise "Yikes"


socket.setdefaulttimeout(6)
#httplib.HTTPConnection.debuglevel = 1 # doesn't work


class SmartRedirectHandler(urllib2.HTTPRedirectHandler):
  def http_error_302(self, req, fp, code, msg, headers):
    # Pretend there was an error, so urllib2 doesn't actually follow the redirect
    result = urllib2.HTTPError(req.get_full_url(), code, msg, headers, fp)
    result.redirectURL = headers["Location"]
    return result

def randomURL():
  request = urllib2.Request('http://delicious.com/recent?random&min=' + str(random.randrange(1, 40)))
  h = urllib2.HTTPHandler() # Use debuglevel=1 to see the requests flying
  opener = urllib2.build_opener(h, SmartRedirectHandler)
  try:
    f = opener.open(request)
    if saneURLs.match(f.redirectURL):
      return f.redirectURL
    else:
      print "Skipping a delicious redirect to a URL that looks weird"
  except IOError, e:
    # I think timeouts will land here.
    print "randomURL caught: " + str(e)
  return "http://www.squarefree.com/start/"


if __name__ == "__main__":
  u = randomURL()
  print u
