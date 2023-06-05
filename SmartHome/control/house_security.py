from parameters import parameters
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
        self.phone = phone



        self.alarmCounting = False  # when door was opened and system locked
        self.alarmCnt = 0

        self.alarm = False
        self.locked = False

    def deactivate_alarm(self):
        self.alarm = False

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
                self.alarm |= cHouseSecurity.DOOR_ALARM
                self.alarmCounting = False

                self.phone.SendSMS(parameters.MY_NUMBER1, "Home system: door ALARM !!")

                self.mySql.updateState("alarm", int(self.alarm))
                self.commProcessor.KeyboardRefresh(self.alarm, self.locked)
                self.commProcessor.PIRSensorRefresh(self.alarm, self.locked)

    def keyboard_data_receive(self, doorSW):
        if doorSW and self.locked and (self.alarm & cHouseSecurity.DOOR_ALARM) == 0 and not self.alarmCounting:
            alarmCounting = True
            self.logger.log("LOCKED and DOORS opened")

    def PIR_sensor_data_receive(self):
        return
        if self.gasAlarm2:
            self.logger.log("PIR GAS ALARM!!")
            self.alarm |= cHouseSecurity.GAS_ALARM_PIR
            if self.alarm_last & cHouseSecurity.GAS_ALARM_PIR == 0:
                self.mySQL.updateState("alarm", int(self.alarm))

                txt = "Home system: PIR sensor - FIRE/GAS ALARM !!"
                self.logger.log(txt)
                self.mySQL.insertEvent(10, 0)
                self.phone.SendSMS(parameters.MY_NUMBER1, txt)
        elif self.PIRalarm and self.locked:
            self.alarm |= cHouseSecurity.PIR_ALARM
            if (self.alarm_last & cHouseSecurity.PIR_ALARM == 0):
                self.mySQL.updateState("alarm", int(self.alarm))

                txt = "Home system: PIR sensor - MOVEMENT ALARM !!"
                self.logger.log(txt)
                self.mySQL.insertEvent(10, 1)

                self.phone.SendSMS(parameters.MY_NUMBER1, txt)

    def keyboard_event(self, data):
        return
        alarmLast = self.alarm
        lockLast = self.locked
        if data[0] == 3:
            if data[1] == 2:  # lock
                house_security.lock_house()
                self.logger.log("LOCKED by keyboard")
            if data[1] == 4:  # doors opened and locked
                if alarm == 0 and locked:
                    alarmCounting = True
                self.logger.log("LOCKED and DOORS opened event")
        if data[0] == 1:
            if data[1] == 1:  # unlock PIN
                locked = False
                alarm = 0
                alarmCounting = False
                alarmCnt = 0
                self.logger.log("UNLOCKED by keyboard PIN")
                house_security.unlock_house()

        if data[0] == 2:
            if data[1] == 0:  # unlock RFID
                locked = False
                alarm = 0
                alarmCounting = False
                alarmCnt = 0
                self.logger.log("UNLOCKED by keyboard RFID")
                house_security.unlock_house()

        if (lockLast != locked or alarmLast != alarm):  # change in locked state or alarm state
            KeyboardRefresh(self.mySQL)
            PIRSensorRefresh(self.mySQL)

            self.mySQL.updateState("locked", int(locked))
            self.mySQL.updateState("alarm", int(alarm))

            # if locked:
            #    os.system("sudo service motion start")
            # else:
            #    os.system("sudo service motion stop")