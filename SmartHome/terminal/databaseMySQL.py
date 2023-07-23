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
            host="192.168.0.3",
            user="mainScript",
            password="mainScript",
            database="db1",
            connection_timeout=10
        )

    def closeDBIfNeeded(self, conn):
        if not self._persistentConnection:
            conn.close()

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
            print("Error while writing to database for insertTxCommand:"+destination+" exception:")
            print(repr(e))
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