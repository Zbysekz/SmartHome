#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
from comm.device import cDevice
from comm.commProcessor import cCommProcessor

# now just simple method, then upgrade by approximation curve probably
def calculatePowerwallSOC(voltage):
    MAX = 49.8
    MIN = 37.2
    
    voltage = min(max(MIN, voltage),MAX)
    
    SOC = ((voltage - MIN)/(MAX-MIN))*100.0
    
    return SOC

class cControlPowerwall:
    def __init__(self, logger, dataProcessor, commProcessor, mySQL):

        self.logger = logger
        self.mySQL = mySQL
        self.dataProcessor = dataProcessor
        self.commProcessor = commProcessor

        self.powerwall_last_full_tmr = 0
        self.powerwall_last_full = False


    def ControlPowerwall(self):  # called each # 5 mins
        globalFlags = self.dataProcessor.globalFlags
        currentValues = self.dataProcessor.currentValues

        device = cDevice.get_device_by_name("POWERWALL", cCommProcessor.devices)
        if device.online:
            if globalFlags['autoPowerwallRun'] == 1:
                solarPowered = currentValues[
                    'status_rackUno_stateMachineStatus'] == 3
               # if enough SoC to run
                if not solarPowered and currentValues['status_powerwall_stateMachineStatus'] == 20 and currentValues[
                    'status_powerwallSoc'] > 75:  # more than 75% SoC
                    self.logger.log("Auto powerwall control - Switching to solar")
                    #MySQL.insertTxCommand(IP_POWERWALL, "10")  # RUN command
                    self.commProcessor.switch_to_solar()
                # if below SoC
                elif solarPowered and currentValues['status_powerwall_stateMachineStatus'] == 20 and currentValues[
                        'status_powerwallSoc'] <= 20:  # less than 20% SoC
                    self.logger.log("Auto powerwall control - Switching to grid")
                    self.commProcessor.switch_to_grid()
                if currentValues['status_powerwall_stateMachineStatus'] == 99:
                    if not self.powerwall_last_fail:
                        self.logger.log("Powerwall in error state!", self.logger.CRITICAL)
                    self.powerwall_last_fail = True
                else:
                    self.powerwall_last_fail = False

                if currentValues[
                        'status_powerwallSoc'] > 95:
                    if not self.powerwall_last_full and time.time() - self.powerwall_last_full_tmr > 3600*6:
                        self.logger.log("Baterie powerwall je skoro plna! PAL TO!!!", self.logger.CRITICAL, all_members = True)
                        self.powerwall_last_full_tmr = time.time()
                    self.powerwall_last_full = True
                else:
                    self.powerwall_last_full = False

    def ControlPowerwall_fast(self):  # called each 30 s

        device = cDevice.get_device_by_name("POWERWALL", cCommProcessor.devices)
        if device.online:
            globalFlags = self.dataProcessor.globalFlags
            currentValues = self.dataProcessor.currentValues

            if globalFlags['autoPowerwallRun'] == 1:

                solarPowered = currentValues[
                    'status_rackUno_stateMachineStatus'] == 3
                # if we are running from solar power
                if solarPowered and currentValues['status_powerwall_stateMachineStatus'] not in (10, 20):
                    self.logger.log(f"Auto powerwall control - powerwall not in proper state - shutdown. status {currentValues['status_powerwall_stateMachineStatus']}")
                    self.commProcessor.switch_to_grid()
