#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from influxdb import InfluxDBClient
import sqlite3

def insertValue(name,sensorName,value):
    client = InfluxDBClient(host='localhost', port=8086, username='inserter', password='inserter')

    client.switch_database('db1')

    timeNow = datetime.utcnow().isoformat("T") + "Z"

    data = [
    {
        "measurement": name,
        "tags": {
            "sensorName": sensorName
        },
        "time": timeNow,
        "fields": {
            "value": value
        }
    }
    ]

    result = client.write_points(data)

    if(not result):
        Log("Error while writing to database for measurement:"+name)
            
def insertEvent(desc1,desc2):

    client = InfluxDBClient(host='localhost', port=8086, username='inserter', password='inserter')

    client.switch_database('db1')

    timeNow = datetime.utcnow().isoformat("T") + "Z"

    data = [
    {
        "measurement": events,
        "tags": {
            "desc1": desc1,
            "desc2": desc2,
        },
        "time": timeNow,
        "fields": {
            "value": 0
        }
    }
    ]

    result = client.write_points(data)

    if(not result):
        Log("Error while writing to database for events:"+name)
    
def updateState(alarm,locked):
    conn=sqlite3.connect('/home/pi/main.db')

    curs=conn.cursor()
    
    if alarm:
        alarm_=1
    else:
        alarm_=0
    if locked:
        locked_=1
    else:
        locked_=0
        
    done = False
    while(not done):
        try:
            curs.execute("UPDATE state SET locked = (?), alarm = (?);",(locked_,alarm_))
            conn.commit()
            done=True
        except sqlite3.OperationalError:
            Log("Cannot write to database.. trying again")
            Log("For query: UPDATE, state, locked:"+str(locked_)+", alarm:"+str(alarm_))
            

def Log(str):
    print("LOGGED:"+str)
    from datetime import datetime
    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("logs/database.log","a") as file:
        file.write(dateStr+" >> "+str+"\n")
