#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os#we must add path to comm folder because inner scripts can now import other scripts in same folder directly
os.sys.path.append(os.path.dirname(os.path.realpath(__file__))+'/comm')

#for calculation of AVGs - the routines are located in web folder
#import importlib.machinery
#avgModule = importlib.machinery.SourceFileLoader('getMeas',os.path.abspath("/var/www/SmartHomeWeb/getMeas.py")).load_module()

import comm
from databaseMySQL import cMySQL
import time, threading
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

#-------------DEFINITIONS-----------------------
SMS_NOTIFICATION = True
RESTART_ON_EXCEPTION = False
PIN_BTN_PC = 26
PIN_GAS_ALARM = 23

MY_NUMBER1 = "+420602187490"

IP_METEO = '192.168.0.10'
IP_KEYBOARD = '192.168.0.11'
IP_ROOMBA = '192.168.0.13'
IP_RACKUNO = '192.168.0.5'
IP_PIR_SENSOR = '192.168.0.14'
IP_SERVER = '192.168.0.3' # it is localhost
IP_POWERWALL = '192.168.0.12'

NORMAL = 0
RICH = 1
FULL = 2
verbosity = RICH

# for periodicity mysql inserts
HOUR = 3600
MINUTE = 60
#-----------------------------------------------

#-------------STATE VARIABLES-------------------
locked=False #locked after startup

NO_ALARM = 0x00
DOOR_ALARM = 0x01      #DOOR ALARM when system was locked
GAS_ALARM_RPI = 0x02   #GAS alarm of the RPI module
GAS_ALARM_PIR = 0x04   #GAS alarm of the PIR sensor module
PIR_ALARM = 0x08       #PIR sensor detected motion when system was locked
alarm=0

roomTemperature = None # for controlling lower temperature while heating inhibition
roomHumidity = None # for controlling ventilation - currently taken from PIR sensor

rackUno_heatingInhibition = False
heatingControlInhibit = False
actualHeatingInhibition = False
INHIBITED_ROOM_TEMPERATURE = 20.0 # °C
#-----------------------------------------------

#------------AUXILIARY VARIABLES----------------
alarmCounting=False  #when door was opened and system locked
watchDogAlarmThread=0
alarmCnt=0
keyboardRefreshCnt=0
wifiCheckCnt=0
tmrPriceCalc = time.time()
gasSensorPrepared=False
tmrPrepareGasSensor = time.time()
alarm_last = 0

tmrRackComm = 0
tmrPowerwallComm=0
tmrConsPowerwall = 0
tmrVentHeatControl = 0

bufferedCellModVoltage = 24*[0]
solarPower = 0
powerwall_stateMachineStatus = 0

# cycle time
tmrCycleTime = 0
cycleTime_avg = 0
cycleTime_cnt = 0
cycleTime_tmp = time.time()
cycleTime = 0
cycleTime_max = 0
#-----------------------------------------------

MySQL = cMySQL()
MySQL_GeneralThread = cMySQL()
MySQL_phoneThread = cMySQL()

###############################################################################################################
def main():
    global watchDogAlarmThread, alarm, alarm_last, locked
    global tmrCycleTime,cycleTime_avg, cycleTime_cnt,cycleTime_tmp,cycleTime,cycleTime_max

    Log("Entry point main.py")
    try:
        #os.system("sudo service motion stop")
        Log("Initializing TCP port...")
        initTCP=True
        nOfTries=0
        while(initTCP):
            try:
                comm.Init()
                initTCP=False #succeeded
            except OSError:
                nOfTries+=1
                if(nOfTries>30):
                    raise Exception('Too much tries to create TCP port', ' ')
                print("Trying to create TCP port again..")
                time.sleep(10)
                
        Log("Ok")
        
        Log("Initializing serial port...")
        phone.Connect()
        Log("Ok")

        MySQL.RemoveOnlineDevices() # clean up online device table
        
        timerGeneral()#it will call itself periodically - new thread
      
        timerPhone()#it will call itself periodically - new thread
    
        
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
        Log(str(exc_type) +" : "+ str(fname) + " : " +str(exc_tb.tb_lineno))
        if RESTART_ON_EXCEPTION:
            Log("Rebooting Raspberry PI in one minute")
            
            os.system("shutdown -r 1")#reboot after one minute
            input("Reboot in one minute. Press Enter to continue...")
        return

    measureTimeMainLoop = MeasureTime()
    measureTimeComm = MeasureTime()
    measureTimePhone = MeasureTime()
    measureTimeDataRcv = MeasureTime()
    ######################## MAIN LOOP ####################################################################################
    while 1:
        measureTimeComm.Start()
        #TCP server communication - remote devices--------
        comm.Handle(MySQL)
        measureTimeComm.Measure()

        if comm.isTerminated():
            return# user interrupt termination

        measureTimePhone.Start()
        phone.Process()
        measureTimePhone.Measure()

        # ----------------------------------------------
        measureTimeDataRcv.Start()

        data = comm.DataReceived()
        processedData = []
        if data:
            MySQL.PersistentConnect()
            while data: # process all received packets
                try:
                    processedData += [data]
                    IncomingData(data)
                except IndexError:
                    Log("IndexError while processing incoming data! data:"+str(data))
                data = comm.DataReceived()
            MySQL.PersistentDisconnect()

        measureTimeDataRcv.Measure()
        if measureTimeDataRcv.getLastPeriod()>4:
            Log("Data RCV took "+"{:.1f}".format(measureTimeDataRcv.getMaxPeriod()) + " s")
            Log(processedData)
        # -------------------------------------------------

        watchDogAlarmThread=0 #to be able to detect lag in this loop

        CheckGasSensor()

        alarm_last = alarm

        measureTimeMainLoop.Measure()

        if measureTimeMainLoop.getMaxPeriod() > 6:
            measureTimeMainLoop.PrintOncePer(30,Log, "MainLoop")
            measureTimeDataRcv.PrintOncePer(30, Log, "Data rcv")
            measureTimeComm.PrintOncePer(30, Log, "Comm")
            measureTimePhone.PrintOncePer(30,Log,"Phone")
        measureTimeMainLoop.Start()
            

def ControlVentilation():# called each 5 mins
    global roomHumidity
    datetimeNow = datetime.now()
    dayTime = 8 < datetimeNow.hour < 21

    if roomHumidity is None:
        ventilationCommand = 99 # do not control
    elif roomHumidity >= 60.0 and dayTime:
        ventilationCommand = 3
    elif roomHumidity > 59.0:
        ventilationCommand = 2
    elif not dayTime:
        ventilationCommand = 1
    else:
        ventilationCommand = 99

    MySQL_GeneralThread.updateState("ventilationCommand", ventilationCommand)

def ControlHeating(): # called each 5 mins
    global heatingControlInhibit, actualHeatingInhibition, INHIBITED_ROOM_TEMPERATURE

    HYSTERESIS = 0.5 # +- °C

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

def CheckGasSensor():
    global  alarm, gasSensorPrepared

    if gasSensorPrepared:
        if not GPIO.input(PIN_GAS_ALARM):
            Log("RPI GAS ALARM!!");
            alarm |= GAS_ALARM_RPI
            MySQL.updateState("alarm", int(alarm))
            if alarm_last & GAS_ALARM_RPI == 0 and SMS_NOTIFICATION:
                phone.SendSMS(MY_NUMBER1, "Home system: fire/gas ALARM - RPI !!")
            KeyboardRefresh()
            PIRSensorRefresh()

    else:
        if time.time() - tmrPrepareGasSensor > 120:  # after 2 mins
            gasSensorPrepared = True

        
######################## General timer thread ##########################################################################
     
def timerGeneral():#it is calling itself periodically
    global alarmCounting,alarmCnt,alarm,watchDogAlarmThread ,MY_NUMBER1,keyboardRefreshCnt,wifiCheckCnt,tmrPriceCalc
    global tmrPowerwallComm, tmrRackComm, tmrVentHeatControl

    if keyboardRefreshCnt >= 4:
        keyboardRefreshCnt=0
        KeyboardRefresh()
        PIRSensorRefresh()
    else:
        keyboardRefreshCnt+=1

    if wifiCheckCnt >= 30:
        wifiCheckCnt = 0
        if not comm.Ping("192.168.0.4"):
           Log("UNABLE TO REACH ROUTER!")
    else:
        wifiCheckCnt = wifiCheckCnt + 1
        
    if tmrRackComm!=0 and time.time() - tmrRackComm > 200: # 200s - nothing came from rackUno for this time
        Log("Comm timeout for RackUNO!")
        tmrRackComm=0
        comm.RemoveOnlineDevice(MySQL_GeneralThread, IP_RACKUNO)
        
    if tmrPowerwallComm!=0 and time.time() - tmrPowerwallComm > 100: # 100s - nothing came from powerwall for this time
        Log("Comm timeout for Powerwall!")
        tmrPowerwallComm=0

        comm.RemoveOnlineDevice(MySQL_GeneralThread, IP_POWERWALL)

    if time.time() - tmrVentHeatControl > 300: # each 5 mins
        tmrVentHeatControl = time.time()
        ControlVentilation()
        ControlHeating()
        
    #check if there are data in mysql that we want to send
    data = MySQL_GeneralThread.getTxBuffer()
    if(len(data)):
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
                    comm.Send(MySQL_GeneralThread, byteArray,packet[1],crc16=True)
        except ValueError:
            Log("MySQL - getTXbuffer - Value Error:"+str(packet[0]))

    if alarmCounting:#user must make unlock until counter expires
        Log("Alarm check",FULL)
        alarmCnt+=1
        if alarmCnt>=10:
            alarmCnt=0
            
            Log("DOOR ALARM!!!!")
            alarm|=DOOR_ALARM
            alarmCounting=False

            if SMS_NOTIFICATION:
                phone.SendSMS(MY_NUMBER1,"Home system: door ALARM !!")

            MySQL_GeneralThread.updateState("alarm", int(alarm))
            KeyboardRefresh()
            PIRSensorRefresh()
         
    
    
    if time.time() - tmrPriceCalc > 3600*4:#each 4 hour
        tmrPriceCalc = time.time()
        try:
            electricityPrice.run()
        except Exception as e:
            Log("Exception for electricityPrice.run()")
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            Log(str(e))
            Log(str(exc_type) +" : "+ str(fname) + " : " +str(exc_tb.tb_lineno))

    if comm.isTerminated(): # do not continue if app terminated
        Log("Ending General thread, because comm is terminated.")
        return
    elif watchDogAlarmThread > 8:
        
        Log("Watchdog in alarm thread! Rebooting Raspberry PI in one minute")
        if RESTART_ON_EXCEPTION:
            os.system("shutdown -r 1")#reboot after one minute
    
    else:
        threading.Timer(8,timerGeneral).start()
        watchDogAlarmThread+=1

####################################################################################################################
def ExecuteTxCommand(mySQLinstance, data):
    global alarm
    if data[0] == 0:  # resetAlarm
        Log("Alarm deactivated by web interface.")
        alarm = 0
        mySQLinstance.updateState("alarm", int(alarm))
        KeyboardRefresh()
        PIRSensorRefresh()
    elif data[0] == 1:
        Log("TODO command")
        

def timerPhone():
    phone.ReadSMS()
    phone.CheckSignalInfo()
    
    #process incoming SMS
    for sms in phone.getIncomeSMSList():
        IncomingSMS(sms)
    phone.clearIncomeSMSList()

    
    MySQL_phoneThread.updateState('phoneSignalInfo',str(phone.getSignalInfo()));
    MySQL_phoneThread.updateState('phoneCommState',int(phone.getCommState()));
    
    if not comm.isTerminated(): # do not continue if app terminated
        threading.Timer(20,timerPhone).start()
  
def PIRSensorRefresh():
    
    Log("PIR sensor refresh!",FULL)
    
    comm.Send(MySQL, bytes([0,int(alarm != 0),int(locked)]),IP_PIR_SENSOR)  #id, alarm(0/1),locked(0/1)
  
def KeyboardRefresh():
    
    Log("Keyboard refresh!",FULL)
    val = (int(alarm != 0)) + 2*(int(locked))
    
    comm.Send(MySQL, bytes([10,val]),IP_KEYBOARD)  #id, alarm(0/1),locked(0/1)
  

def IncomingSMS(data):
    global alarm,locked, heatingControlInhibit, roomTemperature, roomHumidity
    if data[1] == MY_NUMBER1:
        if(data[0].startswith("get status")):

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
            txt += ", powerwall status:"+str(powerwall_stateMachineStatus)
            txt += ", solar power:" + str(int(solarPower))+" W"
            txt += ", room temp:{:.1f} C".format(roomTemperature)
            txt += ", room humid:{:.1f} %".format(roomHumidity)

            phone.SendSMS(data[1], txt)
            Log("Get status by SMS command.")
        elif(data[0].startswith("lock")):
            locked = True

            MySQL_phoneThread.updateState("locked",int(locked))
            Log("Locked by SMS command.")
        elif(data[0].startswith("unlock")):
            locked = False

            MySQL_phoneThread.updateState("locked", int(locked))
            Log("Unlocked by SMS command.")
        elif(data[0].startswith("deactivate alarm")):
            alarm = 0
            locked = False

            MySQL_phoneThread.updateState("alarm",int(alarm))
            MySQL_phoneThread.updateState("locked",int(locked))
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
    GPIO.output(PIN_BTN_PC,True)
    time.sleep(2)
    GPIO.output(PIN_BTN_PC,False)
    
def IncomingData(data):
    global alarm, tmrRackComm, bufferedCellModVoltage,solarPower,powerwall_stateMachineStatus,tmrConsPowerwall
    global alarmCounting, roomHumidity, rackUno_heatingInhibition, roomTemperature
    Log("Incoming data:"+str(data), FULL)
#[100, 3, 0, 0, 1, 21, 2, 119]
#ID,(bit0-door,bit1-gasAlarm),gas/256,gas%256,T/256,T%256,RH/256,RH%256)
    if data[0]==100:# data from keyboard
        doorSW = False if (data[1]&0x01)==0 else True
        gasAlarm = True if (data[1]&0x02)==0 else False
        gas = data[2]*256+data[3]
        temp = (data[4]*256+data[5])/10 + 0.5
        RH = (data[6]*256+data[7])/10
        
        MySQL.insertValue('bools','door switch 1',doorSW,periodicity =120*MINUTE, writeNowDiff = 1)
        #MySQL.insertValue('bools','gas alarm 1',gasAlarm,periodicity =30*MINUTE, writeNowDiff = 1)
        #MySQL.insertValue('gas','keyboard',gas)
        MySQL.insertValue('temperature','keyboard',temp,periodicity =60*MINUTE, writeNowDiff = 1)
        MySQL.insertValue('humidity','keyboard',RH,periodicity =60*MINUTE, writeNowDiff = 1)
        

     
        if(doorSW and locked and alarm&DOOR_ALARM == 0 and not alarmCounting):
            alarmCounting=True
            Log("LOCKED and DOORS opened")
    elif data[0]==101:#data from meteostations
        
        meteoTemp = (data[1]*256+data[2])
        if meteoTemp>32767:
            meteoTemp=meteoTemp-65536 #negative values are inverted like this
        
        MySQL.insertValue('temperature','meteostation 1',meteoTemp/100,periodicity =60*MINUTE, writeNowDiff = 0.5)
        MySQL.insertValue('pressure','meteostation 1',(data[3]*65536+data[4]*256+data[5])/100,periodicity =50*MINUTE, writeNowDiff = 100)
        MySQL.insertValue('voltage','meteostation 1',(data[6]*256+data[7])/1000,periodicity =50*MINUTE, writeNowDiff = 0.2)
        
    elif data[0]>10 and data[0]<=40:# POWERWALL
        voltage = (data[2]*256+data[3])/100
        if data[1]<24:
            bufferedCellModVoltage[data[1]] = voltage # we need to store voltages for each module, to calculate burning energy later
        temp = (data[4]*256+data[5])/10
        
        if voltage < 5:
            MySQL.insertValue('voltage','powerwall cell '+str(data[1]), voltage, periodicity =30*MINUTE, writeNowDiff = 0.1);
        if temp < 70:
            MySQL.insertValue('temperature','powerwall cell '+str(data[1]),temp, periodicity =30*MINUTE, writeNowDiff = 0.5);
    elif data[0]==10: # POWERWALL STATUS
        powerwall_stateMachineStatus = data[1]
        errorStatus = data[2]
        errorStatus_cause = data[3]
        
        MySQL.insertValue('status','powerwall_stateMachineStatus',powerwall_stateMachineStatus, periodicity =30*MINUTE, writeNowDiff=1)
        MySQL.insertValue('status','powerwall_errorStatus',errorStatus, periodicity =30*MINUTE, writeNowDiff=1)
        MySQL.insertValue('status','powerwall_errorStatus_cause',errorStatus_cause, periodicity =30*MINUTE, writeNowDiff=1)
                     
    elif data[0]==69:# general statistics from powerwall
        P = 60.0 # power of the heating element
        WhValue = (data[2]*256+data[1])*P/360.0 #counting pulse per 10s => 6 = P*1Wmin => P/360Wh
        if WhValue > 0:
            MySQL.insertValue('consumption','powerwall_heating',WhValue)
        if data[3] > 0:
            Log("CRC mismatch counter of BMS_controller not zero! Value:"+str(data[3]))
    elif data[0]>40 and data[0]<=69:# POWERWALL - calibrations
        volCal = struct.unpack('f',bytes([data[2],data[3],data[4],data[5]]))[0]
        tempCal = struct.unpack('f',bytes([data[6],data[7],data[8],data[9]]))[0]
        
        #MySQL.insertValue('BMS calibration','powerwall calib.'+str(data[1])+' volt',volCal,one_day_RP=True);
        #MySQL.insertValue('BMS calibration','powerwall calib.'+str(data[1])+' temp',tempCal,one_day_RP=True);
    elif data[0]>70 and data[0]<99:# POWERWALL - statistics
        valueToWrite = (data[2]*256+data[3])

        MySQL.insertValue('counter','powerwall cell '+str(data[1]),valueToWrite ,periodicity=60*MINUTE, writeNowDiff=1)
        
        # compensate dimensionless value from module to represent Wh
        # P=(U^2)/R
        # BurnedEnergy[Wh] = P*T/60
        if data[1]<24:
            bufVolt = bufferedCellModVoltage[data[1]]
            if bufVolt==0:
                bufVolt = 4 # it is too soon to have buffered voltage
        else:
            bufVolt = 4 # some sensible value if error occurs
        val = (data[4]*256+data[5]) # this value is counter for how long bypass was switched on
        T = 10 # each 10 min data comes.
        R = 2 # Ohms of burning resistor
        # coeficient, depends on T and on timer on cell module,
        # e.g. we get this value if we are burning 100% of period T
        valFor100Duty = 462 * T 
        
        Energy = (pow(bufVolt,2)/R)*T/60.0
        Energy = Energy*(min(val,valFor100Duty)/valFor100Duty) # duty calculation

        if Energy > 0:
            MySQL.insertValue('consumption','powerwall cell '+str(data[1]), Energy);
        
    elif data[0]==102:# data from Roomba
        MySQL.insertValue('voltage','roomba cell 1',(data[1]*256+data[2])/1000, periodicity =60*MINUTE, writeNowDiff = 0.2)
        MySQL.insertValue('voltage','roomba cell 2',(data[3]*256+data[4])/1000, periodicity =60*MINUTE, writeNowDiff = 0.2)
        MySQL.insertValue('voltage','roomba cell 3',(data[5]*256+data[6])/1000, periodicity =60*MINUTE, writeNowDiff = 0.2)
    elif data[0]==103:# data from rackUno
        tmrRackComm = time.time()
        #store power
        MySQL.insertValue('power','grid',(data[1]*256+data[2]), periodicity =30*MINUTE, writeNowDiff = 50)
        
        #now store consumption according to tariff
        stdTariff = (data[5]&0x01)==0
        detectSolarPower = (data[5] & 0x02) == 0
        rackUno_heatingInhibition = (data[5] & 0x04) == 0

        MySQL.insertValue('status', 'rackUno_detectSolarPower', int(detectSolarPower), periodicity =60*MINUTE, writeNowDiff = 1)

        if not stdTariff: # T1 - low tariff
            MySQL.insertValue('consumption','lowTariff',(data[3]*256+data[4])/60) # from power to consumption - 1puls=1Wh
        else:
            MySQL.insertValue('consumption','stdTariff',(data[3]*256+data[4])/60)# from power to consumption - 1puls=1Wh
        MySQL.insertValue('status','rackUno_stateMachineStatus',data[6], periodicity =60*MINUTE, writeNowDiff = 1)
    
    elif data[0]==104:# data from PIR sensor
        tempPIR = (data[1] * 256 + data[2])/10.0
        tempPIR = tempPIR - 0.0  # calibration - SHT20 is precalibrated from factory

        humidPIR = (data[3]*256+data[4])/10.0
        
        # check validity and store values
        if tempPIR>-30.0 and tempPIR < 80.0:
            MySQL.insertValue('temperature','PIR sensor',tempPIR,periodicity = 60*MINUTE, writeNowDiff = 1)
            roomTemperature = tempPIR
        else:
            roomTemperature = None

        if humidPIR>=0.0 and tempPIR <= 100.0:
            MySQL.insertValue('humidity','PIR sensor',humidPIR,periodicity =60*MINUTE, writeNowDiff = 1)
            roomHumidity = humidPIR
        else:
            roomHumidity = None
            
        MySQL.insertValue('gas','PIR sensor',(data[5]*256+data[6]),periodicity =60*MINUTE, writeNowDiff = 50)
    elif data[0]==105:# data from PIR sensor
        gasAlarm2 = data[1]
        PIRalarm = data[2]
        
        if gasAlarm2:
            Log("PIR GAS ALARM!!")
            alarm |= GAS_ALARM_PIR
            if (alarm_last & GAS_ALARM_PIR == 0):
                MySQL.updateState("alarm", int(alarm))

                txt = "Home system: PIR sensor - FIRE/GAS ALARM !!"
                Log(txt)
                if SMS_NOTIFICATION:
                    phone.SendSMS(MY_NUMBER1, txt)
                KeyboardRefresh()
                PIRSensorRefresh()
        elif PIRalarm and locked:
            alarm |= PIR_ALARM
            if (alarm_last & PIR_ALARM == 0):
                MySQL.updateState("alarm", int(alarm))

                txt = "Home system: PIR sensor - MOVEMENT ALARM !!"
                Log(txt)

                if SMS_NOTIFICATION:
                    phone.SendSMS(MY_NUMBER1, txt)
                KeyboardRefresh()
                PIRSensorRefresh()
    elif data[0]==106:# data from powerwall ESP
        powerwallVolt = (data[1]*256+data[2])/100.0
        MySQL.insertValue('voltage','powerwallSum',powerwallVolt,periodicity =30*MINUTE, writeNowDiff = 1)
        soc = calculatePowerwallSOC(powerwallVolt)
        MySQL.insertValue('status','powerwallSoc',soc,periodicity =30*MINUTE, writeNowDiff = 1)

        temperature = (data[3]*256+data[4])
        if temperature > 32767:
            temperature =  temperature - 65536 # negative temperatures
        MySQL.insertValue('temperature','powerwallOutside', temperature/100.0, periodicity =30*MINUTE, writeNowDiff = 2)
        solarPower = (data[5]*256+data[6])/100.0
        MySQL.insertValue('power','solar',solarPower)
        
        if time.time() - tmrConsPowerwall > 3600: # each hour
            tmrConsPowerwall = time.time()
            MySQL.insertDailySolarCons((data[7]*256+data[8])*10.0) # in 0.01 kWh

        MySQL.insertValue('status', 'powerwallEpeverBatteryStatus', data[9]*256+data[10], periodicity=30 * MINUTE, writeNowDiff = 1)
        MySQL.insertValue('status', 'powerwallEpeverChargerStatus', data[11]*256+data[12], periodicity=30 * MINUTE, writeNowDiff = 1)
        
    elif data[0]==0 and data[1]==1:#live event
        Log("Live event!",FULL)
    elif(data[0]<4 and len(data)>=2):#events for keyboard
            Log("Incoming keyboard event!"+str(data))
            comm.SendACK(data,IP_KEYBOARD)
            MySQL.insertEvent(data[0],data[1])
            IncomingEvent(data)
            
    elif(data[0]<10 and len(data)>=2):#other events
            Log("Incoming event!"+str(data))
            MySQL.insertEvent(data[0],data[1])
        
    else:
        Log("Unknown event, data:"+str(data));
    
def IncomingEvent(data):
    global locked,alarm,alarmCounting,alarmCnt
    
    alarmLast=alarm
    lockLast=locked
    if data[0]==3:
        if data[1]==2:#lock
            locked=True
        if data[1]==4:#doors opened and locked
            if not alarm:
                alarmCounting=True
            Log("LOCKED and DOORS opened event")
    if data[0]==1:
        if data[1]==1:#unlock PIN
            locked=False
            alarm=0
            alarmCounting=False
            alarmCnt=0
            Log("UNLOCKED by keyboard PIN")
    
    if data[0]==2:
        if data[1]==0:#unlock RFID
            locked=False
            alarm=0
            alarmCounting=False
            alarmCnt=0
            Log("UNLOCKED by keyboard RFID")
    
    if(lockLast!=locked or alarmLast != alarm):# change in locked state or alarm state
        KeyboardRefresh()
        PIRSensorRefresh()
        
        MySQL.updateState("locked", int(locked))
        MySQL.updateState("alarm", int(alarm))
        
        #if locked:
        #    os.system("sudo service motion start")
        #else:
        #    os.system("sudo service motion stop")


def Log(s,_verbosity=NORMAL):
    
    if _verbosity > verbosity:
        return
    print(str(s))

    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("logs/main.log","a") as file:
        file.write(dateStr+" >> "+str(s)+"\n")

if __name__ == "__main__":
        
    if(len(sys.argv)>1):
        if('delayStart' in sys.argv[1]):
            Log("Delayed start...")
            sleep(20)
    # execute only if run as a script
    main()
