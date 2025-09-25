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
from comm.device import cDevice
from comm.commProcessor import cCommProcessor
import feels_like_temperature
# for periodicity mysql inserts
HOUR = 3600
MINUTE = 60


class cDataProcessor(cThreadModule):
    def __init__(self, phone, **kwargs):
        super().__init__(**kwargs)
        self.mySQL = cMySQL()
        self.logger = Logger("dataProcessor", verbosity=parameters.VERBOSITY, mySQL=self.mySQL)
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
        self.printQueueSize = time.time()
        self.last_notification = time.time()

    @classmethod
    def correctNegative(cls, val):
        if val > 32767:
            return val - 65536
        return val

    def data_received(self, data):  # called from commProcessor with data received
        try:
            self.receive_queue.put(data)
        except queue.Full:
            self.logger.log("Queue in dataProcessor is FULL!!")

    def _handle(self):

        self.mySQL.PersistentConnect()
        while self.receive_queue.qsize() > 0:
            if time.time() - self.printQueueSize > 60:
                self.printQueueSize = time.time()
                if self.receive_queue.qsize() > 10:
                    self.logger.log(f"-----------------ReceiveQueueSize:{self.receive_queue.qsize()}", Logger.RICH)
                    if self.receive_queue.qsize() > 500 and (time.time() - self.last_notification)>60*60:
                        self.last_notification = time.time()
                        self.logger.log(f"Receive queue large! {self.receive_queue.qsize()}")
                        cnt = 0
                        while cnt<100:
                            self.receive_queue.get(block=False)  ## throw away
                            cnt = cnt + 1
                        
            try:
                data = self.receive_queue.get(block=False)
            except queue.Empty:
                break
            if data:
                try:
                    m = time.time()
                    self.process_incoming_data(data)

                    diff = time.time()-m
                    if diff > 2:
                        self.logger.log("---> %.2f"% (time.time()-m), self.logger.RICH)
                        self.logger.log(f"for data ID:{data[0]}", self.logger.RICH)
                except IndexError:
                    self.logger.log("IndexError while processing incoming data! data:" + str(data))
                except Exception as e:
                    self.logger.log(
                        f"General exception while processing incoming data! data: {data}")
                    self.logger.log_exception(e)

        if time.time() - self.tmrCurrentValues > 5:
            self.tmrCurrentValues = time.time()
            self.currentValues = self.mySQL.getCurrentValues()
            self.globalFlags = self.mySQL.getGlobalFlags()

        self.mySQL.PersistentDisconnect()
        #self.logger.log(f"LEAVING WITH -----------------ReceiveQueueSize:{self.receive_queue.qsize()}")
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

            self.mySQL.insertValue('bools', 'door switch 1', doorSW, periodicity=120 * MINUTE,
                                   writeNowDiff=1)
            # self.mySQL.insertValue('bools','gas alarm 1',gasAlarm,periodicity =30*MINUTE, writeNowDiff = 1)
            # self.mySQL.insertValue('gas','keyboard',gas)
            self.mySQL.insertValue('temperature', 'keyboard', temp, periodicity=60 * MINUTE,
                                   writeNowDiff=1)
            self.mySQL.insertValue('humidity', 'keyboard', RH, periodicity=60 * MINUTE,
                                   writeNowDiff=1)

            self.house_security.keyboard_data_receive(doorSW)

        elif data[0] == 101:  # data from meteostations
            meteoTemp = cDataProcessor.correctNegative((data[1] * 256 + data[2]))/100
            meteoTemp2 = cDataProcessor.correctNegative((data[8] * 256 + data[9]))/100
            meteoHumidity = (data[20] * 256 + data[21]) / 10
            wind_speed_avg = (data[14] * 256 + data[15]) / 10 # in km/h
            self.mySQL.insertValue('temperature', 'meteostation', meteoTemp,
                                   periodicity=60 * MINUTE,
                                   writeNowDiff=0.5)
            self.mySQL.insertValue('pressure', 'meteostation',
                                   (data[3] * 65536 + data[4] * 256 + data[5]) / 100,
                                   periodicity=50 * MINUTE, writeNowDiff=100)
            self.mySQL.insertValue('voltage', 'meteostation', (data[6] * 256 + data[7]) / 10,
                                   periodicity=50 * MINUTE,
                                   writeNowDiff=0.2)
            self.mySQL.insertValue('temperature', 'meteostation2', meteoTemp2,
                                   periodicity=60 * MINUTE,
                                   writeNowDiff=0.5)
            self.mySQL.insertValue('rain_mm_per_h', 'meteostation', (data[10] * 256 + data[11]) / 100,
                                   periodicity=50 * MINUTE,
                                   writeNowDiff=0.1)
            self.mySQL.insertValue('rain_mm_accumulated', 'meteostation', (data[12] * 256 + data[13]) / 10,
                                   periodicity=1 * MINUTE,
                                   writeNowDiff=0.1)
            self.mySQL.insertValue('wind_speed_avg', 'meteostation',
                                   wind_speed_avg,
                                   periodicity=5 * MINUTE,
                                   writeNowDiff=0.1)
            self.mySQL.insertValue('wind_speed', 'meteostation',
                                   (data[16] * 256 + data[17]) / 10,
                                   periodicity=5 * MINUTE,
                                   writeNowDiff=0.1)
            self.mySQL.insertValue('wind_speed_max', 'meteostation',
                                   (data[18] * 256 + data[19]) / 10,
                                   periodicity=5 * MINUTE,
                                   writeNowDiff=0.1)
            self.mySQL.insertValue('humidity', 'meteostation',
                                   meteoHumidity,
                                   periodicity=50 * MINUTE,
                                   writeNowDiff=1)

            temperature_feels_like = feels_like_temperature.apparent_temp(
                meteoTemp, meteoHumidity, wind_speed_avg/3.6)
            self.mySQL.insertValue('temperature', 'apparent_temp',
                                   temperature_feels_like,
                                   periodicity=60 * MINUTE,
                                   writeNowDiff=0.5)

        elif data[0] > 10 and data[0] <= 40:  # POWERWALL
            voltage = (data[2] * 256 + data[3]) / 100
            if data[1] < 24:
                self.bufferedCellModVoltage[
                    data[
                        1]] = voltage  # we need to store voltages for each module, to calculate burning energy later
            temp = (data[4] * 256 + data[5]) / 10

            if voltage < 5:
                self.mySQL.insertValue('voltage', 'powerwall cell ' + str(data[1]), voltage,
                                       periodicity=10 * MINUTE,
                                       writeNowDiff=0.05)
            #if temp < 70:
            self.mySQL.insertValue('temperature', 'powerwall cell ' + str(data[1]), temp,
                                   periodicity=120 * MINUTE,
                                   writeNowDiff=1)
        elif data[0] == 10:  # POWERWALL STATUS
            powerwall_stateMachineStatus = data[1]
            errorStatus = data[2]
            errorStatus_cause = data[3]
            # solarConnected = (data[4] & 0x01) != 0 not used
            heating = (data[4] & 0x02) != 0
            garage_contactor = (data[4] & 0x04) != 0
            err_module_no = data[5]

            self.mySQL.insertValue('status', 'powerwall_stateMachineStatus',
                                   powerwall_stateMachineStatus,
                                   periodicity=30 * MINUTE, writeNowDiff=1)
            self.mySQL.insertValue('status', 'powerwall_errorStatus', errorStatus,
                                   periodicity=60 * MINUTE,
                                   writeNowDiff=1)
            self.mySQL.insertValue('status', 'powerwall_errorStatus_cause', errorStatus_cause,
                                   periodicity=60 * MINUTE,
                                   writeNowDiff=1)
            self.mySQL.insertValue('status', 'powerwall_garage_contactor', garage_contactor,
                                   periodicity=60 * MINUTE,
                                   writeNowDiff=1)
            self.mySQL.insertValue('status', 'powerwall_heating', heating, periodicity=60 * MINUTE,
                                   writeNowDiff=1)
            self.mySQL.insertValue('status', 'powerwall_err_module_no', err_module_no,
                                   periodicity=60 * MINUTE,
                                   writeNowDiff=1)

        elif data[0] == 69:  # general statistics from powerwall
            P = 300.0 * 1 / 7.0  # power of the heating element * duty_cycle : duty_cycle is ratio is 1:6 so 1/7
            WhValue = (data[2] * 256 + data[
                1]) * P / 360.0  # counting pulse per 10s => 6 = P*1Wmin => P/360Wh
            if WhValue > 0:
                self.mySQL.insertValue('consumption', 'powerwall_heating', WhValue)
            if data[3] > 0:
                self.logger.log(
                    "CRC mismatch counter of BMS_controller not zero! Value:" + str(data[3]))
        elif data[0] > 40 and data[0] <= 69:  # POWERWALL - calibrations
            volCal = struct.unpack('f', bytes([data[2], data[3], data[4], data[5]]))[0]
            tempCal = struct.unpack('f', bytes([data[6], data[7], data[8], data[9]]))[0]

            # self.mySQL.insertValue('BMS calibration','powerwall calib.'+str(data[1])+' volt',volCal,one_day_RP=True);
            # self.mySQL.insertValue('BMS calibration','powerwall calib.'+str(data[1])+' temp',tempCal,one_day_RP=True);
        elif data[0] > 70 and data[0] < 99:  # POWERWALL - statistics
            valueToWrite = (data[2] * 256 + data[3])

            self.mySQL.insertValue('counter', 'powerwall cell ' + str(data[1]), valueToWrite,
                                   periodicity=60 * MINUTE,
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
            val = (data[4] * 256 + data[
                5])  # this value is counter for how long bypass was switched on
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
            self.mySQL.insertValue('power', 'grid', (data[1] * 256 + data[2]),
                                   periodicity=30 * MINUTE, writeNowDiff=50)

            # now store consumption according to tariff
            stdTariff = (data[5] & 0x01) == 0
            detectSolarPower = (data[5] & 0x02) == 0
            rackUno_heatingInhibition = (data[5] & 0x04) == 0

            self.mySQL.insertValue('status', 'rackUno_detectSolarPower', int(detectSolarPower),
                                   periodicity=6 * HOUR,
                                   writeNowDiff=1)

            self.mySQL.insertValue('status', 'rackUno_heatingInhibition',
                                   int(rackUno_heatingInhibition),
                                   periodicity=6 * HOUR,
                                   writeNowDiff=1)

            if not stdTariff:  # T1 - low tariff
                self.mySQL.insertValue('consumption', 'lowTariff',
                                       (data[3] * 256 + data[
                                           4]) / 60)  # from power to consumption - 1puls=1Wh
            else:
                self.mySQL.insertValue('consumption', 'stdTariff',
                                       (data[3] * 256 + data[
                                           4]) / 60)  # from power to consumption - 1puls=1Wh

            rackUno_stateMachineStatus = data[6]
            self.mySQL.insertValue('status', 'rackUno_stateMachineStatus',
                                   rackUno_stateMachineStatus,
                                   periodicity=6 * HOUR,
                                   writeNowDiff=1)

            raw = data[7] * 256 + data[8]

            # if dist_cm < 11:
            #     waterTank_level = 100.0
            # elif dist_cm > 191:
            #     waterTank_level = 0.0
            # else:
            #     waterTank_level = (191.0 - dist_cm) / 180.0 * 100

            waterTank_level = 100 * (
                    -raw * 0.000244052235241 * raw + 0.093727045956581 * raw + 171.116013166274) / 180.0
            waterTank_level = max(0, min(waterTank_level, 100))
            self.avg_water_tank.append_value(waterTank_level)

            self.mySQL.insertValue('status', 'waterTank_level', self.avg_water_tank.value,
                                   periodicity=6 * HOUR,
                                   writeNowDiff=1)
            self.mySQL.insertValue('status', 'waterTank_level_raw', raw, periodicity=1 * HOUR,
                                   writeNowDiff=10)

        elif data[0] == 104:  # data from PIR sensor
            tempPIR = (data[1] * 256 + data[2]) / 10.0
            tempPIR = tempPIR - 0.0  # calibration - SHT20 is precalibrated from factory

            humidPIR = (data[3] * 256 + data[4]) / 10.0

            # check validity and store values
            if tempPIR > -30.0 and tempPIR < 80.0:
                self.mySQL.insertValue('temperature', 'PIR sensor', tempPIR,
                                       periodicity=60 * MINUTE, writeNowDiff=1)

            if humidPIR >= 0.0 and tempPIR <= 100.0:
                self.mySQL.insertValue('humidity', 'PIR sensor', humidPIR, periodicity=60 * MINUTE,
                                       writeNowDiff=1)

            self.mySQL.insertValue('gas', 'PIR sensor', (data[5] * 256 + data[6]),
                                   periodicity=60 * MINUTE,
                                   writeNowDiff=50)
        elif data[0] == 105:  # data from PIR sensor
            gasAlarm2 = data[1]
            PIRalarm = data[2]

            self.house_security.PIR_sensor_data_receive()

        elif data[0] == 106:  # data from powerwall ESP
            epever_statuses = data[1]
            self.mySQL.insertValue('status', f'powerwallEpeverStatuses', epever_statuses,
                                   periodicity=3 * HOUR,
                                   writeNowDiff=1)

            MODULES_CNT = 5
            offset = 2
            #self.logger.log(f"ESP RECEIVED {data}")
            cons_logged = False
            if len(data) >= (2 + 16*MODULES_CNT):
                powers = [0.0] * MODULES_CNT
                powerwallVolt = 0.0
                powerwallVoltSum = 0.0
                powerwallVoltSum_cnt = 0
                for i in range(1, MODULES_CNT+1):
                    batteryStatus = data[offset+12] * 256 + data[offset+13]
                    self.mySQL.insertValue('status', f'powerwallEpeverBatteryStatus{i}', batteryStatus,
                                           periodicity=6 * HOUR,
                                           writeNowDiff=1)
                    self.mySQL.insertValue('status', f'powerwallEpeverChargerStatus{i}',
                                           data[offset+14] * 256 + data[offset+15],
                                           periodicity=6 * HOUR,
                                           writeNowDiff=1)
                    if batteryStatus == 0 and (
                            self.currentValues.get(
                                'status_powerwall_stateMachineStatus') in (10, 20)):  # valid only if epever reports battery ok and battery is really connected
                        powerwallVolt = (data[offset] * 256 + data[offset+1]) / 100.0
                        self.mySQL.insertValue('voltage', f'powerwallSum{i}', powerwallVolt,
                                               periodicity=60 * MINUTE,
                                               writeNowDiff=0.5)
                        powerwallVoltSum += powerwallVolt
                        powerwallVoltSum_cnt += 1
                    temperature = cDataProcessor.correctNegative(data[offset+2] * 256 + data[offset+3])

                    self.mySQL.insertValue('temperature', f'powerwallOutside{i}', temperature / 100.0,
                                           periodicity=30 * MINUTE,
                                           writeNowDiff=2)
                    powers[i-1] = (data[offset+4] * 16777216 + data[offset+5] * 65536 + data[offset+6] * 256 + data[offset+7]) / 100.0
                    self.mySQL.insertValue('power', f'solar{i}', powers[i-1])

                    if batteryStatus == 0 and time.time() - self.tmrConsPowerwall > 3600:  # each hour
                        self.logger.log("Daily solar cons", _verbosity=Logger.RICH)
                        cons_logged = True
                        self.mySQL.insertDailySolarCons(i, (data[offset+8] * 16777216 + data[offset+9] * 65536 + data[
                            offset+10] * 256 + data[offset+11]) * 10.0)  # in 0.01 kWh
                    offset += 16
                if cons_logged:  # we have logged consumptions, reset timer
                    self.tmrConsPowerwall = time.time()

                self.mySQL.insertValue('power', 'solar', sum(powers))

                if powerwallVoltSum_cnt != 0 and powerwallVoltSum != 0.0:
                    soc = calculatePowerwallSOC(powerwallVoltSum/powerwallVoltSum_cnt)
                    self.mySQL.insertValue('status', 'powerwallSoc', soc, periodicity=2 * HOUR,
                                           writeNowDiff=1)
                self.logger.log("process completed", _verbosity=Logger.RICH)


        elif data[0] == 107:  # data from brewhouse
            self.mySQL.insertValue('temperature', 'brewhouse_horkaVoda',
                                   (data[1] * 256 + data[2]) / 100.0 + 6.0,
                                   # with correction
                                   periodicity=5 * MINUTE,
                                   writeNowDiff=0.1)
            self.mySQL.insertValue('temperature', 'brewhouse_horkaVoda_setpoint',
                                   (data[3] * 256 + data[4]) / 100.0,
                                   periodicity=5 * MINUTE,
                                   writeNowDiff=0.1)
            self.mySQL.insertValue('temperature', 'brewhouse_rmut',
                                   (data[5] * 256 + data[6]) / 100.0,
                                   periodicity=5 * MINUTE,
                                   writeNowDiff=0.1)
        elif data[0] == 108:  # data from chiller
            temperature = cDataProcessor.correctNegative(data[1] * 256 + data[2])

            self.mySQL.insertValue('temperature', 'powerwall_thermostat', temperature / 100.0,
                                   periodicity=300 * MINUTE,
                                   writeNowDiff=3)
        elif data[0] == 109:  # data from cellar
            bits = data[1]
            bits2 = data[2]
            bits3 = data[3]

            temperature_sht = cDataProcessor.correctNegative(data[4] * 256 + data[5])
            humidity = (data[6] * 256 + data[7])
            dew_point = cDataProcessor.correctNegative(data[8] * 256 + data[9])
            polybox_setpoint = cDataProcessor.correctNegative(data[10] * 256 + data[11])
            polybox_hysteresis = cDataProcessor.correctNegative(data[12] * 256 + data[13])
            fermentor_setpoint = cDataProcessor.correctNegative(data[14] * 256 + data[15])
            fermentor_hysteresis = cDataProcessor.correctNegative(data[16] * 256 + data[17])

            temp_polybox = cDataProcessor.correctNegative(data[18] * 256 + data[19])
            temp_cellar = cDataProcessor.correctNegative(data[20] * 256 + data[21])
            temp_fermentor = cDataProcessor.correctNegative(data[22] * 256 + data[23])
            pump_activations_per_h = data[24] * 256 + data[25]

            garden2_watering_duration = data[26] * 256 + data[27]
            garden3_watering_duration = data[28] * 256 + data[29]
            garden_watering_morning_hour = data[30] * 256 + data[31]
            garden_watering_evening_hour = data[32] * 256 + data[33]

            bits_list = {
                "params_valid": bool(bits & (1 << 0)),
                "errorFlags": bool(bits & (1 << 1)),
                "water_pump_alarm": bool(bits & (1 << 2)),
                "fanControl_autMan": bool(bits & (1 << 3)),
                "fan_onOff": bool(bits & (1 << 4)),
                "brewhouse_polybox_autMan": bool(bits & (1 << 5)),
                "brewhouse_chillPump_onOff": bool(bits & (1 << 6)),
                "brewhouse_freezer_onOff": bool(bits & (1 << 7)),
                "brewhouse_ferm_autMan": bool(bits2 & (1 << 0)),
                "brewhouse_ferm_heat_onOff": bool(bits2 & (1 << 1)),
                "garden1_autMan": bool(bits2 & (1 << 2)),
                "garden1_onOff": bool(bits2 & (1 << 3)),
                "garden2_autMan": bool(bits2 & (1 << 4)),
                "garden2_onOff": bool(bits2 & (1 << 5)),
                "garden3_autMan": bool(bits2 & (1 << 6)),
                "garden3_onOff": bool(bits2 & (1 << 7)),
                "brewhouse_valve_cellar1_onOff": bool(bits3 & (1 << 0)),
                "brewhouse_valve_cellar2_onOff": bool(bits3 & (1 << 1)),
                "request_clock": bool(bits3 & (1 << 2))
            }

            if bits_list["request_clock"]:
                self.commProcessor.send_clock(cDevice.get_ip("CELLAR", cCommProcessor.devices))

            def insert_for_bits(name, val):
                self.mySQL.insertValue('status', name, val,
                                       periodicity=240 * MINUTE,  # with correction
                                       writeNowDiff=0.1,
                                       onlyCurrent=False)

            for name, val in bits_list.items():
                insert_for_bits(name, val)

            def insert_for_temps(name, val):
                self.mySQL.insertValue('temperature', name, val/10.0,
                                       periodicity=240 * MINUTE,  # with correction
                                       writeNowDiff=0.5,
                                       onlyCurrent=False)

            temp_list = {
                "brewhouse_room": temperature_sht,
                "brewhouse_polybox_setpoint" : polybox_setpoint,
                "brewhouse_fermentor_setpoint": fermentor_setpoint,
                "brewhouse_polybox": temp_polybox,
                "brewhouse_cellar": temp_cellar,
                "brewhouse_fermentor": temp_fermentor,
            }
            for name, val in temp_list.items():
                insert_for_temps(name, val)

            self.mySQL.insertValue('temperature', 'brewhouse_polybox_hysteresis', polybox_hysteresis / 10.0,
                                   periodicity=240 * MINUTE,  # with correction
                                   writeNowDiff=0.01,
                                   onlyCurrent=True)
            self.mySQL.insertValue('temperature', 'brewhouse_fermentor_hysteresis',
                                   fermentor_hysteresis / 10.0,
                                   periodicity=240 * MINUTE,  # with correction
                                   writeNowDiff=0.01,
                                   onlyCurrent=True)

            self.mySQL.insertValue('humidity', 'brewhouse_room', humidity / 10.0,
                                   periodicity=240 * MINUTE,  # with correction
                                   writeNowDiff=0.5)
            self.mySQL.insertValue('temperature', 'brewhouse_dew_point', dew_point / 10.0,
                                   periodicity=240 * MINUTE,  # with correction
                                   writeNowDiff=0.1)

            self.mySQL.insertValue('status', 'brewhouse_pump_act_per_h',
                                   pump_activations_per_h / 10.0,
                                   periodicity=60 * MINUTE,  # with correction
                                   writeNowDiff=1)
            self.mySQL.insertValue('status', 'garden2_watering_duration_min',
                                   garden2_watering_duration,
                                   periodicity=600 * MINUTE,  # with correction
                                   writeNowDiff=1)

            self.mySQL.insertValue('status', 'garden3_watering_duration_min',
                                    garden3_watering_duration,
                                   periodicity=600 * MINUTE,  # with correction
                                   writeNowDiff=1)
            self.mySQL.insertValue('status', 'garden_watering_morning_h',
                                    garden_watering_morning_hour,
                                   periodicity=600 * MINUTE,  # with correction
                                   writeNowDiff=1)
            self.mySQL.insertValue('status', 'garden_watering_evening_h',
                                    garden_watering_evening_hour,
                                   periodicity=600 * MINUTE,  # with correction
                                   writeNowDiff=1)



        elif data[0] == 110:  # data from iSpindel
            temperature = data[2] * 256 + data[3]
            gravity = data[4] * 256 + data[5]
            voltage = data[6] * 256 + data[7]

            if temperature > 32767:
                temperature = temperature - 65536  # negative temperatures

            if gravity > 32767:
                gravity = gravity - 65536  # negative inclinations

            name = 'iSpindel_' + str(data[1])

            if temperature != 0:
                self.mySQL.insertValue('temperature', name, temperature / 100.0,
                                       periodicity=60 * MINUTE,  # with correction
                                       writeNowDiff=0.1)
            if gravity != 0:
                self.mySQL.insertValue('gravity', name, gravity / 1000.0,
                                       periodicity=30 * MINUTE,  # with correction
                                       writeNowDiff=0.1)
            if voltage != 0:
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
                                   periodicity=300 * MINUTE,  # with correction
                                   writeNowDiff=5)
        elif data[0] == 113:  # data from victron inverter
            status = data[1]

            #self.logger.log("VICTRON:")
            #self.logger.log(data)
            #if status & 0x01 == 0:  # valid data
            self.mySQL.insertValue('power', 'inverter', (data[2] * 256 + data[3]),
                                   periodicity=5 * MINUTE,  # with correction
                                   writeNowDiff=50)
            # self.mySQL.insertValue('status', 'inverter', status,
            #                        periodicity=6 * HOUR,
            #                        writeNowDiff=1)

        elif data[0] == 114:  # data from martha tent
            reqClock_martha = data[1]
            if reqClock_martha:
                self.logger.log("Martha requested clock, sending...")
                self.commProcessor.send_clock(cDevice.get_ip("MARTHA_TENT", cCommProcessor.devices))
            temperature = cDataProcessor.correctNegative(data[2] * 256 + data[3])

            self.mySQL.insertValue('temperature', 'martha_tent', temperature/10.0,
                                   periodicity=120 * MINUTE,
                                   writeNowDiff=1)
            self.mySQL.insertValue('humidity', 'martha_tent', (data[4] * 256 + data[5]) / 10.0,
                                   periodicity=120 * MINUTE,
                                   writeNowDiff=2)
            self.mySQL.insertValue('gas', 'martha_tent', (data[6] * 256 + data[7]),
                                   periodicity=120 * MINUTE,
                                   writeNowDiff=10)
        elif data[0] == 115:  # data from Geiger-Muller counter
            CPM = data[1]*256 + data[2]
            self.mySQL.insertValue('radioactivity', f'geiger_muller_counter', CPM,
                                   periodicity=6 * HOUR,
                                   writeNowDiff=5)
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
        self.logger.log("Done", Logger.FULL)

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
                txt += ", powerwall status:" + str(
                    self.currentValues.get('status_powerwall_stateMachineStatus'))
                txt += ", solar power:" + str(int(self.currentValues.get('power_solar'))) + " W"
                txt += ", room temp:{:.1f} C".format(
                    self.currentValues.get("temperature_PIR sensor"))
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
