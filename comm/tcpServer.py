#!/usr/bin/env python3
# -*- coding: utf-8 -*-

conn=''
s=''
BUFFER_SIZE = 256  # Normally 1024, but we want fast response
sendQueue = []
TXQUEUELIMIT=30
printDebugInfo = False

def Init():
    import socket
    import serialData

    global conn,s
    
    TCP_IP = '192.168.0.3'
    TCP_PORT = 23

    print ('Start')
    #socket.setdefaulttimeout(5)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setblocking(0)
    s.bind((TCP_IP, TCP_PORT))
    s.listen(1)

    
 
    #conn.close()
    #print ('end')

def Handle():
    import serialData
    import socket
    
    global conn,BUFFER_SIZE,s,sendQueue
    global printDebugInfo

    try:
        s.settimeout(4.0)
        conn, addr = s.accept()
        print ('Connection address:', addr)
        conn.settimeout(4.0)
        #tady mu pošlu něco pokud mám
        for tx in sendQueue:
            if(tx[1]==addr[0]):#jen pokud mám co říct adrese co se připojila
#                print("Sending:")
#                for a in tx[0]:
#                    print(">>"+str(a))
                conn.send(tx[0])
                sendQueue.remove(tx)
            else:
                print("want to send but not the one")
                print(addr[0])
                print(tx[1])

        #příjem dat
        import select
        r, _, _ = select.select([conn], [], [],4)
        if r:
            data = conn.recv(BUFFER_SIZE)
        else:
            Log("No DATA, returning.")
            return;

        if not data: return
        st = ""

        for d in data:
            serialData.Receive(d)
            st+= str(d)+", "
        if printDebugInfo:
            Log("RCVD:"+str(st))

        conn.close();

    except:
        import sys
        import traceback
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        
        if(exc_type == socket.timeout):
            if printDebugInfo:
                Log("timeout")
        else:
            if printDebugInfo:
                Log(''.join('!! ' + line for line in lines))

def Send(data,destination):#zařadí do fronty pro poslání
    global TXQUEUELIMIT,sendQueue
    import serialData
    
    if getSendQueueCount()<TXQUEUELIMIT:
        sendQueue.append((serialData.CreatePacket(data),destination))
    else:
        print("MAXIMUM TX QUEUE LIMIT REACHED")
def SendACK(data,destination):
    #poslem CRC techto dat na danou destinaci
    global sendQueue,TXQUEUELIMIT
    import serialData
    CRC = serialData.calculateCRC(data) + len(data)
    
    if getSendQueueCount()<TXQUEUELIMIT:
        sendQueue.append((serialData.CreatePacket(bytes([99,int(CRC)%256,int(CRC/256)])),destination))
        print("sending BACK"+str(CRC)+" to destination:"+destination)
    else:
        print("MAXIMUM TX QUEUE LIMIT REACHED")
    
def getSendQueueCount():
    global sendQueue
    return len(sendQueue)

def DataReceived():
    import serialData
    
    return serialData.getRcvdData()

def Log(str):
    print("LOGGED:"+str)
    from datetime import datetime
    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("tcpServer_log.txt","a") as file:
        file.write(dateStr+" >> "+str+"\n")
