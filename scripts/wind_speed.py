#!/usr/bin/python3
# Code to control the wind speed sensor. Write observations to disk
# Paul A. Kucera, Ph.D. and Joseph E. Rener
# UCAR
# Boulder, CO USA
# Email: pkucera@ucar.edu and jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import RPi.GPIO as GPIO, adafruit_mcp9808 as mcp9808, busio, board, time, datetime, helper_functions, sys

# Get inputs
arguments = helper_functions.getArguments()
record_interval = arguments[0]
test_toggle = arguments[6]
test = 0
if len(sys.argv) > 1:
	test = int(sys.argv[1])
i2c = busio.I2C(board.SCL, board.SDA)

# Check if this is a test (1) or real (0) and set interval appropriately
command_test = False
if test > 0:
	rest = test
	command_test = True
elif test_toggle == "true":
	rest = record_interval
	command_test = True
else:
	rest = 60*record_interval

# Sensor counter variable
COUNT = 1

# Number of sensors in anemometer
SENSOR_NUM = 2

# Sample time in seconds
SAMPLE = rest

# Wind speed calibration factor
CAL_Factor = 2.64 # (3.14/1.19)

# Offset factor for different plastic material (PLA)
OFFSET = 0.0

SCALE = CAL_Factor*(2*3.14156*0.079)/(SENSOR_NUM*SAMPLE) # wind speed in m/s

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
	wind = wind + COUNT
					
# Register the call back for pin interrupts
GPIO.add_event_detect(PIN, GPIO.FALLING, callback=cb, bouncetime=1)

print("Wind Speed Sensor")

# Display and write data to file and send to CHORDS
while True:
	try:
		if wind > 0:
			wind_spd = wind*SCALE+OFFSET
		else:
			wind_spd = 0.0
		try:
			connect = mcp9808.MCP9808(i2c)
		except:
			if wind_spd == 0.0:
				wind_spd = -999.99

		# Get current time for each record and filename
		now = datetime.datetime.utcnow()

		# Handle script output
		line = "%.4f" % (wind_spd)	
		if command_test:
			helper_functions.output(True, line, "test_wind_speed")
		else:
			helper_functions.output(True, line, "wind_speed")

		wind = 0
		time.sleep(rest)

	except Exception as e:
		helper_functions.handleError(e, "wind_speed")
		pass
		
GPIO.cleanup()