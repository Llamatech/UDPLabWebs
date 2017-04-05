#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import socket
import asyncio
import argparse
import datetime
import numpy as np
import os.path as osp
import dateutil.parser as dateparser

parser = argparse.ArgumentParser(
    description='Simple lightweight UDP server')
parser.add_argument('--port',
                    default=10000,
                    help="UDP port to be listened")

LOGGING_PATH = 'logs'
# events = []

events = {}


def generate_report(addr):
    event = events.pop(addr)
    now = datetime.datetime.now()
    diff = now - event['initial_time']
    seqs = sorted(event['seqs'], key=lambda x: x[-1])
    print(seqs)
    print("Time elapsed: %gs" % (diff.microseconds / 1e6))
    filename = '_'.join([str(i) for i in addr] + [now.isoformat()]) + '.log'
    lines = ['seq_num,elapsed_time']
    values = []
    for seq in seqs:
        num_seq, send_time, arrival_time = seq
        time_delta = arrival_time - send_time
        values.append([int(num_seq), time_delta.microseconds / 1e6])
        lines.append(','.join([num_seq, str(time_delta.microseconds / 1e6)]))
    values = np.array(values)
    mean = np.mean(values[:, 1])
    lines.append('Mean Reception Time: %g' % (mean))
    lines.append('Lost Objects: %d' % (event['num_messages'] -
                                       values.shape[0]))
    lines.append('Total Objects: %d' % (event['num_messages']))
    lines = '\n'.join(lines)
    with open(osp.join(LOGGING_PATH, filename), 'w') as fp:
        fp.write(lines)


class EchoServerProtocol:
    def connection_made(self, transport):
        self.transport = transport
        # print(self.transport.get_extra_info('socket'))
        sock = self.transport.get_extra_info('socket')
        snd_bufsize = sock.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, snd_bufsize)

    def datagram_received(self, data, addr):
        now = datetime.datetime.now()
        message = data.decode()
        # 100,2017-04-04T11:20:25.416749,Hi!,100
        seq, timestamp, message, total_seq = message.split(',')
        if addr not in events:
            events[addr] = {'num_messages': int(total_seq), 'seqs': [],
                            'initial_time': now}
        timestamp = dateparser.parse(timestamp)
        diff = now - timestamp
        # diff2 = events[addr]['initial_time'] - timestamp
        print(diff.microseconds / 1000)
        # print(diff2.microseconds / 1000)
        events[addr]['seqs'].append([seq, timestamp, now])
        print('Received %r from %s - %s' % (message, addr,
                                            datetime.datetime.now()))
        if events[addr]['num_messages'] == int(seq):
            generate_report(addr)


if __name__ == '__main__':
    try:
        os.mkdir(LOGGING_PATH)
    except Exception:
        pass
    args = parser.parse_args()
    HOST, PORT = '0.0.0.0', int(args.port)
    loop = asyncio.get_event_loop()
    print("Starting UDP server")
    # One protocol instance will be created to serve all client requests
    listen = loop.create_datagram_endpoint(
        EchoServerProtocol, local_addr=(HOST, PORT))
    # tasks = [loop.create_task(generate_report())]
    print("Now listening on %s:%d" % (HOST, PORT))
    print("Press Ctrl+C to Stop")
    transport, protocol = loop.run_until_complete(listen)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    # print(events)
    transport.close()
    loop.close()
