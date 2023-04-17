import platform
import configparser
import pathlib
import os

rootPath = str(pathlib.Path(__file__).parent.absolute())

class Parameters:

    NORMAL = 0
    RICH = 1
    FULL = 2

    MY_NUMBER1 = "+420602187490"
    PETA_NUMBER = "+420777438947"