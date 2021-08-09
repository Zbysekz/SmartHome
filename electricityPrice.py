#!usr/bin/python3

# ceník ČEZ tarif D57d
# https://www.cez.cz/edee/content/file/produkty-a-sluzby/obcane-a-domacnosti/elektrina-2019/moo/web_cenik_elektrina_dobu_neurcitou_moo_20199_cezdi.pdf

# A = [0]*40
#
# A[1] = 2116.29
# A[2] = 2116.29
# A[3] = 95.59
# A[4] = 228.19
# A[5] = 204.99
#
# A[9] = 352.11 #3x25A
#
# A[21] = 34.24
# A[22] = 92.19
# A[23] = 8.39
# A[24] = 16.41
# A[25] = 598.95
# A[26] = 2470.92
# A[27] = 2447.71
# A[28] = A[3] + A[9] + A[23]
# A[29] = A[24]*numPhases*amperage
# A[30] = 598.95
#


import json
from databaseMySQL import cMySQL
from datetime import datetime,timedelta

printDebug = True

MySQL = cMySQL()

def yearPrice(consHighTariff_wh = 0,consLowTariff_wh = 0, numPhases = 3, amperage = 25):


# zelený tarif D57d
#https://www.cez.cz/edee/content/file/produkty-a-sluzby/obcane-a-domacnosti/elektrina-2020/moo/web-cenik_ele-zelena_elektrina_moo_202001_cezdi.pdf
    A = [0] * 40

    A[1] = 2152.59
    A[2] = 2152.59
    A[3] = 95.59
    A[4] = 265.66
    A[5] = 227.33

    A[9] = 356.95  # 3x25A

    A[21] = 34.24
    A[22] = 93.32
    A[23] = 6.15
    A[24] = 16.06
    A[25] = 598.95
    A[26] = 2545.80
    A[27] = 2507.48
    A[28] = A[3] + A[9] + A[23]
    A[29] = A[24] * numPhases * amperage
    A[30] = 598.95


    year_sum = (consHighTariff_wh/1000000)*A[26]+\
               (consLowTariff_wh/1000000)*A[27]+\
               (12*A[28])+\
               min(12*A[29],(consHighTariff_wh/1000000+consLowTariff_wh/1000000)*A[30])

    return year_sum


#current percentage to monthly cash advance (100% means match, 50% means sparing,using only half)
def percent(consHighTariff_wh = 0, consLowTariff_wh = 0, monthlyCashAdvance=0):

    yPrice = yearPrice(consHighTariff_wh, consLowTariff_wh)
    Log("Roční cena:"+str(yPrice)+" Kč")
    diff = ((yPrice/12) / monthlyCashAdvance)*100
    return round(diff,1)

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
    

def getConsSumLastDay():
    consLow = MySQL.getValues('consumption','lowTariff',datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)-timedelta(1),datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),_sum=True)
    consStd = MySQL.getValues('consumption','stdTariff',datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)-timedelta(1),datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),_sum=True)
    
    
    consLow = 0 if consLow[0] is None else consLow[0]
    consStd = 0 if consStd[0] is None else consStd[0]
    
    
    return [consLow,consStd]
    

# cena za minulý den
# cena za poslední měsíc
# plnění od posledního vyúčtování (procenta, Wh na oba tarify)
# TODO? možnost vynulovat tlačítkem vyúčtováním

def run():
    
    monthlyCashAdvance = 2960
    
    yearCons = findYearConsForCashAdvance(monthlyCashAdvance)
    price_kWh = monthlyCashAdvance*12/(yearCons[1]/1000)
    
    Log("Cena kWh:"+str(price_kWh)+" Kč")
    
    
    lastDay_low_Wh,lastDay_std_Wh = getConsSumLastDay();
    
    Log("Spotřeba za včerejší den:"+str(int(lastDay_low_Wh))+" Wh "+str(int(lastDay_std_Wh))+" Wh")

    totalSum_low,totalSum_std = MySQL.getTotalSum()
    
    priceData = MySQL.getPriceData()
 
    
    totalSum_low = totalSum_low - priceData['totalSumBias_low']#abychom ziskali roční spotřebu - od posledního vyúčtování
    totalSum_std = totalSum_std - priceData['totalSumBias_std']
    
    Log("Roční suma nízký tarif: "+str(int(totalSum_low))+" Wh ; Vysoký tarif:"+str(int(totalSum_std))+" Wh")

    yearPerc = percent(totalSum_std, totalSum_low, monthlyCashAdvance)
    Log("Roční plnění:"+str(yearPerc)+"%")

    #-----------------------


    priceLastDay = price_kWh*(lastDay_std_Wh+lastDay_low_Wh)/1000
    Log("Cena  za včerejší den:" +str(int(priceLastDay)) + " Kč")

    MySQL.updatePriceData("priceLastDay", priceLastDay)
    MySQL.updatePriceData("yearPerc", yearPerc)
    


def Log(msg):
    if printDebug:
        print(msg)    
#yearPrice(powerHighTariff_wh, findYearConsForCashAdvance(2200)[1]) / 12
if __name__ == "__main__":

    run();
    