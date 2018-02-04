#!/usr/bin/python3 -u

'''
This product is produced independently from the Tor® anonymity software and carries no guarantee from The Tor Project about quality, suitability or anything else.

You can verify the original source of Tor for yourselves by visiting the official Tor website: https://www.torproject.org/
'''

from PyQt5 import QtCore
from PyQt5.QtWidgets import *

import sys, os
import re
from subprocess import Popen, PIPE
import time


class RestartTor(QWidget):
    def __init__(self):
        super().__init__()

        self.text = QLabel(self)
        self.bootstrap_progress = QProgressBar(self)
        self.layout = QGridLayout()

        self.setupUI()

    def setupUI(self):
        self.setGeometry(300, 150, 450, 150)
        self.setWindowTitle('Restart tor')

        self.text.setWordWrap(True)
        self.text.setAlignment(QtCore.Qt.AlignLeft|QtCore.Qt.AlignTop)
        self.text.setMinimumSize(0, 120)

        self.bootstrap_progress.setMinimumSize(400, 0)
        self.bootstrap_progress.setMinimum(0)
        self.bootstrap_progress.setMaximum(100)

        self.layout.addWidget(self.text, 0, 1, 1, 2)
        self.layout.addWidget(self.bootstrap_progress, 1, 1, 1, 1)
        self.setLayout(self.layout)

        self.restart_tor()

    def center(self):
        rectangle = self.frameGeometry()
        center_point = QDesktopWidget().availableGeometry().center()
        rectangle.moveCenter(center_point)
        self.move(rectangle.topLeft())

    def update_bootstrap(self, status):
        if status != 'timeout':
            bootstrap_phase = re.search(r'SUMMARY=(.*)', status).group(1)
            bootstrap_percent = int(re.match('.* PROGRESS=([0-9]+).*', status).group(1))
            if bootstrap_percent == 100:
                self.text.setText('<p><b>Tor bootstrapping done</b></p>Bootstrap phase: {0}'.format(bootstrap_phase))
                self.bootstrap_done = True
            else:
                self.text.setText('<p><b>Bootstrapping Tor...</b></p>Bootstrap phase: {0}'.format(bootstrap_phase))
            self.bootstrap_progress.setValue(bootstrap_percent)
        else:
            self.bootstrap_timeout = True

    def close(self):
        time.sleep(2)
        sys.exit()

    def restart_tor(self):
        '''
        Restart tor.
        Use subprocess.Popen instead of subprocess.call in order to catch
        possible errors from "restart tor" command.
        '''
        command = Popen(['sudo', 'systemctl', 'restart', 'tor@default'], stdout=PIPE, stderr=PIPE)
        stdout, stderr = command.communicate()

        std_err = "b''"
        stderr = str(stderr)
        command_success = stderr == std_err

        if not command_success:
            # Format stderr for readability in message box.
            stderr = re.sub(r'\n', stderr, ' \n')[3:][:-1]
            error = QMessageBox(QMessageBox.Critical, 'Restart tor', stderr, QMessageBox.Ok)
            error.exec_()
            self.close()

        self.bootstrap_thread = TorBootstrap(self)
        self.bootstrap_thread.signal.connect(self.update_bootstrap)
        self.bootstrap_thread.finished.connect(self.close)
        self.bootstrap_thread.start()

        self.show()
        self.center()


class TorBootstrap(QtCore.QThread):
    signal = QtCore.pyqtSignal(str)
    def __init__(self, main):
        QtCore.QThread.__init__(self, parent=None)

        self.control_cookie_path = '/run/tor/control.authcookie'
        self.control_socket_path = '/run/tor/control'

        self.previous_status = ''
        self.bootstrap_percent = 0
        #self.is_running = False
        self.tor_controller = self.connect_to_control_port()

    def connect_to_control_port(self):
        import stem
        import stem.control
        import stem.socket
        from stem.connection import connect

        '''
        In case something wrong happened when trying to start Tor,
        causing /run/tor/control never be generated.
        We set up a time counter and hardcode the wait time limitation as 15s.
        '''
        self.count_time = 0
        while(not os.path.exists(self.control_socket_path) and self.count_time < 15):
            self.previous_status = 'Waiting for /run/tor/control...'
            time.sleep(0.2)
            self.count_time += 0.2

        if os.path.exists(self.control_socket_path):
            self.tor_controller = stem.control.Controller.from_socket_file(self.control_socket_path)
        else:
            print(self.control_socket_path + ' not found!!!')

        if not os.path.exists(self.control_cookie_path):
            # TODO: can we let Tor generate a cookie to fix this situiation?
            print(self.control_cookie_path + ' not found!!!')
        else:
            with open(self.control_cookie_path, "rb") as f:
                cookie = f.read()
            try:
                self.tor_controller.authenticate(cookie)
            except stem.connection.IncorrectCookieSize:
                pass  #if the cookie file's size is wrong
            except stem.connection.UnreadableCookieFile:
                pass  #if # TODO: he cookie file doesn't exist or we're unable to read it
            except stem.connection.CookieAuthRejected:
                pass  #if cookie authentication is attempted but the socket doesn't accept it
            except stem.connection.IncorrectCookieValue:
                pass  #if the cookie file's value is rejected
        return self.tor_controller


    def run(self):
        while self.bootstrap_percent < 100:
            bootstrap_status = self.tor_controller.get_info("status/bootstrap-phase")
            self.bootstrap_percent = int(re.match('.* PROGRESS=([0-9]+).*', bootstrap_status).group(1))

            if bootstrap_status != self.previous_status:
                sys.stdout.write('{0}\n'.format(bootstrap_status))
                sys.stdout.flush()
                self.previous_status = bootstrap_status
                self.signal.emit(bootstrap_status)
            time.sleep(0.2)


def main():
    app = QApplication(sys.argv)
    restart_tor = RestartTor()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
