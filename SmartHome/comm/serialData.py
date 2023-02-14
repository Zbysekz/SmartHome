#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from logger import Logger
logger = Logger("serialData")

rcvdData=[]#list of lists of rcvd data

RXBUFFSIZE=100

NORMAL = 0
RICH = 1
FULL = 2
verbosity = RICH

def getRcvdData():#get last data and remove from queue
    if(len(rcvdData)>0):
        temp = rcvdData[0]
        del rcvdData[0]
        return temp
    return []

class Receiver:

    def __init__(self):
        self.readState=0
        self.rxBuffer=[0]*RXBUFFSIZE
        self.rxPtr=0
        self.crcH=0
        self.crcL=0
        self.rxLen=0
        self.queue_large = False

    def ResetReceiver(self):
        self.rxPtr=0
        self.readState=0
        
    # returns false if some error occurs
    def Receive(self, rcv, noCRC=False):
        result = True
        #prijimame zpravu
        if(self.readState==0):
            if(rcv==111):
                self.readState=1 #start token
        elif(self.readState==1):
            if(rcv==222):
                self.readState=2
            else:
                self.readState=0#second start token
                logger.log("ERR1",RICH)
                result = False
        elif(self.readState==2):
            self.rxLen = rcv#length
            
            if(self.rxLen>20):
                self.readState=0
                logger.log("ERR2",RICH)
                result = False
            else:
                self.readState=3
            self.rxPtr=0
        elif(self.readState==3):
            self.rxBuffer[self.rxPtr] = rcv#data
            self.rxPtr+=1
            if self.rxPtr>=RXBUFFSIZE:
               logger.log("ERR5 (Buff FULL)",RICH)
               self.readState=0
               result = False
            elif self.rxPtr>=self.rxLen:
                self.readState=4
        elif(self.readState==4):
            self.crcH=rcv#high crc
            self.readState=5
        elif(self.readState==5):
            self.crcL=rcv#low crc
            calcCRC = CRC16([self.rxLen,*self.rxBuffer[0:self.rxPtr]]) # include length
            if( calcCRC == self.crcL+self.crcH*256) or noCRC:#crc check
                self.readState=6
            else:
                self.readState=0
                result = False
                logger.log("ERR3 (CRC mismatch)",RICH)
                logger.log("calc:"+str(calcCRC),RICH)
                logger.log("real:"+str(self.crcL+self.crcH*256))
                logger.log([self.rxLen,*self.rxBuffer[0:self.rxPtr]],RICH)
        elif(self.readState==6):
            if(rcv==222):#end token
                rcvdData.append(self.rxBuffer[0:self.rxLen])
                self.readState=0
                logger.log("New data received!",FULL)
                if len(rcvdData)>10:
                    logger.log("Rcv queue is large! Len:"+str(len(rcvdData)),NORMAL)
                    self.queue_large = True
                    logger.log(rcvdData, RICH)
                elif len(rcvdData) < 2:
                    logger.log("Rcv queue is ok! Len:" + str(len(rcvdData)), NORMAL)
                    self.queue_large = False
            else:
                self.readState=0
                result = False
                logger.log("ERR4",RICH)
        
        return result
            
# general methods
def CreatePacket(d,crc16=True):
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
