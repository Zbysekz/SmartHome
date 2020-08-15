#!/usr/bin/env python3
# -*- coding: utf-8 -*-

readState=0
RXBUFFSIZE=100
rxBuffer=[0]*RXBUFFSIZE
rxPtr=0
crcH=0
crcL=0
rcvdData=[]#list of lists of rcvd datas
rxLen=0

NORMAL = 0
RICH = 1
FULL = 2
verbosity = NORMAL

def getRcvdData():#get last data and remove from queue
    if(len(rcvdData)>0):
        temp = rcvdData[0]
        del rcvdData[0]
        return temp
    return [];

def ResetReceiver():
    rxPtr=0
    readState=0
    
def Receive(rcv):
    global readState,rxBuffer,rxPtr,crcH,crcL,RXBUFFSIZE,rxLen

    #prijimame zpravu
    if(readState==0):
        if(rcv==111):
            readState=1 #start token
    elif(readState==1):
        if(rcv==222):
            readState=2
        else:
            readState=0#second start token
            Log("ERR1",RICH)
    elif(readState==2):
        rxLen = rcv#length
        
        if(rxLen>20):
            readState=0
            Log("ERR2",RICH)
        else:
            readState=3
        rxPtr=0
    elif(readState==3):
        rxBuffer[rxPtr] = rcv#data
        rxPtr+=1
        if(rxPtr>=RXBUFFSIZE or rxPtr>=rxLen):
            readState=4
    elif(readState==4):
        crcH=rcv#high crc
        readState=5
    elif(readState==5):
        crcL=rcv#low crc
        calcCRC = rxLen+calculateCRC(rxBuffer[0:rxPtr])
        if( calcCRC == crcL+crcH*256):#crc check
            readState=6
        else:
            readState=0
            Log("ERR3 (CRC mismatch)",RICH)
            Log("calc:"+str(calcCRC),RICH)
    elif(readState==6):
        if(rcv==222):#end token
            rcvdData.append(rxBuffer[0:rxLen])
            readState=0
            Log("New data received!",FULL)
        else:
            readState=0
            Log("ERR4",RICH)
def CreatePacket(d,crc16=False):
    data=bytearray(3)
    data[0]=111#start byte
    data[1]=222#start byte

    data[2]=len(d);
    
    
    data = data[:3]+d
    
    if crc16:
        crc = CRC16(data[2:])
    else:
        crc = calculateCRC(data[2:])
        
    data.append(int(crc/256))
    data.append(crc%256)
    data.append(222)#end byte
    
    return data

def Log(s,_verbosity=NORMAL):
    if _verbosity > verbosity:
        return
    print(str(s))
    from datetime import datetime
    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("logs/serialData.log","a") as file:
        file.write(dateStr+" >> "+str(s)+"\n")
        
# legacy, should be substituted with CRC16
def calculateCRC(data):
    crc=0
    for d in data:
        crc+=d
    return crc

# Corresponds to CRC-16/XMODEM on https://crccalc.com/
def CRC16(data):
    crc = 0
    generator = 0x1021
    
    for byte in data:
        crc ^= byte << 8
        for i in range(8):

            if crc & 0x8000 != 0:
                crc = (crc << 1) ^ generator
                crc &= 0xFFFF # ensure 16 bit width
            else:
                crc <<= 1 # shift left
    return crc
