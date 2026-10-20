#!/usr/bin/python3
# Code to control the Adafruit PM25AQI air quality sensor. Write observations to disk
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import board, busio, helper_functions

try:
	from adafruit_pm25.i2c import PM25_I2C
	i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
	sensor = PM25_I2C(i2c, None)

	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1

	for x in range(0, iterations):
		data = sensor.read()
		pm1e10  = data["pm10 env"]
		pm1e25  = data["pm25 env"]
		pm1e100 = data["pm100 env"]

		print("PM25AQI Sensor")
		print("PM1.0 env:  %.2f µg/m³" % pm1e10)
		print("PM2.5 env:  %.2f µg/m³" % pm1e25)
		print("PM10.0 env: %.2f µg/m³" % pm1e100)
		print()

		line = "%.2f %.2f %.2f" % (pm1e10, pm1e25, pm1e100)
		helper_functions.output(False, line, "pm25aqi")

		if test_mode == "true":
			time.sleep(10)
		else:
			break

except Exception as e:
	helper_functions.handleError(e, "pm25aqi")
