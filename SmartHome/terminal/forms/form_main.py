import json

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QStackedWidget, QMessageBox, QFileDialog, \
    QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtCore import pyqtSignal, QObject
from widgets.parameter import ParameterLine
from databaseMySQL import cMySQL
import datetime

class Communicate(QObject):
    closeApp = pyqtSignal()
    showNotFoundError = pyqtSignal()
    cellarParameter = pyqtSignal(str, str, str)


IP_RACKUNO = "192.168.0.5"
IP_POWERWALL = "192.168.0.12"
IP_SERVER = "192.168.0.3"
IP_CELLAR = "192.168.0.33"

SINGLE_VALUE = 1
DOUBLE_VALUE = 2


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('./forms/main.ui', self)  # Load the .ui file

        self.setWindowTitle("Terminal app")
        self.c = Communicate()
        self.c.closeApp.connect(self.close)
        self.c.cellarParameter.connect(self.cellar_parameter_set)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.MySQL = cMySQL()
        self.timer.start(5000)
        self.all_params = []

        cellar_wd = [["brewhouse_polybox_autMan", "0", SINGLE_VALUE],
                     ["fanControl_autMan", "1", SINGLE_VALUE],
                     ["brewhouse_freezer_onOff", "2", SINGLE_VALUE],
                     ["brewhouse_chillPump_onOff", "3", SINGLE_VALUE],
                     ["fan_onOff", "4", SINGLE_VALUE],
                     ["brewhouse_polybox_setpoint", "5", DOUBLE_VALUE],
                     ["brewhouse_fermentor_autMan", "6", SINGLE_VALUE],
                     ["brewhouse_fermentor_setpoint", "7", DOUBLE_VALUE],
                     ["brewhouse_fermentor_heating", "8", SINGLE_VALUE],
                     ["garden1_autMan", "20", SINGLE_VALUE],
                     ["garden2_autMan", "21", SINGLE_VALUE],
                     ["garden3_autMan", "22", SINGLE_VALUE],
                     ["garden1_onOff", "23", SINGLE_VALUE],
                     ["garden2_onOff", "24", SINGLE_VALUE],
                     ["garden3_onOff", "25", SINGLE_VALUE],
                     ["garden2_duration_min", "28", SINGLE_VALUE],
                     ["garden3_duration_min", "29", SINGLE_VALUE],
                     ["garden_morning_h", "30", SINGLE_VALUE],
                     ["garden_evening_h", "31", SINGLE_VALUE],]
        self.cellar_params = []
        layout = self.cellarLayout.layout()
        for name, id, type in cellar_wd:
            wd = ParameterLine(name, id, self.c.cellarParameter, type)
            # wd.setFixedHeight(60)
            self.cellar_params.append(wd)
            layout.addWidget(wd)

        self.all_params += self.cellar_params
        self.show()

    def cellar_parameter_set(self, id, val, val2):
        self.SendData(id + "," + val + "," + val2, address=IP_CELLAR)

    def SendData(self, data, address=None):
        self.MySQL.insertTxCommand(address, data)

    def showError(self, str):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(str)
        msg.setWindowTitle("Chyba")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def closeEvent(self, event):  # overriden method from ui
        self.close()

    def keyPressEvent(self, event):
        # if event.key() == Qt.Key.Key_Escape:
        pass

    def update(self):
        values = self.MySQL.getCurrentValues()

        if values is not None:
            for name, vals in values.items():
                value = vals[0]
                last_update = vals[1]
                stripped = name.replace("temperature_", "").replace("status_", "")

                try:
                    idx = [x.name for x in self.all_params].index(stripped)
                except ValueError:
                    continue
                if (datetime.datetime.utcnow() - last_update).total_seconds() < 3600:
                    self.all_params[idx].update(value)
