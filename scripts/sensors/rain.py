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

# Get arguments
arguments = helper_functions.getArguments()
record_interval = arguments[0]
chords_interval = arguments[1]
test_toggle = arguments[6]

# Set rest interval based on if we're testing or not
test = True
if len(sys.argv) > 1:
	rest = int(sys.argv[1])
elif test_toggle == "true":
	rest = record_interval
elif os.isatty(sys.stdin.fileno()):
	rest = 60*record_interval
else:
	test = False
	rest = 60*record_interval

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

# Main loop
while True:
	# Wait until the interval has passed and run again
	time.sleep(rest)

	try:
		# Handle script output
		line = "%.2f" % (rain)		
		if test:
			helper_functions.output(True, line, "test_rain")
		else:
			helper_functions.output(True, line, "rain")

		# Reset rain
		rain = 0.0

	except Exception as e:
		helper_functions.handleError(e, "rain")
		GPIO.cleanup()
		pass
