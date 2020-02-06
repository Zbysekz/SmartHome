# ceník ČEZ tarif D57d
# https://www.cez.cz/edee/content/file/produkty-a-sluzby/obcane-a-domacnosti/elektrina-2019/moo/web_cenik_elektrina_dobu_neurcitou_moo_20199_cezdi.pdf

import databaseInfluxDB
from datetime import datetime, timedelta

def yearPrice(consHighTariff_wh = 0,consLowTariff_wh = 0, numPhases = 3, amperage = 25):

    A = [0]*40

    A[1] = 2116.29
    A[2] = 2116.29
    A[3] = 95.59
    A[4] = 228.19
    A[5] = 204.99

    A[9] = 352.11 #3x25A

    A[21] = 34.24
    A[22] = 92.19
    A[23] = 8.39
    A[24] = 16.41
    A[25] = 598.95
    A[26] = 2470.92
    A[27] = 2447.71
    A[28] = A[3] + A[9] + A[23]
    A[29] = A[24]*numPhases*amperage
    A[30] = 598.95


    year_sum = (consHighTariff_wh/1000000)*A[26]+\
               (consLowTariff_wh/1000000)*A[27]+\
               (12*A[28])+\
               min(12*A[29],(consHighTariff_wh/1000000+consLowTariff_wh/1000000)*A[30])

    return year_sum


#current percentage of month conumption to monthly cash advance (100% means match, 50% means sparing,using only half)
def monthPercent(consHighTariff_wh = 0, consLowTariff_wh = 0, monthlyCashAdvance=0):

    yPrice = yearPrice(consHighTariff_wh*12, consLowTariff_wh*12)
    diff = ((yPrice/12) / monthlyCashAdvance)*100
    return diff

def findYearConsForCashAdvance(monthlyCashAdvance):

    timeoutIter = 0
    powerHighTariff_wh = 0
    powerLowTariff_wh = 0
    
    price = yearPrice(powerHighTariff_wh, powerLowTariff_wh)/12
    #print("FFF"+str(price))
    if price > monthlyCashAdvance:
        return powerHighTariff_wh, powerLowTariff_wh# lowest possible
    
    while(not (price>monthlyCashAdvance-1 and price<monthlyCashAdvance+1)):
        price = yearPrice(powerHighTariff_wh, powerLowTariff_wh)/12

        if price < monthlyCashAdvance:
            powerLowTariff_wh += abs(price-monthlyCashAdvance)*1000
        else:
            powerLowTariff_wh -= 1
        #print(price)
            
        timeoutIter+=1
        
        if timeoutIter>300:
            print("Calculation timeout!")
            break
            powerHighTariff_wh=0
            powerLowTariff_wh=0

    return powerHighTariff_wh, powerLowTariff_wh
    

def test():
    powerHighTariff_wh = 0
    powerLowTariff_wh = 1 #572kWh/m
    cashAdvance = 2200



    yearCons = findYearConsForCashAdvance(cashAdvance)[1]

    print("Roční spotřeba pro zálohu "+str(cashAdvance)+"Kč je {:d}".format(int(yearCons/1000))+" kWh")


    percMonth = monthPercent(powerHighTariff_wh, powerLowTariff_wh, cashAdvance)

    print("Měsíční náklady: "+str(int(percMonth))+" %")
    print("Úspora:"+str(int((1-percMonth*0.01)*cashAdvance))+"Kč")

def getSum(points):
    sum = 0
    for p in points:
        sum += int(p["value"])
    return sum
        
def CalculateConsPrices():
    
    cashAdvance = 2200
    
    stdPoints = databaseInfluxDB.getValues("two_months","consumption","stdTariff",datetime.now() - timedelta(days=30),datetime.now())
    stdSum_wh=getSum(stdPoints)
        
    print(stdSum_wh)
    
    lowPoints = databaseInfluxDB.getValues("two_months","consumption","lowTariff",datetime.now() - timedelta(days=30),datetime.now())
    lowSum_wh=getSum(lowPoints)
    
    yearCons = findYearConsForCashAdvance(cashAdvance)[1]

    print("Roční spotřeba pro zálohu "+str(cashAdvance)+"Kč je {:d}".format(int(yearCons/1000))+" kWh")

    percMonth = monthPercent(stdSum_wh, lowSum_wh, cashAdvance)
    print("Plnění za poslední měsíc:"+str(int(percMonth))+" %")


    if datetime.now().month>5:
        year = datetime.now().year
    else:
        year = datetime.now().year - 1
        
    stdPoints = databaseInfluxDB.getValues("autogen","hist_consumption","stdTariff",datetime(year,5,31,23,59), datetime.now())
    stdSum_wh=getSum(stdPoints)
        
    print(stdSum_wh)
    
    lowPoints = databaseInfluxDB.getValues("autogen","hist_consumption","lowTariff",datetime(year,5,31,23,59),datetime.now())
    lowSum_wh=getSum(lowPoints)
    
    print(lowSum_wh)
    
    
    percHeatingSeason = (int)(((stdSum_wh + lowSum_wh) / yearCons)*100)
    
    print("Plnění topné sezóny:"+str(percHeatingSeason)+"%")

CalculateConsPrices()
#print(int(yearPrice(powerHighTariff_wh, yearCons)/12))

#import numpy as np
#import matplotlib.pyplot as plt

#x = np.arange(0, 5, 0.1);
#y = np.sin(x)
#plt.plot(x, y)
