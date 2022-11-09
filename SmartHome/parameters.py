import platform
import configparser
import pathlib
import os

rootPath = str(pathlib.Path(__file__).parent.absolute())

class Parameters:

    NORMAL = 0
    RICH = 1
    FULL = 2
    verbosity = NORMAL