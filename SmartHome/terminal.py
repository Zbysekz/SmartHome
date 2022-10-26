#!/usr/bin/python3
from tkinter import *
from databaseMySQL import cMySQL
import struct

IP_RACKUNO = "192.168.0.5"
IP_POWERWALL = "192.168.0.12"
IP_SERVER = "192.168.0.3"
MySQL = cMySQL()

def SendData(data, address=None):
    if address is None:
        address = DEST.get()
        
    MySQL.insertTxCommand(address, data)

def sendRawCallback():
          
    data = e[0].get()
    for i in range(1,int(LEN.get())):
        data+=","+e[i].get();
    print(data)
    
    SendData(data)
    
def sendCal(id, address):
        
    data = id+","+modID.get()
    
    buffer = struct.pack('f',float(eCal1.get()))
    
    data+=","+str(buffer[0])+","+str(buffer[1])+","+str(buffer[2])+","+str(buffer[3]);
    
    SendData(data, address)
    
def sendCal2(id, address):
        
    data = id+","+modID.get()
    
    buffer = struct.pack('f',float(eCal2.get()))
    
    data+=","+str(buffer[0])+","+str(buffer[1])+","+str(buffer[2])+","+str(buffer[3]);
    
    SendData(data, address)

    
def buttonTempCallback():
    sendCal("5", address=IP_POWERWALL)
def buttonVoltCallback():
    sendCal("4", address=IP_POWERWALL)
    
def buttonTemp2Callback():
    sendCal2("16", address=IP_POWERWALL)
def buttonVolt2Callback():
    sendCal2("15", address=IP_POWERWALL)

def buttonBurnCallback():
    data = "14,"+modID2.get()
    
    val = int(float(eBurnV.get())*100)
    
    data+=","+str(val//256)+","+str(val%256)
    
    SendData(data, address=IP_POWERWALL)

def buttonRunCallback():
    SendData("10", address=IP_POWERWALL)
def buttonChargeOnlyCallback():
    SendData("11", address=IP_POWERWALL)
def buttonDisconnectCallback():
    SendData("12", address=IP_POWERWALL)
def buttonResetCallback():
    SendData("13", address=IP_POWERWALL)
    
def buttonAddressSetCallback():
    SendData("7,"+str(eCellID.get())+","+str(eCellNewAddr.get()), address=IP_POWERWALL)
def buttonProvisionCallback():
    SendData("2", address=IP_POWERWALL)
def buttonBlinkCallback():
    SendData("0,"+str(eCellID.get())+",170", address=IP_POWERWALL)
def buttonHeatInhibitCallback():
    SendData("1,1", address=IP_RACKUNO)
def buttonStopHeatInhibitCallback():
    SendData("1,0", address=IP_RACKUNO)

def buttonStopHeatControlCallback():
    SendData("1", address=IP_SERVER)
def buttonStartHeatControlCallback():
    SendData("2", address=IP_SERVER)

      
def buttonVentilationCallback():
    SendData("2,"+str(E_VENT.get()), address=IP_RACKUNO)

def buttonSwitchToGridCallback():
    SendData("3", address=IP_RACKUNO)
def buttonSwitchToSolarCallback():
    SendData("4", address=IP_RACKUNO)
    
top = Tk()
top.title('Terminal')
top.geometry("500x600")

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

B = Button(top,text="Provision",command = buttonProvisionCallback)
B.place(x=20,y=100)

B = Button(top,text="Blink cell",command = buttonBlinkCallback)
B.place(x=110,y=100)

B = Button(top,text="Set new addr",command = buttonAddressSetCallback)
B.place(x=200,y=100)

eCellID = Entry(top)
eCellID.place(x=350,y=105,width=40)
eCellID.insert(0,"24")

eCellNewAddr = Entry(top)
eCellNewAddr.place(x=400,y=105,width=40)
eCellNewAddr.insert(0,"24")

#--------------------------temperature and voltage calibration
y=140
l = Label(top, text="Calibration:")
l.place(x=0, y=y)

B = Button(top,text="TempCal",command = buttonTempCallback)
B.place(x=20,y=y+20)

B = Button(top,text="TempCal",command = buttonTemp2Callback)
B.place(x=40,y=y+20)

modID = Entry(top)
modID.place(x=120,y=y+40,width=50)
modID.insert(0,"24")

eCal1 = Entry(top)
eCal1.place(x=190,y=y+40,width=50)
eCal1.insert(0,"1.00")
eCal2 = Entry(top)
eCal2.place(x=190,y=y+60,width=50)
eCal2.insert(0,"1.00")

B = Button(top,text="VoltCal",command = buttonVoltCallback)
B.place(x=20,y=y+60)
B = Button(top,text="VoltCal",command = buttonVolt2Callback)
B.place(x=40,y=y+60)

B = Button(top,text="Burn",command = buttonBurnCallback)
B.place(x=280,y=y+40)

modID2 = Entry(top)
modID2.place(x=350,y=y+40,width=50)
modID2.insert(0,"24")

eBurnV = Entry(top)
eBurnV.place(x=420,y=y+40,width=50)
eBurnV.insert(0,"4.0")

#CONNECT and DISCONNECT BATTERY
y=240
l = Label(top, text="Battery:")
l.place(x=0, y=y)
B = Button(top,text="Run",command = buttonRunCallback)
B.place(x=0,y=y+20)
B = Button(top,text="ChargeOnly",command = buttonChargeOnlyCallback)
B.place(x=60,y=y+20)
B = Button(top,text="Disconnect",command = buttonDisconnectCallback)
B.place(x=180,y=y+20)
B = Button(top,text="Reset Error",command = buttonResetCallback)
B.place(x=300,y=y+20)

#HEATING INHIBIT
y=300
l = Label(top, text="Heating inhibition:")
l.place(x=0, y=y)
B = Button(top,text="Inhibit",command = buttonHeatInhibitCallback)
B.place(x=0,y=y+20)
B = Button(top,text="Stop inhibit",command = buttonStopHeatInhibitCallback)
B.place(x=100,y=y+20)

#HEATING CONTROL
y=360
l = Label(top, text="Heating control:")
l.place(x=0, y=y)
B = Button(top,text="Start",command = buttonStartHeatControlCallback)
B.place(x=0,y=y+20)
B = Button(top,text="Stop",command = buttonStopHeatControlCallback)
B.place(x=100,y=y+20)


#VENTILATION
y=420
l = Label(top, text="Ventilation control:")
l.place(x=0, y=y)
B = Button(top,text="OK",command = buttonVentilationCallback)
B.place(x=100,y=y+20)
E_VENT = Entry(top)
E_VENT.place(x=30,y=y+20,width=30)
E_VENT.insert(0,"0")

#VENTILATION
y=480
l = Label(top, text="Switching source of power:")
l.place(x=0, y=y)
B = Button(top,text="GRID",command = buttonSwitchToGridCallback)
B.place(x=20,y=y+20)
B = Button(top,text="SOLAR",command = buttonSwitchToSolarCallback)
B.place(x=120,y=y+20)

top.mainloop()

