#!/usr/bin/python3
# Code to control the DFRobot B-LUX-V30B ambient light sensor. Write observations to disk
# I2C address: 0x4A. Read 4 bytes from register 0x00 (little-endian uint32), lux = raw * 1.4 / 1000
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time, struct
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import helper_functions

BLX_ADDRESS = 0x4A
BLX_REG_DATA = 0x00

# Point at the data register and read all 4 bytes in one transaction (repeated start), like the Particle firmware
def blx_read(bus):
	msg = smbus2.i2c_msg.read(BLX_ADDRESS, 4)
	bus.i2c_rdwr(smbus2.i2c_msg.write(BLX_ADDRESS, [BLX_REG_DATA]), msg)
	raw = struct.unpack_from('<I', bytes(list(msg)))[0]
	return (raw * 1.4) / 1000.0

import smbus2

try:
	bus = smbus2.SMBus(1)

	# Verify sensor is present
	bus.write_byte(BLX_ADDRESS, BLX_REG_DATA)

	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1

	for x in range(0, iterations):
		lux = blx_read(bus)

		print("B-LUX-V30B Sensor")
		print("Lux:  %.2f" % lux)
		print()

		line = "%.2f" % lux
		helper_functions.output(False, line, "b_lux_v30b")

		if test_mode == "true":
			time.sleep(10)
		else:
			break

except Exception as e:
	helper_functions.handleError(e, "b_lux_v30b")
