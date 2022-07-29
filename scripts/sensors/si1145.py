#!/usr/bin/python3
# Code to control the tipping bucket rain gauge. Write observations to disk
# Paul A. Kucera, Ph.D. and Joseph E. Rener
# UCAR
# Boulder, CO USA
# Email: pkucera@ucar.edu and jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

# Adpated from Joe Gutting Adafruit SI1145 library for Arduino, Adafruit_GPIO.I2C & BMP Library by Tony DiCola
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

import SI1145.SI1145 as SI1145, helper_functions

try:
	# Assign variable to sensor name
	sensor = SI1145.SI1145()

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
		# Run the code
		vis = sensor.readVisible()
		IR = sensor.readIR()
		UV = sensor.readUV()
		uvIndex = UV / 100.0

		# Print to screen
		print("SI1145 Sensor")
		print("Vis:       ", vis)
		print("IR:        ", IR)
		print("UV Index:  ", uvIndex)
		print()

		# Handle script output
		line = "%.2f %.2f %.2f" % (vis, IR, UV)
		helper_functions.output(False, line, "si1145")

		iterations += 1
		if test_mode == "true":
			time.sleep(wait)

except Exception as e:
	helper_functions.handleError(e, "si1145")
