#!/bin/sh
# launcher.sh
# navigate to home directory, then to this directory, then execute python script, then back home

cd /
cd home/pi/SmartHome
sudo lxterminal -e "sudo python3 /home/pi/SmartHome/main.py delayStart"

cd /

