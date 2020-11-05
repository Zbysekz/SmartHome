#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os#we must add path to comm folder because inner scripts can now import other scripts in same folder directly
os.sys.path.append(os.path.dirname(os.path.realpath(__file__))+'/comm')

#for calculation of AVGs - the routines are located in web folder
#import importlib.machinery
#avgModule = importlib.machinery.SourceFileLoader('getMeas',os.path.abspath("/var/www/SmartHomeWeb/getMeas.py")).load_module()

import comm
import databaseMySQL
import time, threading
import phone
from datetime import datetime
import RPi.GPIO as GPIO
from time import sleep
import sys
import struct
import electricityPrice
import time

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

NORMAL = 0
RICH = 1
FULL = 2
verbosity = RICH
#-----------------------------------------------

#-------------STATE VARIABLES-------------------
locked=False #locked after startup

NO_ALARM = 0x00
DOOR_ALARM = 0x01      #DOOR ALARM when system was locked
GAS_ALARM_RPI = 0x02   #GAS alarm of the RPI module
GAS_ALARM_PIR = 0x04   #GAS alarm of the PIR sensor module
PIR_ALARM = 0x08       #PIR sensor detected motion when system was locked
alarm=0

#-----------------------------------------------

#------------AUXILIARY VARIABLES----------------
alarmCounting=False  #when door was opened and system locked
watchDogAlarmThread=0
alarmCnt=0
keyboardRefreshCnt=0
wifiCheckCnt=0
tmrPriceCalc = 0
gasSensorPrepared=False
tmrPrepareGasSensor = time.time()
alarm_last = 0
#-----------------------------------------------

###############################################################################################################
def main():
    global watchDogAlarmThread, alarm, alarm_last, locked

    Log("Entry point main.py")
    try:
        os.system("sudo service motion stop")
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

        databaseMySQL.RemoveOnlineDevices()
        
        timerGeneral()#it will call itself periodically - new thread
      
        timerPhone()#it will call itself periodically - new thread
    
        
        Log("Initializing pin for PC button...")
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_BTN_PC, GPIO.OUT)
        GPIO.setup(PIN_GAS_ALARM, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        Log("Ok")

        databaseMySQL.updateState("locked", int(locked))
        databaseMySQL.updateState("alarm", int(alarm))

    except Exception as inst:
        Log(type(inst))    # the exception instance
        Log(inst.args)     # arguments stored in .args
        Log(inst)
        if RESTART_ON_EXCEPTION:
            Log("Rebooting Raspberry PI in one minute")
            
            os.system("shutdown -r 1")#reboot after one minute
            input("Reboot in one minute. Press Enter to continue...")
        return
######################## MAIN LOOP ####################################################################################
    while(1):
        #TCP server communication - remote devices--------
        comm.Handle()

        if comm.isTerminated():
            return# user interrupt termination

        phone.Process()
        
        data = comm.DataReceived()
        while(data!=[]): # process all received packets
            IncomingData(data)
            data = comm.DataReceived()
        #-------------------------------------------------

        watchDogAlarmThread=0; #to be able to detect lag in this loop

        CheckGasSensor();

        alarm_last = alarm
            


def CheckGasSensor():
    global  alarm, gasSensorPrepared

    if gasSensorPrepared:
        if (not GPIO.input(PIN_GAS_ALARM)):
            Log("RPI GAS ALARM!!");
            alarm |= GAS_ALARM_RPI
            databaseMySQL.updateState("alarm", int(alarm))
            if (alarm_last & GAS_ALARM_RPI == 0 and SMS_NOTIFICATION):
                phone.SendSMS(MY_NUMBER1, "Home system: fire/gas ALARM - RPI !!")
            KeyboardRefresh()
            PIRSensorRefresh()

    else:
        if time.time() - tmrPrepareGasSensor > 120:  # after 2 mins
            gasSensorPrepared = True

        
######################## General timer thread ##########################################################################
     
def timerGeneral():#it is calling itself periodically
    global alarmCounting,alarmCnt,alarm,watchDogAlarmThread ,MY_NUMBER1,keyboardRefreshCnt,wifiCheckCnt,tmrPriceCalc
    
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
    
    #check if there are data in sqlite3 that we want to send
    data = databaseMySQL.getTXbuffer()
    if(len(data)):
        try:
            for packet in data:
                byteArray = bytes([int(x) for x in packet[0].split(',')])
                print("Sending data from SQLITE database:")
                print(byteArray)
                print(packet[1])
                comm.Send(byteArray,packet[1],crc16=True)
        except ValueError:
            Log("SQLite - getTXbuffer - Value Error:"+str(packet[0]))

    data = databaseMySQL.getCmds()
    if data is not None:
        if data[0] is not None:#heatingInihibt
            comm.Send(bytes([1, data[0]]), IP_RACKUNO)
        if data[1] is not None:#ventilationCmd
            comm.Send(bytes([2, data[1]]), IP_RACKUNO)
        if data[2] is not None:  # resetAlarm
            Log("Alarm deactivated by web interface.")
            alarm = 0
            databaseMySQL.updateState("alarm", int(alarm))
            KeyboardRefresh()
            PIRSensorRefresh()

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

            databaseMySQL.updateState("alarm", int(alarm))
            KeyboardRefresh()
            PIRSensorRefresh()
         
    
    
    if time.time() - tmrPriceCalc > 3600:#each 1 hour
        tmrPriceCalc = time.time()
        try:
            electricityPrice.run()
        except Exception as inst:
            Log("Exception for electricityPrice.run()")
            Log(type(inst))  # the exception instance
            Log(inst.args)  # arguments stored in .args
            Log(inst)

    if not comm.isTerminated(): # do not continue if app terminated
        return
    elif watchDogAlarmThread > 4:
        
        Log("Watchdog in alarm thread! Rebooting Raspberry PI in one minute")
        if RESTART_ON_EXCEPTION:
            os.system("shutdown -r 1")#reboot after one minute
    
    else:
        threading.Timer(8,timerGeneral).start()
        watchDogAlarmThread+=1

####################################################################################################################

def timerPhone():
    phone.ReadSMS()
    phone.CheckSignalInfo()
    
    #process incoming SMS
    for sms in phone.getIncomeSMSList():
        IncomingSMS(sms)
    phone.clearIncomeSMSList()

    
    databaseMySQL.updateState('phoneSignalInfo',str(phone.getSignalInfo()));
    databaseMySQL.updateState('phoneCommState',int(phone.getCommState()));
    
    if not comm.isTerminated(): # do not continue if app terminated
        threading.Timer(20,timerPhone).start()
  
def PIRSensorRefresh():
    
    Log("PIR sensor refresh!",FULL)
    
    comm.Send(bytes([0,int(alarm != 0),int(locked)]),IP_PIR_SENSOR)  #id, alarm(0/1),locked(0/1)
  
def KeyboardRefresh():
    
    Log("Keyboard refresh!",FULL)
    val = (int(alarm != 0)) + 2*(int(locked))
    
    comm.Send(bytes([10,val]),IP_KEYBOARD)  #id, alarm(0/1),locked(0/1)
  

def IncomingSMS(data):
    global alarm,locked
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

            phone.SendSMS(data[1], txt)
            Log("Get status by SMS command.")
        elif(data[0].startswith("lock")):
            locked = True

            databaseMySQL.updateState("locked",int(locked))
            Log("Locked by SMS command.")
        elif(data[0].startswith("unlock")):
            locked = False

            databaseMySQL.updateState("locked", int(locked))
            Log("Unlocked by SMS command.")
        elif(data[0].startswith("deactivate alarm")):
            alarm = 0
            locked = False

            databaseMySQL.updateState("alarm",int(alarm))
            databaseMySQL.updateState("locked",int(locked))
            Log("Alarm deactivated by SMS command.")
        elif data[0].startswith("toggle PC"):
            Log("Toggle PC button by SMS command.")
            TogglePCbutton()
        elif data[0].startswith("heating on"):
            Log("Heating on by SMS command.")
            comm.Send(bytes([1, 0]), IP_RACKUNO)
        elif data[0].startswith("heating off"):
            Log("Heating off by SMS command.")
            comm.Send(bytes([1, 1]), IP_RACKUNO)
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
    global alarm
    Log("Incoming data:"+str(data), FULL)
#[100, 3, 0, 0, 1, 21, 2, 119]
#ID,(bit0-door,bit1-gasAlarm),gas/256,gas%256,T/256,T%256,RH/256,RH%256)
    if data[0]==100:# data from keyboard
        doorSW = False if (data[1]&0x01)==0 else True
        gasAlarm = True if (data[1]&0x02)==0 else False
        gas = data[2]*256+data[3]
        temp = (data[4]*256+data[5])/10 + 0.5
        RH = (data[6]*256+data[7])/10
        
        databaseMySQL.insertValue('bools','door switch 1',doorSW)
        databaseMySQL.insertValue('bools','gas alarm 1',gasAlarm)
        #databaseMySQL.insertValue('gas','keyboard',gas)
        databaseMySQL.insertValue('temperature','keyboard',temp)
        databaseMySQL.insertValue('humidity','keyboard',RH)
        
        global alarmCounting,locked
     
        if(doorSW and locked and alarm&DOOR_ALARM == 0 and not alarmCounting):
            alarmCounting=True
            Log("LOCKED and DOORS opened",RICH)
    elif data[0]==101:#data from meteostations
        
        meteoTemp = (data[1]*256+data[2])
        if meteoTemp>32767:
            meteoTemp=meteoTemp-65536 #negative values are inverted like this
        
        databaseMySQL.insertValue('temperature','meteostation 1',meteoTemp/100)
        databaseMySQL.insertValue('pressure','meteostation 1',(data[3]*65536+data[4]*256+data[5])/100)
        databaseMySQL.insertValue('voltage','meteostation 1',(data[6]*256+data[7])/1000)
        
    elif data[0]>10 and data[0]<=40:
        databaseMySQL.insertValue('voltage','BMS '+str(data[1]),(data[2]*256+data[3])/100);
        databaseMySQL.insertValue('temperature','BMS '+str(data[1]),(data[4]*256+data[5])/100);
    elif data[0]>40 and data[0]<70:
        volCal = struct.unpack('f',bytes([data[2],data[3],data[4],data[5]]))[0]
        tempCal = struct.unpack('f',bytes([data[6],data[7],data[8],data[9]]))[0]
        
        databaseMySQL.insertValue('BMS calibration','BMS '+str(data[1])+' volt',volCal,one_day_RP=True);
        databaseMySQL.insertValue('BMS calibration','BMS '+str(data[1])+' temp',tempCal,one_day_RP=True);
    
    elif data[0]==102:# data from Roomba
        databaseMySQL.insertValue('voltage','roomba cell 1',(data[1]*256+data[2])/1000)
        databaseMySQL.insertValue('voltage','roomba cell 2',(data[3]*256+data[4])/1000)
        databaseMySQL.insertValue('voltage','roomba cell 3',(data[5]*256+data[6])/1000)
    elif data[0]==103:# data from rackUno
        #store power
        databaseMySQL.insertValue('power','grid',(data[1]*256+data[2]))
        
        #now store consumption according to tariff
        if data[3]!=0: # T1
            databaseMySQL.insertValue('consumption','lowTariff',(data[1]*256+data[2])/60) # from power to consumption - 1puls=1Wh
        else:
            databaseMySQL.insertValue('consumption','stdTariff',(data[1]*256+data[2])/60)# from power to consumption - 1puls=1Wh
    
    elif data[0]==104:# data from PIR sensor
        tempPIR = (data[1] * 256 + data[2])/10.0
        tempPIR = tempPIR - 4.2  # calibration

        humidPIR = (data[3]*256+data[4])/10.0
        
        # check validity and store values
        if tempPIR>-30.0 and tempPIR < 80.0:
            databaseMySQL.insertValue('temperature','PIR sensor',tempPIR)
        if humidPIR>=0.0 and tempPIR <= 100.0:
            databaseMySQL.insertValue('humidity','PIR sensor',humidPIR)
            
        databaseMySQL.insertValue('gas','PIR sensor',(data[5]*256+data[6]))
    elif data[0]==105:# data from PIR sensor
        gasAlarm2 = data[1]
        PIRalarm = data[2]
        
        if gasAlarm2:
            Log("PIR GAS ALARM!!")
            alarm |= GAS_ALARM_PIR
            if (alarm_last & GAS_ALARM_PIR == 0):
                databaseMySQL.updateValue("alarm", int(alarm))

                txt = "Home system: PIR sensor - FIRE/GAS ALARM !!"
                Log(txt)
                if SMS_NOTIFICATION:
                    phone.SendSMS(MY_NUMBER1, txt)
                KeyboardRefresh()
                PIRSensorRefresh()
        elif PIRalarm and locked:
            alarm |= PIR_ALARM
            if (alarm_last & PIR_ALARM == 0):
                databaseMySQL.updateState("alarm", int(alarm))

                txt = "Home system: PIR sensor - MOVEMENT ALARM !!"
                Log(txt)

                if SMS_NOTIFICATION:
                    phone.SendSMS(MY_NUMBER1, txt)
                KeyboardRefresh()
                PIRSensorRefresh()

    elif data[0]==0 and data[1]==1:#live event
        Log("Live event!",FULL)
    elif(data[0]<10 and len(data)>=2):#other events, reserved for keyboard
            Log("Incoming event!")
            comm.SendACK(data,IP_KEYBOARD)
            databaseMySQL.insertEvent(getEventString1(data[0]),getEventString2(data[1]))
            IncomingEvent(data)
    else:
        Log("Unknown event, data:"+str(data));
            
def getEventString1(id):#get text by event id
    textList = ["First event",
                "Second event"]
    if(id>=len(textList) or id <0):
        return "id."+str(id)
    return textList[id]
    

def getEventString2(id):#get text by event sub id
    textList = ["First subevent",
                "Second subevent"]
    if(id>=len(textList) or id <0):
        return "id."+str(id)
    return textList[id]
    
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
        
        databaseMySQL.updateState("locked", int(locked))
        databaseMySQL.updateState("alarm", int(alarm))
        
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
