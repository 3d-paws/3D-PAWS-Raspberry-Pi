#!/usr/bin/python3
# Code to control the tipping bucket rain gauge. Write observations to disk
# Paul A. Kucera, Ph.D. and Joseph Rener
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

import sys, time
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import SI1145.SI1145 as SI1145, helper_functions

try:
	# Assign variable to sensor name
	sensor = SI1145.SI1145()

	#Get arguments
	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1 # runs every 10 seconds over the interval, minus the last 10 seconds

	# Run once... or if in test mode, run every 10 seconds during the interval
	for x in range (0,iterations):
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

		# Wait 10 seconds and repeat if in test mode
		if test_mode == "true":
			time.sleep(10)
		else:
			break

except Exception as e:
	helper_functions.handleError(e, "si1145")
