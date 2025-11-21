from parameters import parameters
if parameters.ON_RASPBERRY:
    import RPi.GPIO as GPIO
import time
import electricityPrice
import os
import sys
from databaseMySQL import cMySQL
from datetime import datetime

from logger import Logger
from templates.threadModule import cThreadModule

PIN_BTN_PC = 26
PIN_GAS_ALARM = 23

actualHeatingInhibition = False
INHIBITED_ROOM_TEMPERATURE = 20.0  # °C


def new_relative_humidity(rh_orig, t_orig, t_new):
    """
    Calculate the new relative humidity after a temperature change.

    Parameters:
    rh_orig (float): Original relative humidity in percent (e.g., 50 for 50%)
    t_orig (float): Original temperature in Celsius
    t_new (float): New temperature in Celsius

    Returns:
    float: New relative humidity in percent
    """

    def saturation_vapor_pressure(T):
        # T in Celsius
        if T != -237.3:
            return 6.11 * 10 ** (7.5 * T / (237.3 + T))
        return None
    if rh_orig is None or t_orig is None or t_new is None:
        return None
    es_orig = saturation_vapor_pressure(t_orig)
    es_new = saturation_vapor_pressure(t_new)
    if es_orig is not None and es_new is not None and es_new != 0:
        rh_new = rh_orig * es_orig / es_new
    else:
        rh_new = None
    return rh_new
# Example usage:
# new_relative_humidity(50, 20, 30)

class cHouseControl(cThreadModule):
    def __init__(self, dataProcessor, **kwargs):
        super().__init__(**kwargs)
        self.mySQL = cMySQL()

        self.logger = Logger("houseControl", verbosity=parameters.VERBOSITY, mySQL=self.mySQL)
        if parameters.ON_RASPBERRY:
            self.logger.log("Initializing pin for PC button & gas alarm...")
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(PIN_BTN_PC, GPIO.OUT)
            GPIO.setup(PIN_GAS_ALARM, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.logger.log("Ok")
        self.tmrPriceCalc = 0
        self.tmrVentHeatControl = 0

        self.dataProcessor = dataProcessor
        self.house_security = None
        self.commProcessor = None
        self.tmrUpdateVals = 0


    def _handle(self):
        if time.time() - self.tmrPriceCalc > 3600 * 2:  # each 2 hours
            self.tmrPriceCalc = time.time()
            try:
                electricityPrice.run()
            except Exception as e:
                self.logger.log("Exception for electricityPrice.run()")
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                self.logger.log(str(e))
                self.logger.log(str(exc_type) + " : " + str(fname) + " : " + str(exc_tb.tb_lineno))
            self.mySQL.update_day_solar_production()

        if time.time() - self.tmrVentHeatControl > 300:  # each 5 mins
            self.tmrVentHeatControl = time.time()

            if len(self.dataProcessor.globalFlags) > 0 and len(self.dataProcessor.currentValues) > 0:  # we get both values from DTB
                self.ControlVentilation()
                self.ControlHeating()
            else:
                self.tmrVentHeatControl = time.time() - 200  # try it sooner

        if time.time() - self.tmrUpdateVals > 30:  # each 30secs
            self.tmrUpdateVals = time.time()
            self.mySQL.PersistentConnect()
            self.dataProcessor.globalFlags = self.mySQL.getGlobalFlags()  # update global flags
            self.dataProcessor.currentValues = self.mySQL.getCurrentValues()
            self.mySQL.PersistentDisconnect()


    def CheckGasSensor(self):
        if self.gasSensorPrepared:
            if not GPIO.input(PIN_GAS_ALARM):
                self.house_security.gas_alarm_detected()

        else:
            if time.time() - self.tmrPrepareGasSensor > 120:  # after 2 mins
                self.gasSensorPrepared = True

    def TogglePCbutton(self):
        GPIO.output(PIN_BTN_PC, True)
        time.sleep(2)
        GPIO.output(PIN_BTN_PC, False)

    def ControlVentilation(self):  # called each 5 mins
        if self.dataProcessor.globalFlags['autoVentilation'] == 1:
            datetimeNow = datetime.now()
            dayTime = 7 < datetimeNow.hour < 21
            summerTime = 5 < datetimeNow.month < 9

            roomHumidity = self.dataProcessor.currentValues.get("humidity_PIR sensor")
            outsideTemperature = self.dataProcessor.currentValues.get("temperature_meteostation")
            roomTemperature = self.dataProcessor.currentValues.get("temperature_PIR sensor")
            outsideHumidity = self.dataProcessor.currentValues.get("humidity_meteostation")

            humidityFromOutsideHeated = new_relative_humidity(outsideHumidity, outsideTemperature,
                                                              roomTemperature)

            self.mySQL.insertValue('humidity_from_outside_heated', 'calculated',
                                   humidityFromOutsideHeated,
                                   periodicity=240 * 60,  # with correction
                                   writeNowDiff=1,
                                   onlyCurrent=True)
            if roomHumidity is None:
                ventilationCommand = 99  # do not control
            else:
                if not summerTime:  # COLD OUTSIDE
                    if roomHumidity >= 63.0 and dayTime:
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
                    if roomHumidity >= 61.0:
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

                # limit if there is lot of moisture outside and the temperature difference is small
                if humidityFromOutsideHeated is not None:
                    if ventilationCommand == 4 and roomHumidity - humidityFromOutsideHeated < 30.0:
                        ventilationCommand = 3
                    elif ventilationCommand == 3 and roomHumidity - humidityFromOutsideHeated < 20.0:
                        ventilationCommand = 2
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
