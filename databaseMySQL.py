#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import mysql.connector
import time
import sys
import os
from datetime import datetime,timezone

   
def getTotalSum():
    
    points_low=getValues("consumption","lowTariff",datetime(2000,1,1,0,0),datetime.now(),True)
    points_std=getValues("consumption","stdTariff",datetime(2000,1,1,0,0),datetime.now(),True)

    
    return points_low[0], points_std[0]

def AddOnlineDevice(ip):
    try:
        db, cursor = Connect()
        
        sql = "UPDATE onlineDevices SET online=1,stateChangeTime=UTC_TIMESTAMP() WHERE ip=%s"
        val = (ip,)
        cursor.execute(sql, val)

        db.commit()
        cursor.close()
        db.close()
            
    except Exception as e:
        Log("Error while writing to database for AddOnlineDevice:"+ip+" exception:")
        LogException(e)
        return False
    
    return True

def RemoveOnlineDevices():
    RemoveOnlineDevice(ip=None)
    
def RemoveOnlineDevice(ip):
    try:
        db, cursor = Connect()
        
        if ip is None: # delete all
            sql = "UPDATE onlineDevices SET online=0,stateChangeTime=UTC_TIMESTAMP()"
            cursor.execute(sql)
        else:
            sql = "UPDATE onlineDevices SET online=0,stateChangeTime=UTC_TIMESTAMP() WHERE ip=%s"
            val = (ip,)
            cursor.execute(sql, val)

        db.commit()
        cursor.close()
        db.close()
            
    except Exception as e:
        Log("Error while writing to database for RemoveOnlineDevice, exception:")
        LogException(e)
        return False
    
    return True

def Connect():
    db = mysql.connector.connect(
          host="localhost",
          user="mainScript",
          password="mainScript",
          database="db1"
        )
        
    cursor = db.cursor()
        
    return db, cursor

def updatePriceData(name, value):
    try:
        db, cursor = Connect()
        
        sql = "UPDATE prices SET value=%s WHERE name=%s"
        val = (value,name)
        cursor.execute(sql, val)
        
        db.commit()

            
    except Exception as e:
        Log("Error while writing to database for updatePriceData name:"+str(name)+", exception:")
        LogException(e)
        return False

    return True
    
def getPriceData():
    try:
        db, cursor = Connect()
        
        sql = "SELECT name, value FROM prices"
        cursor.execute(sql)

        data = cursor.fetchall()
        
        values = {}
        for d in data:
            values[d[0]] = d[1]
            
    except Exception as e:
        Log("Error while writing to database for getPriceData, exception:")
        LogException(e)
        return None

    return values

def getValues(kind, sensorName, timeFrom, timeTo, _sum = False):
    
    try:
        db, cursor = Connect()
        
        
        if not _sum:
            select = 'SELECT value'
        else:
            select = 'SELECT SUM(value)'
        
        sql = select+" FROM measurements WHERE source=%s AND time > %s AND time < %s"
        val = (sensorName, timeFrom, timeTo)
        cursor.execute(sql, val)

        result = cursor.fetchall()
        
        values = []
        for x in result:
            values.append(x[0])
            
    except Exception as e:
        Log("Error while writing to database for measurement:"+sensorName+" exception:")
        LogException(e)
        return None

    
    return values

def insertValue(name, sensorName, value, timestamp=None, periodicity=0):
    try:
        db, cursor = Connect()
        
        if not timestamp: # if not defined, set time now
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        args = (timestamp, name, sensorName, value, periodicity)
        res = cursor.callproc('insertMeasurement',args)
        
        db.commit()
        cursor.close()
        db.close()
            
    except Exception as e:
        Log("Error while writing to database for measurement:"+name+" exception:")
        LogException(e)
        return False

    return True

def insertDailySolarCons(value):
    try:
        db, cursor = Connect()
        
        args = (value,)
        res = cursor.callproc('DailySolarCons',args)
        
        db.commit()
        cursor.close()
        db.close()
            
    except Exception as e:
        Log("Error while writing to database for insertDailyCons, exception:")
        LogException(e)
        return False

    return True

def updateState(name, value):
    try:
        db, cursor = Connect()
        
        sql = "UPDATE state SET "+str(name)+"=%s"
        val = (value,)
        cursor.execute(sql, val)

        db.commit()
        
        cursor.close()
        db.close()
            
    except Exception as e:
        Log("Error while writing to database for state:"+name+" exception:")
        LogException(e)
        return False
    
def insertEvent(desc1, desc2, timestamp=None):
    try:
        db, cursor = Connect()
        
        if not timestamp: # if not defined, set time now
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        sql = "INSERT INTO events (time, desc1, desc2) VALUES (%s, %s, %s)"
        val = (timestamp, desc1, desc2)
        cursor.execute(sql, val)

        db.commit()
        cursor.close()
        db.close()
            
    except Exception as e:
        Log("Error while writing to database for events:"+desc1+" exception:")
        LogException(e)
        return False
    
    if cursor.rowcount>0:
        return True
    else:
        return False        
        
def getTxBuffer():
    try:
        db, cursor = Connect()
        
        res = cursor.callproc('getTxCommands')
        
        db.commit()
        for d in cursor.stored_results():
            data = d.fetchall()
        cursor.close()
        db.close()
            
    except Exception as e:
        Log("Error while writing to database for getTXbuffer, exception:")
        LogException(e)
        return []

    
    return data

def insertTxCommand(destination, data):
    try:
        db, cursor = Connect()
        
        sql = "INSERT INTO TXbuffer (destination, data) VALUES (%s, %s)"
        val = (destination, str(data))
        cursor.execute(sql, val)

        db.commit()
        cursor.close()
        db.close()
            
    except Exception as e:
        Log("Error while writing to database for insertTxCommand:"+destination+" exception:")
        LogException(e)
        return False

    return True
          
def LogException(e):
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    Log(str(e))
    Log(str(exc_type) +" : "+ str(fname) + " : " +str(exc_tb.tb_lineno))

def Log(strr):
    txt=str(strr)
    print("LOG:"+txt)
    from datetime import datetime
    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("logs/databaseMySQL.log","a") as file:
        file.write(dateStr+" >> "+txt+"\n")
        
                
if __name__=="__main__":
    print("run")