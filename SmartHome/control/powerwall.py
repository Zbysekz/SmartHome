#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# now just simple method, then upgrade by approximation curve probably
def calculatePowerwallSOC(voltage):
    MAX = 49.8
    MIN = 37.2
    
    voltage = min(max(MIN, voltage),MAX)
    
    SOC = ((voltage - MIN)/(MAX-MIN))*100.0
    
    return SOC


def ControlPowerwall(globalFlags, currentValues):  # called each # 5 mins
    if globalFlags['autoPowerwallRun'] == 1:
        solarPowered = currentValues[
            'status_rackUno_stateMachineStatus'] == 3
       # if enough SoC to run
        if not solarPowered and currentValues['status_powerwall_stateMachineStatus'] == 20 and currentValues[
            'status_powerwallSoc'] > 75:  # more than 75% SoC
            logger.log("Auto powerwall control - Switching to solar")
            #MySQL.insertTxCommand(IP_POWERWALL, "10")  # RUN command
            MySQL.insertTxCommand(IP_RACKUNO, "4")  # Switch to SOLAR command
        # if below SoC
        elif solarPowered and currentValues['status_powerwall_stateMachineStatus'] == 20 and currentValues[
                'status_powerwallSoc'] <= 20:  # less than 20% SoC
            logger.log("Auto powerwall control - Switching to grid")
            MySQL.insertTxCommand(IP_RACKUNO, "3")  # Switch to GRID command
        if currentValues['status_powerwall_stateMachineStatus'] == 99:
            if not powerwall_last_fail:
                logger.log("Powerwall in error state!", Logger.CRITICAL)
            powerwall_last_fail = True
        else:
            powerwall_last_fail = False

        if currentValues[
                'status_powerwallSoc'] > 95:
            if not powerwall_last_full and time.time() - powerwall_last_full_tmr > 3600*6:
                logger.log("Baterie powerwall je skoro plna! PAL TO!!!", Logger.CRITICAL, all_members = True)
                powerwall_last_full_tmr = time.time()
            powerwall_last_full = True
        else:
            powerwall_last_full = False

def ControlPowerwall_fast():  # called each 30 s
    global globalFlags, currentValues
    if globalFlags['autoPowerwallRun'] == 1:

        solarPowered = currentValues[
            'status_rackUno_stateMachineStatus'] == 3
        # if we are running from solar power
        if solarPowered and currentValues['status_powerwall_stateMachineStatus'] not in (10, 20):
            logger.log(f"Auto powerwall control - powerwall not in proper state - shutdown. status {currentValues['status_powerwall_stateMachineStatus']}")
            MySQL_GeneralThread.insertTxCommand(IP_RACKUNO, "3")  # Switch to GRID command
