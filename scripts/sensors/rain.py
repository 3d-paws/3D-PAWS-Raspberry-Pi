#!/usr/bin/python3
# Code to control the wind direction sensor. Write observations to disk
# Computes a 1 minute geometric average
# Paul A. Kucera, Ph.D. and Joseph Rener
# UCAR
# Boulder, CO USA
# Email: pkucera@ucar.edu and jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import RPi.GPIO as GPIO, time, os, helper_functions

#Get variables
variables = helper_functions.getVariables()
test_toggle = variables[0]
interval = helper_functions.getCron()[0]

# Set rest interval based on if we're testing or not
test = True
if len(sys.argv) > 1:
	rest = int(sys.argv[1])
	iterations = int((interval*60/rest)-1)
elif os.isatty(sys.stdin.fileno()) or test_toggle == "true":
	rest = 10
	iterations = (interval*6)-1
else:
	test = False
	rest = 60*interval - 1
	iterations = 1

# Rainfall Accumulation in mm per bucket tip (TB3 Specs)
CALIBRATION = 0.2

# Identify the GPIO pin for the rain gauge
PIN = 23

# Start sensor
GPIO.setmode(GPIO.BCM)  
GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Variable to keep track of how much rain
rain = 0.0

# Call back function for each bucket tip
def tipped(channel):
	global rain
	rain = rain + CALIBRATION
				
# Register the call back for pin interrupts
GPIO.add_event_detect(PIN, GPIO.FALLING, callback=tipped, bouncetime=300)

print("Rain (tipping bucket) Sensor")

# Run once... or if in test mode, run every 10 seconds during the interval
for x in range (0, iterations):
	time.sleep(rest)
	try:
		# Handle script output
		line = "%.2f" % (rain)		
		if test:
			helper_functions.output(True, line, "test_rain")
		else:
			helper_functions.output(True, line, "rain")

		# Reset rain
		if test:
			rain = 0.0
		else:
			break

	except Exception as e:
		helper_functions.handleError(e, "rain")
		GPIO.cleanup()
		pass
