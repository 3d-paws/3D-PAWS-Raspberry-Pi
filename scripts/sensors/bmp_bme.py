#!/usr/bin/python
# Code to control the BMP280 and BME280 I2C sensors. Write observations to disk
# Paul A. Kucera, Ph.D. and Joseph Rener
# UCAR
# Boulder, CO USA
# Email: pkucera@ucar.edu and jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import board, busio, helper_functions, time

try:
	# Get variables
	variables = helper_functions.getVariables()
	test_mode = variables[0]
	pressure_level = variables[3]
	altitude = variables[4]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1 # runs every 10 seconds over the interval, minus the last 10 seconds

	# Initialize correct sensor
	which_sensor = False
	try:
		import adafruit_bmp280
		i2c = busio.I2C(board.SCL, board.SDA)
		bmp = adafruit_bmp280.Adafruit_BMP280_I2C(i2c)
		which_sensor = "bmp"
	except:
		import adafruit_bme280
		i2c = board.I2C()
		bme = adafruit_bme280.Adafruit_BME280_I2C(i2c)
		which_sensor = "bme"

	# Run once... or if in test mode, run every 10 seconds during the interval
	for x in range (0,iterations):
		# Get and calculate data
		if which_sensor == "bmp":
			bmp.sea_level_pressure = pressure_level
			tempC = bmp.temperature
			pressure = bmp.pressure
		else:
			tempC = bme.temperature
			pressure = bme.pressure
			humidity = bme.humidity
		slp = pressure*pow(1-(0.0065*altitude)/(tempC+0.0065*altitude+273.15),-5.257)
		tempF = tempC*1.8+32
		slp_hg = slp/33.86389
		station_pres = pressure

		# Print to screen
		if which_sensor == "bmp":
			print("BMP280 Sensor")
			print("Altitude:            %.2f m" % altitude)
		else:
			print("BME280 Sensor")
			print("Relative Humidity:   %.2f" % humidity)
		print("Temperature:         %.2f degC" % tempC)
		print("Temperature:         %.2f degF" % tempF)
		print("Station Pressure:   ", station_pres, "mb")
		print("Sea Level Pressure:  %.2f mb" % slp)
		print("Sea Level Pressure:  %.2f inHg" % slp_hg)
		print()

		# Handle script output
		if which_sensor == "bmp":
			line = "%.2f %.2f %.2f %.2f" % (tempC, station_pres, slp, altitude)
		else:
			line = "%.2f %.2f %.2f %.2f %.2f" % (tempC, station_pres, slp, altitude, humidity)
		helper_functions.output(False, line, which_sensor)

		# Wait 10 seconds and repeat if in test mode
		if test_mode == "true":
			time.sleep(10)
		else:
			break

except Exception as e:
	if which_sensor:
		helper_functions.handleError(e, which_sensor)
	else:
		helper_functions.handleError(e, "bmp_bme")