#!/usr/bin/python3
# Code to control the Tinovi i2cArduino soil moisture sensor. Write observations to disk
# I2C address: 0x63
# Protocol mirrors the i2cArduino (SVCS3) library from Tinovi:
#   newReading: write REG_READ_START (0x01), wait 300ms
#   getData:    write REG_GET_DATA (0x09), read 8 bytes (4 x signed int16 LE)
#     bytes 0-1: E25  / 100.0  (dS/m, electrical conductivity at 25°C)
#     bytes 2-3: EC   / 10.0   (mS/m, raw electrical conductivity)
#     bytes 4-5: TEMP / 100.0  (°C)
#     bytes 6-7: VWC  / 10.0   (%, volumetric water content)
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time, struct
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import helper_functions

TSM_ADDRESS     = 0x63
REG_READ_START  = 0x01
REG_GET_DATA    = 0x09

def tinovi_soil_read(bus):
	bus.write_byte(TSM_ADDRESS, REG_READ_START)
	time.sleep(0.30)
	bus.read_byte(TSM_ADDRESS)  # discard state byte

	bus.write_byte(TSM_ADDRESS, REG_GET_DATA)
	time.sleep(0.01)
	raw = [bus.read_byte(TSM_ADDRESS) for _ in range(8)]

	e25  = struct.unpack_from('<h', bytes(raw[0:2]))[0] / 100.0
	ec   = struct.unpack_from('<h', bytes(raw[2:4]))[0] / 10.0
	tempC = struct.unpack_from('<h', bytes(raw[4:6]))[0] / 100.0
	vwc  = struct.unpack_from('<h', bytes(raw[6:8]))[0] / 10.0
	return e25, ec, tempC, vwc

try:
	import smbus2
	bus = smbus2.SMBus(1)

	# Verify sensor is present
	bus.write_byte(TSM_ADDRESS, REG_READ_START)
	time.sleep(0.30)
	bus.read_byte(TSM_ADDRESS)

	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1

	for x in range(0, iterations):
		e25, ec, tempC, vwc = tinovi_soil_read(bus)
		tempF = tempC * 1.8 + 32

		print("Tinovi Soil Moisture Sensor")
		print("EC @ 25C (e25):  %.2f dS/m"  % e25)
		print("Raw EC (ec):     %.2f mS/m"  % ec)
		print("Temperature:     %.2f degC"  % tempC)
		print("Temperature:     %.2f degF"  % tempF)
		print("VWC:             %.2f%%"      % vwc)
		print()

		line = "%.2f %.2f %.2f %.2f" % (e25, ec, tempC, vwc)
		helper_functions.output(False, line, "tinovi_soil")

		if test_mode == "true":
			time.sleep(10)
		else:
			break

except Exception as e:
	helper_functions.handleError(e, "tinovi_soil")
