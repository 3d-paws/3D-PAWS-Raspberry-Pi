#!/usr/bin/python3
# Code to control the wind direction sensor. Write observations to disk
# and to web in intervals determined by input.txt
# Computes a 1 minute geometric average
# Paul A. Kucera, Ph.D. and Joseph E. Rener
# UCAR
# Boulder, CO USA
# Email: pkucera@ucar.edu and jrener@ucar.edu
# Copyright (c) 2022 UCAR
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import RPi.GPIO as GPIO, busio, board, time, sys, datetime, helper_functions

arguments = helper_functions.getArguments()
record_interval = arguments[0]
chords_interval = arguments[1]
test_toggle = arguments[6]
test = 0
command_test = False
if len(sys.argv) > 1:
	test = int(sys.argv[1])
if test > 0:
	rest = test
	command_test = True
elif test_toggle == "true":
	rest = record_interval
	command_test = True
else:
	rest = 60*record_interval
i2c = busio.I2C(board.SCL, board.SDA)

# Rainfall Accumulation in mm per bucket tip (TB3 Specs)
CALIBRATION = 0.2

# Identify the GPIO pin for the rain gauge
PIN = 23

GPIO.setmode(GPIO.BCM)  
GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Variable to keep track of how much rain
rain = 0
rain_accumulation = 0.0
rain_accumulation_chords = 0.0

# Call back function for each bucket tip
def tipped(channel):
	global rain
	rain = rain + CALIBRATION
				
# Register the call back for pin interrupts
GPIO.add_event_detect(PIN, GPIO.FALLING, callback=tipped, bouncetime=300)

print("Rain (tipping bucket) Sensor")

# Display, write to file, and send to CHORDS
while True:
	try:
		# Get current time for writing to file
		now = datetime.datetime.utcnow()

		# Accumulate rain for larger intervals
		rain_accumulation += rain
		rain_accumulation_chords += rain

		# Handle script output
		line = "%.2f" % (rain_accumulation)		
		if command_test:
			helper_functions.output(True, line, "test_rain")
		else:
			helper_functions.output(True, line, "rain")

		# Reset rain_accumination
		rain_accumulation = 0.0

		# Reset rain_accumination_chords if it's time to send it to chords
		if test == "false" and now.minute % chords_interval == 0: 
			rain_accumulation_chords = 0.0
					
		rain = 0		

		# Wait until the interval has passed and run again
		time.sleep(rest)

	except Exception as e:
		helper_functions.handleError(e, "rain")
		pass
		
GPIO.cleanup()

