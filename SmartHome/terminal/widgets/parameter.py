from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, \
    QGraphicsPixmapItem, QGraphicsScene
from PyQt5.QtGui import QPixmap
import datetime
from PyQt5.QtCore import pyqtSignal

class ParameterLine(QWidget):
    def __init__(self, name, id, callback_change :pyqtSignal, type):
        super(ParameterLine, self).__init__()  # Call the inherited classes __init__ method
        if type == 1:
            uic.loadUi('./widgets/parameter.ui', self)  # Load the .ui file
        else:
            uic.loadUi('./widgets/parameter2.ui', self)  # Load the .ui file
            self.label_real_2.setText("(?)")

        # self.show() # Show the GUI
        self.label.setText(name)
        self.label_real.setText("(?)")
        self.callback_change = callback_change
        self.btnSet.clicked.connect(self.setPar)
        self.id = id
        self.type = type
        self.name = name

    def setPar(self):
        if self.type == 1:
            self.callback_change.emit(str(self.id), str(self.spinBox.value()), "0")
        else:
            self.callback_change.emit(str(self.id), str(self.spinBox.value()), str(int(self.doubleSpinBox.value()*10)))

    def update(self, value):
        self.label_real.setText(str(value))
    def update2(self, value2):
        self.label_real_2.setText(str(value2))