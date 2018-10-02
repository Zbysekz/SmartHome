#!/usr/bin/python3
from tkinter import *
import sqlite3

def buttonCallback():
       
    conn=sqlite3.connect('/home/pi/main.db')

    curs=conn.cursor()
    
    data = e[0].get()
    for i in range(1,int(LEN.get())):
        data+=","+e[i].get();
    print(data)
    
    try:
        curs.execute("INSERT into TXbuffer values ((?),(?));",(DEST.get(),data))
        conn.commit()
    except sqlite3.OperationalError:
        print("Cannot write to database..")

top = Tk()
top.title('Terminal')
top.geometry("400x100")

B = Button(top,text="OK",command = buttonCallback)
B.place(x=50,y=45)


DEST = Entry(top)
DEST.place(x=0,y=10,width=80)
DEST.insert(0,"192.168.0.1")

LEN = Entry(top)
LEN.place(x=100,y=10,width=30)
LEN.insert(0,"1")

offsetX = 100
E1 = Entry(top)
E1.place(x=offsetX+0,y=50,width=30)
E2 = Entry(top)
E2.place(x=offsetX+30,y=50,width=30)
E3 = Entry(top)
E3.place(x=offsetX+60,y=50,width=30)
E4 = Entry(top)
E4.place(x=offsetX+90,y=50,width=30)
E5 = Entry(top)
E5.place(x=offsetX+120,y=50,width=30)
E6 = Entry(top)
E6.place(x=offsetX+150,y=50,width=30)
E7 = Entry(top)
E7.place(x=offsetX+180,y=50,width=30)
E8 = Entry(top)
E8.place(x=offsetX+210,y=50,width=30)

e = []
e.append(E1)
e.append(E2)
e.append(E3)
e.append(E4)
e.append(E5)
e.append(E6)
e.append(E7)
e.append(E8)


top.mainloop()

