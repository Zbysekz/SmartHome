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
from threading import Thread
from parameters import parameters
from templates.threadModule import cThreadModule
from logger import Logger
from databaseMySQL import cMySQL
from comm.device import cDevice

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)


class cTCPServer(cThreadModule):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mySQL = cMySQL()

        self.logger = Logger("tcpServer", parameters.VERBOSITY, mySQL=self.mySQL)
        self.conn = ''
        self.s = ''
        self.BUFFER_SIZE = 256  # Normally 1024, but we want fast response
        self.sendQueue = []
        self.TXQUEUELIMIT = 30  # send buffer size for all messages
        self.TXQUEUELIMIT_PER_DEVICE = 5  #  how much send messages can be in queue at the same time - if there is this count,

        self.tmrPrintBufferStat = time.time()
        self.data_received_callback = None

        self.devices = None

    def init(self):
        self.logger.log(f'tcp server init - opening {parameters.SERVER_PORT} port on '
                        f'{parameters.SERVER_IP}')
        # socket.setdefaulttimeout(5)
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.setblocking(0)
        self.s.bind((parameters.SERVER_IP, int(parameters.SERVER_PORT)))
        self.s.listen(10)

        self.tmrPrintBufferStat = time.time()


        # conn.close()
        # print ('end')
    def __del__(self):
        self.logger.log("Called destructor")
        if self.s:
            self.s.close()

    def _handle(self):
        self.PrintBufferStatistics()

        try:
            self.s.settimeout(4.0)
            conn, addr = self.s.accept()
            ip = addr[0]
            device = cDevice.get_device(ip, self.devices)
            if device is None:
                self.logger.log(f"Unknown device was trying to connect! IP:{ip}")
                return
            device.mark_activity()
            self.logger.log(f'Device {str(device)} was connected', Logger.RICH)
            if not device.online:
                self.logger.log(f'New device {str(device)} was connected', Logger.NORMAL)
                self.mySQL.AddOnlineDevice(str(ip))
                device.online = True

            conn.settimeout(4.0)

            Thread(target=self.ReceiveThread, args=(conn, device)).start()

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

    def ReceiveThread(self, conn, device): # this thread starts, when some device connect to server

        try:
            persistent_connection = device.name in ["RACKUNO"]
            while persistent_connection:
                # if you have something to send, send it
                sendWasPerformed = False

                queueNotForThisIp = [x for x in self.sendQueue if x[1] != device.ip_address]

                for tx in self.sendQueue:
                    if tx[1] == device.ip_address:  # only if we have something to send to the address that has connected
                        conn.send(tx[0])

                        sendWasPerformed = True
                        self.logger.log(f"Sending tx data to {str(device)} data:{tx[0]}", Logger.NORMAL)

                self.sendQueue = queueNotForThisIp  # replace items with the items that we haven't sent

                if not sendWasPerformed:
                    self.logger.log(f"Nothing to be send to this connected device {str(device)}", Logger.FULL)

                if not persistent_connection:
                    conn.send(serialData.CreatePacket(
                        bytes([199])))  # ending packet - signalizing that we don't have anything to sent no more

                    time.sleep(0.5)  # give client some time to send me data

                receiverInstance = serialData.Receiver()
                tryit = 3


                while tryit > 0:
                    # data receive
                    r, _, _ = select.select([conn], [], [], 5)
                    if r:
                        data = conn.recv(self.BUFFER_SIZE)
                    else:
                        tryit -= 1
                        if tryit == 0 and not persistent_connection:
                            self.logger.log(f"Device {str(device)} was connected,"
                                            f" but haven't send any data.")
                        continue
                    if not data:
                        self.logger.log(f"Device: {str(device)} breaking with data None")
                        break

                    st = ""
                    for d in data:
                        # if last received byte was ok, finish
                        # client can send multiple complete packets
                        isMeteostation = str(device.name) == "METEO"  # extra exception for meteostation
                        if not receiverInstance.Receive(d, noCRC=isMeteostation):
                            self.logger.log(f"Error receiving for {device.name} !")
                        st += str(d) + ", "
                    if persistent_connection:
                        device.mark_activity()
                    self.logger.log("Received data:" + str(st), Logger.FULL)
                    while receiverInstance.getRcvdDataLen() > 0:
                        self.data_received_callback(receiverInstance.getRcvdData())

        except ConnectionResetError:
            if device.ip_address != "192.168.0.11":  # ignore keyboard reset errors
                exc_type, exc_value, exc_traceback = sys.exc_info()
                lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
                self.logger.log("Exception in rcv thread, device:" + str(device))
                self.logger.log(''.join('!! ' + line for line in lines))
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            self.logger.log("Exception in rcv thread, device:" + str(device))
            self.logger.log(''.join('!! ' + line for line in lines))

        conn.close()

    def send(self, data, destination, crc16=True) -> bool:  # put in send queue

        device = cDevice.get_device(destination, self.devices)

        if device.online:
            if len(self.sendQueue) >= self.TXQUEUELIMIT_PER_DEVICE:  # if buffer is at least that full
                cnt = sum([msg[1] == destination for msg in self.sendQueue])  # how much are with same address
                if cnt >= self.TXQUEUELIMIT_PER_DEVICE:  # this device will become offline
                    self.logger.log(f"Limit for TX queue per device was reached! {device.name}")
                    # now remove the oldest message and further normally append newest
                    oldMsgs = [msg for msg in self.sendQueue if msg[1] == destination]

                    if len(oldMsgs) > 0:
                        self.sendQueue.remove(oldMsgs[0])

            if len(self.sendQueue) < self.TXQUEUELIMIT:
                self.sendQueue.append((serialData.CreatePacket(data, crc16), destination))
                return True
            else:
                self.logger.log("MAXIMUM TX QUEUE LIMIT REACHED!!")

        self.logger.log(f"Sending to {device.name} failed, device is not online!")
        return False
    def RemoveOnlineDevice(self, MySQL, destination):
        device = cDevice.get_device(destination, self.devices)
        if device is None:
            self.logger.log(f"Device {str(device)} tried to be removed but it doesn't exists in list! IP:{destination}")
            return
        device.online = False
        self.logger.log(f"Device {str(device)} became OFFLINE!")
        MySQL.RemoveOnlineDevice(destination)

    def SendACK(self, data, destination):
        # poslem CRC techto dat na danou destinaci
        CRC = serialData.calculateCRC(data) + len(data)
        device = cDevice.get_device(destination, self.devices)
        if device is None:
            self.logger.log(f"Attempted to send ACK to device {str(device)} but it doesn't exists in list! IP:{destination}")
            return
        if len(self.sendQueue) < self.TXQUEUELIMIT:
            self.sendQueue.append((serialData.CreatePacket(bytes([99, int(CRC) % 256, int(CRC / 256)])), destination))
            self.logger.log("sending BACK" + str(CRC) + f" to device:{str(device)}")
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
