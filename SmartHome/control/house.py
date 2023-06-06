import RPi.GPIO as GPIO
import time
import electricityPrice
import os
import sys

PIN_BTN_PC = 26
PIN_GAS_ALARM = 23

actualHeatingInhibition = False
INHIBITED_ROOM_TEMPERATURE = 20.0  # °C


class cHouseControl:
    def __init__(self, logger):
        self.logger = logger
        self.logger.log("Initializing pin for PC button & gas alarm...")
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_BTN_PC, GPIO.OUT)
        GPIO.setup(PIN_GAS_ALARM, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.logger.log("Ok")
        self.tmrPriceCalc = 0
        self.tmrVentHeatControl = 0

    def handle(self):
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
            updateStats.execute_4hour(MySQL_GeneralThread)


        if time.time() - self.tmrVentHeatControl > 300:  # each 5 mins
            tmrVentHeatControl = time.time()

            if len(globalFlags) > 0 and len(currentValues) > 0:  # we get both values from DTB
                ControlPowerwall()
                ControlVentilation()
                ControlHeating()
            else:
                tmrVentHeatControl = time.time() - 200  # try it sooner

        if time.time() - tmrFastPowerwallControl > 30:  # each 30secs
            tmrFastPowerwallControl = time.time()
            globalFlags = MySQL_GeneralThread.getGlobalFlags()  # update global flags
            currentValues = MySQL_GeneralThread.getCurrentValues()

            ControlPowerwall_fast()

    def CheckGasSensor(self):
        if gasSensorPrepared:
            if not GPIO.input(PIN_GAS_ALARM):
                logger.log("RPI GAS ALARM!!");
                alarm |= GAS_ALARM_RPI
                MySQL.updateState("alarm", int(alarm))
                if alarm_last & GAS_ALARM_RPI == 0:
                    phone.SendSMS(Parameters.MY_NUMBER1, "Home system: fire/gas ALARM - RPI !!")
                KeyboardRefresh(MySQL)
                PIRSensorRefresh(MySQL)

        else:
            if time.time() - tmrPrepareGasSensor > 120:  # after 2 mins
                gasSensorPrepared = True

    def TogglePCbutton():
        global PIN_BTN_PC
        GPIO.output(PIN_BTN_PC, True)
        time.sleep(2)
        GPIO.output(PIN_BTN_PC, False)


    def ControlVentilation():  # called each 5 mins
        if globalFlags['autoVentilation'] == 1:
            datetimeNow = datetime.now()
            dayTime = 7 < datetimeNow.hour < 21
            summerTime = 5 < datetimeNow.month < 9
            afterSchool = datetimeNow.weekday()<5 and datetimeNow.hour > 8 and\
                datetimeNow.hour < 10

            roomHumidity = currentValues.get("humidity_PIR sensor")
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

        MySQL_GeneralThread.updateState("ventilationCommand", ventilationCommand)

    def ControlHeating(self):  # called each 5 mins

        HYSTERESIS = 0.5  # +- °C
        roomTemperature = currentValues.get("temperature_PIR sensor")
        heatingControlInhibit = currentValues.get("status_heatingControlInhibit")

        if heatingControlInhibit:
            if roomTemperature is not None:
                if actualHeatingInhibition:
                    if roomTemperature <= INHIBITED_ROOM_TEMPERATURE - HYSTERESIS:
                        actualHeatingInhibition = False
                else:
                    if roomTemperature >= INHIBITED_ROOM_TEMPERATURE + HYSTERESIS:
                        actualHeatingInhibition = True

            if roomTemperature is not None and actualHeatingInhibition:
                comm.Send(MySQL, bytes([1, 1]), IP_RACKUNO)
            else:
                comm.Send(MySQL, bytes([1, 0]), IP_RACKUNO)
        else:
            comm.Send(MySQL, bytes([1, 0]), IP_RACKUNO)  # not controlling