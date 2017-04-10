#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import base64
import socket
import hashlib
import asyncio
import argparse
import datetime
import numpy as np
import os.path as osp
import dateutil.parser as dateparser

if sys.version_info < (3, 6):
    import sha3

parser = argparse.ArgumentParser(
    description='Simple lightweight UDP server')
parser.add_argument('--port',
                    default=10000,
                    help="UDP port to be listened")
parser.add_argument('--bufsize',
                    default=212992,
                    help="Size of input buffer")

LOGGING_PATH = 'logs'
UPLOADS_FOLDER = 'uploads'
# events = []

events = {}
file_uploads = {}


def generate_report(addr):
    event = events.pop(addr)
    now = datetime.datetime.now()
    diff = now - event['initial_time']
    seqs = sorted(event['seqs'], key=lambda x: x[-1])
    # print(seqs)
    print("Time elapsed: %gs" % (diff.microseconds / 1e6))
    filename = '_'.join([str(i) for i in addr] + [now.isoformat()]) + '.log'
    lines = ['seq_num,elapsed_time']
    values = []
    for seq in seqs:
        num_seq, send_time, arrival_time = seq
        time_delta = arrival_time - send_time
        values.append([int(num_seq), time_delta.microseconds / 1e6])
        lines.append(','.join([str(num_seq),
                               str(time_delta.microseconds / 1e6)]))
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
        print(bufsize)
        sock = self.transport.get_extra_info('socket')
        # snd_bufsize = sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
        # print(snd_bufsize)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, bufsize)

    def datagram_received(self, data, addr):
        now = datetime.datetime.now()
        message = data.decode()
        # print(message)
        data = json.loads(message)

        if data['type'] == 'MSG':
            self.handle_msg(data, addr, now)
        elif data['type'] == 'FILE':
            self.handle_upload(data, addr)
        elif data['type'] == 'MD5':
            self.handle_digest(data, addr)

    def handle_msg(self, data, addr, now):
        total_seq = data['total_messages']
        timestamp = data['timestamp']
        seq = data['sequence_num']
        message = data['message']
        if addr not in events:
            events[addr] = {'num_messages': int(total_seq), 'seqs': [],
                            'initial_time': now}
        timestamp = dateparser.parse(timestamp)
        diff = now - timestamp
        print(diff.microseconds / 1000)
        events[addr]['seqs'].append([seq, timestamp, now])
        print('Received %r from %s - %s' % (message, addr,
                                            datetime.datetime.now()))
        if events[addr]['num_messages'] == int(seq):
            generate_report(addr)

    def handle_upload(self, data, addr):
        print(data['seq_num'])
        if addr not in file_uploads:
            file_uploads[addr] = {'num_seqs': data['total_seq'], 'chunks': [],
                                  'filename': osp.join(UPLOADS_FOLDER,
                                                       data['file']),
                                  'seg_write': 0,
                                  'md5sum': hashlib.sha3_256()}
        chunk = base64.b64decode(bytes(data['payload'], 'utf-8'))
        file_uploads[addr]['chunks'].append([data['seq_num'], chunk])
        file_uploads[addr]['chunks'] = sorted(file_uploads[addr]['chunks'],
                                              key=lambda x: x[0])
        self.write_to_file(addr)
        self.transport.sendto(b'ACK', addr)

    def write_to_file(self, addr):
        data = file_uploads[addr]
        last_seg = data['seg_write']
        i = 0
        cur_seg = data['chunks'][i][0]
        with open(data['filename'], 'ab') as fp:
            while cur_seg == last_seg + 1:
                data['md5sum'].update(data['chunks'][i][1])
                fp.write(data['chunks'][i][1])
                i += 1
                last_seg = cur_seg
                try:
                    cur_seg = data['chunks'][i][0]
                except IndexError:
                    break
                # last_seg, cur_seg = cur_seg, cur_seg + 1
        data['chunks'] = data['chunks'][cur_seg + 1:]
        data['seg_write'] = last_seg

    def handle_digest(self, data, addr):
        print(data)
        print(file_uploads[addr]['seg_write'])
        md5sum = self.flush_chunks(addr)
        print(md5sum)
        self.transport.sendto(bytes(md5sum == data['payload']), addr)

    def flush_chunks(self, addr):
        data = file_uploads[addr]
        with open(data['filename'], 'ab') as fp:
            for chunk in data['chunks']:
                data['md5sum'].update(chunk[1])
                fp.write(chunk[1])
        md5sum = data['md5sum'].hexdigest()
        file_uploads.pop(addr)
        return md5sum


if __name__ == '__main__':
    try:
        os.mkdir(LOGGING_PATH)
    except Exception:
        pass

    try:
        os.mkdir(UPLOADS_FOLDER)
    except Exception:
        pass

    args = parser.parse_args()
    HOST, PORT = '0.0.0.0', int(args.port)
    bufsize = args.bufsize
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
