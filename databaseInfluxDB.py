#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from influxdb import InfluxDBClient
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
        Log("Error while writing to database for measurement")
         

def getValues(retentionPolicy, table, sensorName, timeFrom, timeTo):
    result = False

    client = InfluxDBClient(host='192.168.0.3', port=8086, username='inserter', password='inserter')

    client.switch_database('db1')

    _timeFrom = timeFrom.isoformat("T") + "Z"
    _timeTo = timeTo.isoformat("T") + "Z"

    queryString = 'SELECT "value" FROM "'+retentionPolicy+'"."'+table+'"'+" WHERE sensorName='"+ sensorName +"' and time >" + "'" +_timeFrom + "' and time < '"+_timeTo +"'"
    print(queryString)
    result = client.query(queryString)

    points = result.get_points()

    # for p in points:
    #     print(p)
    #     print(str(p['time']) + " -- " + str(p["value"]))

    return points

def insertValue(name,sensorName,value,one_day_RP=False):
    
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
        
        if one_day_RP:
            result = client.write_points(data,retention_policy="one_day")
        else:
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

        result = client.write_points(data,retention_policy="autogen")#infinite duration for events
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
        Log2("Error while writing to database for measurement")
          

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
    
