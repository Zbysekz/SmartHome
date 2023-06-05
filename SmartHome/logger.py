import threading
from datetime import datetime
import pathlib
import traceback
import os
import sys
from parameters import Parameters

send_SMS = False
rootPath = str(pathlib.Path(__file__).parent.absolute())

class Logger:
    CRITICAL = 0
    NORMAL = 1
    RICH = 2
    FULL = 3

    phone = None

    def __init__(self, filename="main", verbosity=NORMAL):
        self.filename = filename
        self._terminate = False
        self.queue = []
        self.verbosity = verbosity

    def log(self, txt, _verbosity=NORMAL, all_members=False):
        if _verbosity > self.verbosity:
            return
        print(str(txt))

        dateStr = datetime.now().strftime('%Y-%m-%d')
        datetimeStr = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        path = f"/var/log/SmartHome/{dateStr}"
        if not os.path.exists(path):
            os.makedirs(path)

        with open(f"{path}/{self.filename}.log", "a") as file:
            file.write(datetimeStr + " >> " + str(txt) + "\n")

        all_ok = False
        if send_SMS:
            if _verbosity == Logger.CRITICAL:
                if len(self.queue) == 0:
                    all_ok = True
                    if all_members:
                        if not Logger.phone.SendSMS(Parameters.PETA_NUMBER, txt):  # no success
                            self.queue += [[Parameters.PETA_NUMBER, txt]]
                            all_ok = False
                    if not Logger.phone.SendSMS(Parameters.MY_NUMBER1, txt):  # no success
                        self.queue += [[Parameters.MY_NUMBER1, txt]]
                        all_ok = False

                    if not all_ok:
                        self.sendQueue()
                else:
                    if len(self.queue) < 4:
                        if all_members:
                            self.queue += [[Parameters.PETA_NUMBER, txt]]
                        self.queue += [[Parameters.MY_NUMBER1, txt]]
                        #self.queue += [[Parameters.PETA_NUMBER, txt]]

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

    def sendQueue(self):

        if len(self.queue) > 0:
            if Logger.phone.SendSMS(self.queue[0][0], self.queue[0][1]):
                self.queue.pop(0) # pop only in case of success

        if not self._terminate:  # do not continue if app terminated
            threading.Timer(60, self.sendQueue).start()

    def terminate(self):
        self._terminate = True
