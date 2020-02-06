#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from influxdb import InfluxDBClient
from datetime import datetime


def getValues(table, sensorName, timeFrom, timeTo):
    result = False

    client = InfluxDBClient(host='192.168.0.3', port=8086, username='inserter', password='inserter')

    client.switch_database('db1')

    _timeFrom = timeFrom.isoformat("T") + "Z"
    _timeTo = timeTo.isoformat("T") + "Z"

    queryString = 'SELECT "value" FROM "two_months"."'+table+'" WHERE time >' + "'" +_timeFrom + "' and time < '"+_timeTo +"'"
    print(queryString)
    result = client.query(queryString)

    points = result.get_points()

    # for p in points:
    #     print(p)
    #     print(str(p['time']) + " -- " + str(p["value"]))

    return points


def insertValue(name, sensorName, value, time = datetime.utcnow().isoformat("T") + "Z"):
    client = InfluxDBClient(host='192.168.0.3', port=8086, username='inserter', password='inserter')

    client.switch_database('db1')

    data = [
        {
            "measurement": name,
            "tags": {
                "sensorName": sensorName
            },
            "time": time,
            "fields": {
                "value": value
            }
        }
    ]


    result = client.write_points(data)



def run():
    points = getValues("consumption","stdTariff",datetime(2019,12,8,19,30),datetime(2019,12,19,18,30))

    it = 0

    #insertValue("consumption","lowTariff",1.0,"2019-12-19T14:00:54.453089024Z")

    print("adds")
    for p in points:
         print(it)
         it+=1
         print(insertValue("consumption","lowTariff",float(p["value"]),p["time"]))


    print("AA")

