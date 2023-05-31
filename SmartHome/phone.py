#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
from datetime import datetime
from enum import Enum
from logger import Logger
import time
from parameters import Parameters

DISABLE_SMS = False

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

logger = Logger("phone", verbosity = Parameters.NORMAL)

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
            logger.log("Phone is ringing!!!")

def STATE_SMS_sendFail():#if sendinf SMS fail, wait for some time and try it again
    global reqSendSMS
    if CheckTimeout(60):
        reqSendSMS=True
        NextState(STATE_idle)
         
def STATE_SMS_send():
    global serPort
    
    serPort.write(bytes("AT+CMGF=1\x0D",'UTF-8'));
        
    NextState()
 
def STATE_SMS_send2():
    global serPort,commState
    
    
    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:
        if b"OK" in rcvLine:
            serPort.write(bytes("AT+CMGS=\x22"+receiverNumber+"\x22\x0D",'UTF-8'));# \x22 is "
            NextState();
            break

    if CheckTimeout(5):
        logger.log("Timeout in state:"+str(currState))
        NextState(STATE_SMS_sendFail)
        commState=False

def STATE_SMS_send3():
    global serPort,commState
    
    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:
        if b">" in rcvLine:
            serPort.write(bytes(sendSMStext+"\x1A",'UTF-8'));
            NextState();
            break
        
    if CheckTimeout(5):
        logger.log("Timeout in state:"+str(currState))
        NextState(STATE_SMS_sendFail)
        commState=False

def STATE_SMS_sendVerify():
    global serPort,commState
    
    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:
        if b"OK" in rcvLine:
            logger.log("SMS succesfully sent!")
            NextState(STATE_idle);
            commState=True
            break
        
    if CheckTimeout(5):
        logger.log("Timeout in state:"+str(currState))
        NextState(STATE_SMS_sendFail)
        commState=False

def STATE_SMS_read():
    global serPort
    
    serPort.write(bytes("AT+CMGF=1\x0D",'UTF-8'));
        
    NextState();
    
def STATE_SMS_read2():
    global serPort,readSMSsender, nOfReceivedSMS,commState,configLine
    
    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:
        logger.log("Phone RCV:"+str(rcvLine),Parameters.FULL)
        if b"OK" in rcvLine:
            serPort.write(bytes("AT+CMGL=\x22ALL\x22\x0D",'UTF-8'));
            
            readSMSsender = ""
            nOfReceivedSMS = 0
    
            configLine = ""
            NextState();
            break

    if CheckTimeout(5):
        logger.log("Timeout in state:"+str(currState))
        NextState(STATE_idle)
        commState=False
    
    
# Example:
# Phone RCV2:b'AT+CMGL="ALL"\r\r'
# Phone RCV2:b'+CMGL: 1,"REC UNREAD","+420602187490","","20/11/1'
# Phone RCV2:b'4,08:30:40+04"\r'
# Phone RCV2:b'heating off\r'
# Phone RCV2:b'\r'
# Phone RCV2:b'OK\r'
def STATE_SMS_read3():
    global readSMSsender, readSMStext, incomeSMSList, nOfReceivedSMS, commState, configLine

    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:#receiving of one way asynchronnous commands
        try:
            if readSMSsender!="":
                readSMStext = rcvLine.decode("utf-8").replace('\r','')
                
                nOfReceivedSMS = nOfReceivedSMS + 1

                logger.log("Received SMS text:'" + str(readSMStext) + "' From:"+str(readSMSsender), Parameters.NORMAL)
                incomeSMSList.append((readSMStext,readSMSsender))
                readSMSsender = ""
                continue
            elif b"+CMGL:" in rcvLine or configLine!="":#waits for sms sender, but wait for complete line
                logger.log("Phone RCV2:"+str(rcvLine),Parameters.FULL)
                configLine += rcvLine.decode("utf-8")

                if('\r' in configLine):#we have it complete
                    readSMSsender = configLine.split(',')[2].replace('"','')
                    timeOfReceive = configLine.split(',')[4].replace('"','')
                    configLine=""
                continue
            elif b"OK" in rcvLine:
                if nOfReceivedSMS > 0:
                    NextState(STATE_SMS_delete)
                else:
                    NextState(STATE_idle)
                
                logger.log("Check completed, received "+str(nOfReceivedSMS) + " SMS",Parameters.FULL)
                logger.log(incomeSMSList,Parameters.FULL)

                commState=True
                break
        except:
            continue

    if CheckTimeout(10):
        logger.log("Timeout in state:"+str(currState))
        NextState(STATE_idle)
        commState=False
        
def STATE_SMS_delete():
    global serPort
    
    serPort.write(bytes("AT+CMGDA=\x22DEL ALL\x22\x0D",'UTF-8'));
    
    NextState()
    
def STATE_SMS_delete2():
    global commState
    
    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:#receiving of one way asynchronnous commands
        try:
            if b"OK" in rcvLine:
                NextState(STATE_idle)
        except:
            continue

    if CheckTimeout(5):
        logger.log("Timeout in state:"+str(currState))
        NextState(STATE_idle)
        commState=False

def STATE_SIGNAL_req():
    global serPort
    
    serPort.write(bytes("AT+CMGF=1\x0D",'UTF-8'));
        
    NextState()
    
def STATE_SIGNAL_req2():
    global serPort,commState
    
    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:#receiving of one way asynchronnous commands
        if b"OK" in rcvLine:
             serPort.write(bytes("AT+CSQ\x0D",'UTF-8'));
             NextState(STATE_SIGNAL_response);
             break

    if CheckTimeout(5):
        logger.log("Timeout in state:"+str(currState))
        NextState(STATE_idle)
        commState=False
    
    
def STATE_SIGNAL_response():
    global signalStrength, qualityIndicator, commState

    rcvLines = ReceiveLinesFromSerial()
    
    for rcvLine in rcvLines:#receiving of one way asynchronnous commands
        try:
            if b"+CSQ:" in rcvLine:
                signalStrength = int(rcvLine[rcvLine.find(b"+CSQ:")+5:].split(b',')[0])
                qualityIndicator = "Excellent" if signalStrength>19 else "Good" if signalStrength>14 else "Average" if signalStrength>9 else "Poor"
            
                logger.log("Quality "+qualityIndicator+" -> "+str(signalStrength),Parameters.FULL)
            
                NextState(STATE_idle)
                commState=True
                break
        except:
            continue

    if CheckTimeout(5):
        logger.log("Timeout in state:"+str(currState))
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
        logger.log("Phone - transition to:"+nextState.__name__,Parameters.FULL)
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

    if DISABLE_SMS:
        logger.log("SMS feature manually disabled! SMS:'"+str(text)+"' will not be send!")
        return True

    if reqSendSMS:
        logger.log("Already sending SMS! Text:"+str(sendSMStext))
        return False
    else:
        logger.log("Sending SMS:" + text)
        reqSendSMS = True
        receiverNumber = receiver
        sendSMStext = text
        return True

def getCommState():#status of communication with SIM800L module
    return commState

def getSignalInfo():
    return qualityIndicator

def ReceiveLinesFromSerial():
    global serPort,clearBufferWhenPhoneOffline

    maxChars = 200#max this count of chars can be read
    rcvLine = bytes()
    rcvLines = []
    ptr=0
    try:
        ch = serPort.read(maxChars)
    except Exception as inst:
        logger.log("Exception in reading phone serial port")
        logger.log(type(inst))    # the exception instance
        logger.log(inst.args)     # arguments stored in .args
        logger.log(inst)
        
        return rcvLines
        
    if len(ch)==maxChars:#if we have received maximum characters, increase var and then reset input buffer - when phone is offline, input buffer is full of zeroes
        clearBufferWhenPhoneOffline += 1
    
    if (clearBufferWhenPhoneOffline>3):
        logger.log("Serial input buffer reset!")
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
