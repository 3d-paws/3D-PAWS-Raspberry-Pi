#!/usr/bin/python3
# Code to control the Adafruit LPS35HW water-resistant pressure sensor. Write observations to disk
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import board, busio, helper_functions

try:
	import adafruit_lps35hw
	i2c = board.I2C()
	sensor = adafruit_lps35hw.LPS35HW(i2c)

	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1

	for x in range(0, iterations):
		pressure = sensor.pressure
		tempC    = sensor.temperature
		tempF    = tempC * 1.8 + 32

		print("LPS35HW Sensor")
		print("Pressure:     %.2f hPa" % pressure)
		print("Temperature:  %.2f degC" % tempC)
		print("Temperature:  %.2f degF" % tempF)
		print()

		line = "%.2f %.2f" % (pressure, tempC)
		helper_functions.output(False, line, "lps35hw")

		if test_mode == "true":
			time.sleep(10)
		else:
			break

except Exception as e:
	helper_functions.handleError(e, "lps35hw")
