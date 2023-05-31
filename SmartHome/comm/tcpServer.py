#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import socket
from serialData import Receiver
import serialData
import time
import select
import traceback
import subprocess
from datetime import datetime
from threading import Thread
from parameters import Parameters

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from logger import Logger

logger = Logger("tcpServer", Parameters.NORMAL)
conn=''
s=''
BUFFER_SIZE = 256  # Normally 1024, but we want fast response
sendQueue = []
TXQUEUELIMIT=30 # send buffer size for all messages
TXQUEUELIMIT_PER_DEVICE = 5 # how much send messages can be in queue at the same time - if there is this count,
                            # device is considered as offline
onlineDevices = [] # list of online devices - offline becomes when we want to send lot of data to it, but it's not connecting

terminate = False # termination by user keyboard

def Init():
    global conn, s, tmrPrintBufferStat
    
    TCP_IP = '192.168.0.3'
    TCP_PORT = 23

    logger.log ('tcp server init')
    #socket.setdefaulttimeout(5)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setblocking(0)
    s.bind((TCP_IP, TCP_PORT))
    s.listen(10)

    tmrPrintBufferStat = time.time()
 
    #conn.close()
    #print ('end')

def isTerminated():
    return terminate

def Handle(MySQL):
    global conn, BUFFER_SIZE, s, sendQueue, terminate

    PrintBufferStatistics()

    try:
        s.settimeout(4.0)
        conn, addr = s.accept()
        ip = addr[0]
        logger.log('Device with address '+str(ip)+' was connected', Parameters.RICH)
        if addr[0] not in onlineDevices:
            onlineDevices.append(ip)
            logger.log('New device with address ' + str(ip) + ' was connected')
            MySQL.AddOnlineDevice(str(ip))

        conn.settimeout(4.0)
        
        Thread(target=ReceiveThread, args=(conn, ip)).start()

    except KeyboardInterrupt:
        logger.log("Interrupted by user keyboard -----")
        terminate = True

    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        
        if(exc_type == socket.timeout):
            logger.log("Socket timeout!", Parameters.FULL)
        else:
            logger.log("Exception:")
            logger.log(''.join('!! ' + line for line in lines))

def ReceiveThread(conn, ip):
    global sendQueue
    try:
        #if you have something to send, send it
        sendWasPerformed = False
        
        queueNotForThisIp = [x for x in sendQueue if x[1]!=ip]
        
        for tx in sendQueue:
            if(tx[1]==ip):#only if we have something to send to the address that has connected                  
                conn.send(tx[0])

                sendWasPerformed = True
        
        sendQueue = queueNotForThisIp # replace items with the items that we haven't sent

        if not sendWasPerformed:
            logger.log("Nothing to be send to this connected device '"+str(ip)+"'", Parameters.FULL)
        
        conn.send(serialData.CreatePacket(bytes([199]))) # ending packet - signalizing that we don't have anything to sent no more

        time.sleep(0.1) # give client some time to send me data
        
        
        receiverInstance = Receiver()
        while True:
            #data receive
            r, _, _ = select.select([conn], [], [],4)
            if r:
                data = conn.recv(BUFFER_SIZE)
            else:
                logger.log("Device '"+str(ip)+"' was connected, but haven't send any data.")
                break

            if not data:
                break

            st = ""
            for d in data:
                 # if last received byte was ok, finish
                 # client can send multiple complete packets
                isMeteostation = str(ip)=="192.168.0.10"#extra exception for meteostation
                if not receiverInstance.Receive(d, noCRC=isMeteostation):
                    logger.log("Error above for ip:"+str(ip))
                st+= str(d)+", "
            
            logger.log("Received data:"+str(st), Parameters.FULL)

    except ConnectionResetError:
        if ip != "192.168.0.11":# ignore keyboard reset errors
           exc_type, exc_value, exc_traceback = sys.exc_info()
           lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
           logger.log("Exception in rcv thread, IP:" + str(ip))
           logger.log(''.join('!! ' + line for line in lines))
    except Exception :
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        logger.log("Exception in rcv thread, IP:"+str(ip))
        logger.log(''.join('!! ' + line for line in lines))
            
    conn.close()
        
def Send(MySQL, data, destination, crc16=True):#put in send queue
    global sendQueue, onlineDevices

    if len(sendQueue) >= TXQUEUELIMIT_PER_DEVICE: # if buffer is at least that full
        cnt = sum([msg[1] == destination for msg in sendQueue]) # how much are with same address
        if cnt >= TXQUEUELIMIT_PER_DEVICE:# this device will become offline

            RemoveOnlineDevice(MySQL, destination)
            # now remove the oldest message and further normally append newest
            oldMsgs = [msg for msg in sendQueue if msg[1] == destination]

            if(len(oldMsgs)>0):
                sendQueue.remove(oldMsgs[0])

    if len(sendQueue)<TXQUEUELIMIT:
        sendQueue.append((serialData.CreatePacket(data, crc16),destination))
    else:
        logger.log("MAXIMUM TX QUEUE LIMIT REACHED!!")

def RemoveOnlineDevice(MySQL, destination):
    global onlineDevices
    
    if destination in onlineDevices:
        onlineDevices.remove(destination)
        logger.log("Device with address:'"+destination+"' became OFFLINE!")
        MySQL.RemoveOnlineDevice(destination)
                
def SendACK(data,destination):
    #poslem CRC techto dat na danou destinaci
    global sendQueue,TXQUEUELIMIT

    CRC = serialData.calculateCRC(data) + len(data)
    
    if len(sendQueue)<TXQUEUELIMIT:
        sendQueue.append((serialData.CreatePacket(bytes([99,int(CRC)%256,int(CRC/256)])),destination))
        logger.log("sending BACK"+str(CRC)+" to destination:"+destination)
    else:
        logger.log("MAXIMUM TX QUEUE LIMIT REACHED")


def PrintBufferStatistics():
    global tmrPrintBufferStat, sendQueue

    if time.time() - tmrPrintBufferStat > 600 and len(sendQueue) >= TXQUEUELIMIT_PER_DEVICE: # periodically and only if there are some messages waiting
        tmrPrintBufferStat = time.time()
        logger.log("------ Buffer statistics:")
        logger.log("Msgs in send buffer:" + str(len(sendQueue)))
        # find different devices in queue
        uniqDev = []
        for dev in sendQueue:
            # find match in uniq
            item = next((x for x in uniqDev if x[0] == dev[1]), None)

            if item is None:
                uniqDev.append([dev[1], 1])
            else:
                item[1] = item[1] + 1 # increase occurence

            logger.log("Occurences:")
            logger.log(uniqDev)
        logger.log("------ ")


def DataReceived():
    return serialData.getRcvdData()

def DataRemaining():
    return serialData.getRcvdDataLen()

def Ping(host):
    ping_response = subprocess.Popen(["/bin/ping", "-c1", "-w100", host], stdout=subprocess.PIPE).stdout.read()

    return True if "1 received" in ping_response.decode("utf-8") else False



