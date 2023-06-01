
from logger import Logger

class cHouseSecurity:
    NO_ALARM = 0x00
    DOOR_ALARM = 0x01  # DOOR ALARM when system was locked
    GAS_ALARM_RPI = 0x02  # GAS alarm of the RPI module
    GAS_ALARM_PIR = 0x04  # GAS alarm of the PIR sensor module
    PIR_ALARM = 0x08  # PIR sensor detected motion when system was locked

    def __init__(self, logger, mySql, commProcessor, dataProcessor, phone):
        self.logger = logger
        self.mySql = mySql
        self.commProcessor = commProcessor
        self.dataProcessor = dataProcessor

        self.alarmCounting = False  # when door was opened and system locked
        self.alarmCnt = 0

        self.alarm = False
        self.locked = False

    def lock_house(self):
        self.locked = 1
        self.mySql.updateState("locked", int(self.locked))
        self.mySql.updateState("alarm", int(self.alarm))
    def unlock_house(self):
        self.alarm = 0
        self.locked = 0
        self.mySql.updateState("alarm", int(self.alarm))
        self.commProcessor.KeyboardRefresh(self.alarm, self.locked)
        self.commProcessor.PIRSensorRefresh(self.alarm, self.locked)

    def handle(self):
        if self.alarmCounting:  # user must make unlock until counter expires
            self.logger.log("Alarm check", Logger.FULL)
            self.alarmCnt += 1
            if self.alarmCnt >= 10:
                self.alarmCnt = 0

                self.logger.log("DOOR ALARM!!!!")
                self.alarm |= DOOR_ALARM
                self.alarmCounting = False

                self.phone.SendSMS(parameters.MY_NUMBER1, "Home system: door ALARM !!")

                self.mySql.updateState("alarm", int(self.alarm))
                self.commProcessor.KeyboardRefresh(self.alarm, self.locked)
                self.commProcessor.PIRSensorRefresh(self.alarm, self.locked)