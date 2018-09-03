#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from influxdb import InfluxDBClient
import sqlite3
from datetime import datetime



def test():
    
    result = False
    try:
        client = InfluxDBClient(host='localhost', port=8086, username='inserter', password='inserter')

        client.switch_database('db1')

        timeNow = datetime.utcnow().isoformat("T") + "Z"

        data = [{
            'name': 'events',
            'columns': ['tags', 'text', 'title'],
            'points': [['nejaky tag', 'text text', 'titulek']]
        }]
        
        result = client.write_points(data)
    except Exception as e:
        Log("Error while writing to database for measurement exception:")
        Log(type(e))    # the exception instance
        Log(e.args)     # arguments stored in .args
        Log(e)
        result = True
        
    if(not result):
        Log("Error while writing to database for measurement:"+name)
         


def insertValue(name,sensorName,value):
    
    result = False
    try:
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
    except Exception as e:
        Log("Error while writing to database for measurement:"+name+" exception:")
        Log(type(e))    # the exception instance
        Log(e.args)     # arguments stored in .args
        Log(e)
        result = True
        
    if(not result):
        Log("Error while writing to database for measurement:"+name)
            
def insertEvent(desc1,desc2):
    
    result = False
    try:
        
        client = InfluxDBClient(host='localhost', port=8086, username='inserter', password='inserter')

        client.switch_database('db1')

        timeNow = datetime.utcnow().isoformat("T") + "Z"

        data = [
        {
            "measurement": "events",
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
    except Exception as e:
        Log("Error while writing to database for events, exception:")
        Log(type(e))    # the exception instance
        Log(e.args)     # arguments stored in .args
        Log(e)
        result = True
        
    if(not result):
        Log("Error while writing to database for events")

def insertHardwareMonitoringValue(CPUtemp,CPUusage,memoryUsage,memoryRelUsage,diskUsage,diskRelUsage):
    
    result = False
    try:
        client = InfluxDBClient(host='localhost', port=8086, username='inserter', password='inserter')

        client.switch_database('db2')

        timeNow = datetime.utcnow().isoformat("T") + "Z"

        data = [
        {
            "measurement": "hardwareMonitoring",
            "time": timeNow,
            "fields": {
                "CPUtemp": CPUtemp,
                "CPUusage" : CPUusage,
                "memoryUsage" : memoryUsage,
                "memoryRelUsage" : memoryRelUsage,
                "diskUsage" : diskUsage,
                "diskRelUsage" : diskRelUsage
            }
        }
        ]
        
        result = client.write_points(data)
    except Exception as e:
        Log2("Error while writing to database for hardware monitoring exception:")
        Log2(type(e))    # the exception instance
        Log2(e.args)     # arguments stored in .args
        Log2(e)
        result = True
        
    if(not result):
        Log2("Error while writing to database for measurement:"+name)
          

def Log(strr):
    txt=str(strr)
    print("LOGGED:"+txt)
    from datetime import datetime
    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("logs/databaseInfluxDB.log","a") as file:
        file.write(dateStr+" >> "+txt+"\n")
def Log2(strr):#special Log function for hardware monitoring (separate thread)
    txt=str(strr)
    print("LOGGED:"+txt)
    from datetime import datetime
    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("/home/pi/scripts/logs/databaseInfluxDB_hardwareMonitoring.log","a") as file:
        file.write(dateStr+" >> "+txt+"\n")
                
if __name__=="__main__":
    print("run")
    insertValue("temperature","keyboard",24.0)