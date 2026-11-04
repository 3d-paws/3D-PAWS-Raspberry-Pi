#!/usr/bin/python3
# Code to control the Sensirion SHT45 (SHT4x series) temperature and humidity sensor, e.g. the Adafruit SHT45 breakout.
# Talks to the sensor directly with smbus2, so it needs no Adafruit SHT4x library (which would upgrade Blinka).
# I2C address 0x44. Command 0xFD = high precision, no heater; 6 bytes back: temperature, CRC, humidity, CRC.
# Write observations to disk.
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import helper_functions
from smbus2 import SMBus, i2c_msg

SHT45_ADDRESS = 0x44
MEASURE_HIGH_PRECISION = 0xFD


def crc8(data):
	crc = 0xFF
	for byte in data:
		crc ^= byte
		for _ in range(8):
			crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
	return crc


# Returns (temperature degC, relative humidity %)
def measure(bus):
	bus.write_byte(SHT45_ADDRESS, MEASURE_HIGH_PRECISION)
	time.sleep(0.01)
	msg = i2c_msg.read(SHT45_ADDRESS, 6)
	bus.i2c_rdwr(msg)
	d = list(msg)
	if crc8(d[0:2]) != d[2] or crc8(d[3:5]) != d[5]:
		raise IOError("SHT45 CRC error")
	tempC = -45 + 175 * ((d[0] << 8) | d[1]) / 65535.0
	rh = -6 + 125 * ((d[3] << 8) | d[4]) / 65535.0
	return tempC, min(100.0, max(0.0, rh))


try:
	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1

	with SMBus(1) as bus:
		for x in range(0, iterations):
			tempC, rh = measure(bus)
			tempF = tempC * 1.8 + 32

			print("SHT45 Sensor")
			print("Temperature:  %.2f degC" % tempC)
			print("Temperature:  %.2f degF" % tempF)
			print("Humidity:     %.2f%%" % rh)
			print()

			line = "sht45 %.2f %.2f" % (tempC, rh)
			helper_functions.output(False, line, "sht45")

			if test_mode == "true":
				time.sleep(10)
			else:
				break

except Exception as e:
	helper_functions.handleError(e, "sht45")
