#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os#we must add path to comm folder because inner scripts can now import other scripts in same folder directly
os.sys.path.append(os.path.dirname(os.path.realpath(__file__))+'/comm')

#for calculation of AVGs - the routines are located in web folder
#import importlib.machinery
#avgModule = importlib.machinery.SourceFileLoader('getMeas',os.path.abspath("/var/www/SmartHomeWeb/getMeas.py")).load_module()

import comm
import databaseInfluxDB
import databaseSQLite
import time,threading
import phone
from datetime import datetime
import RPi.GPIO as GPIO
from time import sleep
import sys
import struct


#-------------DEFINITIONS-----------------------
RESTART_ON_EXCEPTION = True
PIN_BTN_PC = 26

MY_NUMBER1 = "+420602187490"

IP_METEO = '192.168.0.10'
IP_KEYBOARD = '192.168.0.11'
#-----------------------------------------------

#-------------STATE VARIABLES-------------------
alarm=False
locked=False #locked after startup
#-----------------------------------------------

#------------AUXILIARY VARIABLES----------------
alarmCounting=False#when door was opened and system locked
watchDogAlarmThread=0
alarmCnt=0
keyboardRefreshCnt=0
wifiCheckCnt=0

#-----------------------------------------------


###############################################################################################################
def main():
    global watchDogAlarmThread,alarm,locked
    Log("Entry point main.py")
    try:
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
        
        timerGeneral()#it will call itself periodically - new thread
      
        timerPhone()#it will call itself periodically - new thread
    
        
        Log("Initializing pin for PC button...")
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_BTN_PC, GPIO.OUT)
        GPIO.setwarnings(False)
        Log("Ok")
        
        databaseSQLite.updateState(alarm,locked)
    except Exception as inst:
        Log(type(inst))    # the exception instance
        Log(inst.args)     # arguments stored in .args
        Log(inst)
        if RESTART_ON_EXCEPTION:
            Log("Rebooting Raspberry PI in one minute")
            import os
            os.system("shutdown -r 1")#reboot after one minute
            input("Reboot in one minute. Press Enter to continue...")
        return
######################## MAIN LOOP ####################################################################################
    while(1):

        #TCP server communication - remote devices--------
        comm.Handle()
    
        phone.Process()
        
        data = comm.DataReceived()
        if(data!=[]):
            IncomingData(data)
        #-------------------------------------------------

        watchDogAlarmThread=0; #to be able to detect lag in this loop
        
######################## General timer thread ##########################################################################
     
def timerGeneral():#it is calling itself periodically
    global alarmCounting,alarmCnt,alarm,watchDogAlarmThread ,MY_NUMBER1,keyboardRefreshCnt,wifiCheckCnt
    
    if keyboardRefreshCnt >= 4:
        keyboardRefreshCnt=0
        KeyboardRefresh()
    else:
        keyboardRefreshCnt+=1

    if wifiCheckCnt >= 30:
        wifiCheckCnt = 0
        if not comm.Ping("192.168.0.4"):
           Log("UNABLE TO REACH ROUTER!")
    else:
        wifiCheckCnt = wifiCheckCnt + 1
    
    #check if there are data in sqlite3 that we want to send
    data = databaseSQLite.getTXbuffer()
    if(len(data)):
        try:
            for packet in data:
                byteArray = bytes([int(x) for x in packet[0].split(',')])
                print("Sending data from SQLITE database:")
                print(byteArray)
                print(packet[1])
                comm.Send(byteArray,packet[1])
        except ValueError:
            Log("SQLite - getTXbufder - Value Error:"+str(packet[0]))
            
    if alarmCounting:#user must make unlock until counter expires
        Log("Alarm check")
        alarmCnt+=1
        if alarmCnt>=10:
            alarmCnt=0
            
            Log("ALARM!!!!")
            alarm=True
            alarmCounting=False

            phone.SendSMS(MY_NUMBER1,"Home system: door alarm !!")
            
            databaseSQLite.updateState(alarm,locked)
            KeyboardRefresh()
         
    if watchDogAlarmThread > 4:
        
        Log("Watchdog in alarm thread! Rebooting Raspberry PI in one minute")
        if RESTART_ON_EXCEPTION:
            import os
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

    
    databaseSQLite.updateValue('phoneSignalInfo',str(phone.getSignalInfo()));
    databaseSQLite.updateValue('phoneCommState',int(phone.getCommState()));
    
    threading.Timer(20,timerPhone).start()
    
def KeyboardRefresh():
    global alarm,locked
    
    #Log("Keyboard refresh!")
    val = (1 if alarm else 0) + (2 if locked else 0)
    
    comm.Send(bytes([10,val]),IP_KEYBOARD)  #id, alarm(0/1),locked(0/1)
  

def IncomingSMS(data):
    global alarm,locked
    if data[1] == MY_NUMBER1:
        if(data[0].startswith("get status")):
            phone.SendSMS(data[1],"Alarm" if alarm else ("Locked" if locked else "Stand-by"))
            Log("Get status by SMS command.")
        elif(data[0].startswith("lock")):
            locked = True

            databaseSQLite.updateState(alarm,locked)
            Log("Locked by SMS command.")
        elif(data[0].startswith("unlock")):
            locked = False

            databaseSQLite.updateState(alarm,locked)
            Log("Unlocked by SMS command.")
        elif(data[0].startswith("deactivate alarm")):
            alarm = False

            databaseSQLite.updateState(alarm,locked)
            Log("Alarm deactivated by SMS command.")
        elif(data[0].startswith("toggle PC")):
            Log("Toggle PC button by SMS command.")
            TogglePCbutton()
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

    #print ("DATA INCOME!!:"+str(data))
#[100, 3, 0, 0, 1, 21, 2, 119]
#ID,(bit0-door,bit1-gasAlarm),gas/256,gas%256,T/256,T%256,RH/256,RH%256)
    if data[0]==100:
        doorSW = False if (data[1]&0x01)==0 else True
        gasAlarm = True if (data[1]&0x02)==0 else False
        gas = data[2]*256+data[3]
        temp = (data[4]*256+data[5])/10 + 0.5
        RH = (data[6]*256+data[7])/10
        
        databaseInfluxDB.insertValue('bools','door switch 1',doorSW)
        databaseInfluxDB.insertValue('bools','gas alarm',gasAlarm)
        databaseInfluxDB.insertValue('gas','keyboard',gas)
        databaseInfluxDB.insertValue('temperature','keyboard',temp)
        databaseInfluxDB.insertValue('humidity','keyboard',RH)
        
        databaseSQLite.updateValue('temp1',temp);
        databaseSQLite.updateValue('humidity',RH);
        
        global alarmCounting,locked
     
        if(doorSW and locked and not alarm and not alarmCounting):
            alarmCounting=True
            Log("LOCKED and DOORS opened")
    elif data[0]==101:#data from meteostations
        
        meteoTemp = (data[1]*256+data[2])
        if meteoTemp>32767:
            meteoTemp=meteoTemp-65536 #negative values are inverted like this
        
        databaseInfluxDB.insertValue('temperature','meteostation 1',meteoTemp/100)
        databaseInfluxDB.insertValue('pressure','meteostation 1',(data[3]*65536+data[4]*256+data[5])/100)
        databaseInfluxDB.insertValue('voltage','meteostation 1',(data[6]*256+data[7])/1000)
        
        databaseSQLite.updateValue('temp2',(data[1]*256+data[2])/100);
        databaseSQLite.updateValue('pressure',(data[3]*65536+data[4]*256+data[5])/100);
        databaseSQLite.updateValue('voltageMet',(data[6]*256+data[7])/1000);
    elif data[0]>10 and data[0]<=40:
        databaseInfluxDB.insertValue('voltage','BMS '+str(data[1]),(data[2]*256+data[3])/1000);
        databaseInfluxDB.insertValue('temperature','BMS '+str(data[1]),(data[4]*256+data[5])/100);
    elif data[0]>40 and data[0]<70:
        volCal = struct.unpack('f',bytes([data[2],data[3],data[4],data[5]]))[0]
        tempCal = struct.unpack('f',bytes([data[6],data[7],data[8],data[9]]))[0]
        
        databaseInfluxDB.insertValue('BMS calibration','BMS '+str(data[1])+' volt',volCal,one_day_RP=True);
        databaseInfluxDB.insertValue('BMS calibration','BMS '+str(data[1])+' temp',tempCal,one_day_RP=True);
        
    elif data[0]==0 and data[1]==1:#live event
        Log("Live event!")
    elif(data[0]<10 and len(data)>=2):#other events, reserved for keyboard
            Log("Incoming event!")
            comm.SendACK(data,IP_KEYBOARD)
            databaseInfluxDB.insertEvent(getEventString1(data[0]),getEventString2(data[1]))
            IncomingEvent(data)
    else:
        Log("Unknown event, data:"+data);
            
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
            alarm=False
            alarmCounting=False
            alarmCnt=0
    
    if data[0]==2:
        if data[1]==0:#unlock RFID
            locked=False
            alarm=False
            alarmCounting=False
            alarmCnt=0
    
    if(lockLast!=locked or alarmLast != alarm):
        KeyboardRefresh()

        databaseSQLite.updateState(alarm,locked)
        

def getState():
    global alarm,locked
    
    if alarm:
        return 1
    if locked:
        return 2
    return 0

def Log(s):
    print("LOGGED:"+str(s))

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
