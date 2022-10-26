#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# now just simple method, then upgrade by approximation curve probably
def calculatePowerwallSOC(voltage):
    MAX = 25.2
    MIN = 18
    
    voltage = min(max(MIN, voltage),MAX)
    
    SOC = ((voltage - MIN)/(MAX-MIN))*100.0
    
    return SOC