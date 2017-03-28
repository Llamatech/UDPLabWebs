#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import os
import sys
import argparse
import socketserver

parser = argparse.ArgumentParser(
    description='Simple lightweight UDP server')
parser.add_argument('--port',
                    default=10000,
                    help="UDP port to be listened")


class UDPHandler(socketserver.BaseRequestHandler):
    """
    This class works similar to the TCP handler class, except that
    self.request consists of a pair of data and client socket, and since
    there is no connection the client address must be given explicitly
    when sending data back via sendto().
    """

    def handle(self):
        data = self.request[0].strip()
        socket = self.request[1]
        print("{} wrote:".format(self.client_address[0]))
        print(data)
        socket.sendto(data.upper(), self.client_address)


class ThreadedUDPServer(socketserver.ForkingMixIn, socketserver.UDPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass):
        socketserver.TCPServer.__init__(self, server_address,
                                        RequestHandlerClass)


if __name__ == '__main__':
    args = parser.parse_args()
    HOST, PORT = '0.0.0.0', int(args.port)
    server = ThreadedUDPServer((HOST, PORT), UDPHandler)
    print("Now listening on %s:%d" % (HOST, PORT))
    print("Press Ctrl+C to Stop")
    while True:
        try:
            server.handle_request()
        except KeyboardInterrupt:
            server.server_close()
            break
