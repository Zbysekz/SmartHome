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

# co platil do roku 2023
# zelený tarif D57d
# https://www.cez.cz/edee/content/file/produkty-a-sluzby/obcane-a-domacnosti/elektrina-2021/moo/web_new-cenik_ele-zelena_elektrina_moo_102021_cezdi.pdf
# účinnost od 31. 12. 2021
# A = [0] * 40
#
# A[1] = 3513.84
# A[2] = 3513.84
# A[3] = 107.69
# A[4] = 254.06
# A[5] = 156.66
#
# A[9] = 377.52  # 3x25A
#
# A[21] = 34.24
# A[22] = 112.89
# A[23] = 4.73
# A[24] = 18.23
# A[25] = 598.95
# A[26] = 3915.04
# A[27] = 3817.63
# A[28] = A[3] + A[9] + A[23]
# A[29] = A[24] * numPhases * amperage
# A[30] = 598.95
# year_sum = (consHighTariff_wh / 1000000) * A[26] + \
#            (consLowTariff_wh / 1000000) * A[27] + \
#            (12 * A[28]) + \
#            min(12 * A[29], (consHighTariff_wh / 1000000 + consLowTariff_wh / 1000000) * A[30])

#


import json
from databaseMySQL import cMySQL
from datetime import datetime,timedelta

printDebug = True

MySQL = cMySQL()

# zelený tarif D57d
# EON - fix na 1 rok - 1.12.2023-1.12.2024
A = [0] * 40

A[9] = 413  # 3x25A

A[25] = 5283.95
A[26] = 4874.86

monthly = 120.0 + A[9] + 4.15
POZE = 0.0

def yearPrice(consHighTariff_wh = 0,consLowTariff_wh = 0, numPhases = 3, amperage = 25):

    year_sum = (consHighTariff_wh/1000000)*A[25]+\
               (consLowTariff_wh/1000000)*A[26]+\
               (12*monthly)+POZE

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

    priceData = MySQL.getPriceData()

    if priceData is not None:
        #yearCons = findYearConsForCashAdvance(priceData['monthly_cash_advance'])
        #price_kWh = priceData['monthly_cash_advance']*12/(yearCons[1]/1000)
        price_kWh_high = A[25]/1000.0
        price_kWh_low = A[26]/1000.0
        Log("Cena kWh VT:"+str(price_kWh_high)+" Kč, NT:"+str(price_kWh_low)+" Kč")


        lastDay_low_Wh,lastDay_std_Wh = getConsSumLastDay()

        Log("Spotřeba za včerejší den:"+str(int(lastDay_low_Wh))+" Wh "+str(int(lastDay_std_Wh))+" Wh")


        date_of_invoicing = str(priceData['date_of_invoicing'])
        date_of_invoicing = datetime(2000+int(date_of_invoicing[0:2]), int(date_of_invoicing[2:4]),
                                     int(date_of_invoicing[4:6]))
        totalSum_low, totalSum_std = MySQL.getTotalSum(date_of_invoicing)

        Log("Suma of posledního vyúčtování -  nízký tarif: "+str(int(totalSum_low))+" Wh ; Vysoký tarif:"+str(int(totalSum_std))+" Wh")

        yearPerc = percent(totalSum_std, totalSum_low, priceData['monthly_cash_advance'])
        Log("Roční plnění:"+str(yearPerc)+"%")

        #-----------------------


        priceLastDay = price_kWh_high*lastDay_std_Wh/1000+price_kWh_low*lastDay_low_Wh/1000
        Log("Cena  za včerejší den:" +str(int(priceLastDay)) + " Kč")

        MySQL.updatePriceData("priceLastDay", priceLastDay)
        MySQL.updatePriceData("yearPerc", yearPerc)

        selfSuf = MySQL.getSelfSuff(datetime.now()-timedelta(days=30), datetime.now())
        if selfSuf is not None:
            Log(f"Soběstačnost: {selfSuf:.1f} %")
        else:
            Log("Chyba výpočtu soběstačnosti")
        MySQL.updatePriceData("selfSufficiency", selfSuf)
    else:
        Log("Chyba výpočtu cen")


def Log(msg):
    if printDebug:
        print(msg)    
#yearPrice(powerHighTariff_wh, findYearConsForCashAdvance(2200)[1]) / 12
if __name__ == "__main__":

    run()
    