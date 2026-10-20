#!/usr/bin/python3
# Code to control the Bosch BMP581 barometric pressure and temperature sensor (e.g. Adafruit BMP581 breakout).
# Talks to the sensor registers directly with smbus2, so it needs no Adafruit BMP5xx library.
# Write observations to disk.
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import helper_functions
from smbus2 import SMBus

ADDRESSES = [0x47, 0x46]       # 0x47 is the Adafruit default; 0x46 when SDO is tied low
CHIP_IDS = [0x50, 0x51]        # BMP580/581, BMP585

# Registers (Bosch BMP581 datasheet)
REG_CHIP_ID = 0x01
REG_TEMP_DATA = 0x1D           # 3 bytes, XLSB first, signed, degC = raw / 65536
REG_PRESS_DATA = 0x20          # 3 bytes, XLSB first, unsigned, Pa = raw / 64
REG_STATUS = 0x28
REG_OSR_CONFIG = 0x36
REG_ODR_CONFIG = 0x37
REG_CMD = 0x7E
SOFT_RESET = 0xB6

# Pressure enabled, 16x pressure oversampling, 2x temperature oversampling (the same as the Particle firmware)
OSR_CONFIG = 0x40 | (0x04 << 3) | 0x01
# Deep standby disabled, forced mode: take one measurement then go back to standby
FORCED_MODE = 0x80 | 0x02


def findSensor(bus):
	for address in ADDRESSES:
		try:
			if bus.read_byte_data(address, REG_CHIP_ID) in CHIP_IDS:
				return address
		except OSError:
			continue
	raise IOError("No BMP581 found at I2C address 0x46 or 0x47")


def setup(bus, address):
	bus.write_byte_data(address, REG_CMD, SOFT_RESET)
	time.sleep(0.01)
	status = bus.read_byte_data(address, REG_STATUS)
	if not status & 0x02 or status & 0x04:
		raise IOError("BMP581 not ready after reset (status 0x%02X)" % status)
	bus.write_byte_data(address, REG_OSR_CONFIG, OSR_CONFIG)


# Returns (temperature degC, pressure hPa)
def measure(bus, address):
	bus.write_byte_data(address, REG_ODR_CONFIG, FORCED_MODE)
	time.sleep(0.1)
	t = bus.read_i2c_block_data(address, REG_TEMP_DATA, 3)
	p = bus.read_i2c_block_data(address, REG_PRESS_DATA, 3)
	raw_t = (t[2] << 16) | (t[1] << 8) | t[0]
	if raw_t & 0x800000:
		raw_t -= 1 << 24
	raw_p = (p[2] << 16) | (p[1] << 8) | p[0]
	return raw_t / 65536.0, raw_p / 64.0 / 100.0


try:
	variables = helper_functions.getVariables()
	test_mode    = variables[0]
	pressure_level = variables[3]
	altitude       = variables[4]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1

	with SMBus(1) as bus:
		address = findSensor(bus)
		setup(bus, address)

		for x in range(0, iterations):
			tempC, pressure = measure(bus, address)
			slp      = pressure * pow(1 - (0.0065 * altitude) / (tempC + 0.0065 * altitude + 273.15), -5.257)
			tempF    = tempC * 1.8 + 32
			slp_hg   = slp / 33.86389

			print("BMP581 Sensor")
			print("Temperature:         %.2f degC" % tempC)
			print("Temperature:         %.2f degF" % tempF)
			print("Station Pressure:    %.2f hPa"  % pressure)
			print("Sea Level Pressure:  %.2f hPa"  % slp)
			print("Sea Level Pressure:  %.2f inHg" % slp_hg)
			print()

			line = "bmp581 %.2f %.2f %.2f %.2f" % (tempC, pressure, slp, altitude)
			helper_functions.output(False, line, "bmp581")

			if test_mode == "true":
				time.sleep(10)
			else:
				break

except Exception as e:
	helper_functions.handleError(e, "bmp581")
