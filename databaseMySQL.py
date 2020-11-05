#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import mysql.connector
import time

   
def getTotalSum():
    
    points_low=getValues("consumption","lowTariff",datetime(2000,1,1,0,0),datetime.now(),True)
    points_std=getValues("consumption","stdTariff",datetime(2000,1,1,0,0),datetime.now(),True)

    
    return next(points_low)['sum'], next(points_std)['sum']

def RemoveOnlineDevices():
    return

def getValues(kind, sensorName, timeFrom, timeTo, sum = False):
    
    try:
        mydb = mysql.connector.connect(
          host="localhost",
          user="mainScript",
          password="mainScript",
          database="db1"
        )
        
        mycursor = mydb.cursor()
        
        if not sum:
            select = 'SELECT value'
        else:
            select = 'SELECT SUM(value)'
        
        sql = select+" FROM measurements WHERE source=%s AND time > %s AND time < %s"
        val = (sensorName, timeFrom, timeTo)
        mycursor.execute(sql, val)

        result = mycursor.fetchall()
        
        values = []
        for x in result:
            values.append(x[0])
            
    except Exception as e:
        Log("Error while writing to database for measurement:"+sensorName+" exception:")
        Log(type(e))    # the exception instance
        Log(e.args)     # arguments stored in .args
        Log(e)
        return False

    
    return values

def insertValue(name, sensorName, value, timestamp=None):
    try:
        mydb = mysql.connector.connect(
          host="localhost",
          user="mainScript",
          password="mainScript",
          database="db1"
        )
        
        mycursor = mydb.cursor()
        
        if not timestamp: # if not defined, set time now
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

        sql = "INSERT INTO measurements (time, kind, source, value) VALUES (%s, %s, %s, %s)"
        val = (timestamp, name, sensorName, value)
        mycursor.execute(sql, val)

        mydb.commit()
            
    except Exception as e:
        Log("Error while writing to database for measurement:"+name+" exception:")
        Log(type(e))    # the exception instance
        Log(e.args)     # arguments stored in .args
        Log(e)
        return False
    
    if mycursor.rowcount>0:
        return True
    else:
        return False

def updateState(name, value):
    try:
        mydb = mysql.connector.connect(
          host="localhost",
          user="mainScript",
          password="mainScript",
          database="db1"
        )
        
        mycursor = mydb.cursor()
        
        sql = "UPDATE state SET "+str(name)+"=%s"
        val = (value,)
        mycursor.execute(sql, val)

        mydb.commit()
            
    except Exception as e:
        Log("Error while writing to database for state:"+name+" exception:")
        Log(type(e))    # the exception instance
        Log(e.args)     # arguments stored in .args
        Log(e)
        return False
    
def insertEvent(desc1, desc2, timestamp=None):
    try:
        mydb = mysql.connector.connect(
          host="localhost",
          user="mainScript",
          password="mainScript",
          database="db1"
        )
        
        mycursor = mydb.cursor()
        
        if not timestamp: # if not defined, set time now
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

        sql = "INSERT INTO events (time, desc1, desc2) VALUES (%s, %s, %s)"
        val = (timestamp, desc1, desc2)
        mycursor.execute(sql, val)

        mydb.commit()
            
    except Exception as e:
        Log("Error while writing to database for events:"+desc1+" exception:")
        Log(type(e))    # the exception instance
        Log(e.args)     # arguments stored in .args
        Log(e)
        return False
    
    if mycursor.rowcount>0:
        return True
    else:
        return False        
        
#TODO
def getCmds():
    return None

def getTXbuffer():
    return []
          

def Log(strr):
    txt=str(strr)
    print("LOGGED:"+txt)
    from datetime import datetime
    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("logs/databaseMySQL.log","a") as file:
        file.write(dateStr+" >> "+txt+"\n")
        
                
if __name__=="__main__":
    print("run")