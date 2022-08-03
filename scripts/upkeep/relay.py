#!/usr/bin/python3
# Code to activate/deactivate the relay
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import time, RPi.GPIO as GPIO, helper_functions

GPIO.setwarnings(False)
GPIO_PIN = 5
GPIO.setmode(GPIO.BCM) 
GPIO.setup(GPIO_PIN, GPIO.OUT) 

try:  
    GPIO.output(GPIO_PIN, GPIO.HIGH) #turn on the relay, turning off the sensors
    time.sleep(5) 
    GPIO.output(GPIO_PIN, GPIO.LOW) #turn off the relay, turning on the sensors

except Exception as e:
	helper_functions.handleError(e, "relay")