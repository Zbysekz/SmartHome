#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3

##
##print ("\nDatabase entries for the garage:\n")
##for row in curs.execute("SELECT * FROM m_key_t WHERE zone='garage'"):
##    print (row)

##
##def insertValue(table,value):
##    conn=sqlite3.connect('/home/pi/main.db')
##
##    curs=conn.cursor()
##    done = False
##    while(not done):
##        try:
##            curs.execute("INSERT INTO "+table+" values (datetime('now','localtime'),(?))",(value,))
##            conn.commit()
##            done=True
##        except sqlite3.OperationalError:
##            Log("Cannot write to database.. trying again")
##            Log("For query: INSERT,"+table+", value"+str(value))
##            
##def insertEvent(id1,id2):
##    conn=sqlite3.connect('/home/pi/main.db')
##
##    curs=conn.cursor()
##
##    done = False
##    while(not done):
##        try:
##            curs.execute("INSERT INTO events values (datetime('now','localtime'),(?),(?))",(id1,id2))
##            conn.commit()
##            done=True
##        except sqlite3.OperationalError:
##                Log("Cannot write to database.. trying again")
##                Log("For query: INSERT, events, id1:"+str(id1)+", id2:"+str(id1))
##    
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
            
def getTXbuffer():
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

def Log(str):
    print("LOGGED:"+str)
    from datetime import datetime
    dateStr=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("logs/database.log","a") as file:
        file.write(dateStr+" >> "+str+"\n")
