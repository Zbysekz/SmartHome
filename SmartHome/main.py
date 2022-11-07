#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os  # we must add path to comm folder because inner scripts can now import other scripts in same folder directly

os.sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/comm')

# for calculation of AVGs - the routines are located in web folder
# import importlib.machinery
# avgModule = importlib.machinery.SourceFileLoader('getMeas',os.path.abspath("/var/www/SmartHomeWeb/getMeas.py")).load_module()

import comm
from databaseMySQL import cMySQL
import threading
import phone
from datetime import datetime
import RPi.GPIO as GPIO
from time import sleep
import sys
import struct
import electricityPrice
import time
from powerwall import calculatePowerwallSOC
from measureTime import MeasureTime

# -------------DEFINITIONS-----------------------
SMS_NOTIFICATION = True
RESTART_ON_EXCEPTION = True
PIN_BTN_PC = 26
PIN_GAS_ALARM = 23

MY_NUMBER1 = "+420602187490"

IP_METEO = '192.168.0.10'
IP_KEYBOARD = '192.168.0.11'
IP_ROOMBA = '192.168.0.13'
IP_RACKUNO = '192.168.0.5'
IP_PIR_SENSOR = '192.168.0.14'
IP_SERVER = '192.168.0.3'  # it is localhost
IP_POWERWALL = '192.168.0.12'
IP_KEGERATOR = "192.168.0.35"
IP_CELLAR = "192.168.0.33"
IP_POWERWALL_THERMOSTAT = "192.168.0.32"

NORMAL = 0
RICH = 1
FULL = 2
verbosity = RICH

# for periodicity mysql inserts
HOUR = 3600
MINUTE = 60

tmrTimeouts = {IP_RACKUNO: [time.time(), 200],
               IP_POWERWALL: [time.time(), 100],
               IP_METEO: [time.time(), HOUR * 3],
               IP_CELLAR: [time.time(), MINUTE * 10],
               IP_KEGERATOR: [time.time(), MINUTE * 10],
               IP_PIR_SENSOR: [time.time(), MINUTE * 10],
               IP_POWERWALL_THERMOSTAT: [time.time(), MINUTE * 10]}


# -----------------------------------------------

# -------------STATE VARIABLES-------------------
locked = False  # locked after startup

NO_ALARM = 0x00
DOOR_ALARM = 0x01  # DOOR ALARM when system was locked
GAS_ALARM_RPI = 0x02  # GAS alarm of the RPI module
GAS_ALARM_PIR = 0x04  # GAS alarm of the PIR sensor module
PIR_ALARM = 0x08  # PIR sensor detected motion when system was locked
alarm = 0

actualHeatingInhibition = False
INHIBITED_ROOM_TEMPERATURE = 20.0  # °C

globalFlags = {}  # contains data from table globalFlags - controls behaviour of subsystems
currentValues = {}  # contains latest measurements data
# -----------------------------------------------

# ------------AUXILIARY VARIABLES----------------
alarmCounting = False  # when door was opened and system locked
watchDogAlarmThread = 0
alarmCnt = 0
keyboardRefreshCnt = 0
wifiCheckCnt = 0
tmrPriceCalc = time.time()
gasSensorPrepared = False
tmrPrepareGasSensor = time.time()
alarm_last = 0

tmrConsPowerwall = 0
tmrVentHeatControl = 0

bufferedCellModVoltage = 24 * [0]

# cycle time
tmrCycleTime = 0
cycleTime_avg = 0
cycleTime_cnt = 0
cycleTime_tmp = time.time()
cycleTime = 0
cycleTime_max = 0
# -----------------------------------------------

MySQL = cMySQL()
MySQL_GeneralThread = cMySQL()
MySQL_phoneThread = cMySQL()


###############################################################################################################
def main():
    global watchDogAlarmThread, alarm, alarm_last, locked
    global tmrCycleTime, cycleTime_avg, cycleTime_cnt, cycleTime_tmp, cycleTime, cycleTime_max

    Log("Entry point main.py")
    try:
        # os.system("sudo service motion stop")
        Log("Initializing TCP port...")
        initTCP = True
        nOfTries = 0
        while (initTCP):
            try:
                comm.Init()
                initTCP = False  # succeeded
            except OSError:
                nOfTries += 1
                if (nOfTries > 30):
                    raise Exception('Too much tries to create TCP port', ' ')
                print("Trying to create TCP port again..")
                time.sleep(10)

        Log("Ok")

        Log("Initializing serial port...")
        phone.Connect()
        Log("Ok")

        MySQL.RemoveOnlineDevices()  # clean up online device table

        timerGeneral()  # it will call itself periodically - new thread

        timerPhone()  # it will call itself periodically - new thread

        Log("Initializing pin for PC button...")
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_BTN_PC, GPIO.OUT)
        GPIO.setup(PIN_GAS_ALARM, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        Log("Ok")

        MySQL.updateState("locked", int(locked))
        MySQL.updateState("alarm", int(alarm))

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        Log(str(e))
        Log(str(exc_type) + " : " + str(fname) + " : " + str(exc_tb.tb_lineno))
        if RESTART_ON_EXCEPTION:
            Log("Rebooting Raspberry PI in one minute")

            os.system("shutdown -r 1")  # reboot after one minute
            input("Reboot in one minute. Press Enter to continue...")
        return

    measureTimeMainLoop = MeasureTime()
    measureTimeComm = MeasureTime()
    measureTimePhone = MeasureTime()
    measureTimeDataRcv = MeasureTime()
    ######################## MAIN LOOP ####################################################################################
    while 1:
        measureTimeComm.Start()
        # TCP server communication - remote devices--------
        comm.Handle(MySQL)
        measureTimeComm.Measure()

        if comm.isTerminated():
            return  # user interrupt termination

        measureTimePhone.Start()
        phone.Process()
        measureTimePhone.Measure()

        # ----------------------------------------------
        measureTimeDataRcv.Start()

        data = comm.DataReceived()
        processedData = []
        if data:
            MySQL.PersistentConnect()
            while data:  # process all received packets
                try:
                    processedData += [data]
                    IncomingData(data)
                except IndexError:
                    Log("IndexError while processing incoming data! data:" + str(data))
                data = comm.DataReceived()
            MySQL.PersistentDisconnect()

        measureTimeDataRcv.Measure()
        if measureTimeDataRcv.getLastPeriod() > 4:
            Log("Data RCV took " + "{:.1f}".format(measureTimeDataRcv.getMaxPeriod()) + " s")
            Log(processedData)
        # -------------------------------------------------

        watchDogAlarmThread = 0  # to be able to detect lag in this loop

        CheckGasSensor()

        alarm_last = alarm

        measureTimeMainLoop.Measure()

        if measureTimeMainLoop.getMaxPeriod() > 6:
            measureTimeMainLoop.PrintOncePer(30, Log, "MainLoop")
            measureTimeDataRcv.PrintOncePer(30, Log, "Data rcv")
            measureTimeComm.PrintOncePer(30, Log, "Comm")
            measureTimePhone.PrintOncePer(30, Log, "Phone")
        measureTimeMainLoop.Start()


def ControlPowerwall():  # called each # 5 mins
    global globalFlags, currentValues

    if globalFlags['autoPowerwallRun'] == 1:
        # if enough SoC to run UPS
        if currentValues['status_powerwall_stateMachineStatus'] == 20 and currentValues[
            'status_powerwallSoc'] > 70:  # more than 50% SoC
            Log("Auto powerwall control - going to RUN")
            MySQL.insertTxCommand(IP_POWERWALL, "10")  # RUN command
        # if UPS is running but we are grid powered
        if currentValues['status_powerwall_stateMachineStatus'] == 10 and currentValues[
            'status_rackUno_stateMachineStatus'] == 0 and currentValues['status_rackUno_detectSolarPower'] == 1:
            Log("Auto powerwall control - switching to SOLAR power")
            MySQL.insertTxCommand(IP_RACKUNO, "4")  # Switch to SOLAR command


def ControlVentilation():  # called each 5 mins
    global currentValues, globalFlags

    if globalFlags['autoVentilation'] == 1:
        datetimeNow = datetime.now()
        dayTime = 7 < datetimeNow.hour < 21
        summerTime = 5 < datetimeNow.month < 9

        roomHumidity = currentValues.get("humidity_PIR sensor")
        if roomHumidity is None:
            ventilationCommand = 99  # do not control
        else:
            if not summerTime:  # COLD OUTSIDE
                if roomHumidity >= 60.0 and dayTime:
                    ventilationCommand = 3
                elif roomHumidity > 59.0:
                    ventilationCommand = 2
                elif not dayTime:
                    ventilationCommand = 1
                else:
                    ventilationCommand = 99
            else:  # WARM OUTSIDE
                if roomHumidity >= 60.0 and dayTime:
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

def ControlHeating():  # called each 5 mins
    global currentValues, actualHeatingInhibition, INHIBITED_ROOM_TEMPERATURE

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


def CheckGasSensor():
    global alarm, gasSensorPrepared

    if gasSensorPrepared:
        if not GPIO.input(PIN_GAS_ALARM):
            Log("RPI GAS ALARM!!");
            alarm |= GAS_ALARM_RPI
            MySQL.updateState("alarm", int(alarm))
            if alarm_last & GAS_ALARM_RPI == 0 and SMS_NOTIFICATION:
                phone.SendSMS(MY_NUMBER1, "Home system: fire/gas ALARM - RPI !!")
            KeyboardRefresh(MySQL)
            PIRSensorRefresh(MySQL)

    else:
        if time.time() - tmrPrepareGasSensor > 120:  # after 2 mins
            gasSensorPrepared = True


######################## General timer thread ##########################################################################

def timerGeneral():  # it is calling itself periodically
    global alarmCounting, alarmCnt, alarm, watchDogAlarmThread, MY_NUMBER1, keyboardRefreshCnt, wifiCheckCnt, tmrPriceCalc
    global tmrVentHeatControl, globalFlags, currentValues, tmrTimeouts

    if keyboardRefreshCnt >= 4:
        keyboardRefreshCnt = 0
        KeyboardRefresh(MySQL_GeneralThread)
        PIRSensorRefresh(MySQL_GeneralThread)
    else:
        keyboardRefreshCnt += 1

    if wifiCheckCnt >= 30:
        wifiCheckCnt = 0
        if not comm.Ping("192.168.0.4"):
            Log("UNABLE TO REACH ROUTER!")
    else:
        wifiCheckCnt = wifiCheckCnt + 1


    # timeouts handling
    for IP, tmr in tmrTimeouts.items():
        if tmr[0] != 0 and time.time() - tmr[0] > tmr[1]:
            Log("Comm timeout for IP:"+str(IP))
            tmr[0]=0
            comm.RemoveOnlineDevice(MySQL_GeneralThread, IP)


    if time.time() - tmrVentHeatControl > 300:  # each 5 mins
        tmrVentHeatControl = time.time()
        globalFlags = MySQL_GeneralThread.getGlobalFlags()  # update global flags
        currentValues = MySQL_GeneralThread.getCurrentValues()

        if globalFlags is not None and currentValues is not None:  # we get both values from DTB
            ControlPowerwall()
            ControlVentilation()
            ControlHeating()
        else:
            tmrVentHeatControl = time.time() - 200  # try it sooner

    # check if there are data in mysql that we want to send
    data = MySQL_GeneralThread.getTxBuffer()
    if (len(data)):
        try:
            for packet in data:
                byteArray = bytes([int(x) for x in packet[0].split(',')])
                Log("Sending data from MYSQL database to:")

                if packet[1] == IP_SERVER:
                    Log("LOCALHOST")
                    Log(byteArray)
                    ExecuteTxCommand(MySQL_GeneralThread, byteArray)
                else:
                    Log(packet[1])
                    Log(byteArray)
                    comm.Send(MySQL_GeneralThread, byteArray, packet[1], crc16=True)
        except ValueError:
            Log("MySQL - getTXbuffer - Value Error:" + str(packet[0]))

    if alarmCounting:  # user must make unlock until counter expires
        Log("Alarm check", FULL)
        alarmCnt += 1
        if alarmCnt >= 10:
            alarmCnt = 0

            Log("DOOR ALARM!!!!")
            alarm |= DOOR_ALARM
            alarmCounting = False

            if SMS_NOTIFICATION:
                phone.SendSMS(MY_NUMBER1, "Home system: door ALARM !!")

            MySQL_GeneralThread.updateState("alarm", int(alarm))
            KeyboardRefresh(MySQL_GeneralThread)
            PIRSensorRefresh(MySQL_GeneralThread)

    if time.time() - tmrPriceCalc > 3600 * 4:  # each 4 hour
        tmrPriceCalc = time.time()
        try:
            electricityPrice.run()
        except Exception as e:
            Log("Exception for electricityPrice.run()")
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            Log(str(e))
            Log(str(exc_type) + " : " + str(fname) + " : " + str(exc_tb.tb_lineno))

    if comm.isTerminated():  # do not continue if app terminated
        Log("Ending General thread, because comm is terminated.")
        return
    elif watchDogAlarmThread > 8:

        Log("Watchdog in alarm thread! Rebooting Raspberry PI in one minute")
        if RESTART_ON_EXCEPTION:
            os.system("shutdown -r 1")  # reboot after one minute

    else:
        threading.Timer(8, timerGeneral).start()
        watchDogAlarmThread += 1


####################################################################################################################
def ExecuteTxCommand(mySQLinstance, data):
    global alarm
    if data[0] == 0:  # resetAlarm
        Log("Alarm deactivated by Tx interface.")
        alarm = 0
        mySQLinstance.updateState("alarm", int(alarm))
        KeyboardRefresh(mySQLinstance)
        PIRSensorRefresh(mySQLinstance)
    elif data[0] == 1:
        MySQL.insertValue('status', 'heatingControlInhibit', False)
        Log("Stop heating control by Tx command")
    elif data[0] == 2:
        MySQL.insertValue('status', 'heatingControlInhibit', True)
        Log("Start heating control by Tx command")


def timerPhone():
    phone.ReadSMS()
    phone.CheckSignalInfo()

    # process incoming SMS
    for sms in phone.getIncomeSMSList():
        IncomingSMS(sms)
    phone.clearIncomeSMSList()

    MySQL_phoneThread.updateState('phoneSignalInfo', str(phone.getSignalInfo()));
    MySQL_phoneThread.updateState('phoneCommState', int(phone.getCommState()));

    if not comm.isTerminated():  # do not continue if app terminated
        threading.Timer(20, timerPhone).start()


def PIRSensorRefresh(sqlInst):
    global locked, alarm
    Log("PIR sensor refresh!", FULL)

    comm.Send(sqlInst, bytes([0, int(alarm != 0), int(locked)]), IP_PIR_SENSOR)  # id, alarm(0/1),locked(0/1)


def KeyboardRefresh(sqlInst):
    global locked, alarm
    Log("Keyboard refresh!", FULL)
    val = (int(alarm != 0)) + 2 * (int(locked))

    comm.Send(sqlInst, bytes([10, val]), IP_KEYBOARD)  # id, alarm(0/1),locked(0/1)


def IncomingSMS(data):
    global alarm, locked, heatingControlInhibit
    if data[1] == MY_NUMBER1:
        if (data[0].startswith("get status")):

            txt = "Stand-by"
            if alarm & DOOR_ALARM != 0:
                txt = "Door alarm"
            elif alarm & GAS_ALARM_RPI != 0:
                txt = "Gas alarm RPI"
            elif alarm & GAS_ALARM_PIR != 0:
                txt = "Gas alarm PIR"
            elif alarm & PIR_ALARM != 0:
                txt = "PIR movement alarm"
            elif locked:
                txt = "Locked"
            txt += ", powerwall status:" + str(currentValues.get('status_powerwall_stateMachineStatus'))
            txt += ", solar power:" + str(int(currentValues.get('power_solar'))) + " W"
            txt += ", room temp:{:.1f} C".format(currentValues.get("temperature_PIR sensor"))
            txt += ", room humid:{:.1f} %".format(currentValues.get("humidity_PIR sensor"))

            phone.SendSMS(data[1], txt)
            Log("Get status by SMS command.")
        elif (data[0].startswith("lock")):
            locked = True

            MySQL_phoneThread.updateState("locked", int(locked))
            Log("Locked by SMS command.")
        elif (data[0].startswith("unlock")):
            locked = False

            MySQL_phoneThread.updateState("locked", int(locked))
            Log("Unlocked by SMS command.")
        elif (data[0].startswith("deactivate alarm")):
            alarm = 0
            locked = False

            MySQL_phoneThread.updateState("alarm", int(alarm))
            MySQL_phoneThread.updateState("locked", int(locked))
            Log("Alarm deactivated by SMS command.")
        elif data[0].startswith("toggle PC"):
            Log("Toggle PC button by SMS command.")
            TogglePCbutton()
        elif data[0].startswith("heating on"):
            Log("Heating on by SMS command.")
            heatingControlInhibit = False
            phone.SendSMS(data[1], "Ok. Heating was set ON.")
        elif data[0].startswith("heating off"):
            Log("Heating off by SMS command.")
            heatingControlInhibit = True
            phone.SendSMS(data[1], "Ok. Heating was set OFF.")
        elif data[0].startswith("help"):
            Log("Sending help hints back")
            phone.SendSMS(data[1], "get status;lock;unlock;deactivate alarm;toggle PC;heating on; heating off;")
        else:
            Log("Not recognized command, text:")
            Log(data)
    else:
        Log("Received SMS from not authorized phone number!")
        Log("Text:")
        Log(data)


def TogglePCbutton():
    global PIN_BTN_PC
    GPIO.output(PIN_BTN_PC, True)
    time.sleep(2)
    GPIO.output(PIN_BTN_PC, False)


def correctNegative(val):
    if val > 32767:
        return val - 65536
    return val

def IncomingData(data):
    global alarm, locked, bufferedCellModVoltage, tmrConsPowerwall
    global alarmCounting
    global tmrTimeouts

    Log("Incoming data:" + str(data), FULL)
    # [100, 3, 0, 0, 1, 21, 2, 119]
    # ID,(bit0-door,bit1-gasAlarm),gas/256,gas%256,T/256,T%256,RH/256,RH%256)
    if data[0] == 100:  # data from keyboard
        doorSW = False if (data[1] & 0x01) == 0 else True
        gasAlarm = True if (data[1] & 0x02) == 0 else False
        gas = data[2] * 256 + data[3]
        temp = (data[4] * 256 + data[5]) / 10 + 0.5
        RH = (data[6] * 256 + data[7]) / 10

        MySQL.insertValue('bools', 'door switch 1', doorSW, periodicity=120 * MINUTE, writeNowDiff=1)
        # MySQL.insertValue('bools','gas alarm 1',gasAlarm,periodicity =30*MINUTE, writeNowDiff = 1)
        # MySQL.insertValue('gas','keyboard',gas)
        MySQL.insertValue('temperature', 'keyboard', temp, periodicity=60 * MINUTE, writeNowDiff=1)
        MySQL.insertValue('humidity', 'keyboard', RH, periodicity=60 * MINUTE, writeNowDiff=1)

        if doorSW and locked and (alarm & DOOR_ALARM) == 0 and not alarmCounting:
            alarmCounting = True
            Log("LOCKED and DOORS opened")
    elif data[0] == 101:  # data from meteostations
        tmrTimeouts[IP_METEO][0] = time.time()
        meteoTemp = correctNegative((data[1] * 256 + data[2]))

        MySQL.insertValue('temperature', 'meteostation 1', meteoTemp / 100, periodicity=60 * MINUTE, writeNowDiff=0.5)
        MySQL.insertValue('pressure', 'meteostation 1', (data[3] * 65536 + data[4] * 256 + data[5]) / 100,
                          periodicity=50 * MINUTE, writeNowDiff=100)
        MySQL.insertValue('voltage', 'meteostation 1', (data[6] * 256 + data[7]) / 1000, periodicity=50 * MINUTE,
                          writeNowDiff=0.2)

    elif data[0] > 10 and data[0] <= 40:  # POWERWALL
        voltage = (data[2] * 256 + data[3]) / 100
        if data[1] < 24:
            bufferedCellModVoltage[
                data[1]] = voltage  # we need to store voltages for each module, to calculate burning energy later
        temp = (data[4] * 256 + data[5]) / 10

        if voltage < 5:
            MySQL.insertValue('voltage', 'powerwall cell ' + str(data[1]), voltage, periodicity=30 * MINUTE,
                              writeNowDiff=0.1);
        if temp < 70:
            MySQL.insertValue('temperature', 'powerwall cell ' + str(data[1]), temp, periodicity=30 * MINUTE,
                              writeNowDiff=0.5);
    elif data[0] == 10:  # POWERWALL STATUS
        powerwall_stateMachineStatus = data[1]
        errorStatus = data[2]
        errorStatus_cause = data[3]
        solarConnected = (data[4] & 0x01) != 0
        heating = (data[4] & 0x02) != 0
        err_module_no = data[5]

        MySQL.insertValue('status', 'powerwall_stateMachineStatus', powerwall_stateMachineStatus,
                          periodicity=30 * MINUTE, writeNowDiff=1)
        MySQL.insertValue('status', 'powerwall_errorStatus', errorStatus, periodicity=60 * MINUTE, writeNowDiff=1)
        MySQL.insertValue('status', 'powerwall_errorStatus_cause', errorStatus_cause, periodicity=60 * MINUTE,
                          writeNowDiff=1)
        MySQL.insertValue('status', 'powerwall_solarConnected', solarConnected, periodicity=60 * MINUTE,
                          writeNowDiff=1)
        MySQL.insertValue('status', 'powerwall_heating', heating, periodicity=60 * MINUTE,
                          writeNowDiff=1)
        MySQL.insertValue('status', 'powerwall_err_module_no', err_module_no, periodicity=60 * MINUTE,
                          writeNowDiff=1)

    elif data[0] == 69:  # general statistics from powerwall
        P = 300.0 * 1 / 7.0  # power of the heating element * duty_cycle : duty_cycle is ratio is 1:6 so 1/7
        WhValue = (data[2] * 256 + data[1]) * P / 360.0  # counting pulse per 10s => 6 = P*1Wmin => P/360Wh
        if WhValue > 0:
            MySQL.insertValue('consumption', 'powerwall_heating', WhValue)
        if data[3] > 0:
            Log("CRC mismatch counter of BMS_controller not zero! Value:" + str(data[3]))
    elif data[0] > 40 and data[0] <= 69:  # POWERWALL - calibrations
        volCal = struct.unpack('f', bytes([data[2], data[3], data[4], data[5]]))[0]
        tempCal = struct.unpack('f', bytes([data[6], data[7], data[8], data[9]]))[0]

        # MySQL.insertValue('BMS calibration','powerwall calib.'+str(data[1])+' volt',volCal,one_day_RP=True);
        # MySQL.insertValue('BMS calibration','powerwall calib.'+str(data[1])+' temp',tempCal,one_day_RP=True);
    elif data[0] > 70 and data[0] < 99:  # POWERWALL - statistics
        valueToWrite = (data[2] * 256 + data[3])

        MySQL.insertValue('counter', 'powerwall cell ' + str(data[1]), valueToWrite, periodicity=60 * MINUTE,
                          writeNowDiff=1)

        # compensate dimensionless value from module to represent Wh
        # P=(U^2)/R
        # BurnedEnergy[Wh] = P*T/60
        if data[1] < 24:
            bufVolt = bufferedCellModVoltage[data[1]]
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
            MySQL.insertValue('consumption', 'powerwall cell ' + str(data[1]), Energy);

    elif data[0] == 102:  # data from Roomba
        MySQL.insertValue('voltage', 'roomba cell 1', (data[1] * 256 + data[2]) / 1000, periodicity=60 * MINUTE,
                          writeNowDiff=0.2)
        MySQL.insertValue('voltage', 'roomba cell 2', (data[3] * 256 + data[4]) / 1000, periodicity=60 * MINUTE,
                          writeNowDiff=0.2)
        MySQL.insertValue('voltage', 'roomba cell 3', (data[5] * 256 + data[6]) / 1000, periodicity=60 * MINUTE,
                          writeNowDiff=0.2)
    elif data[0] == 103:  # data from rackUno
        tmrTimeouts[IP_RACKUNO][0] = time.time()
        # store power
        MySQL.insertValue('power', 'grid', (data[1] * 256 + data[2]), periodicity=30 * MINUTE, writeNowDiff=50)

        # now store consumption according to tariff
        stdTariff = (data[5] & 0x01) == 0
        detectSolarPower = (data[5] & 0x02) == 0
        rackUno_heatingInhibition = (data[5] & 0x04) == 0

        MySQL.insertValue('status', 'rackUno_detectSolarPower', int(detectSolarPower), periodicity=6 * HOUR,
                          writeNowDiff=1)

        MySQL.insertValue('status', 'rackUno_heatingInhibition', int(rackUno_heatingInhibition), periodicity=6 * HOUR,
                          writeNowDiff=1)

        if not stdTariff:  # T1 - low tariff
            MySQL.insertValue('consumption', 'lowTariff',
                              (data[3] * 256 + data[4]) / 60)  # from power to consumption - 1puls=1Wh
        else:
            MySQL.insertValue('consumption', 'stdTariff',
                              (data[3] * 256 + data[4]) / 60)  # from power to consumption - 1puls=1Wh

        rackUno_stateMachineStatus = data[6]
        MySQL.insertValue('status', 'rackUno_stateMachineStatus', rackUno_stateMachineStatus, periodicity=6 * HOUR,
                          writeNowDiff=1)
        MySQL.insertValue('status', 'waterTank_level', (data[7] * 256 + data[8]), periodicity=6 * HOUR,
                          writeNowDiff=0.5)

    elif data[0] == 104:  # data from PIR sensor
        tmrTimeouts[IP_PIR_SENSOR][0] = time.time()
        tempPIR = (data[1] * 256 + data[2]) / 10.0
        tempPIR = tempPIR - 0.0  # calibration - SHT20 is precalibrated from factory

        humidPIR = (data[3] * 256 + data[4]) / 10.0

        # check validity and store values
        if tempPIR > -30.0 and tempPIR < 80.0:
            MySQL.insertValue('temperature', 'PIR sensor', tempPIR, periodicity=60 * MINUTE, writeNowDiff=1)

        if humidPIR >= 0.0 and tempPIR <= 100.0:
            MySQL.insertValue('humidity', 'PIR sensor', humidPIR, periodicity=60 * MINUTE, writeNowDiff=1)

        MySQL.insertValue('gas', 'PIR sensor', (data[5] * 256 + data[6]), periodicity=60 * MINUTE, writeNowDiff=50)
    elif data[0] == 105:  # data from PIR sensor
        gasAlarm2 = data[1]
        PIRalarm = data[2]

        if gasAlarm2:
            Log("PIR GAS ALARM!!")
            alarm |= GAS_ALARM_PIR
            if (alarm_last & GAS_ALARM_PIR == 0):
                MySQL.updateState("alarm", int(alarm))

                txt = "Home system: PIR sensor - FIRE/GAS ALARM !!"
                Log(txt)
                MySQL.insertEvent(10, 0)
                if SMS_NOTIFICATION:
                    phone.SendSMS(MY_NUMBER1, txt)
                KeyboardRefresh(MySQL)
                PIRSensorRefresh(MySQL)
        elif PIRalarm and locked:
            alarm |= PIR_ALARM
            if (alarm_last & PIR_ALARM == 0):
                MySQL.updateState("alarm", int(alarm))

                txt = "Home system: PIR sensor - MOVEMENT ALARM !!"
                Log(txt)
                MySQL.insertEvent(10, 1)

                if SMS_NOTIFICATION:
                    phone.SendSMS(MY_NUMBER1, txt)
                KeyboardRefresh(MySQL)
                PIRSensorRefresh(MySQL)
    elif data[0] == 106:  # data from powerwall ESP

        batteryStatus = data[9] * 256 + data[10]
        MySQL.insertValue('status', 'powerwallEpeverBatteryStatus', batteryStatus, periodicity=6 * HOUR,
                          writeNowDiff=1)
        MySQL.insertValue('status', 'powerwallEpeverChargerStatus', data[11] * 256 + data[12], periodicity=6 * HOUR,
                          writeNowDiff=1)

        if batteryStatus == 0 and (
                currentValues.get('status_powerwall_stateMachineStatus') == 10 or currentValues.get('status_powerwall_stateMachineStatus') == 20):  # valid only if epever reports battery ok and battery is really connected
            powerwallVolt = (data[1] * 256 + data[2]) / 100.0
            MySQL.insertValue('voltage', 'powerwallSum', powerwallVolt, periodicity=60 * MINUTE, writeNowDiff=0.5)
            soc = calculatePowerwallSOC(powerwallVolt)
            MySQL.insertValue('status', 'powerwallSoc', soc, periodicity=2 * HOUR, writeNowDiff=1)

        temperature = correctNegative(data[3] * 256 + data[4])

        MySQL.insertValue('temperature', 'powerwallOutside', temperature / 100.0, periodicity=30 * MINUTE,
                          writeNowDiff=2)
        solarPower = (data[5] * 256 + data[6]) / 100.0
        MySQL.insertValue('power', 'solar', solarPower)

        if batteryStatus == 0 and time.time() - tmrConsPowerwall > 3600:  # each hour
            tmrConsPowerwall = time.time()
            MySQL.insertDailySolarCons((data[7] * 256 + data[8]) * 10.0)  # in 0.01 kWh


    elif data[0] == 107:  # data from brewhouse
        MySQL.insertValue('temperature', 'brewhouse_horkaVoda', (data[1] * 256 + data[2]) / 100.0 + 6.0,  # with correction
                          periodicity=5 * MINUTE,
                          writeNowDiff=0.1)
        MySQL.insertValue('temperature', 'brewhouse_horkaVoda_setpoint', (data[3] * 256 + data[4]) / 100.0,
                          periodicity=5 * MINUTE,
                          writeNowDiff=0.1)
        MySQL.insertValue('temperature', 'brewhouse_rmut', (data[5] * 256 + data[6]) / 100.0,
                          periodicity=5 * MINUTE,
                          writeNowDiff=0.1)
    elif data[0] == 108:  # data from chiller
        tmrTimeouts[IP_POWERWALL_THERMOSTAT][0] = time.time()
        temperature = correctNegative(data[1] * 256 + data[2])

        MySQL.insertValue('temperature', 'powerwall_thermostat', temperature / 100.0,
                          periodicity=5 * MINUTE,
                          writeNowDiff=0.1)
    elif data[0] == 109:  # data from cellar
        tmrTimeouts[IP_CELLAR][0] = time.time()
        temperature1 = correctNegative(data[1] * 256 + data[2])
        temperature2 = correctNegative(data[3] * 256 + data[4])
        temperature_sht = correctNegative(data[5] * 256 + data[6])
        humidity = (data[7] * 256 + data[8])
        dew_point = correctNegative(data[9] * 256 + data[10])
        fan_active = data[11] & 0x01

        MySQL.insertValue('temperature', 'brewhouse_cellar', temperature1 / 100.0,
                          periodicity=5 * MINUTE,  # with correction
                          writeNowDiff=0.1)
        MySQL.insertValue('temperature', 'brewhouse_cellarbox', temperature2 / 100.0,
                          periodicity=5 * MINUTE,  # with correction
                          writeNowDiff=0.1)
        MySQL.insertValue('temperature', 'brewhouse_room', temperature_sht / 100.0,
                          periodicity=5 * MINUTE,  # with correction
                          writeNowDiff=0.1)
        MySQL.insertValue('humidity', 'brewhouse_room', humidity / 100.0,
                          periodicity=5 * MINUTE,  # with correction
                          writeNowDiff=0.5)
        MySQL.insertValue('temperature', 'brewhouse_dew_point', dew_point / 100.0,
                          periodicity=5 * MINUTE,  # with correction
                          writeNowDiff=0.1)
        MySQL.insertValue('bools', 'brewhouse_fan', fan_active,
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

        MySQL.insertValue('temperature', name, temperature / 100.0,
                          periodicity=60 * MINUTE,  # with correction
                          writeNowDiff=0.1)
        MySQL.insertValue('gravity', name, gravity / 1000.0,
                          periodicity=30 * MINUTE,  # with correction
                          writeNowDiff=0.1)
        MySQL.insertValue('voltage', name, voltage / 1000.0,
                          periodicity=60 * MINUTE,  # with correction
                          writeNowDiff=0.1)
    elif data[0] == 111:  # data from chiller
        tmrTimeouts[IP_KEGERATOR][0] = time.time()
        temperature = correctNegative(data[1] * 256 + data[2])

        MySQL.insertValue('temperature', 'brewhouse_chiller', temperature / 100.0,
                          periodicity=5 * MINUTE,  # with correction
                          writeNowDiff=0.1)
    elif data[0] == 0 and data[1] == 1:  # live event
        Log("Live event!", FULL)
    elif (data[0] < 4 and len(data) >= 2):  # events for keyboard
        Log("Incoming keyboard event!" + str(data))
        comm.SendACK(data, IP_KEYBOARD)
        MySQL.insertEvent(data[0], data[1])
        IncomingEvent(data)

    elif (data[0] < 10 and len(data) >= 2):  # other events
        Log("Incoming event!" + str(data))
        MySQL.insertEvent(data[0], data[1])

    else:
        Log("Unknown event, data:" + str(data))


def IncomingEvent(data):
    global locked, alarm, alarmCounting, alarmCnt

    alarmLast = alarm
    lockLast = locked
    if data[0] == 3:
        if data[1] == 2:  # lock
            locked = True
            Log("LOCKED by keyboard")
        if data[1] == 4:  # doors opened and locked
            if alarm == 0 and locked:
                alarmCounting = True
            Log("LOCKED and DOORS opened event")
    if data[0] == 1:
        if data[1] == 1:  # unlock PIN
            locked = False
            alarm = 0
            alarmCounting = False
            alarmCnt = 0
            Log("UNLOCKED by keyboard PIN")

    if data[0] == 2:
        if data[1] == 0:  # unlock RFID
            locked = False
            alarm = 0
            alarmCounting = False
            alarmCnt = 0
            Log("UNLOCKED by keyboard RFID")

    if (lockLast != locked or alarmLast != alarm):  # change in locked state or alarm state
        KeyboardRefresh(MySQL)
        PIRSensorRefresh(MySQL)

        MySQL.updateState("locked", int(locked))
        MySQL.updateState("alarm", int(alarm))

        # if locked:
        #    os.system("sudo service motion start")
        # else:
        #    os.system("sudo service motion stop")


def Log(s, _verbosity=NORMAL):
    if _verbosity > verbosity:
        return
    print(str(s))

    dateStr = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("logs/main.log", "a") as file:
        file.write(dateStr + " >> " + str(s) + "\n")


if __name__ == "__main__":

    if (len(sys.argv) > 1):
        if ('delayStart' in sys.argv[1]):
            Log("Delayed start...")
            sleep(20)
    # execute only if run as a script
    main()
