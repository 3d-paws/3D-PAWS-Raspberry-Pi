#!/usr/bin/python3
# Code to control the Tinovi LeafSens leaf wetness and temperature sensor. Write observations to disk
# I2C address: 0x61
# Protocol mirrors the LeafArduinoI2c library from Tinovi:
#   newReading: write REG_READ_ST (0x01), wait 200ms
#   getWet:     write REG_WET (0x05), read 2 bytes as signed int16 LE, divide by 100.0
#   getTemp:    write REG_TEMP (0x04), read 2 bytes as signed int16 LE, divide by 100.0
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time, struct
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import helper_functions

TLW_ADDRESS   = 0x61
REG_READ_ST   = 0x01
REG_TEMP      = 0x04
REG_WET       = 0x05

def tinovi_read_reg(bus, addr, reg, nbytes, delay_s=0.01):
	bus.write_byte(addr, reg)
	time.sleep(delay_s)
	return [bus.read_byte(addr) for _ in range(nbytes)]

def tinovi_leaf_read(bus):
	# Trigger new reading
	bus.write_byte(TLW_ADDRESS, REG_READ_ST)
	time.sleep(0.20)
	bus.read_byte(TLW_ADDRESS)  # discard state byte

	raw_wet  = tinovi_read_reg(bus, TLW_ADDRESS, REG_WET,  2)
	raw_temp = tinovi_read_reg(bus, TLW_ADDRESS, REG_TEMP, 2)

	wetness = struct.unpack_from('<h', bytes(raw_wet))[0]  / 100.0
	tempC   = struct.unpack_from('<h', bytes(raw_temp))[0] / 100.0
	return wetness, tempC

try:
	import smbus2
	bus = smbus2.SMBus(1)

	# Verify sensor is present
	bus.write_byte(TLW_ADDRESS, REG_READ_ST)
	time.sleep(0.20)
	bus.read_byte(TLW_ADDRESS)

	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1

	for x in range(0, iterations):
		wetness, tempC = tinovi_leaf_read(bus)
		tempF = tempC * 1.8 + 32

		print("Tinovi LeafSens Sensor")
		print("Leaf Wetness:  %.2f" % wetness)
		print("Temperature:   %.2f degC" % tempC)
		print("Temperature:   %.2f degF" % tempF)
		print()

		line = "%.2f %.2f" % (wetness, tempC)
		helper_functions.output(False, line, "tinovi_leaf")

		if test_mode == "true":
			time.sleep(10)
		else:
			break

except Exception as e:
	helper_functions.handleError(e, "tinovi_leaf")
