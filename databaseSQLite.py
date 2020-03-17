#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
            
def updateValue(name, value):
    conn=sqlite3.connect('/home/pi/main.db')

    curs=conn.cursor()
    maxTries=10
    done = False
    while(not done and maxTries>0):
        try:
            curs.execute("UPDATE state SET {} = (?);".format(name),(value,))
            conn.commit()
            done=True
        except sqlite3.OperationalError as e:
            maxTries-=1
            Log("Exception:"+str(e))
            Log("For query: UPDATE value, name:"+str(name)+", value:"+str(value))
            
def getTXbuffer():
    data = []
    conn=sqlite3.connect('/home/pi/main.db')

    curs=conn.cursor()
    
    try:
        curs.execute("SELECT data,destination FROM TXbuffer;")# where destination = '"+destination+"';")
        conn.commit()
        
        data = curs.fetchall()
    except sqlite3.OperationalError:
        Log("Cannot read from database!")
        Log("SELECT data,destination FROM TXbuffer;")
        
    #now remove from database
    try:
        curs.execute("DELETE FROM TXbuffer;")# where destination = '"+destination+"';")
        conn.commit()
        
    except sqlite3.OperationalError:
        Log("Cannot delete from table TXbuffer!")

    return data


def getCmds():
    data = []
    conn = sqlite3.connect('/home/pi/main.db')

    curs = conn.cursor()

    try:
        curs.execute("SELECT updated,ventilationCmd,heatingInhibit FROM cmd;")
        conn.commit()

        data = curs.fetchall()
    except sqlite3.OperationalError:
        Log("Cannot read from database!")
        Log("SELECT data,destination FROM cmd;")

    # now reset update flag from database
    try:
        curs.execute("UPDATE cmd SET updated=0")
        conn.commit()

    except sqlite3.OperationalError:
        Log("Cannot reset update flag from table cmd!")

    if len(data) > 0 and len(data[0]) > 0 and data[0][0] != 0:  # update flag is true
        return data[0][1:]
    else:
        return None

def Log(str):
    print("LOGGED:"+str)
    from datetime import datetime
    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("logs/database.log","a") as file:
        file.write(dateStr+" >> "+str+"\n")
