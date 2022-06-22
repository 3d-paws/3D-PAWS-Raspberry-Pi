#!/usr/bin/python
# Code to control the BMP280 and BME280 I2C sensors. Write observations to disk
# and to web in intervals determined by input.txt
# Paul A. Kucera, Ph.D. and Joseph E. Rener
# NCAR/RAL
# Boulder, CO USA
# Email: pkucera@ucar.edu and jrener@ucar.edu
# Copyright (c) 2022 UCAR
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import board, busio, helper_functions

try:
	#Get arguments
	arguments = helper_functions.getArguments()
	wait = arguments[0]
	pressure_level = arguments[5]
	test_mode = arguments[6]
	altitude = arguments[7]

	#Initialize correct sensor
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

	#Handle test mode
	target = 1
	if test_mode == "true":
		target = (60/wait)-1
		import time

	iterations = 0
	while iterations < target:
		#Get and calculate data
		if which_sensor == "bmp":
			bmp.sea_level_pressure = pressure_level
			tempC = bmp.temperature
			pressure = bmp.pressure
		else:
			altitude = arguments[5]
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

		iterations += 1
		if test_mode == "true":
			time.sleep(wait)

except Exception as e:
	if which_sensor:
		helper_functions.handleError(e, which_sensor)
	else:
		helper_functions.handleError(e, "bmp_bme")