#!/usr/bin/env python
          

import time
import serial


ser = serial.Serial(
  
   port='/dev/ttyS0',
   baudrate = 9600,
   parity=serial.PARITY_NONE,
   stopbits=serial.STOPBITS_ONE,
   bytesize=serial.EIGHTBITS,
   timeout=1
)
counter=0
      
ser.write(bytes("AT+CGMI\r",'UTF-8'))
while 1:
   #ser.write(bytes('Write counter: %d \n'%(counter),'UTF-8'))
    x = ser.readline()
    if(len(x)>0):
        print(x)
    counter += 1
