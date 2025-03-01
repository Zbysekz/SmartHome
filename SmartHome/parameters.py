import platform
import configparser
import pathlib
import os

rootPath = str(pathlib.Path(__file__).parent.absolute())

class Parameters:
    config = configparser.ConfigParser()
    config.read('../config.ini')

    ON_RASPBERRY = platform.machine() != "x86_64"

    #MY_NUMBER1 = "+420602187490"
    #SECOND_NUMBER = "+420777438947"

    def __init__(self):
        config = configparser.ConfigParser()
        configPath = os.path.join(rootPath, '../config.ini')
        cnt = len(config.read(configPath))

        if cnt == 0:
            raise RuntimeError("Cannot open config.ini file in working directory!")

        for p in config.items():
            for p2 in config[p[0]].items():
                setattr(self, p2[0].upper(), p2[1])

        # special conversion for verbosity
        if type(self.VERBOSITY) == str:
            self.VERBOSITY = int(self.verbosity_convert(config['debug']['verbosity']))

        if hasattr(self, "DEBUG_FLAG"):
            self.DEBUG_FLAG = eval(self.DEBUG_FLAG)
        if hasattr(self, "INSTANCE_CHECK"):
            self.INSTANCE_CHECK = eval(self.INSTANCE_CHECK)
    def verbosity_convert(self, name):
        d = {"CRITICAL": 0, "NORMAL": 1, "RICH": 2, "FULL": 3}
        return d[name]

    def save(self):
        config = configparser.ConfigParser()
        configPath = os.path.join(rootPath, '../config.ini')
        cnt = len(config.read(configPath))
        if cnt == 0:
            raise RuntimeError("Cannot open config.ini file in working directory!")

        for p in config.items():
            for p2 in config[p[0]].items():
                config.set(p[0], p2[0], str(getattr(self, p2[0].upper(), p2[1])))
        with open(os.path.join(rootPath, '../config.ini'), 'w') as configfile:
            config.write(configfile)

parameters = Parameters()

