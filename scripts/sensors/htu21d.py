#!/usr/bin/python3
# Code to control the HTU21D temperature and humidity sensor. Write observations to disk
# Paul A. Kucera, Ph.D. and Joseph Rener
# UCAR
# Boulder, CO USA
# Email: pkucera@ucar.edu and jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import board, busio, helper_functions
from adafruit_htu21d import HTU21D

try:
	i2c = busio.I2C(board.SCL, board.SDA)
	sensor = HTU21D(i2c)

	#Get arguments
	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1 # runs every 10 seconds over the interval, minus the last 10 seconds

	# Run once... or if in test mode, run every 10 seconds during the interval
	for x in range (0,iterations):
		tempC = sensor.temperature
		tempF = tempC*1.8+32
		rh = sensor.relative_humidity

		# Print to screen
		print("HTU21D Sensor")
		print("Temperature:  %.2f degC" % tempC)
		print("Temperature:  %.2f degF" % tempF)
		print("Humidity:     %.0f%%" % rh)
		print()

		# Handle script output
		line = '%.2f %.2f' % (tempC, rh)
		helper_functions.output(False, line, "htu21d")

		# Wait 10 seconds and repeat if in test mode
		if test_mode == "true":
			time.sleep(10)
		else:
			break

except Exception as e:
	helper_functions.handleError(e, "htu21d")
