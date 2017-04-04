#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import argparse
import datetime

parser = argparse.ArgumentParser(
    description='Simple lightweight UDP server')
parser.add_argument('--port',
                    default=10000,
                    help="UDP port to be listened")

events = []


class EchoServerProtocol:
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        message = data.decode()
        events.append(message)
        print('Received %r from %s - %s' % (message, addr,
                                            datetime.datetime.now()))
        # print('Send %r to %s' % (message, addr))
        # self.transport.sendto(data, addr)


if __name__ == '__main__':
    args = parser.parse_args()
    HOST, PORT = '0.0.0.0', int(args.port)
    loop = asyncio.get_event_loop()
    print("Starting UDP server")
    # One protocol instance will be created to serve all client requests
    listen = loop.create_datagram_endpoint(
        EchoServerProtocol, local_addr=(HOST, PORT))
    print("Now listening on %s:%d" % (HOST, PORT))
    print("Press Ctrl+C to Stop")
    transport, protocol = loop.run_until_complete(listen)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    print(events)
    transport.close()
    loop.close()
