#!/usr/bin/env python

# Note: this module abuses strings in a way that is specific to Python 2.
# Will need changes for Python 3.
# http://stackoverflow.com/questions/2411864/python-socket-send-buffer-vs-str

"""
An HTTP echo server that uses threads to handle multiple clients at a time.
Entering any line of input at the terminal will exit the server.
"""

from __future__ import division

import base64
import os
import select
import socket
import sys
import threading
import time


class Server:
    # Based on http://ilab.cs.byu.edu/python/threadingmodule.html
    # which is CC (by-nc-nd)

    def __init__(self):
        self.host = ''
        self.port = int(sys.argv[1]) if len(sys.argv) > 1 else 9606
        self.backlog = 5
        self.size = 1024
        self.server = None
        self.threads = []

    def open_socket(self):
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind((self.host, self.port))
            self.server.listen(5)
        except socket.error, (value, message):
            if self.server:
                self.server.close()
            print "Could not open socket: " + message
            sys.exit(1)

    def run(self):
        self.open_socket()
        input = [self.server, sys.stdin]

        while True:
            inputready, outputready, exceptready = select.select(input, [], [])

            for s in inputready:

                if s == self.server:
                    # handle the server socket
                    print int(time.time())
                    c = Client(self.server.accept())
                    c.start()
                    self.threads.append(c)

                elif s == sys.stdin:
                    # handle standard input (including pipe closure)
                    junk = sys.stdin.readline()  # prevent fallthrough if I press Ctrl+D in a Terminal window
                    self.server.close()
                    os._exit(0)  # immediately kill all threads. do not join, do not clean up, do not pass Go.


class Client(threading.Thread):
    def __init__(self, (client, address)):
        threading.Thread.__init__(self)
        self.client = client
        self.address = address
        self.size = 1024
        self.httpRequest = ""

    def respond(self, path):
        if not path[0:2] == "/?":
            # e.g. requests for /favicon.ico
            return
        queryParams = path[2:].split("&")
        response = "oops"
        for param in queryParams:
            e = param.find("=")  # not using param.split because base64 can include "="
            if e == -1:
                print "Error: url param without =: " + param[:20]
                return
            name = param[:e]
            value = param[e+1:]
            if name == 'response':
                try:
                    response = base64.standard_b64decode(value)
                except TypeError as e:
                    # e.g. "Incorrect padding"
                    print "Error: standard_b64decode threw " + str(e)
            elif name == 'delay':
                specifiedSeconds = parseInt(value) / 1000
                time.sleep(minmax(0, specifiedSeconds, 10))
            else:
                print "Error: unexpected url param: " + name[:20]
                return
        self.client.sendall(response)

    def run(self):
        running = True
        while running:
            data = self.client.recv(self.size)
            if data:
                self.httpRequest += data
                if len(self.httpRequest) > 100000:
                    print "Error: request URL too long, even for me"
                    running = False
                elif self.httpRequest.endswith("\r\n\r\n"):
                    path = self.httpRequest.split(" ")[1]
                    self.respond(path)
                    running = False
            else:
                running = False
        self.client.close()


def minmax(low, input, high):
    return min(high, max(low, input))


def parseInt(s):
    try:
        return int(s)
    except ValueError:
        return 0


if __name__ == "__main__":
    Server().run()
