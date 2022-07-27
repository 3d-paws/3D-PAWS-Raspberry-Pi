#!/usr/bin/python

import time, RPi.GPIO as GPIO, helper_functions

GPIO.setwarnings(False)
GPIO_PIN = 17 
GPIO.setmode(GPIO.BCM) 
GPIO.setup(GPIO_PIN, GPIO.OUT) 

try:  
    GPIO.output(GPIO_PIN, GPIO.HIGH) #turn on the relay, turning off the sensors
    time.sleep(5) 
    GPIO.output(GPIO_PIN, GPIO.LOW) #turn off the relay, turning on the sensors

except Exception as e:
	helper_functions.handleError(e, "relay")