#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import serialData
import time
import select
import sys
import traceback
import subprocess
from datetime import datetime
import databaseSQLite

conn=''
s=''
BUFFER_SIZE = 256  # Normally 1024, but we want fast response
sendQueue = []
TXQUEUELIMIT=30 # send buffer size for all messages
TXQUEUELIMIT_PER_DEVICE = 5 # how much send messages can be in queue at the same time - if there is this count,
                            # device is considered as offline
onlineDevices = [] # list of online devices - offline becomes when we want to send lot of data to it, but it's not connecting

terminate = False # termination by user keyboard

NORMAL = 0
RICH = 1
FULL = 2
verbosity = FULL


def Init():
    global conn, s, tmrPrintBufferStat
    
    TCP_IP = '192.168.0.3'
    TCP_PORT = 23

    Log ('tcp server init')
    #socket.setdefaulttimeout(5)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setblocking(0)
    s.bind((TCP_IP, TCP_PORT))
    s.listen(1)

    tmrPrintBufferStat = time.time()
 
    #conn.close()
    #print ('end')

def Handle():    
    global conn, BUFFER_SIZE, s, sendQueue, terminate

    PrintBufferStatistics()

    try:
        s.settimeout(4.0)
        conn, addr = s.accept()
        Log('Device with address '+str(addr[0])+' was connected',FULL)
        if addr[0] not in onlineDevices:
            onlineDevices.append(addr[0])
            Log('New device with address ' + str(addr[0]) + ' was connected')
            databaseSQLite.AddOnlineDevice(str(addr[0]))

        conn.settimeout(4.0)
        #if you have something to send, send it
        sendWasPerformed = False
        for tx in sendQueue:
            if(tx[1]==addr[0]):#only if we have something to send to the address that has connected
                #print("Sending:")
                #for a in tx[0]:
                #    print(">>"+str(a))
                conn.send(tx[0])
                sendQueue.remove(tx)

                sendWasPerformed = True

        if not sendWasPerformed:
            Log("Nothing to be send to this connected device '"+str(addr[0])+"'", FULL)

        time.sleep(0.1) # give client some time to send me data
        #data receive
        r, _, _ = select.select([conn], [], [],4)
        if r:
            data = conn.recv(BUFFER_SIZE)
        else:
            Log("Device '"+str(addr[0])+"' was connected, but haven't send any data.")
            return;

        if not data: return
        st = ""

        for d in data:
            serialData.Receive(d)
            st+= str(d)+", "

        Log("Received data:"+str(st), FULL)

        conn.close()

    except KeyboardInterrupt:
        Log("Interrupted by user keyboard -----")
        terminate = True

    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        
        if(exc_type == socket.timeout):
            Log("Socket timeout!", FULL)
        else:
            Log("Exception:")
            Log(''.join('!! ' + line for line in lines))

def Send(data, destination, crc16=False):#put in send queue
    global sendQueue, onlineDevices

    if len(sendQueue) >= TXQUEUELIMIT_PER_DEVICE: # if buffer is at least that full
        cnt = sum([msg[1] == destination for msg in sendQueue]) # how much are with same address
        if cnt >= TXQUEUELIMIT_PER_DEVICE:# this device will become offline

            if destination in onlineDevices:
                onlineDevices.remove(destination)
                Log("Device with address:'"+destination+"' become OFFLINE!")
                databaseSQLite.RemoveOnlineDevice(destination)
            # now remove the oldest message and further normally append newest
            oldMsgs = [msg for msg in sendQueue if msg[1] == destination]

            if(len(oldMsgs)>0):
                sendQueue.remove(oldMsgs[0])

    if len(sendQueue)<TXQUEUELIMIT:
        sendQueue.append((serialData.CreatePacket(data, crc16),destination))
    else:
        Log("MAXIMUM TX QUEUE LIMIT REACHED!!")

def SendACK(data,destination):
    #poslem CRC techto dat na danou destinaci
    global sendQueue,TXQUEUELIMIT

    CRC = serialData.calculateCRC(data) + len(data)
    
    if len(sendQueue)<TXQUEUELIMIT:
        sendQueue.append((serialData.CreatePacket(bytes([99,int(CRC)%256,int(CRC/256)])),destination))
        Log("sending BACK"+str(CRC)+" to destination:"+destination)
    else:
        Log("MAXIMUM TX QUEUE LIMIT REACHED")


def PrintBufferStatistics():
    global tmrPrintBufferStat, sendQueue

    if time.time() - tmrPrintBufferStat > 600 and len(sendQueue) >= TXQUEUELIMIT_PER_DEVICE: # periodically and only if there are some messages watiting
        tmrPrintBufferStat = time.time()
        Log("------ Buffer statistics:")
        Log("Msgs in send buffer:" + str(len(sendQueue)))
        # find different devices in queue
        uniqDev = []
        for dev in sendQueue:
            # find match in uniq
            item = next((x for x in uniqDev if x[0] == dev[1]), None)

            if item is None:
                uniqDev.append([dev[1], 1])
            else:
                item[1] = item[1] + 1 # increase occurence

            Log("Occurences:")
            Log(uniqDev)
        Log("------ ")


def DataReceived():

    return serialData.getRcvdData()

def Ping(host):
    ping_response = subprocess.Popen(["/bin/ping", "-c1", "-w100", host], stdout=subprocess.PIPE).stdout.read()

    return True if "1 received" in ping_response.decode("utf-8") else False

def Log(s,_verbosity=NORMAL):
    if _verbosity > verbosity:
        return
    s = "TCP: " + str(s)
    print(str(s))

    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("logs/tcpServer.log","a") as file:
        file.write(dateStr+" >> "+str(s)+"\n")


