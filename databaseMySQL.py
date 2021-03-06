#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import mysql.connector
import time
import sys
import os
from datetime import datetime,timezone
import threading
import pathlib

thisScriptPath = str(pathlib.Path(__file__).parent.absolute())


def ThreadingLockDecorator(func):
    def wrapper(*args, **kwargs):
        #cMySQL.mySQLLock.acquire()
        ret = func(*args, **kwargs)
        #cMySQL.mySQLLock.release()
        return ret

    return wrapper

class cMySQL:
    mySQLLock = threading.Lock()

    def __init__(self):
        self._persistentConnection = False
        self.databaseCon = None

    def getConnection(self):
        if self._persistentConnection:
            return self.databaseCon, self.databaseCon.cursor()
        else:
            db = self.init_db()
            return db, db.cursor()

    def PersistentConnect(self):

        self._persistentConnection = True
        self.databaseCon = self.init_db()

    def PersistentDisconnect(self):
        self._persistentConnection = False
        self.databaseCon.close()

    def init_db(self):
        return mysql.connector.connect(
            host="localhost",
            user="mainScript",
            password="mainScript",
            database="db1"
        )

    def closeDBIfNeeded(self, conn):
        if not self._persistentConnection:
            conn.close()

    @ThreadingLockDecorator
    def getTotalSum(self):

        points_low=self.getValues("consumption","lowTariff",datetime(2000,1,1,0,0),datetime.now(),True)
        points_std=self.getValues("consumption","stdTariff",datetime(2000,1,1,0,0),datetime.now(),True)


        return points_low[0], points_std[0]

    @ThreadingLockDecorator
    def AddOnlineDevice(self, ip):
        try:
            db, cursor = self.getConnection()

            sql = "UPDATE onlineDevices SET online=1,stateChangeTime=UTC_TIMESTAMP() WHERE ip=%s"
            val = (ip,)
            cursor.execute(sql, val)

            db.commit()
            cursor.close()
            self.closeDBIfNeeded(db)

        except Exception as e:
            Log("Error while writing to database for AddOnlineDevice:"+ip+" exception:")
            LogException(e)
            return False

        return True

    @ThreadingLockDecorator
    def RemoveOnlineDevices(self):
        self.RemoveOnlineDevice(ip=None)

    def RemoveOnlineDevice(self, ip):
        try:
            db, cursor = self.getConnection()

            if ip is None: # delete all
                sql = "UPDATE onlineDevices SET online=0,stateChangeTime=UTC_TIMESTAMP()"
                cursor.execute(sql)
            else:
                sql = "UPDATE onlineDevices SET online=0,stateChangeTime=UTC_TIMESTAMP() WHERE ip=%s"
                val = (ip,)
                cursor.execute(sql, val)

            db.commit()
            cursor.close()
            self.closeDBIfNeeded(db)

        except Exception as e:
            Log("Error while writing to database for RemoveOnlineDevice, exception:")
            LogException(e)
            return False

        return True

    @ThreadingLockDecorator
    def updatePriceData(self, name, value):
        try:
            db, cursor = self.getConnection()

            sql = "UPDATE prices SET value=%s WHERE name=%s"
            val = (value,name)
            cursor.execute(sql, val)

            db.commit()

            cursor.close()
            self.closeDBIfNeeded(db)


        except Exception as e:
            Log("Error while writing to database for updatePriceData name:"+str(name)+", exception:")
            LogException(e)
            return False

        return True

    @ThreadingLockDecorator
    def getPriceData(self):
        try:
            db, cursor = self.getConnection()

            sql = "SELECT name, value FROM prices"
            cursor.execute(sql)

            data = cursor.fetchall()

            values = {}
            for d in data:
                values[d[0]] = d[1]

            cursor.close()
            self.closeDBIfNeeded(db)

        except Exception as e:
            Log("Error while writing to database for getPriceData, exception:")
            LogException(e)
            return None

        return values


    @ThreadingLockDecorator
    def getValues(self,kind, sensorName, timeFrom, timeTo, _sum = False):

        try:
            db, cursor = self.getConnection()


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

            cursor.close()
            self.closeDBIfNeeded(db)

        except Exception as e:
            Log("Error while writing to database for measurement:"+sensorName+" exception:")
            LogException(e)
            return None


        return values

    @ThreadingLockDecorator
    def insertValue(self,name, sensorName, value, timestamp=None, periodicity=0, writeNowDiff = 1):
        try:
            db, cursor = self.getConnection()

            if not timestamp: # if not defined, set time now
                timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

            args = (timestamp, name, sensorName, value, periodicity, writeNowDiff)
            res = cursor.callproc('insertMeasurement',args)

            db.commit()
            cursor.close()
            self.closeDBIfNeeded(db)

        except Exception as e:
            Log("Error while writing to database for measurement:"+name+" exception:")
            LogException(e)
            return False

        return True

    @ThreadingLockDecorator
    def insertDailySolarCons(self,value):
        try:
            db, cursor = self.getConnection()

            args = (value,)
            res = cursor.callproc('DailySolarCons',args)

            db.commit()
            cursor.close()
            self.closeDBIfNeeded(db)

        except Exception as e:
            Log("Error while writing to database for insertDailyCons, exception:")
            LogException(e)
            return False

        return True

    @ThreadingLockDecorator
    def updateState(self,name, value):
        try:
            db, cursor = self.getConnection()

            sql = "UPDATE state SET "+str(name)+"=%s"
            val = (value,)
            cursor.execute(sql, val)

            db.commit()

            cursor.close()
            self.closeDBIfNeeded(db)

        except Exception as e:
            Log("Error while writing to database for state:"+name+" exception:")
            LogException(e)
            return False

    @ThreadingLockDecorator
    def insertEvent(self,desc1, desc2, timestamp=None):
        try:
            db, cursor = self.getConnection()

            if not timestamp: # if not defined, set time now
                timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

            sql = "INSERT INTO events (time, desc1, desc2) VALUES (%s, %s, %s)"
            val = (timestamp, desc1, desc2)
            cursor.execute(sql, val)

            db.commit()
            cursor.close()
            self.closeDBIfNeeded(db)

        except Exception as e:
            Log("Error while writing to database for events:"+desc1+" exception:")
            LogException(e)
            return False

        if cursor.rowcount>0:
            return True
        else:
            return False

    @ThreadingLockDecorator
    def getTxBuffer(self):
        try:
            db, cursor = self.getConnection()

            res = cursor.callproc('getTxCommands')

            db.commit()
            for d in cursor.stored_results():
                data = d.fetchall()
            cursor.close()
            self.closeDBIfNeeded(db)

        except Exception as e:
            Log("Error while writing to database for getTXbuffer, exception:")
            LogException(e)
            return []


        return data

    @ThreadingLockDecorator
    def insertTxCommand(self, destination, data):
        try:
            db, cursor = self.getConnection()

            sql = "INSERT INTO TXbuffer (destination, data) VALUES (%s, %s)"
            val = (destination, str(data))
            cursor.execute(sql, val)

            db.commit()
            cursor.close()
            self.closeDBIfNeeded(db)

        except Exception as e:
            Log("Error while writing to database for insertTxCommand:"+destination+" exception:")
            LogException(e)
            return False

        return True

    def getCurrentValues(self):
        try:
            db, cursor = self.getConnection()

            sql = "SELECT name, value FROM currentMeasurements"
            cursor.execute(sql)

            data = cursor.fetchall()

            result = {}
            for d in data:
                result[d[0]] = d[1]


        except Exception as e:
            Log("Error while writing to database for getCurrentValues:, exception:")
            LogException(e)
            return None
        return result

    def getStateValues(self):
        try:
            db, cursor = self.getConnection()

            sql = "SELECT locked, alarm, phoneCommState, phoneSignalInfo, ventilationCommand FROM state"
            cursor.execute(sql)

            data = cursor.fetchone()

            result = {}

            result['locked'] = data[0]
            result['alarm'] = data[1]
            result['phoneCommState'] = data[2]
            result['phoneSignalInfo'] = data[3]
            result['ventilationCommand'] = data[4]

        except Exception as e:
            Log("Error while writing to database for getStateValues:, exception:")
            LogException(e)
            return None
        return result

    def getOnlineDevices(self):
        try:
            db, cursor = self.getConnection()

            sql = "SELECT name,online FROM onlineDevices"
            cursor.execute(sql)

            data = cursor.fetchall()

            values = {}
            for d in data:
                values[d[0]] = d[1]

        except Exception as e:
            Log("Error while writing to database for getOnlineDevices, exception:")
            LogException(e)
            return None

        return values

def LogException(e):
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    Log(str(e))
    Log(str(exc_type) +" : "+ str(fname) + " : " +str(exc_tb.tb_lineno))

def Log(strr):
    txt=str(strr)
    print("LOG:"+txt)
    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(thisScriptPath+"/logs/databaseMySQL.log","a") as file:
        file.write(dateStr+" >> "+txt+"\n")
        
                
if __name__=="__main__":
    print("run")