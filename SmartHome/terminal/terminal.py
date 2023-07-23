from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication
import sys
from forms.form_main import MainWindow
import os
import pathlib

import subprocess
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QStackedWidget,QMessageBox

rootPath = str(pathlib.Path(__file__).parent.absolute())
class cApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)

        self.mainWindow = MainWindow()

    def run(self):
        retCode = -1
        try:
            self.mainWindow.update()
            self.mainWindow.show()

            self.timer.start(1000)

            retCode = self.app.exec()
        except Exception as e:
            print(e)

        sys.exit(retCode)

    def update(self):
        try:
            self.mainWindow.update()
        except Exception as e:
            print(e)

    def showError(self, title, text):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(text)
        msg.setWindowTitle(title)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

if __name__ == '__main__':

    app = cApp()
    app.run()
