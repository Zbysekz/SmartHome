#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import socket
import serialData
import time
import select
import traceback
import subprocess
from datetime import datetime
from threading import Thread
from parameters import parameters

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from logger import Logger


class cTCPServer:
    def __init__(self):

        self.logger = Logger("tcpServer", Logger.RICH)
        self.conn = ''
        self.s = ''
        self.BUFFER_SIZE = 256  # Normally 1024, but we want fast response
        self.sendQueue = []
        self.TXQUEUELIMIT = 30  # send buffer size for all messages
        self.TXQUEUELIMIT_PER_DEVICE = 5  # how much send messages can be in queue at the same time - if there is this count,
        # device is considered as offline
        self.onlineDevices = []  # list of online devices - offline becomes when we want to send lot of data to it, but it's not connecting

        self.tmrPrintBufferStat = time.time()

    def init(self):
        self.logger.log('tcp server init')
        # socket.setdefaulttimeout(5)
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.setblocking(0)
        self.s.bind((parameters.SERVER_IP, int(parameters.SERVER_PORT)))
        self.s.listen(10)

        self.tmrPrintBufferStat = time.time()

        # conn.close()
        # print ('end')

    def isTerminated(self):
        return self.terminate

    def _handle(self, MySQL):
        self.PrintBufferStatistics()

        try:
            self.s.settimeout(4.0)
            conn, addr = self.s.accept()
            ip = addr[0]
            self.logger.log('Device with address ' + str(ip) + ' was connected', Logger.RICH)
            if addr[0] not in self.onlineDevices:
                self.onlineDevices.append(ip)
                self.logger.log('New device with address ' + str(ip) + ' was connected')
                MySQL.AddOnlineDevice(str(ip))

            conn.settimeout(4.0)

            Thread(target=self.ReceiveThread, args=(conn, ip)).start()

        except KeyboardInterrupt:
            self.logger.log("Interrupted by user keyboard -----")
            self.terminate = True

        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            lines = traceback.format_exception(exc_type, exc_value, exc_traceback)

            if exc_type == socket.timeout:
                self.logger.log("Socket timeout!", Logger.FULL)
            else:
                self.logger.log("Exception:")
                self.logger.log(''.join('!! ' + line for line in lines))

    def ReceiveThread(self, conn, ip):
        try:
            # if you have something to send, send it
            sendWasPerformed = False

            queueNotForThisIp = [x for x in self.sendQueue if x[1] != ip]

            for tx in self.sendQueue:
                if tx[1] == ip:  # only if we have something to send to the address that has connected
                    conn.send(tx[0])

                    sendWasPerformed = True
                    self.logger.log(f"Sending tx data to '{ip}' data:{tx[0]}", Logger.RICH)

            self.sendQueue = queueNotForThisIp  # replace items with the items that we haven't sent

            if not sendWasPerformed:
                self.logger.log("Nothing to be send to this connected device '" + str(ip) + "'", Logger.FULL)

            conn.send(serialData.CreatePacket(
                bytes([199])))  # ending packet - signalizing that we don't have anything to sent no more

            time.sleep(0.1)  # give client some time to send me data

            receiverInstance = serialData.Receiver()
            while True:
                # data receive
                r, _, _ = select.select([conn], [], [], 4)
                if r:
                    data = conn.recv(self.BUFFER_SIZE)
                else:
                    self.logger.log("Device '" + str(ip) + "' was connected, but haven't send any data.")
                    break

                if not data:
                    break

                st = ""
                for d in data:
                    # if last received byte was ok, finish
                    # client can send multiple complete packets
                    isMeteostation = str(ip) == "192.168.0.10"  # extra exception for meteostation
                    if not receiverInstance.Receive(d, noCRC=isMeteostation):
                        self.logger.log("Error above for ip:" + str(ip))
                    st += str(d) + ", "

                self.logger.log("Received data:" + str(st), Logger.FULL)

        except ConnectionResetError:
            if ip != "192.168.0.11":  # ignore keyboard reset errors
                exc_type, exc_value, exc_traceback = sys.exc_info()
                lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
                self.logger.log("Exception in rcv thread, IP:" + str(ip))
                self.logger.log(''.join('!! ' + line for line in lines))
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            self.logger.log("Exception in rcv thread, IP:" + str(ip))
            self.logger.log(''.join('!! ' + line for line in lines))

        conn.close()

    def send(self, MySQL, data, destination, crc16=True):  # put in send queue

        if len(self.sendQueue) >= self.TXQUEUELIMIT_PER_DEVICE:  # if buffer is at least that full
            cnt = sum([msg[1] == destination for msg in self.sendQueue])  # how much are with same address
            if cnt >= self.TXQUEUELIMIT_PER_DEVICE:  # this device will become offline

                self.RemoveOnlineDevice(MySQL, destination)
                # now remove the oldest message and further normally append newest
                oldMsgs = [msg for msg in self.sendQueue if msg[1] == destination]

                if (len(oldMsgs) > 0):
                    self.sendQueue.remove(oldMsgs[0])

        if len(self.sendQueue) < self.TXQUEUELIMIT:
            self.sendQueue.append((serialData.CreatePacket(data, crc16), destination))
        else:
            self.logger.log("MAXIMUM TX QUEUE LIMIT REACHED!!")

    def RemoveOnlineDevice(self, MySQL, destination):
        if destination in self.onlineDevices:
            self.onlineDevices.remove(destination)
            self.logger.log("Device with address:'" + destination + "' became OFFLINE!")
            self.MySQL.RemoveOnlineDevice(destination)

    def SendACK(self, data, destination):
        # poslem CRC techto dat na danou destinaci
        CRC = serialData.calculateCRC(data) + len(data)

        if len(self.sendQueue) < self.TXQUEUELIMIT:
            self.sendQueue.append((serialData.CreatePacket(bytes([99, int(CRC) % 256, int(CRC / 256)])), destination))
            self.logger.log("sending BACK" + str(CRC) + " to destination:" + destination)
        else:
            self.logger.log("MAXIMUM TX QUEUE LIMIT REACHED")

    def PrintBufferStatistics(self):
        if time.time() - self.tmrPrintBufferStat > 600 and len(
                self.sendQueue) >= self.TXQUEUELIMIT_PER_DEVICE:  # periodically and only if there are some messages waiting
            tmrPrintBufferStat = time.time()
            self.logger.log("------ Buffer statistics:")
            self.logger.log("Msgs in send buffer:" + str(len(self.sendQueue)))
            # find different devices in queue
            uniqDev = []
            for dev in self.sendQueue:
                # find match in uniq
                item = next((x for x in uniqDev if x[0] == dev[1]), None)

                if item is None:
                    uniqDev.append([dev[1], 1])
                else:
                    item[1] = item[1] + 1  # increase occurence

                self.logger.log("Occurences:")
                self.logger.log(uniqDev)
            self.logger.log("------ ")

    def DataReceived(self):
        return serialData.getRcvdData()

    def DataRemaining(self):
        return serialData.getRcvdDataLen()

    @classmethod
    def Ping(cls, host):
        ping_response = subprocess.Popen(["/bin/ping", "-c1", "-w100", host], stdout=subprocess.PIPE).stdout.read()

        return True if "1 received" in ping_response.decode("utf-8") else False
