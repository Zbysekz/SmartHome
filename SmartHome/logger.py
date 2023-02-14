from datetime import datetime
import pathlib
import traceback
import os
import sys
from parameters import Parameters

rootPath = str(pathlib.Path(__file__).parent.absolute())

class Logger:
    def __init__(self, filename="main"):
        self.filename = filename

    def log(self, txt, _verbosity=Parameters.NORMAL, filename="main"):
        if _verbosity > Parameters.verbosity:
            return
        print(str(txt))

        dateStr = datetime.now().strftime('%Y-%m-%d')
        datetimeStr = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(f"/var/log/SmartHome/{dateStr}_{filename}.log", "a") as file:
            file.write(datetimeStr + " >> " + str(txt) + "\n")

    def log_exception(self, e):
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        self.log(str(e))
        self.log(str(exc_type) + " : " + str(fname) + " : " + str(exc_tb.tb_lineno))

        #self.log(traceback.format_exc())

        # exc_type, exc_obj, exc_tb = sys.exc_info()
        # fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        # Log(str(e))
        # Log(str(exc_type) +" : "+ str(fname) + " : " +str(exc_tb.tb_lineno))
