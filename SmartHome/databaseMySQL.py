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
from parameters import parameters
import traceback

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
        self.logger = Logger("databaseMySQL", verbosity=parameters.VERBOSITY)

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
        #for line in traceback.format_stack():
        #    print(line.strip())
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
    def getTotalSum(self, dateOfInvoicing):
        try:
            current_NT = self.getValues("consumption", "lowTariff", dateOfInvoicing, datetime.now(), True)[0]

            archive_NT =  self.getValues_archive("consumption", "lowTariff", dateOfInvoicing,
                                        datetime.now(), True)[0]
            current_VT = self.getValues("consumption", "stdTariff", dateOfInvoicing, datetime.now(), True)[0]
            archive_VT =  self.getValues_archive("consumption", "stdTariff", dateOfInvoicing,
                                        datetime.now(), True)[0]
            if current_VT is None:
                current_VT = 0
            if current_NT is None:
                current_NT = 0
            if archive_VT is None:
                archive_VT = 0
            if archive_NT is None:
                archive_NT = 0
        except Exception as e:
            self.logger.log(
                "Error calculating price from last invoicing:"+repr(e))
            return 0,0
        return current_NT+archive_NT, current_VT+archive_VT

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
            self.logger.log("Error while writing to database for AddOnlineDevice:"+ip+" exception:")
            self.logger.log_exception(e)
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
            self.logger.log("Error while writing to database for RemoveOnlineDevice, exception:")
            self.logger.log_exception(e)
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
            self.logger.log("Error while writing to database for updatePriceData name:"+str(name)+", exception:")
            self.logger.log_exception(e)
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
            self.logger.log("Error while writing to database for getPriceData, exception:")
            self.logger.log_exception(e)
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
            self.logger.log("Error while writing to database for measurement:"+sensorName+" exception:")
            self.logger.log_exception(e)
            return None


        return values

    @ThreadingLockDecorator
    def getValues_archive(self, kind, sensorName, timeFrom, timeTo, _sum=False):

        try:
            db, cursor = self.getConnection()

            if not _sum:
                select = 'SELECT value'
            else:
                select = 'SELECT SUM(value)'

            sql = select + " FROM measurements_archive WHERE source=%s AND time > %s AND time < %s"
            val = (sensorName, timeFrom, timeTo)
            cursor.execute(sql, val)

            result = cursor.fetchall()

            values = []
            for x in result:
                values.append(x[0])

            cursor.close()
            self.closeDBIfNeeded(db)

        except Exception as e:
            self.logger.log(
                "Error while writing to database for measurement:" + sensorName + " exception:")
            self.logger.log_exception(e)
            return None

        return values
    @ThreadingLockDecorator
    def insertValue(self, name, sensorName, value, timestamp=None, periodicity=0, writeNowDiff=1, onlyCurrent=False):
        start_timestamp = time.time()
        self.logger.log(f"MySQL - inserting value {name} for {sensorName}", _verbosity=self.logger.FULL)
        try:
            connection_timestamp = time.time()
            db, cursor = self.getConnection()

            if not timestamp:  # if not defined, set time now
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
            self.logger.log(f"Error while writing to database for measurement:{name} - {sensorName}, exception:")
            self.logger.log_exception(e)
            return False
        diff = time.time() - start_timestamp
        if diff > 1:
            self.logger.log(f"SLOW - MySQL - done inserting value {name} took {'%.2f s'%diff},"
                            f"without conn:{time.time() - connection_timestamp}",
                            _verbosity=self.logger.RICH)
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
            self.logger.log("Error while writing to database for insertCalculatedValue:" + name + " exception:")
            self.logger.log_exception(e)
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
            self.logger.log("Error while writing to database for insertDailyCons, exception:")
            self.logger.log_exception(e)
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
            self.logger.log("Error while writing to database for state:"+name+" exception:")
            self.logger.log_exception(e)
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
            self.logger.log("Error while writing to database for events:"+desc1+" exception:")
            self.logger.log_exception(e)
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
            self.logger.log("Error while writing to database for getTXbuffer, exception:")
            self.logger.log_exception(e)
            return []


        return data

    @ThreadingLockDecorator
    def insertTxCommand(self, destination, data):
        try:
            db, cursor = self.getConnection()

            sql = "INSERT INTO TXbuffer (destination, data, timestamp) VALUES (%s, %s, %s)"
            val = (destination, str(data), datetime.now())
            cursor.execute(sql, val)

            db.commit()
            cursor.close()
            self.closeDBIfNeeded(db)

        except Exception as e:
            self.logger.log("Error while writing to database for insertTxCommand:"+destination+" exception:")
            self.logger.log_exception(e)
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
            self.logger.log("Error while writing to database for getGlobalFlags:, exception:")
            self.logger.log_exception(e)
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
            self.logger.log("Error while writing to database for getCurrentValues:, exception:")
            self.logger.log_exception(e)
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
            self.logger.log("Error while writing to database for getStateValues:, exception:")
            self.logger.log_exception(e)
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
            self.logger.log("Error while writing to database for getOnlineDevices, exception:")
            self.logger.log_exception(e)
            return None

        return values       

    def update_day_solar_production(self):
        try:
            db, cursor = self.getConnection()

            sql = "select value from measurements where kind='consumption' and source='powerwallDaily' order by time desc limit 2;"
            cursor.execute(sql)

            data = cursor.fetchall()

            if data:
                today = data[0][0]
                last_day = data[1][0]

                self.insertCalculatedValue("production", "solar_today", today)
                self.insertCalculatedValue("production", "solar_last_day", last_day)

        except Exception as e:
            self.logger.log("Error while writing to database for update_day_solar_production, exception:")
            self.logger.log_exception(e)
            return None

        return

if __name__=="__main__":
    print("run")