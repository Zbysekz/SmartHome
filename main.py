#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os#we must add path to comm folder because inner scripts can now import other scripts in same folder directly
os.sys.path.append(os.path.dirname(os.path.realpath(__file__))+'/comm')

#for calculation of AVGs - the routines are located in web folder
import importlib.machinery
avgModule = importlib.machinery.SourceFileLoader('getMeas',os.path.abspath("/var/www/html/getMeas.py")).load_module()

import comm
import database
import time,threading
import phone
from datetime import datetime
from datetime import timedelta
import RPi.GPIO as GPIO


#-------------DEFINITIONS-----------------------
RESTART_ON_EXCEPTION = True
PIN_BTN_PC = 26

MY_NUMBER1 = "420602187490"

IP_METEO = '192.168.0.10'
IP_KEYBOARD = '192.168.0.11'
#-----------------------------------------------

#-------------STATE VARIABLES-------------------
alarm=False
locked=True #locked after startup
#-----------------------------------------------

#------------AUXILIARY VARIABLES----------------
alarmCounting=False#when door was opened and system locked
watchDogAlarmThread=0
alarmCnt=0
keyboardRefreshCnt=0
usingPhonePort=False#flag for reserving serial port to be used only by one thread at a time

avgCalcDone=False
avgCalcDone2=False
#-----------------------------------------------


###############################################################################################################
def main():
    global watchDogAlarmThread
    Log("Entry point main.py")
    try:
        Log("Initializing TCP port...")
        initTCP=True
        nOfTries=0
        while(initTCP):
            try:
                comm.Init()
                initTCP=False #succeeded
            except OSError as e:
                Log("ff")
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
        
        database.updateState(alarm,locked)
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

        data = comm.DataReceived()
        if(data!=[]):
            IncomingData(data)
        #-------------------------------------------------

        watchDogAlarmThread=0; #to be able to detect lag in this loop
        
######################## General timer thread ##########################################################################
     
def timerGeneral():#it is calling itself periodically
    global alarmCounting,alarmCnt,alarm,watchDogAlarmThread ,MY_NUMBER1,keyboardRefreshCnt,usingPhonePort
    
    if keyboardRefreshCnt >= 4:
        keyboardRefreshCnt=0
        KeyboardRefresh()
    else:
        keyboardRefreshCnt+=1

    
    if alarmCounting:#user must make unlock until counter expires
        Log("Alarm check")
        alarmCnt+=1
        if alarmCnt>=10:
            alarmCnt=0
            
            Log("ALARM!!!!")
            alarm=True
            alarmCounting=False

            while(usingPhonePort):#wait until phone port is free
                pass
            
            usingPhonePort=True
            phone.SendSMS(MY_NUMBER1,"Home system: door alarm !!")
            usingPhonePort=False
            
            
            database.updateState(alarm,locked)
            KeyboardRefresh()
    
    HandleAvgCalculation()
         
    if watchDogAlarmThread > 4:
        Log("Watchdog in alarm thread! Rebooting Raspberry PI in one minute")
        import os
        os.system("shutdown -r 1")#reboot after one minute
    
    else:
        threading.Timer(8,timerGeneral).start()
        watchDogAlarmThread+=1

####################################################################################################################
def HandleAvgCalculation():
    global avgCalcDone,avgCalcDone2
    
    #eevry zero hour calculate current day average
    if datetime.now().hour == 0:
        if not avgCalcDone:
            Log("Calculating AVGs...")
            timeTo = datetime.now()
            diff = timedelta(days = -1)
            timeFrom = timeTo + diff
            
            avgModule.AvgCalc_day_ext("m_key_t",timeFrom,timeTo,False)
            avgModule.AvgCalc_day_ext("m_key_rh",timeFrom,timeTo,False)
            
            avgModule.AvgCalc_day_ext("m_met_t",timeFrom,timeTo,False)
            avgModule.AvgCalc_day_ext("m_met_p",timeFrom,timeTo,False)
            avgModule.AvgCalc_day_ext("m_met_u",timeFrom,timeTo,False)
            
            Log("Calculating AVGs done")
            avgCalcDone = True
    else:
        avgCalcDone=False
        
    #every zero minute calculate current hour avarages
    if datetime.now().minute == 0:
        if not avgCalcDone2:
            
            Log("Calculating AVGs...")
            
            timeTo = datetime.now()
            diff = timedelta(hours = -1)
            timeFrom = timeTo + diff
            
            try:
                avgModule.AvgCalc_hour_ext("m_key_t",timeFrom,timeTo,False)
                avgModule.AvgCalc_hour_ext("m_key_rh",timeFrom,timeTo,False)
                
                avgModule.AvgCalc_hour_ext("m_met_t",timeFrom,timeTo,False)
                avgModule.AvgCalc_hour_ext("m_met_p",timeFrom,timeTo,False)
                avgModule.AvgCalc_hour_ext("m_met_u",timeFrom,timeTo,False)
            except Exception as inst:
                Log(type(inst))    # the exception instance
                Log(inst.args)     # arguments stored in .args
                Log(inst)
                
            Log("Calculating AVGs done")
            
            avgCalcDone2 = True
    else:
        avgCalcDone2=False
        

def timerPhone():
    global usingPhonePort
    
    while(usingPhonePort):#wait until phone port is free
        pass
    
    usingPhonePort=True
    
    phone.ReceiveCmds()
    phone.CheckUnreadSMS()
    phone.CheckSMSsent()

    usingPhonePort=False
    
    #process incoming SMS
    for sms in phone.getIncomeSMSList():
        IncomingSMS(sms)
    phone.clearIncomeSMSList()
    
    threading.Timer(5,timerPhone).start()
    
def KeyboardRefresh():
    global alarm,locked
    
    Log("Keyboard refresh!")
    val = (1 if alarm else 0) + (2 if locked else 0)
    
    comm.Send(bytes([10,val]),IP_KEYBOARD)  #id, alarm(0/1),locked(0/1)
  

def IncomingSMS(data):
    global alarm,locked
    if data[1] == '420602187490':
        if(data[0].startswith("get status")):
            phone.SendSMS(data[1],"Alarm" if alarm else ("Locked" if locked else "Stand-by"))
            Log("Get status by SMS command.")
        elif(data[0].startswith("lock")):
            locked = True

            database.updateState(alarm,locked)
            Log("Locked by SMS command.")
        elif(data[0].startswith("unlock")):
            locked = False

            database.updateState(alarm,locked)
            Log("Unlocked by SMS command.")
        elif(data[0].startswith("deactivate alarm")):
            alarm = False

            database.updateState(alarm,locked)
            Log("Alarm deactivated by SMS command.")
        elif(data[0].startswith("toggle PC")):
            Log("Toggle PC button by SMS command.")
            TogglePCbutton()
    
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
        
        database.insertValue('m_key_d',doorSW)
        database.insertValue('m_key_ga',gasAlarm)
        database.insertValue('m_key_g',gas)
        database.insertValue('m_key_t',temp)
        database.insertValue('m_key_rh',RH)
        
        global alarmCounting,locked
     
        if(doorSW and locked and not alarm and not alarmCounting):
            alarmCounting=True
            Log("LOCKED and DOORS opened")
    elif data[0]==101:#data z meteostanic
        database.insertValue('m_met_t',(data[1]*256+data[2])/100)
        database.insertValue('m_met_p',(data[3]*65536+data[4]*256+data[5])/100)
        database.insertValue('m_met_u',(data[6]*256+data[7])/1000)
    elif data[0]==0 and data[1]==1:#live event
        Log("Live event!")
    else:
        if(len(data)>=2):
            Log("Incoming event!")
            comm.SendACK(data,IP_KEYBOARD)
            database.insertEvent(getEventString1(data[0]),getEventString2(data[1]))
            IncomingEvent(data)
        else:
            Log("ERROR receving event!")
            
def getEventString1(id):#get text by event id
    textList = ["First event",
                "Second event"]
    if(id>len(textList) or id <0):
        return "id."+str(id)
    return textList[id]
    

def getEventString2(id):#get text by event sub id
    textList = ["First subevent",
                "Second subevent"]
    if(id>len(textList) or id <0):
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

        database.updateState(alarm,locked)
        

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
    # execute only if run as a script
    main()
