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
        self.auto_powerwall_tmr_command_exec_garage = 0
        self.auto_powerwall_tmr_command_exec_house = 0
        self.powerwall_last_full_tmr = 0

    def _handle(self):
        self.ControlPowerwall()


    def ControlPowerwall(self):  # called each 30 s
        globalFlags = self.dataProcessor.globalFlags
        currentValues = self.dataProcessor.currentValues

        if globalFlags['autoPowerwallRun'] != 1:
            return
        datetimeNow = datetime.now()
        summerTime = 3 < datetimeNow.month < 10

        if summerTime:
            house_upperRunThreshold = 60
            house_lowerStopThreshold = 30

            garage_upperRunThreshold = 60
            garage_lowerStopThreshold = 35
        else:
            house_upperRunThreshold = 70
            house_lowerStopThreshold = 30

            garage_upperRunThreshold = 70
            garage_lowerStopThreshold = 40

        house_solarPowered = currentValues[
                           'status_rackUno_stateMachineStatus'] == 3
        garage_solarPowered = currentValues[
                           'status_powerwall_garage_contactor'] == 1

        time_inhibit_house_cmd = time.time() - self.auto_powerwall_tmr_command_exec_house > 60 * 5  # 5 min
        time_inhibit_garage_cmd = time.time() - self.auto_powerwall_tmr_command_exec_garage > 60 * 5  # 5 min
        # HOUSE CONTROL
        # if enough SoC to run
        if (time_inhibit_house_cmd and not house_solarPowered and
                currentValues['status_powerwall_stateMachineStatus'] in [10, 20] and \
                currentValues[
                    'status_powerwallSoc'] > house_upperRunThreshold):  # more than 70% SoC
            self.logger.log("Auto powerwall control - House switching to solar")
            # MySQL.insertTxCommand(IP_POWERWALL, "10")  # RUN command
            self.mySQL.insertTxCommand(cDevice.get_ip("RACKUNO", cCommProcessor.devices),
                                       "4")  # Switch to SOLAR command
            self.auto_powerwall_tmr_command_exec_house = time.time()
        # if below SoC
        elif time_inhibit_house_cmd and house_solarPowered and currentValues['status_powerwall_stateMachineStatus'] in [10,
                                                                                       20] and \
                currentValues[
                    'status_powerwallSoc'] <= house_lowerStopThreshold:  # less than xx% SoC
            self.logger.log("Auto powerwall control - House switching to grid")
            self.mySQL.insertTxCommand(cDevice.get_ip("RACKUNO", cCommProcessor.devices),
                                       "3")  # Switch to GRID command
            self.auto_powerwall_tmr_command_exec_house = time.time()

        # GARAGE CONTROL
        # if enough SoC to run
        if (time_inhibit_garage_cmd and not garage_solarPowered and
                currentValues['status_powerwall_stateMachineStatus'] in [10, 20] and \
                currentValues[
                    'status_powerwallSoc'] > garage_upperRunThreshold):  # more than 70% SoC
            self.logger.log("Auto powerwall control - Garage switching to solar")

            self.mySQL.insertTxCommand(cDevice.get_ip("POWERWALL", cCommProcessor.devices),
                                       "20,1")  # Switch to SOLAR command
            self.auto_powerwall_tmr_command_exec_garage = time.time()
        # if below SoC
        elif time_inhibit_garage_cmd and garage_solarPowered and currentValues[
            'status_powerwall_stateMachineStatus'] in [10,
                                                       20] and \
                currentValues[
                    'status_powerwallSoc'] <= garage_lowerStopThreshold:  # less than xx% SoC
            self.logger.log("Auto powerwall control - Garage switching to grid")
            self.mySQL.insertTxCommand(cDevice.get_ip("POWERWALL", cCommProcessor.devices),
                                       "20,0")  # Switch to GRID command
            self.auto_powerwall_tmr_command_exec_garage = time.time()

        if currentValues['status_powerwall_stateMachineStatus'] == 99:
            if not self.powerwall_last_fail:
                self.logger.log("Powerwall in error state!", Logger.CRITICAL)
            self.powerwall_last_fail = True

            if house_solarPowered:  # prevent immediate solar connect after error recovery
                self.mySQL.insertTxCommand(cDevice.get_ip("RACKUNO", cCommProcessor.devices),
                                           "3")  # Switch to GRID command

        else:
            self.powerwall_last_fail = False

        if currentValues[
            'status_powerwallSoc'] > 95:
            if not self.powerwall_last_full and time.time() - self.powerwall_last_full_tmr > 3600 * 6:
                # self.logger.log("Baterie powerwall je skoro plna! PAL TO!!!", Logger.CRITICAL)
                self.powerwall_last_full_tmr = time.time()
            self.powerwall_last_full = True
        else:
            self.powerwall_last_full = False

        solarPowered = currentValues[
            'status_rackUno_stateMachineStatus'] == 3
        # if we are running from solar power
        if house_solarPowered and currentValues['status_powerwall_stateMachineStatus'] not in (10, 20):
            self.logger.log(f"Auto powerwall control - powerwall not in proper state - shutdown. status {currentValues['status_powerwall_stateMachineStatus']}")
            self.mySQL.insertTxCommand(cDevice.get_ip("RACKUNO", cCommProcessor.devices), "3")  # Switch to GRID command
