#!/usr/bin/python3
from tkinter import *
import databaseMySQL
import struct

IP_RACKUNO = "192.168.0.5"
IP_POWERWALL = "192.168.0.12"

def SendData(data, address=None):
    if address is None:
        address = DEST.get()
        
    databaseMySQL.insertTxCommand(address, data)

def sendRawCallback():
          
    data = e[0].get()
    for i in range(1,int(LEN.get())):
        data+=","+e[i].get();
    print(data)
    
    SendData(data)
    
def sendCal(id):
        
    data = id+","+modID.get()
    print(type(tempCal.get()))
    
    buffer = struct.pack('f',float(tempCal.get()))
    
    data+=","+str(buffer[0])+","+str(buffer[1])+","+str(buffer[2])+","+str(buffer[3]);
    
    SendData(data)
    
def buttonTempCallback():
    sendCal("5", address=IP_POWERWALL)
def buttonVoltCallback():
    sendCal("4", address=IP_POWERWALL)

def buttonConnectCallback():
    SendData("7", address=IP_POWERWALL)
def buttonDisconnectCallback():
    SendData("8", address=IP_POWERWALL)

def buttonHeatInhibitCallback():
    SendData("1,1", address=IP_RACKUNO)
def buttonStopHeatInhibitCallback():
    SendData("1,0", address=IP_RACKUNO)
    
def buttonVentilationCallback():
    SendData("2,"+str(E_VENT.get()), address=IP_RACKUNO)

top = Tk()
top.title('Terminal')
top.geometry("400x350")

B = Button(top,text="Send raw",command = sendRawCallback)
B.place(x=50,y=45)

DEST = Entry(top)
DEST.place(x=0,y=10,width=100)
DEST.insert(0,"192.168.0.12")

LEN = Entry(top)
LEN.place(x=100,y=10,width=30)
LEN.insert(0,"1")

offsetX = 140
E1 = Entry(top)
E1.place(x=offsetX+0,y=50,width=30)
E2 = Entry(top)
E2.place(x=offsetX+30,y=50,width=30)
E3 = Entry(top)
E3.place(x=offsetX+60,y=50,width=30)
E4 = Entry(top)
E4.place(x=offsetX+90,y=50,width=30)
E5 = Entry(top)
E5.place(x=offsetX+120,y=50,width=30)
E6 = Entry(top)
E6.place(x=offsetX+150,y=50,width=30)
E7 = Entry(top)
E7.place(x=offsetX+180,y=50,width=30)
E8 = Entry(top)
E8.place(x=offsetX+210,y=50,width=30)

e = []
e.append(E1)
e.append(E2)
e.append(E3)
e.append(E4)
e.append(E5)
e.append(E6)
e.append(E7)
e.append(E8)

#--------------------------temperature and voltage calibration
l = Label(top, text="Calibration:")
l.place(x=0, y=80)

B = Button(top,text="TempCal",command = buttonTempCallback)
B.place(x=20,y=100)

modID = Entry(top)
modID.place(x=140,y=120,width=80)
modID.insert(0,"1")

tempCal = Entry(top)
tempCal.place(x=210,y=120,width=80)
tempCal.insert(0,"1.00")

B = Button(top,text="VoltCal",command = buttonVoltCallback)
B.place(x=20,y=140)

#CONNECT and DISCONNECT BATTERY
l = Label(top, text="Battery:")
l.place(x=0, y=180)
B = Button(top,text="Connect",command = buttonConnectCallback)
B.place(x=0,y=200)
B = Button(top,text="Disconnect",command = buttonDisconnectCallback)
B.place(x=100,y=200)

#HEATING INHIBIT
l = Label(top, text="Heating inhibition:")
l.place(x=0, y=240)
B = Button(top,text="Inhibit",command = buttonHeatInhibitCallback)
B.place(x=0,y=260)
B = Button(top,text="Stop inhibit",command = buttonStopHeatInhibitCallback)
B.place(x=100,y=260)

#VENTILATION
l = Label(top, text="Ventilation control:")
l.place(x=0, y=300)
B = Button(top,text="OK",command = buttonVentilationCallback)
B.place(x=100,y=320)
E_VENT = Entry(top)
E_VENT.place(x=30,y=320,width=30)
E_VENT.insert(0,"0")


top.mainloop()

