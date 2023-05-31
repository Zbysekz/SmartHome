#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import mysql.connector
import time
import sys
import os
from datetime import datetime,timezone
import threading
import pathlib
from logger import Logger
from parameters import Parameters

logger = Logger("databaseMySQL", verbosity=Parameters.FULL)

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
            database="db1",
            connection_timeout=10
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
            logger.log("Error while writing to database for AddOnlineDevice:"+ip+" exception:")
            logger.log_exception(e)
            return False

        return True

    def RemoveOnlineDevices(self):
        self.RemoveOnlineDevice(ip=None)

    @ThreadingLockDecorator
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
            logger.log("Error while writing to database for RemoveOnlineDevice, exception:")
            logger.log_exception(e)
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
            logger.log("Error while writing to database for updatePriceData name:"+str(name)+", exception:")
            logger.log_exception(e)
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
            logger.log("Error while writing to database for getPriceData, exception:")
            logger.log_exception(e)
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
            logger.log("Error while writing to database for measurement:"+sensorName+" exception:")
            logger.log_exception(e)
            return None


        return values

    @ThreadingLockDecorator
    def insertValue(self,name, sensorName, value, timestamp=None, periodicity=0, writeNowDiff = 1, onlyCurrent=False):
        logger.log(f"MySQL - inserting value {name}", _verbosity=Parameters.FULL)
        try:
            db, cursor = self.getConnection()

            if not timestamp: # if not defined, set time now
                timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

            args = (timestamp, name, sensorName, value, periodicity, writeNowDiff)
            if onlyCurrent:
                res = cursor.callproc('insertMeasurement_onlyCurrent', args)
            else:
                res = cursor.callproc('insertMeasurement', args)

            db.commit()
            cursor.close()
            self.closeDBIfNeeded(db)

        except Exception as e:
            logger.log("Error while writing to database for measurement:"+name+" exception:")
            logger.log_exception(e)
            return False
        logger.log(f"MySQL - done inserting value {name}", _verbosity=Parameters.FULL)
        return True

    @ThreadingLockDecorator
    def insertCalculatedValue(self, kind, name, value):
        try:
            db, cursor = self.getConnection()

            args = (name, kind, value)
            res = cursor.callproc('insertCalculatedValue', args)

            db.commit()
            cursor.close()
            self.closeDBIfNeeded(db)

        except Exception as e:
            logger.log("Error while writing to database for insertCalculatedValue:" + name + " exception:")
            logger.log_exception(e)
            return False

        return True
    @ThreadingLockDecorator
    def insertDailySolarCons(self,value):
        try:
            db, cursor = self.getConnection()

            args = (value,)
            res = cursor.callproc('DailySolarCons', args)

            db.commit()
            cursor.close()
            self.closeDBIfNeeded(db)

        except Exception as e:
            logger.log("Error while writing to database for insertDailyCons, exception:")
            logger.log_exception(e)
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
            logger.log("Error while writing to database for state:"+name+" exception:")
            logger.log_exception(e)
            return False

    @ThreadingLockDecorator
    def insertEvent(self, desc1, desc2, timestamp=None):
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
            logger.log("Error while writing to database for events:"+desc1+" exception:")
            logger.log_exception(e)
            return False

        if cursor.rowcount > 0:
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
            logger.log("Error while writing to database for getTXbuffer, exception:")
            logger.log_exception(e)
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
            logger.log("Error while writing to database for insertTxCommand:"+destination+" exception:")
            logger.log_exception(e)
            return False

        return True

    @ThreadingLockDecorator
    def getGlobalFlags(self):
        try:
            db, cursor = self.getConnection()

            sql = "SELECT name, value FROM globalFlags"
            cursor.execute(sql)

            data = cursor.fetchall()

            result = {}
            for d in data:
                result[d[0]] = d[1]


        except Exception as e:
            logger.log("Error while writing to database for getGlobalFlags:, exception:")
            logger.log_exception(e)
            return None
        return result

    @ThreadingLockDecorator
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
            logger.log("Error while writing to database for getCurrentValues:, exception:")
            logger.log_exception(e)
            return None
        return result

    @ThreadingLockDecorator
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
            logger.log("Error while writing to database for getStateValues:, exception:")
            logger.log_exception(e)
            return None
        return result

    @ThreadingLockDecorator
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
            logger.log("Error while writing to database for getOnlineDevices, exception:")
            logger.log_exception(e)
            return None

        return values       
                
if __name__=="__main__":
    print("run")