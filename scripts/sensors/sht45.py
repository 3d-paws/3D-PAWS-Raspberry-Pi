#!/usr/bin/python3
# Code to control the Adafruit SHT45 (SHT4x series) temperature and humidity sensor.
# Write observations to disk.
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import board, busio, helper_functions

try:
	import adafruit_sht4x
	i2c = board.I2C()
	sensor = adafruit_sht4x.SHT4x(i2c)
	sensor.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION

	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1

	for x in range(0, iterations):
		tempC, rh = sensor.measurements
		tempF = tempC * 1.8 + 32

		print("SHT45 Sensor")
		print("Temperature:  %.2f degC" % tempC)
		print("Temperature:  %.2f degF" % tempF)
		print("Humidity:     %.2f%%" % rh)
		print()

		line = "sht45 %.2f %.2f" % (tempC, rh)
		helper_functions.output(False, line, "sht45")

		if test_mode == "true":
			time.sleep(10)
		else:
			break

except Exception as e:
	helper_functions.handleError(e, "sht45")
