#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os  # we must add path to comm folder because inner scripts can now import other scripts in same folder directly

os.sys.path.append(os.path.dirname(os.path.realpath(__file__)) + '/comm')

# for calculation of AVGs - the routines are located in web folder
# import importlib.machinery
# avgModule = importlib.machinery.SourceFileLoader('getMeas',os.path.abspath("/var/www/SmartHomeWeb/getMeas.py")).load_module()

import comm
from databaseMySQL import cMySQL
import threading
from phone import cPhone
from datetime import datetime
from time import sleep
import sys
import struct
import electricityPrice
import time
import updateStats
from logger import Logger
from parameters import parameters
import data_processing
from templates.threadModule import cThreadModule
from control.house_security import cHouseSecurity

# -------------DEFINITIONS-----------------------
RESTART_ON_EXCEPTION = True

# for periodicity mysql inserts
HOUR = 3600
MINUTE = 60

# -----------------------------------------------

# -------------STATE VARIABLES-------------------


globalFlags = {}  # contains data from table globalFlags - controls behaviour of subsystems
currentValues = {}  # contains latest measurements data
# -----------------------------------------------

# ------------AUXILIARY VARIABLES----------------

tmrPriceCalc = time.time()
gasSensorPrepared = False
tmrPrepareGasSensor = time.time()
alarm_last = 0
powerwall_last_fail = False
powerwall_last_full = False
powerwall_last_full_tmr = 0

terminate = False

tmrConsPowerwall = 0
tmrVentHeatControl = 0
tmrFastPowerwallControl = 0

bufferedCellModVoltage = 24 * [0]

# cycle time
tmrCycleTime = 0
cycleTime_avg = 0
cycleTime_cnt = 0
cycleTime_tmp = time.time()
cycleTime = 0
cycleTime_max = 0
# -----------------------------------------------

logger = Logger("main", verbosity=Logger.FULL)
MySQL = cMySQL()
cThreadModule.logger = logger
###############################################################################################################
def main():
    try:

        logger.log("Entry point main.py")

        phone = cPhone(period_s=20)
        logger.phone = phone
        commProcessor = comm.cCommProcessor(period_s=5)
        dataProcessor = data_processing.cDataProcessor(phone=phone, period_s=10)
        houseSecurity = cHouseSecurity(logger, MySQL, commProcessor, dataProcessor, phone)
        commProcessor.house_security = houseSecurity

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        logger.log(str(e))
        logger.log(str(exc_type) + " in file " + str(fname) + " : on line " + str(exc_tb.tb_lineno))
        raise e
            #os.system("shutdown -r 1")  # reboot after one minute
            #input("Reboot in one minute. Press Enter to continue...")

    commProcessor.handle()
    dataProcessor.handle()
    phone.handle()

    ######################## MAIN LOOP ####################################################################################
    while True:

        if not cThreadModule.checkTermination():
            break
        time.sleep(5)
        # ----------------------------------------------

####################################################################################################################

if __name__ == "__main__":

    if (len(sys.argv) > 1):
        if ('delayStart' in sys.argv[1]):
            logger.log("Delayed start...")
            sleep(20)
    # execute only if run as a script
    main()
