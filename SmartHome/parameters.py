import platform
import configparser
import pathlib
import os

rootPath = str(pathlib.Path(__file__).parent.absolute())

class Parameters:

    CRITICAL = 0
    NORMAL = 1
    RICH = 2
    FULL = 3


    MY_NUMBER1 = "+420602187490"
    PETA_NUMBER = "+420777438947"