#!/usr/bin/python3
# Code to control the HTU21D temperature and humidity sensor. Write observations to disk
# Paul A. Kucera, Ph.D. and Joseph E. Rener
# UCAR
# Boulder, CO USA
# Email: pkucera@ucar.edu and jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import board, busio, helper_functions
from adafruit_htu21d import HTU21D

try:
	i2c = busio.I2C(board.SCL, board.SDA)
	sensor = HTU21D(i2c)

	#Get arguments
	arguments = helper_functions.getArguments()
	wait = arguments[0]
	test_mode = arguments[6]

	#Handle test mode
	target = 1
	if test_mode == "true":
		target = (60/wait)-1
		import time

	iterations = 0
	while iterations < target:
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

		iterations += 1
		if test_mode == "true":
			time.sleep(wait)

except Exception as e:
	helper_functions.handleError(e, "htu21d")
