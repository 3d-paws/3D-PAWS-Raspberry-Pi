#!/usr/bin/python3
# Code to control the Honeywell HIH8000 temperature and humidity sensor. Write observations to disk
# I2C address: 0x27. Protocol: write 0x00 to trigger measurement, read 4 bytes.
# Bytes 0-1: humidity (14-bit, mask 0x3FFF), scale = raw * 6.10e-3
# Bytes 2-3: temperature (14-bit, shift right 2), scale = raw * 1.007e-2 - 40.0
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import helper_functions

HIH8000_ADDRESS = 0x27

def hih8000_read(bus):
	bus.write_byte(HIH8000_ADDRESS, 0x00)
	time.sleep(0.05)
	data = [bus.read_byte(HIH8000_ADDRESS) for _ in range(4)]

	humidity_raw = ((data[0] << 8) | data[1]) & 0x3FFF
	temp_raw     = ((data[2] << 8) | data[3]) >> 2

	rh    = humidity_raw * 6.10e-3
	tempC = temp_raw * 1.007e-2 - 40.0
	return tempC, rh

try:
	import smbus2
	bus = smbus2.SMBus(1)

	# Verify sensor is present
	bus.write_byte(HIH8000_ADDRESS, 0x00)

	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1

	for x in range(0, iterations):
		tempC, rh = hih8000_read(bus)
		tempF = tempC * 1.8 + 32

		print("HIH8000 Sensor")
		print("Temperature:  %.2f degC" % tempC)
		print("Temperature:  %.2f degF" % tempF)
		print("Humidity:     %.2f%%" % rh)
		print()

		line = "%.2f %.2f" % (tempC, rh)
		helper_functions.output(False, line, "hih8000")

		if test_mode == "true":
			time.sleep(10)
		else:
			break

except Exception as e:
	helper_functions.handleError(e, "hih8000")
