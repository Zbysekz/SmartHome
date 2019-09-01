#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
from datetime import datetime
from enum import Enum
import time

NORMAL = 0
RICH = 1
FULL = 2
verbosity = NORMAL

serPort = 0
incomeSMSList=[]
reqReadSMS=False
reqSendSMS=False
reqSignalInfo=False

signalStrength=0
qualityIndicator="Not available"

receiverNumber=""

sendSMStext = ""
sendSMSreceiver = ""
readSMStext = ""
readSMSsender = ""
nOfReceivedSMS = 0
tmrTimeout = 0
clearBufferWhenPhoneOffline=0

#stats
commState = False
signalStrength = 0

#---------------------------------------------------------------------------------------
def STATE_idle():
    global reqReadSMS,reqSendSMS,reqSignalInfo
    
    if reqSendSMS:
        NextState(STATE_SMS_send)
        reqSendSMS=False
    elif reqReadSMS:
        NextState(STATE_SMS_read)
        reqReadSMS=False
    elif reqSignalInfo:
        NextState(STATE_SIGNAL_req)
        reqSignalInfo=False


    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:#receiving of one way asynchronnous commands
        if(b"RING" in rcvLine):
            Log("Phone is ringing!!!")

def STATE_SMS_sendFail():#if sendinf SMS fail, wait for some time and try it again
    if CheckTimeout(60):
        reqSendSMS=True
        NextState(STATE_idle)
         
def STATE_SMS_send():
    global serPort
    
    serPort.write(bytes("AT+CMGF=1\x0D",'UTF-8'));
        
    NextState();
 
def STATE_SMS_send2():
    global serPort,commState
    
    
    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:
        if(b"OK" in rcvLine):
            serPort.write(bytes("AT+CMGS=\x22"+receiverNumber+"\x22\x0D",'UTF-8'));# \x22 is "
            NextState();
            break

    if CheckTimeout(5):
        Log("Timeout in state:"+str(currState))
        NextState(STATE_SMS_sendFail)
        commState=False

def STATE_SMS_send3():
    global serPort,commState
    
    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:
        if(b">" in rcvLine):
            serPort.write(bytes(sendSMStext+"\x1A",'UTF-8'));
            NextState();
            break
        
    if CheckTimeout(5):
        Log("Timeout in state:"+str(currState))
        NextState(STATE_SMS_sendFail)
        commState=False

def STATE_SMS_sendVerify():
    global serPort,commState
    
    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:
        if(b"OK" in rcvLine):
            Log("SMS succesfully sent!")
            NextState(STATE_idle);
            commState=True
            break
        
    if CheckTimeout(5):
        Log("Timeout in state:"+str(currState))
        NextState(STATE_SMS_sendFail)
        commState=False

def STATE_SMS_read():
    global serPort
    
    serPort.write(bytes("AT+CMGF=1\x0D",'UTF-8'));
        
    NextState();
    
def STATE_SMS_read2():
    global serPort,readSMSsender, nOfReceivedSMS,commState
    
    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:
        if(b"OK" in rcvLine):
            serPort.write(bytes("AT+CMGL=\x22ALL\x22\x0D",'UTF-8'));
            
            readSMSsender = ""
            nOfReceivedSMS = 0
    
            NextState();
            break

    if CheckTimeout(5):
        Log("Timeout in state:"+str(currState))
        NextState(STATE_idle)
        commState=False
    
    
def STATE_SMS_read3():
    global readSMSsender, readSMStext, incomeSMSList, nOfReceivedSMS, commState

    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:#receiving of one way asynchronnous commands
        try:
            if readSMSsender!="":
                readSMStext = rcvLine.decode("utf-8").replace('\r','')
                
                nOfReceivedSMS = nOfReceivedSMS + 1
                
                incomeSMSList.append((readSMStext,readSMSsender))
                readSMSsender = ""
                continue
            elif(b"+CMGL:" in rcvLine):
                ss = rcvLine.decode("utf-8")
                readSMSsender = ss.split(',')[2].replace('"','')
                continue
            elif(b"OK" in rcvLine):
                if nOfReceivedSMS > 0:
                    NextState(STATE_SMS_delete);
                else:
                    NextState(STATE_idle);
                
                Log("Check completed, received "+str(nOfReceivedSMS) + " SMS",FULL)
                Log(incomeSMSList,FULL)

                commState=True
                break
        except:
            continue

    if CheckTimeout(10):
        Log("Timeout in state:"+str(currState))
        NextState(STATE_idle)
        commState=False
        
def STATE_SMS_delete():
    global serPort
    
    serPort.write(bytes("AT+CMGDA=\x22DEL ALL\x22\x0D",'UTF-8'));
    
    NextState();
    
def STATE_SMS_delete2():
    global commState
    
    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:#receiving of one way asynchronnous commands
        try:
            if(b"OK" in rcvLine):
                NextState(STATE_idle)
        except:
            continue

    if CheckTimeout(5):
        Log("Timeout in state:"+str(currState))
        NextState(STATE_idle)
        commState=False

def STATE_SIGNAL_req():
    global serPort
    
    serPort.write(bytes("AT+CMGF=1\x0D",'UTF-8'));
        
    NextState();
    
def STATE_SIGNAL_req2():
    global serPort,commState
    
    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:#receiving of one way asynchronnous commands
        if(b"OK" in rcvLine):
             serPort.write(bytes("AT+CSQ\x0D",'UTF-8'));
             NextState(STATE_SIGNAL_response);
             break

    if CheckTimeout(5):
        Log("Timeout in state:"+str(currState))
        NextState(STATE_idle)
        commState=False
    
    
def STATE_SIGNAL_response():
    global signalStrength, qualityIndicator, commState

    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:#receiving of one way asynchronnous commands
        try:
            if(b"+CSQ:" in rcvLine):
                signalStrength = int(rcvLine[rcvLine.find(b"+CSQ:")+5:].split(b',')[0])
                qualityIndicator = "Excellent" if signalStrength>19 else "Good" if signalStrength>14 else "Average" if signalStrength>9 else "Poor"
            
                Log("Quality "+qualityIndicator+" -> "+str(signalStrength),FULL)
            
                NextState(STATE_idle);
                commState=True
                break;
        except:
            continue;

    if CheckTimeout(5):
        Log("Timeout in state:"+str(currState))
        NextState(STATE_idle)
        commState=False

#---------------------------------------------------------------------------------------
stateList = [
    STATE_idle,
    STATE_SMS_sendFail,
    STATE_SMS_send,
    STATE_SMS_send2,
    STATE_SMS_send3,
    STATE_SMS_sendVerify,
    STATE_SMS_read,
    STATE_SMS_read2,
    STATE_SMS_read3,
    STATE_SMS_delete,
    STATE_SMS_delete2,
    STATE_SIGNAL_req,
    STATE_SIGNAL_req2,
    STATE_SIGNAL_response
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
    global currState,nextState,tmrTimeout

    if currState != "" and nextState != "" and currState != nextState:
        Log("Phone - transition to:"+nextState.__name__,FULL)
        currState = nextState
        tmrTimeout = time.time()
    
    # Execute the function
    currState()

def CheckTimeout(timeout):#in seconds
    global tmrTimeout

    if time.time() - tmrTimeout > timeout:
        return True
    else:
        return False
    

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

def ReadSMS():
    global reqReadSMS
    reqReadSMS = True
    
def CheckSignalInfo():
    global reqSignalInfo
    reqSignalInfo = True

def SendSMS(receiver,text):
    global receiverNumber,sendSMStext,reqSendSMS
    
    if reqSendSMS:
        Log("Already sending SMS!")
        Log("Text:"+sendSMStext)
    else:
        reqSendSMS = True
        receiverNumber = receiver
        sendSMStext = text

def getCommState():#status of communication with SIM800L module
    return commState

def getSignalInfo():
    return qualityIndicator

def ReceiveLinesFromSerial():
    global serPort,clearBufferWhenPhoneOffline

    maxChars = 200#maximalne tolik znaku lze precist
    rcvLine = bytes()
    rcvLines = []
    ptr=0
    try:
        ch = serPort.read(maxChars)
    except Exception as inst:
        Log("Exception in reading phone serial port")
        Log(type(inst))    # the exception instance
        Log(inst.args)     # arguments stored in .args
        Log(inst)
        
        return rcvLines
        
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

def Log(s,_verbosity=NORMAL):
    if _verbosity > verbosity:
        return
    print(str(s))

    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("logs/phone.log","a") as file:
        file.write(dateStr+" >> "+str(s)+"\n")
