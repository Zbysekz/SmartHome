import queue

from databaseMySQL import cMySQL
from templates.threadModule import cThreadModule
from control.house_security import cHouseSecurity
from logger import Logger
import struct
from control.powerwall import calculatePowerwallSOC
import time
from parameters import parameters
from avg import cMovingAvg

# for periodicity mysql inserts
HOUR = 3600
MINUTE = 60


class cDataProcessor(cThreadModule):
    def __init__(self, phone, **kwargs):
        super().__init__(**kwargs)
        self.mySQL = cMySQL()
        self.logger = Logger("dataProcessor", verbosity=parameters.VERBOSITY)
        self.phone = phone
        self.house_security = None
        self.house_control = None
        self.commProcessor = None
        self.bufferedCellModVoltage = 24 * [0]

        self.tmrConsPowerwall = 0
        self.tmrCurrentValues = 0
        self.avg_water_tank = cMovingAvg(10)

        # -------------STATE VARIABLES-------------------
        self.globalFlags = {}  # contains data from table globalFlags - controls behaviour of subsystems
        self.currentValues = {}  # contains latest measurements data

        self.receive_queue = queue.Queue()

    @classmethod
    def correctNegative(cls, val):
        if val > 32767:
            return val - 65536
        return val

    def data_received(self, data):  # called from commProcessor with data received
        try:
            self.receive_queue.put(data)
        except queue.Full:
            self.logger.Log("Queue in dataProcessor is FULL!!")

    def _handle(self):

        self.mySQL.PersistentConnect()
        while self.receive_queue.qsize() > 0:
            try:
                data = self.receive_queue.get(block=False)
            except queue.Empty:
                return
            if data:
                try:
                    self.process_incoming_data(data)

                    if time.time() - self.tmrCurrentValues > 5:
                        self.tmrCurrentValues = time.time()
                        self.currentValues = self.mySQL.getCurrentValues()
                        self.globalFlags = self.mySQL.getGlobalFlags()
                except IndexError:
                    self.logger.log("IndexError while processing incoming data! data:" + str(data))
                except Exception as e:
                    self.logger.log(f"General exception while processing incoming data! data: {data}")
                    self.logger.log_exception(e)
        self.mySQL.PersistentDisconnect()
        # -------------------------------------------------

    def process_incoming_data(self, data):

        self.logger.log("Processing incoming data:" + str(data), Logger.FULL)
        # [100, 3, 0, 0, 1, 21, 2, 119]
        # ID,(bit0-door,bit1-gasAlarm),gas/256,gas%256,T/256,T%256,RH/256,RH%256)
        if data[0] == 100:  # data from keyboard
            doorSW = False if (data[1] & 0x01) == 0 else True
            gasAlarm = True if (data[1] & 0x02) == 0 else False
            gas = data[2] * 256 + data[3]
            temp = (data[4] * 256 + data[5]) / 10 + 0.5
            RH = (data[6] * 256 + data[7]) / 10

            self.mySQL.insertValue('bools', 'door switch 1', doorSW, periodicity=120 * MINUTE, writeNowDiff=1)
            # self.mySQL.insertValue('bools','gas alarm 1',gasAlarm,periodicity =30*MINUTE, writeNowDiff = 1)
            # self.mySQL.insertValue('gas','keyboard',gas)
            self.mySQL.insertValue('temperature', 'keyboard', temp, periodicity=60 * MINUTE, writeNowDiff=1)
            self.mySQL.insertValue('humidity', 'keyboard', RH, periodicity=60 * MINUTE, writeNowDiff=1)

            self.house_security.keyboard_data_receive(doorSW)

        elif data[0] == 101:  # data from meteostations
            meteoTemp = cDataProcessor.correctNegative((data[1] * 256 + data[2]))

            self.mySQL.insertValue('temperature', 'meteostation 1', meteoTemp / 100, periodicity=60 * MINUTE,
                                   writeNowDiff=0.5)
            self.mySQL.insertValue('pressure', 'meteostation 1', (data[3] * 65536 + data[4] * 256 + data[5]) / 100,
                                   periodicity=50 * MINUTE, writeNowDiff=100)
            self.mySQL.insertValue('voltage', 'meteostation 1', (data[6] * 256 + data[7]) / 1000,
                                   periodicity=50 * MINUTE,
                                   writeNowDiff=0.2)

        elif data[0] > 10 and data[0] <= 40:  # POWERWALL
            voltage = (data[2] * 256 + data[3]) / 100
            if data[1] < 24:
                self.bufferedCellModVoltage[
                    data[1]] = voltage   # we need to store voltages for each module, to calculate burning energy later
            temp = (data[4] * 256 + data[5]) / 10

            if voltage < 5:
                self.mySQL.insertValue('voltage', 'powerwall cell ' + str(data[1]), voltage, periodicity=30 * MINUTE,
                                       writeNowDiff=0.1)
            if temp < 70:
                self.mySQL.insertValue('temperature', 'powerwall cell ' + str(data[1]), temp, periodicity=30 * MINUTE,
                                       writeNowDiff=0.5)
        elif data[0] == 10:  # POWERWALL STATUS
            powerwall_stateMachineStatus = data[1]
            errorStatus = data[2]
            errorStatus_cause = data[3]
            solarConnected = (data[4] & 0x01) != 0
            heating = (data[4] & 0x02) != 0
            err_module_no = data[5]

            self.mySQL.insertValue('status', 'powerwall_stateMachineStatus', powerwall_stateMachineStatus,
                                   periodicity=30 * MINUTE, writeNowDiff=1)
            self.mySQL.insertValue('status', 'powerwall_errorStatus', errorStatus, periodicity=60 * MINUTE,
                                   writeNowDiff=1)
            self.mySQL.insertValue('status', 'powerwall_errorStatus_cause', errorStatus_cause, periodicity=60 * MINUTE,
                                   writeNowDiff=1)
            self.mySQL.insertValue('status', 'powerwall_solarConnected', solarConnected, periodicity=60 * MINUTE,
                                   writeNowDiff=1)
            self.mySQL.insertValue('status', 'powerwall_heating', heating, periodicity=60 * MINUTE,
                                   writeNowDiff=1)
            self.mySQL.insertValue('status', 'powerwall_err_module_no', err_module_no, periodicity=60 * MINUTE,
                                   writeNowDiff=1)

        elif data[0] == 69:  # general statistics from powerwall
            P = 300.0 * 1 / 7.0  # power of the heating element * duty_cycle : duty_cycle is ratio is 1:6 so 1/7
            WhValue = (data[2] * 256 + data[1]) * P / 360.0  # counting pulse per 10s => 6 = P*1Wmin => P/360Wh
            if WhValue > 0:
                self.mySQL.insertValue('consumption', 'powerwall_heating', WhValue)
            if data[3] > 0:
                self.logger.log("CRC mismatch counter of BMS_controller not zero! Value:" + str(data[3]))
        elif data[0] > 40 and data[0] <= 69:  # POWERWALL - calibrations
            volCal = struct.unpack('f', bytes([data[2], data[3], data[4], data[5]]))[0]
            tempCal = struct.unpack('f', bytes([data[6], data[7], data[8], data[9]]))[0]

            # self.mySQL.insertValue('BMS calibration','powerwall calib.'+str(data[1])+' volt',volCal,one_day_RP=True);
            # self.mySQL.insertValue('BMS calibration','powerwall calib.'+str(data[1])+' temp',tempCal,one_day_RP=True);
        elif data[0] > 70 and data[0] < 99:  # POWERWALL - statistics
            valueToWrite = (data[2] * 256 + data[3])

            self.mySQL.insertValue('counter', 'powerwall cell ' + str(data[1]), valueToWrite, periodicity=60 * MINUTE,
                                   writeNowDiff=1)

            # compensate dimensionless value from module to represent Wh
            # P=(U^2)/R
            # BurnedEnergy[Wh] = P*T/60
            if data[1] < 24:
                bufVolt = self.bufferedCellModVoltage[data[1]]
                if bufVolt == 0:
                    bufVolt = 4  # it is too soon to have buffered voltage
            else:
                bufVolt = 4  # some sensible value if error occurs
            val = (data[4] * 256 + data[5])  # this value is counter for how long bypass was switched on
            T = 10  # each 10 min data comes.
            R = 2  # Ohms of burning resistor
            # coeficient, depends on T and on timer on cell module,
            # e.g. we get this value if we are burning 100% of period T
            valFor100Duty = 462 * T

            Energy = (pow(bufVolt, 2) / R) * T / 60.0
            Energy = Energy * (min(val, valFor100Duty) / valFor100Duty)  # duty calculation

            if Energy > 0:
                self.mySQL.insertValue('consumption', 'powerwall cell ' + str(data[1]), Energy);

        elif data[0] == 102:  # data from Roomba
            self.mySQL.insertValue('voltage', 'roomba cell 1', (data[1] * 256 + data[2]) / 1000,
                                   periodicity=60 * MINUTE,
                                   writeNowDiff=0.2)
            self.mySQL.insertValue('voltage', 'roomba cell 2', (data[3] * 256 + data[4]) / 1000,
                                   periodicity=60 * MINUTE,
                                   writeNowDiff=0.2)
            self.mySQL.insertValue('voltage', 'roomba cell 3', (data[5] * 256 + data[6]) / 1000,
                                   periodicity=60 * MINUTE,
                                   writeNowDiff=0.2)
        elif data[0] == 103:  # data from rackUno
            # store power
            self.mySQL.insertValue('power', 'grid', (data[1] * 256 + data[2]), periodicity=30 * MINUTE, writeNowDiff=50)

            # now store consumption according to tariff
            stdTariff = (data[5] & 0x01) == 0
            detectSolarPower = (data[5] & 0x02) == 0
            rackUno_heatingInhibition = (data[5] & 0x04) == 0

            self.mySQL.insertValue('status', 'rackUno_detectSolarPower', int(detectSolarPower), periodicity=6 * HOUR,
                                   writeNowDiff=1)

            self.mySQL.insertValue('status', 'rackUno_heatingInhibition', int(rackUno_heatingInhibition),
                                   periodicity=6 * HOUR,
                                   writeNowDiff=1)

            if not stdTariff:  # T1 - low tariff
                self.mySQL.insertValue('consumption', 'lowTariff',
                                       (data[3] * 256 + data[4]) / 60)  # from power to consumption - 1puls=1Wh
            else:
                self.mySQL.insertValue('consumption', 'stdTariff',
                                       (data[3] * 256 + data[4]) / 60)  # from power to consumption - 1puls=1Wh

            rackUno_stateMachineStatus = data[6]
            self.mySQL.insertValue('status', 'rackUno_stateMachineStatus', rackUno_stateMachineStatus,
                                   periodicity=6 * HOUR,
                                   writeNowDiff=1)

            raw = data[7] * 256 + data[8]

            # if dist_cm < 11:
            #     waterTank_level = 100.0
            # elif dist_cm > 191:
            #     waterTank_level = 0.0
            # else:
            #     waterTank_level = (191.0 - dist_cm) / 180.0 * 100

            waterTank_level = 100 * (-raw*0.000244052235241*raw+0.093727045956581*raw+171.116013166274)/180.0
            waterTank_level = max(0, min(waterTank_level, 100))
            self.avg_water_tank.append_value(waterTank_level)

            self.mySQL.insertValue('status', 'waterTank_level', self.avg_water_tank.value, periodicity=6 * HOUR,
                                   writeNowDiff=1)
            self.mySQL.insertValue('status', 'waterTank_level_raw', raw, periodicity=1 * HOUR,
                                   writeNowDiff=0.5)

        elif data[0] == 104:  # data from PIR sensor
            tempPIR = (data[1] * 256 + data[2]) / 10.0
            tempPIR = tempPIR - 0.0  # calibration - SHT20 is precalibrated from factory

            humidPIR = (data[3] * 256 + data[4]) / 10.0

            # check validity and store values
            if tempPIR > -30.0 and tempPIR < 80.0:
                self.mySQL.insertValue('temperature', 'PIR sensor', tempPIR, periodicity=60 * MINUTE, writeNowDiff=1)

            if humidPIR >= 0.0 and tempPIR <= 100.0:
                self.mySQL.insertValue('humidity', 'PIR sensor', humidPIR, periodicity=60 * MINUTE, writeNowDiff=1)

            self.mySQL.insertValue('gas', 'PIR sensor', (data[5] * 256 + data[6]), periodicity=60 * MINUTE,
                                   writeNowDiff=50)
        elif data[0] == 105:  # data from PIR sensor
            gasAlarm2 = data[1]
            PIRalarm = data[2]

            self.house_security.PIR_sensor_data_receive()

        elif data[0] == 106:  # data from powerwall ESP
            batteryStatus = data[13] * 256 + data[14]
            self.mySQL.insertValue('status', 'powerwallEpeverBatteryStatus', batteryStatus, periodicity=6 * HOUR,
                                   writeNowDiff=1)
            self.mySQL.insertValue('status', 'powerwallEpeverChargerStatus', data[15] * 256 + data[16],
                                   periodicity=6 * HOUR,
                                   writeNowDiff=1)
            self.logger.log("status inserted", _verbosity=Logger.FULL)
            if batteryStatus == 0 and (
                    self.currentValues.get('status_powerwall_stateMachineStatus') == 10 or self.currentValues.get(
                'status_powerwall_stateMachineStatus') == 20):  # valid only if epever reports battery ok and battery is really connected
                powerwallVolt = (data[1] * 256 + data[2]) / 100.0
                self.mySQL.insertValue('voltage', 'powerwallSum', powerwallVolt, periodicity=60 * MINUTE,
                                       writeNowDiff=0.5)
                soc = calculatePowerwallSOC(powerwallVolt)
                self.mySQL.insertValue('status', 'powerwallSoc', soc, periodicity=2 * HOUR, writeNowDiff=1)

            temperature = cDataProcessor.correctNegative(data[3] * 256 + data[4])

            self.mySQL.insertValue('temperature', 'powerwallOutside', temperature / 100.0, periodicity=30 * MINUTE,
                                   writeNowDiff=2)
            solarPower = (data[5] * 16777216 + data[6] * 65536 + data[7] * 256 + data[8]) / 100.0
            self.mySQL.insertValue('power', 'solar', solarPower)

            if batteryStatus == 0 and time.time() - self.tmrConsPowerwall > 3600:  # each hour
                self.logger.log("Daily solar cons", _verbosity=Logger.RICH)
                self.tmrConsPowerwall = time.time()
                self.mySQL.insertDailySolarCons((data[9] * 16777216 + data[10] * 65536 + data[11] * 256 + data[12]) * 10.0)  # in 0.01 kWh
                self.logger.log("process completed", _verbosity=Logger.RICH)

        elif data[0] == 107:  # data from brewhouse
            self.mySQL.insertValue('temperature', 'brewhouse_horkaVoda', (data[1] * 256 + data[2]) / 100.0 + 6.0,
                                   # with correction
                                   periodicity=5 * MINUTE,
                                   writeNowDiff=0.1)
            self.mySQL.insertValue('temperature', 'brewhouse_horkaVoda_setpoint', (data[3] * 256 + data[4]) / 100.0,
                                   periodicity=5 * MINUTE,
                                   writeNowDiff=0.1)
            self.mySQL.insertValue('temperature', 'brewhouse_rmut', (data[5] * 256 + data[6]) / 100.0,
                                   periodicity=5 * MINUTE,
                                   writeNowDiff=0.1)
        elif data[0] == 108:  # data from chiller
            temperature = cDataProcessor.correctNegative(data[1] * 256 + data[2])

            self.mySQL.insertValue('temperature', 'powerwall_thermostat', temperature / 100.0,
                                   periodicity=5 * MINUTE,
                                   writeNowDiff=0.1)
        elif data[0] == 109:  # data from cellar
            bits = data[1]

            temperature_sht = cDataProcessor.correctNegative(data[2] * 256 + data[3])
            humidity = (data[4] * 256 + data[5])
            dew_point = cDataProcessor.correctNegative(data[6] * 256 + data[7])
            temp_setpoint = cDataProcessor.correctNegative(data[8] * 256 + data[9])
            temperature1 = cDataProcessor.correctNegative(data[10] * 256 + data[11])
            temperature2 = cDataProcessor.correctNegative(data[12] * 256 + data[13])

            params_valid = bits & 0x01
            errorFlags = bits & 0x02
            water_pump_alarm = bits & 0x04
            fanControl_autMan = bits & 0x08
            tempControl_autMan = bits & 0x10
            tempPump_onOff = bits & 0x20
            reserve = bits & 0x40
            fan_active = 0

            self.mySQL.insertValue('status', 'cellar_params_valid', params_valid,
                                   periodicity=240 * MINUTE,  # with correction
                                   writeNowDiff=0.1,
                                   onlyCurrent=True)
            self.mySQL.insertValue('temperature', 'cellar_errorFlags', errorFlags,
                                   periodicity=240 * MINUTE,  # with correction
                                   writeNowDiff=0.1,
                                   onlyCurrent=True)
            self.mySQL.insertValue('temperature', 'cellar_water_pump_alarm', water_pump_alarm,
                                   periodicity=240 * MINUTE,  # with correction
                                   writeNowDiff=0.1,
                                   onlyCurrent=True)
            self.mySQL.insertValue('temperature', 'cellar_fanControl_autMan', fanControl_autMan,
                                   periodicity=240 * MINUTE,  # with correction
                                   writeNowDiff=0.1,
                                   onlyCurrent=True)
            self.mySQL.insertValue('temperature', 'cellar_tempControl_autMan', tempControl_autMan,
                                   periodicity=240 * MINUTE,  # with correction
                                   writeNowDiff=0.1,
                                   onlyCurrent=True)
            self.mySQL.insertValue('temperature', 'cellar_tempPump_onOff', tempPump_onOff,
                                   periodicity=240 * MINUTE,  # with correction
                                   writeNowDiff=0.1,
                                   onlyCurrent=True)
            self.mySQL.insertValue('temperature', 'cellar_temp_setpoint', temp_setpoint,
                                   periodicity=240 * MINUTE,  # with correction
                                   writeNowDiff=0.5,
                                   onlyCurrent=True)

            self.mySQL.insertValue('temperature', 'brewhouse_cellar', temperature2 / 10.0,
                                   periodicity=5 * MINUTE,  # with correction
                                   writeNowDiff=0.1)
            self.mySQL.insertValue('temperature', 'brewhouse_cellarbox', temperature1 / 10.0,
                                   periodicity=5 * MINUTE,  # with correction
                                   writeNowDiff=0.1)
            self.mySQL.insertValue('temperature', 'brewhouse_room', temperature_sht / 10.0,
                                   periodicity=5 * MINUTE,  # with correction
                                   writeNowDiff=0.1)
            self.mySQL.insertValue('humidity', 'brewhouse_room', humidity / 10.0,
                                   periodicity=5 * MINUTE,  # with correction
                                   writeNowDiff=0.5)
            self.mySQL.insertValue('temperature', 'brewhouse_dew_point', dew_point / 10.0,
                                   periodicity=5 * MINUTE,  # with correction
                                   writeNowDiff=0.1)
            self.mySQL.insertValue('bools', 'brewhouse_fan', fan_active,
                                   periodicity=30 * MINUTE,  # with correction
                                   writeNowDiff=0.5)


        elif data[0] == 110:  # data from iSpindel
            temperature = data[2] * 256 + data[3]
            gravity = data[4] * 256 + data[5]
            voltage = data[6] * 256 + data[7]

            if temperature > 32767:
                temperature = temperature - 65536  # negative temperatures

            if gravity > 32767:
                gravity = gravity - 65536  # negative inclinations

            name = 'iSpindel_' + str(data[1])

            self.mySQL.insertValue('temperature', name, temperature / 100.0,
                                   periodicity=60 * MINUTE,  # with correction
                                   writeNowDiff=0.1)
            self.mySQL.insertValue('gravity', name, gravity / 1000.0,
                                   periodicity=30 * MINUTE,  # with correction
                                   writeNowDiff=0.1)
            self.mySQL.insertValue('voltage', name, voltage / 1000.0,
                                   periodicity=60 * MINUTE,  # with correction
                                   writeNowDiff=0.1)
        elif data[0] == 111:  # data from chiller
            temperature = cDataProcessor.correctNegative(data[1] * 256 + data[2])

            self.mySQL.insertValue('temperature', 'brewhouse_chiller', temperature / 100.0,
                                   periodicity=5 * MINUTE,  # with correction
                                   writeNowDiff=0.1)
        elif data[0] == 112:  # data from old freezer
            temperature = data[1] * 256 + data[2]

            if temperature > 32767:
                temperature = temperature - 65536  # negative temperatures

            name = 'old_freezer_thermostat'

            self.mySQL.insertValue('temperature', name, temperature / 100.0,
                                   periodicity=60 * MINUTE,  # with correction
                                   writeNowDiff=0.1)
        elif data[0] == 113:  # data from victron inverter

            self.mySQL.insertValue('power', 'inverter', (data[1] * 256 + data[2]),
                                   periodicity=5 * MINUTE,  # with correction
                                   writeNowDiff=50)

        elif data[0] == 0 and data[1] == 1:  # live event
            self.logger.log("Live event!", Logger.FULL)
        elif data[0] < 4 and len(data) >= 2:  # events for keyboard
            self.logger.log("Incoming keyboard event!" + str(data))
            self.mySQL.insertEvent(data[0], data[1])
            self.commProcessor.send_ack_keyboard()
            self.house_security.keyboard_event(data)

        elif (data[0] < 10 and len(data) >= 2):  # other events
            self.logger.log("Incoming event!" + str(data))
            self.mySQL.insertEvent(data[0], data[1])

        else:
            self.logger.log("Unknown event, data:" + str(data))

    def sms_received(self, data):
        if data[1] == parameters.MY_NUMBER1:
            sms_text = data[0].lower()
            if sms_text.startswith("get status"):

                txt = "Stand-by"
                if self.house_security.alarm & cHouseSecurity.DOOR_ALARM != 0:
                    txt = "Door alarm"
                elif self.house_security.alarm & cHouseSecurity.GAS_ALARM_RPI != 0:
                    txt = "Gas alarm RPI"
                elif self.house_security.alarm & cHouseSecurity.GAS_ALARM_PIR != 0:
                    txt = "Gas alarm PIR"
                elif self.house_security.alarm & cHouseSecurity.PIR_ALARM != 0:
                    txt = "PIR movement alarm"
                elif self.house_security.locked:
                    txt = "Locked"
                txt += ", powerwall status:" + str(self.currentValues.get('status_powerwall_stateMachineStatus'))
                txt += ", solar power:" + str(int(self.currentValues.get('power_solar'))) + " W"
                txt += ", room temp:{:.1f} C".format(self.currentValues.get("temperature_PIR sensor"))
                txt += ", room humid:{:.1f} %".format(self.currentValues.get("humidity_PIR sensor"))

                self.phone.SendSMS(data[1], txt)
                self.logger.log("Get status by SMS command.")
            elif sms_text.startswith("lock"):
                locked = True

                self.mySQL_phoneThread.updateState("locked", int(locked))
                self.logger.log("Locked by SMS command.")
            elif sms_text.startswith("unlock"):
                locked = False

                self.mySQL_phoneThread.updateState("locked", int(locked))
                self.logger.log("Unlocked by SMS command.")
            elif sms_text.startswith("deactivate alarm"):
                self.logger.log("Alarm deactivated by SMS command.")
                self.house_security.deactivate_alarm()

            elif sms_text.startswith("toggle pc"):
                self.logger.log("Toggle PC button by SMS command.")
                self.house_control.TogglePCbutton()
            elif sms_text.startswith("heating on"):
                self.logger.log("Heating on by SMS command.")
                heatingControlInhibit = False
                self.phone.SendSMS(data[1], "Ok. Heating was set ON.")
            elif sms_text.startswith("heating off"):
                self.logger.log("Heating off by SMS command.")
                heatingControlInhibit = True
                self.phone.SendSMS(data[1], "Ok. Heating was set OFF.")
            elif sms_text.startswith("help"):
                self.logger.log("Sending help hints back")
                self.phone.SendSMS(data[1],
                                   "get status;lock;unlock;deactivate alarm;toggle PC;heating on; heating off;")
            else:
                self.logger.log("Not recognized command, text:")
                self.logger.log(data)
        else:
            self.logger.log("Received SMS from not authorized phone number!")
            self.logger.log("Text:")
            self.logger.log(data)
