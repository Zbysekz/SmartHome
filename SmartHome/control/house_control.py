import RPi.GPIO as GPIO
import time
import electricityPrice
import os
import sys
from databaseMySQL import cMySQL
from control.powerwall import cControlPowerwall
from datetime import datetime

PIN_BTN_PC = 26
PIN_GAS_ALARM = 23

actualHeatingInhibition = False
INHIBITED_ROOM_TEMPERATURE = 20.0  # °C


class cHouseControl:
    def __init__(self, logger, dataProcessor, commProcessor):
        self.logger = logger
        self.logger.log("Initializing pin for PC button & gas alarm...")
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_BTN_PC, GPIO.OUT)
        GPIO.setup(PIN_GAS_ALARM, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.logger.log("Ok")
        self.tmrPriceCalc = 0
        self.tmrVentHeatControl = 0
        self.mySQL = cMySQL()
        self.powerwallControl = cControlPowerwall(self.logger, dataProcessor, commProcessor, self.mySQL)
        self.dataProcessor = dataProcessor
        self.commProcessor = commProcessor
        self.tmrFastPowerwallControl = 0

    def handle(self):
        try:
            self.logger.log("entry handle")
            if time.time() - self.tmrPriceCalc > 3600 * 4:  # each 4 hour
                self.tmrPriceCalc = time.time()
                try:
                    electricityPrice.run()
                except Exception as e:
                    self.logger.log("Exception for electricityPrice.run()")
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    self.logger.log(str(e))
                    self.logger.log(str(exc_type) + " : " + str(fname) + " : " + str(exc_tb.tb_lineno))
                self.logger.log("solar cons handle")
                self.mySQL.update_day_solar_production()
                self.logger.log("Successfully run price calculation", self.logger.RICH)
        except Exception as e:
            self.logger.log_exception(e)

        if time.time() - self.tmrVentHeatControl > 300:  # each 5 mins
            self.tmrVentHeatControl = time.time()

            if len(self.dataProcessor.globalFlags) > 0 and len(self.dataProcessor.currentValues) > 0:  # we get both values from DTB
                self.powerwallControl.ControlPowerwall()
                self.ControlVentilation()
                self.ControlHeating()
            else:
                self.tmrVentHeatControl = time.time() - 200  # try it sooner

        if time.time() - self.tmrFastPowerwallControl > 30:  # each 30secs
            self.tmrFastPowerwallControl = time.time()

            self.powerwallControl.ControlPowerwall_fast()

    def TogglePCbutton(self):
        GPIO.output(PIN_BTN_PC, True)
        time.sleep(2)
        GPIO.output(PIN_BTN_PC, False)


    def ControlVentilation(self):  # called each 5 mins
        if self.dataProcessor.globalFlags['autoVentilation'] == 1:
            datetimeNow = datetime.now()
            dayTime = 7 < datetimeNow.hour < 21
            summerTime = 5 < datetimeNow.month < 9
            afterSchool = datetimeNow.weekday()<5 and datetimeNow.hour > 8 and\
                datetimeNow.hour < 10

            roomHumidity = self.dataProcessor.currentValues.get("humidity_PIR sensor")
            if roomHumidity is None:
                ventilationCommand = 99  # do not control
            else:
                if not summerTime:  # COLD OUTSIDE
                    if (roomHumidity >= 63.0 and dayTime) or (afterSchool and roomHumidity >= 61.0):
                        ventilationCommand = 4
                    elif roomHumidity >= 59.0 and dayTime:
                        ventilationCommand = 3
                    elif roomHumidity > 59.0:
                        ventilationCommand = 2
                    elif not dayTime:
                        ventilationCommand = 1
                    else:
                        ventilationCommand = 99
                else:  # WARM OUTSIDE
                    if (afterSchool and roomHumidity >= 61.0):
                        ventilationCommand = 4
                    elif roomHumidity >= 60.0 and dayTime:
                        ventilationCommand = 3
                    elif roomHumidity > 59.0 and dayTime:
                        ventilationCommand = 2
                    elif roomHumidity >= 60.0 and not dayTime:
                        ventilationCommand = -2
                    elif roomHumidity > 59.0 and not dayTime:
                        ventilationCommand = -1
                    else:
                        ventilationCommand = 99

        else:
            ventilationCommand = 99

        self.mySQL.updateState("ventilationCommand", ventilationCommand)

    def ControlHeating(self):  # called each 5 mins

        HYSTERESIS = 0.5  # +- °C
        roomTemperature = self.dataProcessor.currentValues.get("temperature_PIR sensor")
        heatingControlInhibit = self.dataProcessor.currentValues.get("status_heatingControlInhibit")

        if heatingControlInhibit:
            if roomTemperature is not None:
                if self.actualHeatingInhibition:
                    if roomTemperature <= INHIBITED_ROOM_TEMPERATURE - HYSTERESIS:
                        self.actualHeatingInhibition = False
                else:
                    if roomTemperature >= INHIBITED_ROOM_TEMPERATURE + HYSTERESIS:
                        self.actualHeatingInhibition = True

            if roomTemperature is not None and self.actualHeatingInhibition:
                self.commProcessor.heating_inhibition(True)
            else:
                self.commProcessor.heating_inhibition(False)
        else:
            self.commProcessor.heating_inhibition(False)  # not controlling