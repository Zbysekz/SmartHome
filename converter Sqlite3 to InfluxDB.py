#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import databaseInfluxDB
import json
import sys
import datetime

connection=0
curs=0

##
##print ("\nDatabase entries for the garage:\n")
##for row in curs.execute("SELECT * FROM m_key_t WHERE zone='garage'"):
##    print (row)


def insertValue(table,value):
    conn=sqlite3.connect('/home/pi/main.db')

    curs=conn.cursor()
    done = False
    while(not done):
        try:
            curs.execute("INSERT INTO "+table+" values (datetime('now','localtime'),(?))",(value,))
            conn.commit()
            done=True
        except sqlite3.OperationalError:
            Log("Cannot write to database.. trying again")
            Log("For query: INSERT,"+table+", value"+str(value))
            

def getLastData(tableName,count):

    global connection,curs
    
    connection=sqlite3.connect('/home/pi/mainExtract.db')
    curs=connection.cursor()
    
    curs.execute("SELECT time,value,min,max FROM {} order by time desc limit ?;".format(tableName),(count,))
    
    return curs.fetchall()

def deleteLastData(tableName,count):

    global connection,curs
    
    connection=sqlite3.connect('/home/pi/mainExtract.db')
    curs=connection.cursor()
    
    curs.execute("DELETE FROM {} ORDER BY time desc limit ?;".format(tableName),(count,))
    
    return curs.fetchall()

def Log(str):
    print("LOGGED:"+str)
    from datetime import datetime
    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("logs/converter.log","a") as file:
        file.write(dateStr+" >> "+str+"\n")

if __name__ == "__main__":

    tableName = "m_key_t"

    print ("Starting conversion")
    data = getLastData(tableName,10)

    print("Data are read")
    i=0
    for x in x:
        print("inserting:"+str(i))
        i+=1
        databaseInfluxDB.insertValue("temperatures","keyboard",value)

    print("deleting")
    deleteLastData(tableName,10)

    print("COMPLETED!")
    
