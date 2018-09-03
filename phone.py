#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
from datetime import datetime

smsc = "420602909909";#vodafone 420608005681


commCheck = 0
sendingSMS = 0
receivingSMS = 0
serPort = 0
rcvState = 0
UNREAD_SMS_TIME = 2 #x5s
unreadSMSTimer = UNREAD_SMS_TIME
MAX_TRIES = 3
numberOfTries = MAX_TRIES
TRY_TIME = 5#x5s
tryTimer = TRY_TIME
lastReceiver = ""
lastText = ""
incomeSMSList=[]
idOfStoredSMS=0
clearBufferWhenPhoneOffline=0

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

def CheckSMSsent():#kontrola jestli se sms skutecne poslala, kdyz ne, zkousi znovu
    global lastReceiver,lastText,sendingSMS,tryTimer,numberOfTries
    
    if sendingSMS != 0:
        tryTimer -=1
        
        if(tryTimer==0):
            tryTimer = TRY_TIME
            sendingSMS = 0
            if(numberOfTries!=0):
                Log("Trying to send SMS again! remaining tries:"+str(numberOfTries))
                SendSMS(lastReceiver,lastText)#posli sms znovu s poslednim cislem a textem
                numberOfTries -= 1
            else:
                Log("No more trying to send SMS, max number of tries reached !!!")
    else:
        tryTimer = TRY_TIME
        numberOfTries = MAX_TRIES

def CheckUnreadSMS():
    global unreadSMSTimer,UNREAD_SMS_TIME,commCheck,serPort
    
    commCheck+=1#to detect that phone is not responding
    
    if unreadSMSTimer == 0:
        unreadSMSTimer = UNREAD_SMS_TIME
        
        Log("Checking Unread SMS!")
        
        serPort.write(bytes("AT+CPMS=\x22ME\x22,\x22ME\x22,\x22ME\x22\x0D",'UTF-8'));#\x22 = "
        
        time.sleep(0.5)
        
        serPort.write(bytes("AT+CMGL=0\x0D",'UTF-8'));#\x22 = " //0 unread, 1 read, 4 all
        
    else:
        unreadSMSTimer-=1

def ReceiveCmds():
    global sendingSMS,receivingSMS,MAX_TRIES,numberOfTries,incomeSMSList,idOfStoredSMS
    global serPort,commCheck
    
    rcvLines = ReceiveLinesFromSerial()
    #rcvLine = serPort.readline() #nejde pouzit, protoze kdyz je mobil vyplej tak se zasekne - asi nefunguje timout v knihovne?
    #rcvLines.append(rcvLine)

    for rcvLine in rcvLines:
        
        Log("Received from serial:"+str(rcvLine))
        if(rcvState==0):#prijimani jednorazovych prikazu
            
            if(b"RING" in rcvLine):
                Log("Mobile is ringing!!!")
            elif(b"+CMGW:" in rcvLine):
                Log("CMGW income!!!!")
                if sendingSMS==1:
                    idOfStoredSMS = -1
                    
                    pos = rcvLine.find(b"+CMGW:")
                    if len(rcvLine)>pos+8:
                        if rcvLine[pos+7] >=48 and rcvLine[pos+7]<=57:#pokud jsou to validni cisla na svych mistech
                            
                            if rcvLine[pos+8] >=48 and rcvLine[pos+8]<=57:#pokud je prvni i druhe validni
                                idOfStoredSMS = int(chr(rcvLine[pos+7]))*10 + int(chr(rcvLine[pos+8]))
                            else:
                                idOfStoredSMS = int(chr(rcvLine[pos+7]))#pokud je jen druhe validni             
                    
                    if idOfStoredSMS != 0:
                        CMSScommand(idOfStoredSMS)
                    sendingSMS=2
            elif(b"+CMGL:" in rcvLine):
                Log("CMGL income!")
                #pos = rcvLine.find(b"07")
                receivingSMS = 1
                Log(rcvLine)
                
                
            elif (b"OK\r" in rcvLine):
                Log("OK received!")
                commCheck=0#to detect that phone is not responding
                if(sendingSMS==2):
                    Log("CMGW OK received!")
                    sendingSMS=3
                elif(sendingSMS==3):
                    Log("Sending of SMS successful!")
                    CMGDcommand(idOfStoredSMS)#delete SMS stored in memory
                    numberOfTries = MAX_TRIES
                    sendingSMS=0
            elif(receivingSMS==1 and rcvLine[0]==ord("0") and rcvLine[1]==ord("7")):
                txt,transmitter = DecodePDU(str(rcvLine))
                incomeSMSList.append((txt,transmitter))
                
                Log("RECEIVED SMS:"+txt+",from:"+transmitter)
            else:
                receivingSMS=0
                Log("Not processed.")
                    

def ReceiveLinesFromSerial():
    global serPort,clearBufferWhenPhoneOffline

    maxChars = 200#maximalne tolik znaku lze precist
    rcvLine = bytes()
    rcvLines = []
    ptr=0
    ch = serPort.read(maxChars)
    
    if len(ch)==maxChars:#if we have received maximum characters, increase var and then reset input buffer - when phone is offline, input buffer is full of zeroes
        clearBufferWhenPhoneOffline += 1
    
    if (clearBufferWhenPhoneOffline>3):
        Log("Serial input buffer reset!")
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

def CMSScommand(idSMS):  
    
    cmd = "AT+CMSS=%02d" % (idSMS,)
    
    print("sending CMSS command:"+cmd)
    serPort.write(bytes(cmd+"\x0D",'UTF-8'))
    
    
def CMGDcommand(idSMS):
    global serPort
    cmd = "AT+CMGD=%02d" % (idSMS,)	

    Log("deleting message id:"+str(idSMS))
    
    serPort.write(bytes(cmd+"\x0D",'UTF-8'));#CMGW
    
    time.sleep(1)
    
    x = serPort.readline()
    while(len(x)>0):
        print("rcvd:"+str(x))
        x = serPort.readline()
    
def SendSMS(receiver, text):
    global serPort,sendingSMS,lastReceiver,lastText
    
    Log("Sending SMS !")
    
    if(sendingSMS!=0):
        Log("Already sending SMS ! Aborting !!")
        return
    
    lastReceiver = receiver
    lastText = text
        
    output,telegramLen = codePDU(receiver,text)
    
    serPort.write(bytes("AT+CPMS=\x22ME\x22,\x22ME\x22,\x22ME\x22\x0D",'UTF-8'));#\x22 = "
	
    telegramLen=telegramLen/2 - 8
    
    pomCmd = "AT+CMGW=";
    pomCmd+=chr(int(((telegramLen)/10)+48));#convert to number instead of two 00
    pomCmd+=chr(int(((telegramLen)%10)+48));#
		
    
    time.sleep(0.5)
    x = serPort.readline()
    if(len(x)>0):
        print("rcvd:"+str(x))
    
    Log("sending cmd:"+pomCmd)
    serPort.write(bytes(pomCmd+"\x0D",'UTF-8'));#CMGW
	
	#add SUB character -> value 26 na konec

    time.sleep(0.5)
    x = serPort.readline()
    if(len(x)>0):
        print("rcvd:"+str(x))
    print(output)
    #output = "079124602009999011000C912460208147090000FF0441F45B0D"
    
    print("sending output:"+output)
    serPort.write(bytes(output+"\x1A\x0D",'UTF-8'))#posle zpravu CMGW
 
    sendingSMS=1         
    

def codePDU(receiver, text):
    
    textLen = len(text)

    output=""

    output+="0791"#pevne
    #smc 420608005681
    #246080006518

    smsc_pom = list(smsc)
    for i in range(6):
        smsc_pom[i*2]=smsc[i*2+1]
        smsc_pom[i*2+1]=smsc[i*2]
    
    output+=''.join(smsc_pom)
    #SMS deliver?
    #11
    #00
    #0C
    #91
    output+="11000C91"
    #rec. adress 420737282211
    #247073822211

    receiver_pom=list(receiver)
    for i in range(6):
        receiver_pom[i*2]=receiver[i*2+1]
        receiver_pom[i*2+1]=receiver[i*2]
        
    output+=''.join(receiver_pom)
   
    #0000
    #timestamp 
    #AA
    output+="0000AA"
    
    #length of data (neni delka hexa dat ale textu z toho vznikleho)
    #0F
    ln = format(textLen, 'x').upper()

    if len(ln)==1:
        ln = ['0',ln[0]]
        
    output+=ln[0] 
    output+=ln[1]
    
    #data - prevod 8bit na 7 bit dle tab    "Hello world! :)"
    #C8
    #32
    #9B
    #FD
    #06
    #DD
    #DF
    #72
    #36
    #39
    #04
    #D2   
    #A5   
    #00


    q=0
    offset=0#poc bytu co jsme usetrili
    textHex=list([0]*textLen*3)
    textPom = list([0]*textLen*3)
    
    for i in range(textLen):
        textPom[i]=ord(text[i])>>q
        textPom[i]= textPom[i]|getPart(ord(text[i+1])if i+1<len(text)else 0,q+1)
    
        ln = format(textPom[i], 'x').upper()
        if len(ln)==1:
            ln = ['0',ln[0]]
            
        print("hex:"+''.join(ln))
        textHex[(i-offset)*2]=ln[0]
        textHex[(i-offset)*2+1]=ln[1]
    
        if(q<7):
            q+=1
        else:
            q=0
            offset+=1
            
    for i in range(textLen - offset):
        output+=textHex[i*2]
        output+=textHex[i*2+1]
    
    telegramLen = len(output)

    return output,telegramLen


def DecodePDU(msg):
    
    msg = msg.replace("\\n","").replace("\\r","")
    txt = ""
    
    
    p=0;#startovni index
	
    for i in range(6):#hleda pro zacatecni znak, nekdy totiz muze prijit znak navic
        if(msg[p]=='1'):#49
            p+=1;
            break
        p+=1;
        
    smsc=list("000000000000")
    
	#smc 420608005681
	#246080006518 
	#p+=4;
    for i in range(6):
        smsc[i*2+1] = msg[p]
        p+=1
        smsc[i*2] = msg[p]
        p+=1
    smsc = "".join(smsc)
    
    print("smsc:"+str(smsc))
    p+=6;

    sender=list("000000000000")
	#send. adress 420737282211
	#247073822211
    for i in range(6):
        sender[i*2+1] = msg[p];
        p+=1
        sender[i*2] = msg[p];
        p+=1
    sender = "".join(sender)
    Log("sender:"+str(sender))
    p+=18;#6

    #length of data (neni delka hexa dat ale textu z toho vznikleho)
	#0F
    print(p)
    print(msg[p])
    print(msg[p+1])
    textLength = int(""+msg[p]+msg[p+1],16);
    p+=2


    print("TXTLEN:"+str(len(msg)))


    offset=0;#poc bytu co jsme pridali
    textInt = [0]*textLength
    for i in range(textLength):
        if p+1 < len(msg):
            textInt[i] = int(""+msg[p]+msg[p+1],16);
            p+=2

    q=0;
    txt=list(" "*textLength)
    for i in range(textLength):
        if(q<7):
            txt[i]= chr(MaskUpper(textInt[i - offset],q+1)<<q);#maskuje q horních bitu
            if(q!=0):
                txt[i] = chr(ord(txt[i]) | getPart2(textInt[i-1 - offset],q));#vezme q horních bitu a vrátí je dole
		
            q+=1;
        else:
            txt[i] = chr(getPart2(textInt[i-1 - offset],q))
            q=0
            offset+=1;   
    txt = "".join(txt)
    
    return txt,sender

def getIncomeSMSList():
    global incomeSMSList
    return incomeSMSList

def clearIncomeSMSList():
    global incomeSMSList
    incomeSMSList.clear()

def getPart(value,count):#vezme dolní bity a vrátí je nahore   pro count=3 : xxxxx010 vrátí 010xxxxx 
    if(count==1):
        value &= 0x01
        value=value<<7;
    elif(count==2):
        value &=0x03
        value=value<<6;
    elif(count==3):
        value &= 0x07;
        value=value<<5;
    elif(count==4):
        value &= 0x0F;
        value=value<<4;
    elif(count==5):
        value &= 0x1F;
        value=value<<3;
    elif(count==6):
        value &= 0x3F;
        value=value<<2;
    elif(count==7):
        value &= 0x7F;
        value=value<<1;
    return value;

def getPart2(value,count):#vezme horní bity a vrátí je dole   pro count=3 : 010xxxxx vrátí xxxxx010 
    value = value>>(8-count)
    return value

def MaskUpper(value,count):#zamaskuje horní bity  pro count=3 : 110xxxxx vrátí 000xxxxx
    if count==1:
        value &= 0x7F
    if count==2:
        value &= 0x3F
    if count==3:
        value &= 0x1F
    if count==4:
        value &= 0x0F
    if count==5:
        value &= 0x07
    if count==6:
        value &= 0x03
    if count==7:
        value &= 0x01
        
    return value

def getCommState():
    return True if commCheck>5 else False

def Log(s):
    print("LOGGED:"+str(s))

    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("logs/phone.log","a") as file:
        file.write(dateStr+" >> "+str(s)+"\n")
