#!/usr/bin/env python
from __future__ import division
from subprocess import PIPE, Popen
import psutil
from time import sleep
import databaseInfluxDB

def get_cpu_temperature():
    process = Popen(['vcgencmd', 'measure_temp'], stdout=PIPE)
    output, _error = process.communicate()
    return float(output[output.index(b'=') + 1:output.rindex(b"'")])


def main():
    cpu_temperature = get_cpu_temperature()
    cpu_usage = psutil.cpu_percent()
    
    ram = psutil.virtual_memory()
    #ram_total = ram.total / 2**20       # MiB.
    ram_used = ram.used / 2**20
    #ram_free = ram.free / 2**20
    ram_percent_used = ram.percent
    
    disk = psutil.disk_usage('/')
    #disk_total = disk.total / 2**30     # GiB.
    disk_used = disk.used / 2**20  # MiB.
    #disk_free = disk.free / 2**30
    disk_percent_used = disk.percent
    
    #top3CPUprocesses = ([(p.pid, p.info['name'], sum(p.info['cpu_times'])) for p in sorted(psutil.process_iter(attrs=['name', 'cpu_times']), key=lambda p: sum(p.info['cpu_times'][:2]))][-3:])
    
    #top3MemoryProcesses = ([(p.pid, p.info) for p in sorted(psutil.process_iter(attrs=['name', 'memory_percent']), key=lambda p: p.info['memory_percent'])][-3:])


    databaseInfluxDB.insertHardwareMonitoringValue(cpu_temperature,cpu_usage,ram_used,ram_percent_used,disk_used,disk_percent_used)


try:
    sleep(30)#wait until influxDB is started
    while(True):
        main()
        sleep(5)
        
except KeyboardInterrupt:
    print("Canceled by user")