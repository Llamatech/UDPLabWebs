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
                            QVBoxLayout, QWidget,
                            QProgressBar, QApplication,
                            QToolButton, QComboBox, QSpinBox, QLineEdit)


parser = argparse.ArgumentParser(
    description='Simple lightweight UDP client')
parser.add_argument('--headless',
                    action="store_true",
                    default=False,
                    help="Do not start GUI")
parser.add_argument('--port',
                    default=10000,
                    help="Server UDP port")
parser.add_argument('--host',
                    default='127.0.0.1',
                    help="Server hostname")


def create_toolbutton(parent, text=None, shortcut=None, icon=None, tip=None,
                      toggled=None, triggered=None,
                      autoraise=True, text_beside_icon=False):
    """Create a QToolButton"""
    button = QToolButton(parent)
    if text is not None:
        button.setText(text)
    if text is not None or tip is not None:
        button.setToolTip(text if tip is None else tip)
    if text_beside_icon:
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    button.setAutoRaise(autoraise)
    if triggered is not None:
        button.clicked.connect(triggered)
    if toggled is not None:
        button.toggled.connect(toggled)
        button.setCheckable(True)
    if shortcut is not None:
        button.setShortcut(shortcut)
    return button


class SendMessagesThread(QThread):
    sig_finished = Signal()
    sig_current_message = Signal(int, int)

    def __init__(self, parent):
        QThread.__init__(self, parent)
        self.mutex = QMutex()
        self.stopped = None
        self.canceled = False

    def initialize(self, host, port, num_messages, message):
        self.host = host
        self.port = port
        self.num_messages = num_messages
        self.message = message
        # self.file = osp.join('downloads', file)
        # self.msglen = size

    def run(self):
        self.start_time = time.time()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.send_messages()
        self.stop()
        self.sig_finished.emit()

    def stop(self):
        with QMutexLocker(self.mutex):
            self.stopped = True
            self.canceled = True
            self.sock.close()
            print("Time elapsed: {0}".format(time.time() - self.start_time))

    def send_messages(self):
        # chunks = []
        message_header = ['sequence_num', 'timestamp', 'message',
                          'total_messages']
        message = {'sequence_num': 0, 'timestamp': None,
                   'message': self.message,
                   'total_messages': self.num_messages}
        for i in range(0, self.num_messages):
            with QMutexLocker(self.mutex):
                if self.stopped:
                    return False
            message['sequence_num'] = i + 1
            message['timestamp'] = datetime.datetime.now().isoformat()
            data = ','.join([str(message[k]) for k in message_header])
            self.sock.sendto(bytes(data, "utf-8"), (self.host,
                                                    self.port))
            self.sig_current_message.emit(i, self.num_messages)


class DownloadButtons(QWidget):
    start_sig = Signal()
    stop_sig = Signal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.start = create_toolbutton(self, text="Send Message",
                                       triggered=lambda: self.start_sig.emit(),
                                       tip="Send Messages")
        self.stop = create_toolbutton(self, text="Stop",
                                      triggered=lambda: self.stop_sig.emit(),
                                      tip="Stop")
        self.stop.setEnabled(False)
        self.start.setEnabled(True)
        layout = QHBoxLayout()
        layout.addWidget(self.start)
        layout.addWidget(self.stop)
        self.setLayout(layout)


class FileProgressBar(QWidget):
    """Simple progress bar with a label"""
    MAX_LABEL_LENGTH = 60

    def __init__(self, parent, *args, **kwargs):
        QWidget.__init__(self, parent)
        self.pap = parent
        self.status_text = QLabel(self)
        self.bar = QProgressBar(self)
        self.bar.setRange(0, 0)
        layout = QVBoxLayout()
        layout.addWidget(self.status_text)
        layout.addWidget(self.bar)
        self.setLayout(layout)

    def __truncate(self, text):
        ellipsis = '...'
        part_len = (self.MAX_LABEL_LENGTH - len(ellipsis)) / 2.0
        left_text = text[:int(math.ceil(part_len))]
        right_text = text[-int(math.floor(part_len)):]
        return left_text + ellipsis + right_text

    def set_bounds(self, a, b):
        self.bar.setRange(a, b)

    def initial_state(self):
        self.status_text.setText("  Waiting for a message exchange to begin")
        self.bar.hide()

    def reset_files(self):
        self.status_text.setText("  Transfering messages...")
        self.bar.show()

    def reset_status(self):
        self.status_text.setText("  Transfer Complete!")
        self.bar.hide()

    @Slot(str, int, int, int)
    def update_progress(self, current_message, total_messages):
        text = "  Sending message {0} out of {1}"
        self.status_text.setText(text.format(
            current_message, total_messages))
        self.bar.setValue(current_message)


class FileDownloaderWidget(QWidget):
    def __init__(self, parent, host, port):
        QWidget.__init__(self, parent)
        self.host = host
        self.port = port
        self.thread = None

        self.host_selector = QLineEdit(self)
        self.host_selector.setText(host)
        # self.host_selector.setEditable(True)
        # self.host_selector.setEditText(host)
        vlayout1 = QVBoxLayout()
        vlayout1.addWidget(QLabel("Server Host", self))
        vlayout1.addWidget(self.host_selector)

        vlayout2 = QVBoxLayout()
        self.port_spinner = QSpinBox(self)
        self.port_spinner.setMinimum(1)
        self.port_spinner.setMaximum(60000)
        self.port_spinner.setValue(port)
        self.port_spinner.setToolTip("UDP Server Port")
        vlayout2.addWidget(QLabel("Port", self))
        vlayout2.addWidget(self.port_spinner)
        hlayout = QHBoxLayout()
        hlayout.addLayout(vlayout1)
        hlayout.addLayout(vlayout2)

        vlayout3 = QVBoxLayout()
        vlayout3.addWidget(QLabel("Message", self))
        self.message_input = QLineEdit(self)
        vlayout3.addWidget(self.message_input)
        hlayout2 = QHBoxLayout()
        hlayout2.addLayout(vlayout3)
        vlayout4 = QVBoxLayout()
        vlayout4.addWidget(QLabel("Number of messages", self))
        self.num_messages = QSpinBox(self)
        self.num_messages.setValue(1)
        self.num_messages.setMinimum(1)
        self.num_messages.setMaximum(200000)
        vlayout4.addWidget(self.num_messages)
        hlayout2.addLayout(vlayout4)
        # hlayout.addLayout(hlayout2)
        main_layout = QVBoxLayout()
        main_layout.addLayout(hlayout)
        main_layout.addLayout(hlayout2)
        self.buttons = DownloadButtons(self)
        self.progress_bar = FileProgressBar(self)
        # self.progress_bar.hide()
        self.progress_bar.initial_state()
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.buttons)
        self.setLayout(main_layout)

        self.buttons.start_sig.connect(self.start_transfer)
        self.buttons.stop_sig.connect(self.stop_and_reset_thread)

    def start_transfer(self):
        print("Transfer messages!")
        self.stop_and_reset_thread()
        message = self.message_input.text()
        num_messages = self.num_messages.value()
        host = self.host_selector.text()
        print(host)
        port = self.port_spinner.value()
        self.progress_bar.set_bounds(0, num_messages)
        self.thread = SendMessagesThread(self)
        self.thread.initialize(host, port, num_messages, message)
        self.thread.sig_finished.connect(self.transfer_complete)
        self.thread.sig_current_message.connect(
            self.progress_bar.update_progress)
        self.progress_bar.reset_files()
        self.thread.start()
        self.buttons.stop.setEnabled(True)
        self.buttons.start.setEnabled(False)

    def transfer_complete(self):
        self.progress_bar.reset_status()
        self.buttons.stop.setEnabled(False)
        self.buttons.start.setEnabled(True)

    def stop_and_reset_thread(self):
        if self.thread is not None:
            if self.thread.isRunning():
                self.thread.sig_finished.disconnect(self.transfer_complete)
                self.thread.stop()
                self.thread.wait()
            self.thread.setParent(None)
            self.thread = None
            self.transfer_complete()


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
    if args.headless:
        headless_conn(host, port)
    else:
        app = QApplication.instance()
        if app is None:
            app = QApplication(['UDP Client'])
        widget = FileDownloaderWidget(None, host=host, port=port)
        widget.resize(640, 60)
        widget.show()
        sys.exit(app.exec_())
