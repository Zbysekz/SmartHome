#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
from datetime import datetime
from enum import Enum

serPort = 0
incomeSMSList=[]
reqCheckUnread=False,reqSendSMS=False,reqSignalInfo=False
sendSMStext = ""
sendSMSreceiver = ""
timeout = 0
clearBufferWhenPhoneOffline=0

#stats
commState = False
signalStrength = 0

#---------------------------------------------------------------------------------------
def STATE_idle():
    global reqCheckUnread,reqSendSMS,reqSignalInfo
    
    if reqSendSMS:
        NextState(STATE_SMS_send)
        reqSendSMS=False
    elif reqSendSMS:
        NextState(STATE_SMS_send)
        reqSendSMS=False
    elif reqSignalInfo:
        NextState(STATE_SMS_send)
        reqSignalInfo=False


    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:#receiving of one way asynchronnous commands
        if(b"RING" in rcvLine):
            Log("Phone is ringing!!!")
        
    return "1"
 
def STATE_SMS_send():
    global serPort
    
    serPort.write(bytes("AT+CSQ\x0D",'UTF-8'));
        
    NextState();
    return "2"
 
def STATE_SMS_wait():
    NextState(STATE_idle);
    return "3"

def STATE_SIGNAL_req():
    global serPort
    
    serPort.write(bytes("AT+CSQ\x0D",'UTF-8'));

    NextState(STATE_SIGNAL_response);
    return ""
    
def STATE_SIGNAL_response():

    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:#receiving of one way asynchronnous commands
        if(b"+CSQ:" in rcvLine):
            
            Log("Phone is ringing!!!")
        
    
#---------------------------------------------------------------------------------------
stateList = [
    STATE_idle,
    STATE_SMS_send,
    STATE_SMS_wait
]

currState = STATE_idle
nextState = ""

def NextState(name = ""):
    global switcher,currState,nextState

    if name == "":
        idx = stateList.index(currState)
        idx = idx + 1
        nextState = stateList[idx]
    else:
        nextState = name
    

def Process():
    global currState,nextState

    if currState != "" and nextState != "" and currState != nextState:
        print("Transition to:"+nextState.__name__)
        currState = nextState
    
    # Execute the function
    print(currState())


def Connect():
    global serPort
    serPort = serial.Serial(
  
       port='/dev/ttyS0',
       baudrate = 9600,
       parity=serial.PARITY_NONE,
       stopbits=serial.STOPBITS_ONE,
       bytesize=serial.EIGHTBITS,
       timeout=0.1
    )

def getIncomeSMSList():
    global incomeSMSList
    return incomeSMSList

def clearIncomeSMSList():
    global incomeSMSList
    incomeSMSList.clear()

def CheckUnreadSMS():
    global reqCheckUnread
    reqCheckUnread = True
    
def CheckSignalInfo():
    global reqSignalInfo
    reqSignalInfo = True

def SendSMS(receiver,text):
    global sendSMSreceiver,sendSMStext,reqSendSMS
    
    if reqSendSMS:
        Log("Already sending SMS!")
        Log("Text:"+sendSMStext)
    else:
        reqSendSMS = True
        sendSMSreceiver = receiver
        sendSMStext = text

def getCommState():#status of communication with SIM800L module
    return commState


def ReceiveLinesFromSerial():
    global serPort,clearBufferWhenPhoneOffline

    maxChars = 200#maximalne tolik znaku lze precist
    rcvLine = bytes()
    rcvLines = []
    ptr=0
    ch = serPort.read(maxChars)
    
    if len(ch)==maxChars:#if we have received maximum characters, increase var and then reset input buffer - when phone is offline, input buffer is full of zeroes
        clearBufferWhenPhoneOffline += 1
    
    if (clearBufferWhenPhoneOffline>3):
        Log("Serial input buffer reset!")
        clearBufferWhenPhoneOffline=0
        serPort.reset_input_buffer()
        return []
    
    while(ptr<len(ch)):
    
        if(ch[ptr]==10):#b'\n'
            rcvLines.append(rcvLine)
            rcvLine=bytes()
            
        elif(ch[ptr]!=0):#b'\x00'
            #print(ch)
            #print("chr:"+chr(ord(ch)))
            #print(ch[ptr])
            rcvLine+=ch[ptr].to_bytes(1, byteorder='big')
        ptr += 1

    if(len(rcvLine)!=0):
        rcvLines.append(rcvLine)
    return rcvLines

commCheck = 0
sendingSMS = 0
receivingSMS = 0
rcvState = 0
UNREAD_SMS_TIME = 2 #x5s
unreadSMSTimer = UNREAD_SMS_TIME
MAX_TRIES = 3
numberOfTries = MAX_TRIES
TRY_TIME = 5#x5s
tryTimer = TRY_TIME
lastReceiver = ""
lastText = ""

idOfStoredSMS=0



 

def CheckUnreadSMS():
    global unreadSMSTimer,UNREAD_SMS_TIME,commCheck,serPort
    
    commCheck+=1#to detect that phone is not responding
    
    if unreadSMSTimer == 0:
        unreadSMSTimer = UNREAD_SMS_TIME
        
        Log("Checking Unread SMS!")
        
        serPort.write(bytes("AT+CPMS=\x22ME\x22,\x22ME\x22,\x22ME\x22\x0D",'UTF-8'));#\x22 = "
        
        time.sleep(0.5)
        
        serPort.write(bytes("AT+CMGL=0\x0D",'UTF-8'));#\x22 = " //0 unread, 1 read, 4 all
        
    else:
        unreadSMSTimer-=1

def ReceiveCmds():
    global sendingSMS,receivingSMS,MAX_TRIES,numberOfTries,incomeSMSList,idOfStoredSMS
    global serPort,commCheck
    
    rcvLines = ReceiveLinesFromSerial()
    #rcvLine = serPort.readline() #nejde pouzit, protoze kdyz je mobil vyplej tak se zasekne - asi nefunguje timout v knihovne?
    #rcvLines.append(rcvLine)

    for rcvLine in rcvLines:
        
        Log("Received from serial:"+str(rcvLine))
        if(rcvState==0):#prijimani jednorazovych prikazu
            
            if(b"RING" in rcvLine):
                Log("Mobile is ringing!!!")
            elif(b"+CMGW:" in rcvLine):
                Log("CMGW income!!!!")
                if sendingSMS==1:
                    idOfStoredSMS = -1
                    
                    pos = rcvLine.find(b"+CMGW:")
                    if len(rcvLine)>pos+8:
                        if rcvLine[pos+7] >=48 and rcvLine[pos+7]<=57:#pokud jsou to validni cisla na svych mistech
                            
                            if rcvLine[pos+8] >=48 and rcvLine[pos+8]<=57:#pokud je prvni i druhe validni
                                idOfStoredSMS = int(chr(rcvLine[pos+7]))*10 + int(chr(rcvLine[pos+8]))
                            else:
                                idOfStoredSMS = int(chr(rcvLine[pos+7]))#pokud je jen druhe validni             
                    
                    if idOfStoredSMS != 0:
                        CMSScommand(idOfStoredSMS)
                    sendingSMS=2
            elif(b"+CMGL:" in rcvLine):
                Log("CMGL income!")
                #pos = rcvLine.find(b"07")
                receivingSMS = 1
                Log(rcvLine)
                
                
            elif (b"OK\r" in rcvLine):
                Log("OK received!")
                commCheck=0#to detect that phone is not responding
                if(sendingSMS==2):
                    Log("CMGW OK received!")
                    sendingSMS=3
                elif(sendingSMS==3):
                    Log("Sending of SMS successful!")
                    CMGDcommand(idOfStoredSMS)#delete SMS stored in memory
                    numberOfTries = MAX_TRIES
                    sendingSMS=0
            elif(receivingSMS==1 and rcvLine[0]==ord("0") and rcvLine[1]==ord("7")):
                txt,transmitter = DecodePDU(str(rcvLine))
                incomeSMSList.append((txt,transmitter))
                
                Log("RECEIVED SMS:"+txt+",from:"+transmitter)
            else:
                receivingSMS=0
                Log("Not processed.")
                    




    
def SendSMS(receiver, text):
    global serPort,sendingSMS,lastReceiver,lastText
    
    Log("Sending SMS !")
    
    if(sendingSMS!=0):
        Log("Already sending SMS ! Aborting !!")
        return
    
    lastReceiver = receiver
    lastText = text
        
    output,telegramLen = codePDU(receiver,text)
    
    serPort.write(bytes("AT+CPMS=\x22ME\x22,\x22ME\x22,\x22ME\x22\x0D",'UTF-8'));#\x22 = "
	
    telegramLen=telegramLen/2 - 8
    
    pomCmd = "AT+CMGW=";
    pomCmd+=chr(int(((telegramLen)/10)+48));#convert to number instead of two 00
    pomCmd+=chr(int(((telegramLen)%10)+48));#
		
    
    time.sleep(0.5)
    x = serPort.readline()
    if(len(x)>0):
        print("rcvd:"+str(x))
    
    Log("sending cmd:"+pomCmd)
    serPort.write(bytes(pomCmd+"\x0D",'UTF-8'));#CMGW
	
	#add SUB character -> value 26 na konec

    time.sleep(0.5)
    x = serPort.readline()
    if(len(x)>0):
        print("rcvd:"+str(x))
    print(output)
    #output = "079124602009999011000C912460208147090000FF0441F45B0D"
    
    print("sending output:"+output)
    serPort.write(bytes(output+"\x1A\x0D",'UTF-8'))#posle zpravu CMGW
 
    sendingSMS=1         
    





def Log(s):
    print("LOGGED:"+str(s))

    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("logs/phone.log","a") as file:
        file.write(dateStr+" >> "+str(s)+"\n")
