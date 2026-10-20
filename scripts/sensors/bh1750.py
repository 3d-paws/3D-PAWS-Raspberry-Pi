#!/usr/bin/python3
# Code to control the DFRobot SEN0562 ambient light sensor (1-65535 lux, BH1750 chip). Write observations to disk
# Uses continuous high-resolution mode and lux = raw / 1.2, the same as the BH1750 library in the Particle firmware
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import helper_functions
from smbus2 import SMBus, i2c_msg

ADDRESSES = [0x23, 0x5C]       # 0x23 is the default; 0x5C when the ADDR pin is high
POWER_ON = 0x01
CONTINUOUS_HIGH_RES = 0x10


def findSensor(bus):
	for address in ADDRESSES:
		try:
			bus.write_byte(address, POWER_ON)
			return address
		except OSError:
			continue
	raise IOError("No BH1750 light sensor found at I2C address 0x23 or 0x5C")


def readLux(bus, address):
	msg = i2c_msg.read(address, 2)
	bus.i2c_rdwr(msg)
	data = list(msg)
	return ((data[0] << 8) | data[1]) / 1.2


try:
	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1

	with SMBus(1) as bus:
		address = findSensor(bus)
		bus.write_byte(address, CONTINUOUS_HIGH_RES)
		time.sleep(0.2)    # First measurement takes up to 180 ms

		for x in range(0, iterations):
			lux = readLux(bus, address)

			print("BH1750 (SEN0562) Light Sensor")
			print("Lux:  %.2f" % lux)
			print()

			line = "%.2f" % lux
			helper_functions.output(False, line, "bh1750")

			if test_mode == "true":
				time.sleep(10)
			else:
				break

except Exception as e:
	helper_functions.handleError(e, "bh1750")
