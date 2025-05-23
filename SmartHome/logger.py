from datetime import datetime
import pathlib
import os
import sys

send_notification = True
rootPath = str(pathlib.Path(__file__).parent.absolute())

class Logger:
    CRITICAL = 0
    NORMAL = 1
    RICH = 2
    FULL = 3

    phone = None

    def __init__(self, filename="main", verbosity=NORMAL, mySQL=None):
        self.mySQL = mySQL
        self.filename = filename
        self._terminate = False
        self.queue = []
        self.verbosity = verbosity

    def log(self, txt, _verbosity=NORMAL):
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

        try:
            if send_notification:
                if _verbosity == Logger.CRITICAL and self.mySQL:
                    self.mySQL.add_to_notificator_queue(subject='SmartHome critical error', text=txt)
                    #if len(self.queue) == 0:
                        # if all_members:
                        #     if not Logger.phone.SendSMS(parameters.SECOND_NUMBER, txt):  # no success
                        #         self.queue += [[parameters.SECOND_NUMBER, txt]]
                        # if not Logger.phone.SendSMS(parameters.MY_NUMBER1, txt):  # no success
                        #     self.queue += [[parameters.MY_NUMBER1, txt]]

                    # else:
                    #     if len(self.queue) < 4:
                    #         if all_members:
                    #             self.queue += [[parameters.SECOND_NUMBER, txt]]
                    #         self.queue += [[parameters.MY_NUMBER1, txt]]
        except Exception as e:
            with open(f"{path}/{self.filename}.log", "a") as file:
                file.write(datetimeStr + " >> " + str(repr(e)) + "\n")

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

    # def sendQueue(self):
    #     try:
    #         if len(self.queue) > 0:
    #             if Logger.phone.SendSMS(self.queue[0][0], self.queue[0][1]):
    #                 self.queue.pop(0)  # pop only in case of success
    #     except Exception as e:
    #         self.log_exception(e)
       # if not self._terminate:  # do not continue if app terminated
         #   threading.Timer(60, self.sendQueue).start()

    def terminate(self):
        self._terminate = True
