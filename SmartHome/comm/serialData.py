#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
from parameters import parameters
from logger import Logger


class Receiver:
    def __init__(self):

        self.logger = Logger("serialData", verbosity=parameters.VERBOSITY)

        self.RXBUFFSIZE = 100
        self.readState = 0
        self.rxBuffer = [0] * self.RXBUFFSIZE
        self.rxPtr = 0
        self.crcH = 0
        self.crcL = 0
        self.rxLen = 0

        self.rcvdData = []  # list of lists of rcvd data
        self.queue_large = False

    def getRcvdData(self):  # get last data and remove from queue
        if self.queue_large and len(self.rcvdData) < 3:
            self.logger.log("Rcv queue is ok! Len:" + str(len(self.rcvdData)), Logger.NORMAL)
            self.queue_large = False

        if len(self.rcvdData) > 0:
            temp = self.rcvdData[0]
            del self.rcvdData[0]
            return temp
        return []

    def getRcvdDataLen(self):
        return len(self.rcvdData)

    def ResetReceiver(self):
        self.rxPtr = 0
        self.readState = 0

    # returns false if some error occurs
    def Receive(self, rcv, noCRC=False):
        result = True
        # prijimame zpravu
        if self.readState == 0:
            if rcv == 111:
                self.readState = 1  # start token
        elif self.readState == 1:
            if rcv == 222:
                self.readState = 2
            else:
                self.readState = 0  # second start token
                self.logger.log("ERR1", Logger.RICH)
                result = False
        elif self.readState == 2:
            self.rxLen = rcv  # length

            if self.rxLen > 20:
                self.readState = 0
                self.logger.log("ERR2", Logger.RICH)
                result = False
            else:
                self.readState = 3
            self.rxPtr = 0
        elif self.readState == 3:
            self.rxBuffer[self.rxPtr] = rcv  # data
            self.rxPtr += 1
            if self.rxPtr >= self.RXBUFFSIZE:
                self.logger.log("ERR5 (Buff FULL)", Logger.RICH)
                self.readState = 0
                result = False
            elif self.rxPtr >= self.rxLen:
                self.readState = 4
        elif self.readState == 4:
            self.crcH = rcv  # high crc
            self.readState = 5
        elif self.readState == 5:
            self.crcL = rcv  # low crc
            calcCRC = CRC16([self.rxLen, *self.rxBuffer[0:self.rxPtr]])  # include length
            if (calcCRC == self.crcL + self.crcH * 256) or noCRC:  # crc check
                self.readState = 6
            else:
                self.readState = 0
                result = False
                self.logger.log("ERR3 (CRC mismatch)", Logger.RICH)
                self.logger.log("calc:" + str(calcCRC), Logger.RICH)
                self.logger.log("real:" + str(self.crcL + self.crcH * 256))
                self.logger.log([self.rxLen, *self.rxBuffer[0:self.rxPtr]], Logger.RICH)
        elif self.readState == 6:
            if rcv == 222:  # end token
                self.rcvdData.append(self.rxBuffer[0:self.rxLen])
                self.readState = 0
                self.logger.log("New data received!", Logger.FULL)
                if len(self.rcvdData) > 10:
                    self.logger.log("Rcv queue is large! Len:" + str(len(self.rcvdData)), Logger.NORMAL)
                    self.queue_large = True
                    self.logger.log(self.rcvdData, Logger.RICH)
            else:
                self.readState = 0
                result = False
                self.logger.log("ERR4", Logger.RICH)

        return result


# general methods
def CreatePacket(d, crc16=True):
    data = bytearray(3)
    data[0] = 111  # start byte
    data[1] = 222  # start byte

    data[2] = len(d)

    data = data[:3] + d

    if crc16:
        crc = CRC16(data[2:])
    else:
        crc = calculateCRC(data[2:])

    data.append(int(crc / 256))
    data.append(crc % 256)
    data.append(222)  # end byte

    return data


# legacy, should be substituted with CRC16
def calculateCRC(data):
    crc = 0
    for d in data:
        crc += d
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
                crc &= 0xFFFF  # ensure 16 bit width
            else:
                crc <<= 1  # shift left
    return crc
