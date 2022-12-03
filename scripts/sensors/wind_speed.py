#!/usr/bin/python3
# Code to control the wind speed sensor. Write observations to disk
# Paul A. Kucera, Ph.D. and Joseph Rener
# UCAR
# Boulder, CO USA
# Email: pkucera@ucar.edu and jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import RPi.GPIO as GPIO, time, helper_functions, os 

# Get inputs
arguments = helper_functions.getArguments()
record_interval = arguments[0]
test_toggle = arguments[6]

# Check if this is a test (1) or real (0) and set interval appropriately
test = True
if len(sys.argv) > 1:
	rest = int(sys.argv[1])
elif os.isatty(sys.stdin.fileno()):
	rest = 60*record_interval
elif test_toggle == "true":
	rest = record_interval
else:
	test = False
	rest = 60*record_interval

# Number of sensors in anemometer
SENSOR_NUM = 2

# Wind speed calibration factor
CAL_Factor = 2.64 # (3.14/1.19)
SCALE = CAL_Factor*(2*3.14156*0.079)/(SENSOR_NUM*rest) # wind speed in m/s

# Identify the GPIO pin for the wind sensor
PIN = 22

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)  
GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Variable to keep track of how much rotations
wind = 0

# Call back function for each wind sensor reading
def cb(channel):
	global wind
	wind = wind + 1
					
# Register the call back for pin interrupts
GPIO.add_event_detect(PIN, GPIO.FALLING, callback=cb, bouncetime=1)

print("Wind Speed Sensor")

# Display and write data to file and send to CHORDS
while True:
	time.sleep(rest)
	try:
		if wind > 0:
			wind_spd = wind*SCALE
		else:
			wind_spd = 0.0

		# Handle script output
		line = "%.4f" % (wind_spd)	
		if test:
			helper_functions.output(True, line, "test-wind_speed")
		else:
			helper_functions.output(True, line, "wind_speed")

		wind = 0

	except Exception as e:
		helper_functions.handleError(e, "wind_speed")
		GPIO.cleanup()
		pass