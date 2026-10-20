#!/usr/bin/python3
# Code to control the VEML7700 ambient light sensor. Write observations to disk
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import board, busio, helper_functions

try:
	import adafruit_veml7700
	i2c = board.I2C()
	sensor = adafruit_veml7700.VEML7700(i2c)

	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1

	for x in range(0, iterations):
		lux = sensor.lux

		print("VEML7700 Sensor")
		print("Lux:  %.2f" % lux)
		print()

		line = "%.2f" % lux
		helper_functions.output(False, line, "veml7700")

		if test_mode == "true":
			time.sleep(10)
		else:
			break

except Exception as e:
	helper_functions.handleError(e, "veml7700")
