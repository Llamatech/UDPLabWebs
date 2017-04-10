#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import os
import sys
import time
import math
import json
import socket
import base64
import hashlib
import argparse
import datetime
import humanize
import os.path as osp

from utils import add_actions, create_toolbutton, create_action

from qtpy.compat import getopenfilename
from qtpy.QtCore import QMutex, QMutexLocker, QThread, Signal, Slot
from qtpy.QtWidgets import (QHBoxLayout, QLabel, QMainWindow,
                            QVBoxLayout, QWidget,
                            QProgressBar, QApplication,
                            QSpinBox, QLineEdit, QActionGroup)

import qtawesome as qta

if sys.version_info < (3, 6):
    import sha3

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
parser.add_argument('--bufsize',
                    default=212992,
                    help="Server hostname")


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
        print(self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF))
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
        # message_header = ['type', 'sequence_num', 'timestamp', 'message',
        # 'total_messages']
        message = {'type': 'MSG', 'sequence_num': 0, 'timestamp': None,
                   'message': self.message,
                   'total_messages': self.num_messages}
        for i in range(0, self.num_messages):
            with QMutexLocker(self.mutex):
                if self.stopped:
                    return False
            message['sequence_num'] = i + 1
            message['timestamp'] = datetime.datetime.now().isoformat()
            data = json.dumps(message)
            # data = ','.join([str(message[k]) for k in message_header])
            self.sock.sendto(bytes(data, "utf-8"), (self.host,
                                                    self.port))
            self.sig_current_message.emit(i, self.num_messages)


class FileUploadThread(QThread):
    sig_finished = Signal()
    sig_current_chunk = Signal(int, int)

    def __init__(self, parent):
        QThread.__init__(self, parent)
        self.mutex = QMutex()
        self.stopped = None
        self.canceled = False

    def initialize(self, host, port, path, size, bufsize):
        self.host = host
        self.port = port
        self.path = path
        self.size = size
        self.bufsize = bufsize

    def run(self):
        self.start_time = time.time()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.bufsize)
        self.upload_file()
        self.stop()
        self.sig_finished.emit()

    def stop(self):
        with QMutexLocker(self.mutex):
            self.stopped = True
            self.canceled = True
            self.sock.close()
            print("Time elapsed: {0}".format(time.time() - self.start_time))

    def upload_file(self):
        print(self.path)
        chunk = 2048
        hash_md5 = hashlib.sha3_256()
        total_size = self.size // chunk
        total_size += self.size % chunk != 0
        filename = osp.basename(self.path)

        message = {'seq_num': 0, 'file': filename,
                   'total_seq': total_size, 'payload': None,
                   'type': 'FILE'}
        cur_seq = 1
        bytes_snt = 0
        with open(self.path, 'rb') as fp:
            buf = fp.read(chunk)
            while buf:
                with QMutexLocker(self.mutex):
                    if self.stopped:
                        return False
                message['seq_num'] = cur_seq

                message['payload'] = str(base64.b64encode(buf), 'utf-8')
                hash_md5.update(buf)
                data = json.dumps(message)

                self.sock.sendto(bytes(data, "utf-8"), (self.host,
                                                        self.port))
                self.sock.settimeout(5.0)
                try:
                    received = str(self.sock.recv(2048), "utf-8")
                except socket.timeout:
                    self.sock.sendto(bytes(data, "utf-8"), (self.host,
                                                            self.port))
                    received = str(self.sock.recv(2048), "utf-8")

                assert received == 'ACK'
                bytes_snt += len(buf)
                self.sig_current_chunk.emit(total_size, bytes_snt)
                cur_seq += 1
                buf = fp.read(chunk)
        message = {'type': 'MD5', 'file': filename,
                   'payload': hash_md5.hexdigest()}
        data = json.dumps(message)
        self.sock.sendto(bytes(data, 'utf-8'), (self.host, self.port))
        received = str(self.sock.recv(2048), "utf-8")
        print(bool(received))


class DownloadButtons(QWidget):
    start_sig = Signal()
    stop_sig = Signal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        upload_icon = qta.icon("fa.upload")
        self.start = create_toolbutton(self, text="Start uploading",
                                       triggered=lambda: self.start_sig.emit(),
                                       tip="Send Messages",
                                       icon=upload_icon,
                                       text_beside_icon=True)
        stop_icon = qta.icon("fa.stop", color="red")
        self.stop = create_toolbutton(self, text="Stop",
                                      triggered=lambda: self.stop_sig.emit(),
                                      tip="Stop", icon=stop_icon,
                                      text_beside_icon=True)
        self.stop.setEnabled(False)
        self.start.setEnabled(True)
        layout = QHBoxLayout()
        layout.addWidget(self.start)
        layout.addWidget(self.stop)
        self.setLayout(layout)


class FileProgressBar(QWidget):
    """Simple progress bar with a label"""
    MAX_LABEL_LENGTH = 40

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
        self.status_text.setText("  Waiting for a upload to begin")
        self.bar.hide()

    def reset_files(self):
        self.status_text.setText("  Transfer in progress...")
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

    @Slot(str, int, int, int)
    def update_file_upload_progress(self, file, num_chunks,
                                    bytes_snt, total_bytes):
        text = " Uploading {0} - {1}/{2} (Chunk {3})"
        self.status_text.setText(text.format(self.__truncate(file),
                                             humanize.naturalsize(bytes_snt),
                                             humanize.naturalsize(total_bytes),
                                             num_chunks))
        self.bar.setValue(bytes_snt)


class HostOptionsWidget(QWidget):
    def __init__(self, parent, host, port):
        QWidget.__init__(self, parent)

        self.host_selector = QLineEdit(self)
        self.host_selector.setText(host)

        self.port_spinner = QSpinBox(self)
        self.port_spinner.setMinimum(1)
        self.port_spinner.setMaximum(60000)
        self.port_spinner.setValue(port)
        self.port_spinner.setToolTip("UDP Server Port")

        vlayout1 = QVBoxLayout()
        vlayout1.addWidget(QLabel("Server Host", self))
        vlayout1.addWidget(self.host_selector)

        vlayout2 = QVBoxLayout()
        vlayout2.addWidget(QLabel("Port", self))
        vlayout2.addWidget(self.port_spinner)
        hlayout = QHBoxLayout()
        hlayout.addLayout(vlayout1)
        hlayout.addLayout(vlayout2)

        self.setLayout(hlayout)

    def get_host_info(self):
        host = self.host_selector.text()
        port = self.port_spinner.value()
        return host, port


class MessageInfoWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)

        self.message_input = QLineEdit(self)
        self.num_messages = QSpinBox(self)
        self.num_messages.setValue(1)
        self.num_messages.setMinimum(1)
        self.num_messages.setMaximum(200000)

        vlayout_msg = QVBoxLayout()
        vlayout_msg.addWidget(QLabel("Message", self))
        vlayout_msg.addWidget(self.message_input)

        hlayout = QHBoxLayout()
        hlayout.addLayout(vlayout_msg)

        vlayout_nmsg = QVBoxLayout()
        vlayout_nmsg.addWidget(QLabel("Number of messages", self))
        vlayout_nmsg.addWidget(self.num_messages)
        hlayout.addLayout(vlayout_nmsg)

        self.setLayout(hlayout)

    def get_info(self):
        message = self.message_input.text()
        num_messages = self.num_messages.value()
        return message, num_messages


class MessageUploaderWidget(QWidget):
    def __init__(self, parent, host, port):
        QWidget.__init__(self, parent)
        self.host = host
        self.port = port
        self.thread = None

        self.host_selector = HostOptionsWidget(self, host, port)
        self.msg_info = MessageInfoWidget(self)
        self.buttons = DownloadButtons(self)
        self.progress_bar = FileProgressBar(self)
        self.progress_bar.initial_state()

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.host_selector)
        main_layout.addWidget(self.msg_info)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.buttons)
        self.setLayout(main_layout)

        self.buttons.start_sig.connect(self.start_transfer)
        self.buttons.stop_sig.connect(self.stop_and_reset_thread)

    def start_transfer(self):
        print("Transfer messages!")
        self.stop_and_reset_thread()

        message, num_messages = self.msg_info.get_info()
        host, port = self.host_selector.get_host_info()
        print(host, port)

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


class FileChooserWidget(QWidget):
    def __init__(self, parent, bufsize):
        QWidget.__init__(self, parent)

        self.file_selector = QLineEdit(self)
        dir_icon = qta.icon('fa.folder-open')
        self.file_btn = create_toolbutton(self, text="Choose a file",
                                          triggered=self.select_file,
                                          tip="Choose a file", icon=dir_icon)
        self.file_btn.setToolTip("Choose a file")

        self.buf_size_spin = QSpinBox(self)
        # print(bufsize)
        self.buf_size_spin.setMinimum(1)
        self.buf_size_spin.setMaximum(100000000)
        self.buf_size_spin.setValue(bufsize)

        vlayout = QVBoxLayout()
        vlayout.addWidget(QLabel("File to upload", self))
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.file_selector)
        hlayout.addWidget(self.file_btn)
        vlayout.addLayout(hlayout)

        buf_layout = QVBoxLayout()
        buf_layout.addWidget(QLabel("Buffer Size (Bytes)", self))
        buf_layout.addWidget(self.buf_size_spin)

        wid_layout = QHBoxLayout()
        wid_layout.addLayout(vlayout)
        wid_layout.addLayout(buf_layout)
        self.setLayout(wid_layout)

    def select_file(self):
        filename, _ = getopenfilename(self, caption="Select a file")
        print(filename)
        self.file_selector.setText(filename)

    def get_selected_file(self):
        path = self.file_selector.text()
        size = os.stat(path).st_size
        return path, size

    def get_bufsize(self):
        return self.buf_size_spin.value()


class FileUploaderWidget(QWidget):
    def __init__(self, parent, host, port, bufsize):
        QWidget.__init__(self, parent)
        self.host = host
        self.port = port
        self.bufsize = bufsize
        self.thread = None

        self.host_selector = HostOptionsWidget(self, host, port)
        self.file_selector = FileChooserWidget(self, bufsize)
        self.buttons = DownloadButtons(self)
        self.progress_bar = FileProgressBar(self)
        self.progress_bar.initial_state()

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.host_selector)
        main_layout.addWidget(self.file_selector)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.buttons)
        self.setLayout(main_layout)

        self.buttons.start_sig.connect(self.start_upload)
        self.buttons.stop_sig.connect(self.stop_and_reset_thread)

    def start_upload(self):
        print("Transfer messages!")
        self.stop_and_reset_thread()
        host, port = self.host_selector.get_host_info()
        path, size = self.file_selector.get_selected_file()
        bufsize = self.file_selector.get_bufsize()
        self.progress_bar.set_bounds(0, size)
        self.thread = FileUploadThread(self)
        self.thread.initialize(host, port, path, size, bufsize)
        self.thread.sig_finished.connect(self.transfer_complete)
        self.thread.sig_current_chunk.connect(
            lambda x, y:
                self.progress_bar.update_file_upload_progress(path, x,
                                                              y, size))
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


class MainWindow(QMainWindow):
    def __init__(self, parent, host, port, bufsize):
        QMainWindow.__init__(self, parent)
        self.host = host
        self.port = port
        self.bufsize = bufsize

        self.msg_uploader = MessageUploaderWidget(self, host, port)
        self.file_uploader = FileUploaderWidget(self, host, port, bufsize)

        self.setCentralWidget(self.msg_uploader)

        action_group = QActionGroup(self)
        self.mode_menu = self.menuBar().addMenu("Mode")
        self.msg_mode_action = create_action(action_group, "Send messages",
                                             triggered=self.toggle_msg_view)
        self.file_mode_action = create_action(action_group, "Upload files",
                                              triggered=self.toggle_file_view)

        self.view_state = 'msg'
        self.msg_mode_action.setCheckable(True)
        self.msg_mode_action.setChecked(True)
        self.file_mode_action.setCheckable(True)
        self.file_mode_action.setChecked(False)

        add_actions(self.mode_menu, [self.msg_mode_action,
                                     self.file_mode_action])
        action_group.setExclusive(True)

    def toggle_msg_view(self):
        if self.view_state != 'msg':
            self.msg_uploader = MessageUploaderWidget(self, host=self.host,
                                                      port=self.port)
            self.setCentralWidget(self.msg_uploader)
            self.view_state = 'msg'

    def toggle_file_view(self):
        if self.view_state != 'files':
            self.file_uploader = FileUploaderWidget(self, host=self.host,
                                                    port=self.port,
                                                    bufsize=self.bufsize)
            self.setCentralWidget(self.file_uploader)
            self.view_state = 'files'


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
    bufsize = args.bufsize
    if args.headless:
        headless_conn(host, port)
    else:
        app = QApplication.instance()
        if app is None:
            app = QApplication(['UDP Client'])
        widget = MainWindow(None, host, port, bufsize)
        widget.resize(640, 60)
        widget.show()
        sys.exit(app.exec_())
