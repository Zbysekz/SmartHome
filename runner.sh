#!/bin/bash

while :
do
	res=$(pgrep -f screenVisApp); 
	if ! [[ ${#res} -gt 1 ]]; then
	nohup /home/pi/screenVis/screenVis/autorunMain_noDelay.sh &
	fi
	sleep 10s
done

