import sys
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import Slot, Signal, QProcess, QObject


class Main(QObject):

    def __init__(self):
        QObject.__init__(self)

    def ping(self):
        proc = QProcess(self)
        proc.readyReadStandardOutput.connect(self.ping_read)
        proc.start('ping', ['8.8.8.8', '-c', '4'])

    def ping_read(self):
        proc = self.sender()  # <---- "None" is returned by self.sender()
        print('proc', proc)
        data = bytearray(proc.readAllStandardOutput()).decode()
        print(data, end='')


if __name__ == "__main__":
    app = QApplication([])
    main = Main()
    main.ping()
    sys.exit(app.exec_())
