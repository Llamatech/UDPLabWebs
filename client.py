#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import os
import sys
import time
import math
import socket
import argparse
import datetime

from qtpy.QtCore import QMutex, QMutexLocker, Qt, QThread, Signal, Slot
from qtpy.QtWidgets import (QHBoxLayout, QLabel,
                            QTreeWidgetItem, QVBoxLayout, QWidget,
                            QProgressBar, QTreeWidget, QApplication,
                            QToolButton)


parser = argparse.ArgumentParser(
    description='Simple lightweight UDP client')
parser.add_argument('--port',
                    default=10000,
                    help="Server UDP port")
parser.add_argument('--host',
                    default='127.0.0.1',
                    help="Server hostname")


def headless_conn(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    data = 'hai'
    sock.sendto(bytes(data + "\n", "utf-8"), (host, port))
    received = str(sock.recv(1024), "utf-8")
    print("Sent:     {}".format(data))
    print("Received: {}".format(received))


if __name__ == '__main__':
    args = parser.parse_args()
    host = args.host
    port = args.port
    headless_conn(host, port)
