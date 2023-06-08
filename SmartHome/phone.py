#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
from datetime import datetime
from enum import Enum
from logger import Logger
import time
from parameters import parameters
from databaseMySQL import cMySQL
from templates.threadModule import cThreadModule
import threading

DISABLE_SMS = False


class cPhone(cThreadModule):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logger = Logger("phone", verbosity=parameters.VERBOSITY)

        self.mySQL = cMySQL()
        self.serPort = 0
        self.incomeSMSList = []
        self.reqReadSMS = False
        self.reqSendSMS = False
        self.reqSignalInfo = False

        self.signalStrength = 0
        self.qualityIndicator = "Not available"

        self.receiverNumber = ""

        self.sendSMStext = ""
        self.sendSMSreceiver = ""
        self.readSMStext = ""
        self.readSMSsender = ""
        self.nOfReceivedSMS = 0
        self.tmrTimeout = 0
        self.clearBufferWhenPhoneOffline = 0
        self.timeOfReceive = 0
        self.configLine = ""

        # stats
        self.commState = False
        self.signalStrength = 0

        self.tmrHandle = 0

        # ---------------------------------------------------------------------------------------
        self.stateList = [
            self.STATE_idle,
            self.STATE_SMS_sendFail,
            self.STATE_SMS_send,
            self.STATE_SMS_send2,
            self.STATE_SMS_send3,
            self.STATE_SMS_sendVerify,
            self.STATE_SMS_read,
            self.STATE_SMS_read2,
            self.STATE_SMS_read3,
            self.STATE_SMS_delete,
            self.STATE_SMS_delete2,
            self.STATE_SIGNAL_req,
            self.STATE_SIGNAL_req2,
            self.STATE_SIGNAL_response
        ]

        self.currState = self.STATE_idle
        self.nextState = ""

        self.connect()

    # ---------------------------------------------------------------------------------------
    def STATE_idle(self):
        if self.reqSendSMS:
            self.NextState(self.STATE_SMS_send)
            self.reqSendSMS = False
        elif self.reqReadSMS:
            self.NextState(self.STATE_SMS_read)
            self.reqReadSMS = False
        elif self.reqSignalInfo:
            self.NextState(self.STATE_SIGNAL_req)
            self.reqSignalInfo = False

        rcvLines = self.ReceiveLinesFromSerial()

        for rcvLine in rcvLines:  # receiving of one way asynchronnous commands
            if b"RING" in rcvLine:
                self.logger.log("Phone is ringing!!!")

    def STATE_SMS_sendFail(self):  # if sendinf SMS fail, wait for some time and try it again
        if self.CheckTimeout(60):
            self.reqSendSMS = True
            self.NextState(self.STATE_idle)

    def STATE_SMS_send(self):
        self.serPort.write(bytes("AT+CMGF=1\x0D", 'UTF-8'))

        self.NextState()

    def STATE_SMS_send2(self):
        rcvLines = self.ReceiveLinesFromSerial()

        for rcvLine in rcvLines:
            if b"OK" in rcvLine:
                self.serPort.write(bytes("AT+CMGS=\x22" + self.receiverNumber + "\x22\x0D", 'UTF-8'))  # \x22 is "
                self.NextState()
                break

        if self.CheckTimeout(5):
            self.logger.log("Timeout in state:" + str(self.currState))
            self.NextState(self.STATE_SMS_sendFail)
            self.commState = False

    def STATE_SMS_send3(self):
        rcvLines = self.ReceiveLinesFromSerial()

        for rcvLine in rcvLines:
            if b">" in rcvLine:
                self.serPort.write(bytes(self.sendSMStext + "\x1A", 'UTF-8'))
                self.NextState()
                break

        if self.CheckTimeout(5):
            self.logger.log("Timeout in state:" + str(self.currState))
            self.NextState(self.STATE_SMS_sendFail)
            self.commState = False

    def STATE_SMS_sendVerify(self):
        rcvLines = self.ReceiveLinesFromSerial()

        for rcvLine in rcvLines:
            if b"OK" in rcvLine:
                self.logger.log("SMS succesfully sent!")
                self.NextState(self.STATE_idle)
                self.commState = True
                break

        if self.CheckTimeout(5):
            self.logger.log("Timeout in state:" + str(self.currState))
            self.NextState(self.STATE_SMS_sendFail)
            self.commState = False

    def STATE_SMS_read(self):
        self.serPort.write(bytes("AT+CMGF=1\x0D", 'UTF-8'))

        self.NextState()

    def STATE_SMS_read2(self):
        rcvLines = self.ReceiveLinesFromSerial()

        for rcvLine in rcvLines:
            self.logger.log("Phone RCV:" + str(rcvLine), Logger.FULL)
            if b"OK" in rcvLine:
                self.serPort.write(bytes("AT+CMGL=\x22ALL\x22\x0D", 'UTF-8'))

                self.readSMSsender = ""
                self.nOfReceivedSMS = 0

                self.configLine = ""
                self.NextState()
                break

        if self.CheckTimeout(5):
            self.logger.log("Timeout in state:" + str(self.currState))
            self.NextState(self.STATE_idle)
            self.commState = False

    # Example:
    # Phone RCV2:b'AT+CMGL="ALL"\r\r'
    # Phone RCV2:b'+CMGL: 1,"REC UNREAD","+420602187490","","20/11/1'
    # Phone RCV2:b'4,08:30:40+04"\r'
    # Phone RCV2:b'heating off\r'
    # Phone RCV2:b'\r'
    # Phone RCV2:b'OK\r'
    def STATE_SMS_read3(self):
        rcvLines = self.ReceiveLinesFromSerial()

        for rcvLine in rcvLines:  # receiving of one way asynchronnous commands
            try:
                if self.readSMSsender != "":
                    self.readSMStext = rcvLine.decode("utf-8").replace('\r', '')

                    self.nOfReceivedSMS = self.nOfReceivedSMS + 1

                    self.logger.log("Received SMS text:'" + str(self.readSMStext) + "' From:" + str(self.readSMSsender),
                               Logger.NORMAL)
                    self.incomeSMSList.append((self.readSMStext, self.readSMSsender))
                    self.readSMSsender = ""
                    continue
                elif b"+CMGL:" in rcvLine or self.configLine != "":  # waits for sms sender, but wait for complete line
                    self.logger.log("Phone RCV2:" + str(rcvLine), Logger.FULL)
                    self.configLine += rcvLine.decode("utf-8")

                    if ('\r' in self.configLine):  # we have it complete
                        self.readSMSsender = self.configLine.split(',')[2].replace('"', '')
                        self.timeOfReceive = self.configLine.split(',')[4].replace('"', '')
                        self.configLine = ""
                    continue
                elif b"OK" in rcvLine:
                    if self.nOfReceivedSMS > 0:
                        self.NextState(self.STATE_SMS_delete)
                    else:
                        self.NextState(self.STATE_idle)

                    self.logger.log("Check completed, received " + str(self.nOfReceivedSMS) + " SMS", Logger.FULL)
                    self.logger.log(self.incomeSMSList, Logger.FULL)

                    self.commState = True
                    break
            except:
                continue

        if self.CheckTimeout(10):
            self.logger.log("Timeout in state:" + str(self.currState))
            self.NextState(self.STATE_idle)
            commState = False

    def STATE_SMS_delete(self):
        self.serPort.write(bytes("AT+CMGDA=\x22DEL ALL\x22\x0D", 'UTF-8'))
        self.NextState()

    def STATE_SMS_delete2(self):
        rcvLines = self.ReceiveLinesFromSerial()

        for rcvLine in rcvLines:  # receiving of one way asynchronnous commands
            try:
                if b"OK" in rcvLine:
                    self.NextState(self.STATE_idle)
            except:
                continue

        if self.CheckTimeout(5):
            self.logger.log("Timeout in state:" + str(self.currState))
            self.NextState(self.STATE_idle)
            self.commState = False

    def STATE_SIGNAL_req(self):
        self.serPort.write(bytes("AT+CMGF=1\x0D", 'UTF-8'))

        self.NextState()

    def STATE_SIGNAL_req2(self):
        rcvLines = self.ReceiveLinesFromSerial()

        for rcvLine in rcvLines:  # receiving of one way asynchronnous commands
            if b"OK" in rcvLine:
                self.serPort.write(bytes("AT+CSQ\x0D", 'UTF-8'))
                self.NextState(self.STATE_SIGNAL_response)
                break

        if self.CheckTimeout(5):
            self.logger.log("Timeout in state:" + str(self.currState))
            self.NextState(self.STATE_idle)
            self.commState = False

    def STATE_SIGNAL_response(self):
        rcvLines = self.ReceiveLinesFromSerial()

        for rcvLine in rcvLines:  # receiving of one way asynchronnous commands
            try:
                if b"+CSQ:" in rcvLine:
                    self.signalStrength = int(rcvLine[rcvLine.find(b"+CSQ:") + 5:].split(b',')[0])
                    self.qualityIndicator = "Excellent" if self.signalStrength > 19 else "Good" if self.signalStrength > 14 else "Average" if self.signalStrength > 9 else "Poor"

                    self.logger.log("Quality " + self.qualityIndicator + " -> " + str(self.signalStrength), Logger.FULL)

                    self.NextState(self.STATE_idle)
                    self.commState = True
                    break
            except:
                continue

        if self.CheckTimeout(5):
            self.logger.log("Timeout in state:" + str(self.currState))
            self.NextState(self.STATE_idle)
            self.commState = False

    def NextState(self, name=""):
        if name == "":
            idx = self.stateList.index(self.currState)
            idx = idx + 1
            self.nextState = self.stateList[idx]
        else:
            self.nextState = name

    def Process(self):
        if self.currState != "" and self.nextState != "" and self.currState != self.nextState:
            self.logger.log("Phone - transition to:" + self.nextState.__name__, Logger.FULL)
            self.currState = self.nextState
            self.tmrTimeout = time.time()

        # Execute the function
        self.currState()

    def CheckTimeout(self, timeout):  # in seconds
        if time.time() - self.tmrTimeout > timeout:
            return True
        else:
            return False

    def connect(self):
        self.logger.log("Initializing serial port...")

        self.serPort = serial.Serial(

            port='/dev/ttyS0',
            baudrate=9600,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=0.1
        )
        self.logger.log("ok")

    def getIncomeSMSList(self):
        return self.incomeSMSList

    def clearIncomeSMSList(self):
        self.incomeSMSList.clear()

    def ReadSMS(self):
        self.reqReadSMS = True

    def CheckSignalInfo(self):
        self.reqSignalInfo = True

    def SendSMS(self, receiver, text):
        if DISABLE_SMS:
            self.logger.log("SMS feature manually disabled! SMS:'" + str(text) + "' will not be send!")
            return True

        if self.reqSendSMS:
            self.logger.log("Already sending SMS! Text:" + str(self.sendSMStext))
            return False
        else:
            self.logger.log("Sending SMS:" + text)
            self.reqSendSMS = True
            self.receiverNumber = receiver
            self.sendSMStext = text
            return True

    def getCommState(self):  # status of communication with SIM800L module
        return self.commState

    def getSignalInfo(self):
        return self.qualityIndicator

    def ReceiveLinesFromSerial(self):
        maxChars = 200  # max this count of chars can be read
        rcvLine = bytes()
        rcvLines = []
        ptr = 0
        try:
            ch = self.serPort.read(maxChars)
        except Exception as inst:
            self.logger.log("Exception in reading phone serial port")
            self.logger.log(type(inst))  # the exception instance
            self.logger.log(inst.args)  # arguments stored in .args
            self.logger.log(inst)

            return rcvLines

        if len(ch) == maxChars:  # if we have received maximum characters, increase var and then reset input buffer - when phone is offline, input buffer is full of zeroes
            self.clearBufferWhenPhoneOffline += 1

        if self.clearBufferWhenPhoneOffline > 3:
            self.logger.log("Serial input buffer reset!")
            clearBufferWhenPhoneOffline = 0
            self.serPort.reset_input_buffer()
            return []

        while ptr < len(ch):

            if ch[ptr] == 10:  # b'\n'
                rcvLines.append(rcvLine)
                rcvLine = bytes()

            elif ch[ptr] != 0:  # b'\x00'
                # print(ch)
                # print("chr:"+chr(ord(ch)))
                # print(ch[ptr])
                rcvLine += ch[ptr].to_bytes(1, byteorder='big')
            ptr += 1

        if len(rcvLine) != 0:
            rcvLines.append(rcvLine)
        return rcvLines

    def _handle(self):
        self.Process()  # fast call

        if time.time() - self.tmrHandle > 20:
            self.tmrHandle = time.time()
            self.ReadSMS()
            self.CheckSignalInfo()

            # process incoming SMS
            for sms in self.getIncomeSMSList():
                self.IncomingSMS(sms)
            self.clearIncomeSMSList()

            self.mySQL.updateState('phoneSignalInfo', str(self.getSignalInfo()))
            self.mySQL.updateState('phoneCommState', int(self.getCommState()))
