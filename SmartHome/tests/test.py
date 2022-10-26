import RPi.GPIO as GPIO

pin_btnPC = 26

GPIO.setmode(GPIO.BCM)
GPIO.setup(pin_btnPC, GPIO.OUT)
GPIO.setwarnings(False)
    
GPIO.output(pin_btnPC,True)
import time
time.sleep(2)
GPIO.output(pin_btnPC,False)




