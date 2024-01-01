#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from comm.device import cDevice
from comm.commProcessor import cCommProcessor
from templates.threadModule import cThreadModule
from parameters import parameters
from logger import Logger
from databaseMySQL import cMySQL
import time
from datetime import datetime

# now just simple method, then upgrade by approximation curve probably
def calculatePowerwallSOC(voltage):
    MAX = 49.8
    MIN = 37.2
    
    voltage = min(max(MIN, voltage),MAX)
    
    SOC = ((voltage - MIN)/(MAX-MIN))*100.0
    
    return SOC

class cPowerwallControl(cThreadModule):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mySQL = cMySQL()
        self.logger = Logger("powerwall", verbosity=parameters.VERBOSITY)

        self.dataProcessor = None
        self.powerwall_last_full = False
        self.powerwall_last_fail = False
        self.tmr_slow_control = 0

    def _handle(self):
        self.ControlPowerwall_fast()
        if time.time() - self.tmr_slow_control > 5*60:
            self.tmr_slow_control = time.time()
            self.ControlPowerwall()

    def ControlPowerwall(self):
        globalFlags = self.dataProcessor.globalFlags
        currentValues = self.dataProcessor.currentValues

        if globalFlags['autoPowerwallRun'] == 1:

            datetimeNow = datetime.now()
            summerTime = 3 < datetimeNow.month < 10

            if summerTime:
                upperRunThreshold = 70
                lowerStopThreshold = 20
            else:
                upperRunThreshold = 90
                lowerStopThreshold = 40

            solarPowered = currentValues[
                'status_rackUno_stateMachineStatus'] == 3
           # if enough SoC to run
            if not solarPowered and currentValues['status_powerwall_stateMachineStatus'] in [10, 20] and currentValues[
                'status_powerwallSoc'] > upperRunThreshold:  # more than 70% SoC
                self.logger.log("Auto powerwall control - Switching to solar")
                #MySQL.insertTxCommand(IP_POWERWALL, "10")  # RUN command
                self.mySQL.insertTxCommand(cDevice.get_ip("RACKUNO", cCommProcessor.devices), "4")  # Switch to SOLAR command
            # if below SoC
            elif solarPowered and currentValues['status_powerwall_stateMachineStatus'] in [10, 20] and currentValues[
                    'status_powerwallSoc'] <= lowerStopThreshold:  # less than 20% SoC
                self.logger.log("Auto powerwall control - Switching to grid")
                self.mySQL.insertTxCommand(cDevice.get_ip("RACKUNO", cCommProcessor.devices), "3")  # Switch to GRID command
            if currentValues['status_powerwall_stateMachineStatus'] == 99:
                if not self.powerwall_last_fail:
                    self.logger.log("Powerwall in error state!", Logger.CRITICAL)
                self.powerwall_last_fail = True

                if solarPowered: # prevent immediate solar connect after error recovery
                    self.mySQL.insertTxCommand(cDevice.get_ip("RACKUNO", cCommProcessor.devices),
                                               "3")  # Switch to GRID command

            else:
                self.powerwall_last_fail = False

            if currentValues[
                    'status_powerwallSoc'] > 95:
                if not self.powerwall_last_full and time.time() - self.powerwall_last_full_tmr > 3600*6:
                    self.logger.log("Baterie powerwall je skoro plna! PAL TO!!!", Logger.CRITICAL, all_members = True)
                    self.powerwall_last_full_tmr = time.time()
                self.powerwall_last_full = True
            else:
                self.powerwall_last_full = False

    def ControlPowerwall_fast(self):  # called each 30 s
        globalFlags = self.dataProcessor.globalFlags
        currentValues = self.dataProcessor.currentValues
        if globalFlags['autoPowerwallRun'] == 1:

            solarPowered = currentValues[
                'status_rackUno_stateMachineStatus'] == 3
            # if we are running from solar power
            if solarPowered and currentValues['status_powerwall_stateMachineStatus'] not in (10, 20):
                self.logger.log(f"Auto powerwall control - powerwall not in proper state - shutdown. status {currentValues['status_powerwall_stateMachineStatus']}")
                self.mySQL.insertTxCommand(cDevice.get_ip("RACKUNO", cCommProcessor.devices), "3")  # Switch to GRID command
