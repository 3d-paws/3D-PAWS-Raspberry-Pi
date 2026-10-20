#!/usr/bin/python3
# Code to control the Tinovi i2cMultiSm multi-depth soil moisture sensor. Write observations to disk
# I2C address: 0x65
# Protocol mirrors the i2cMultiArd (SVMULTI) library from Tinovi:
#   newReading: write REG_READ_START (0x01), wait 300ms
#   getData:    write REG_GET_DATA (0x09), read 14 bytes
#     struct layout (little-endian int16):
#       bytes  0- 3: temp[0], temp[1]  → / 100.0  (°C)
#       bytes  4-13: dp[0]..dp[4]      → / 100.0  (raw dielectric permittivity)
#     VWC conversion: (4.3e-6 * dp^3 - 5.5e-4 * dp^2 + 2.92e-2 * dp - 5.3e-2) * 100
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time, struct
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import helper_functions

TMSM_ADDRESS    = 0x65
REG_READ_START  = 0x01
REG_GET_DATA    = 0x09
MULTI_TEMPS     = 2
MULTI_ZONES     = 5

def dp_to_vwc(dp):
	return (4.3e-6 * dp**3 - 5.5e-4 * dp**2 + 2.92e-2 * dp - 5.3e-2) * 100.0

def tinovi_multi_read(bus):
	bus.write_byte(TMSM_ADDRESS, REG_READ_START)
	time.sleep(0.30)
	bus.read_byte(TMSM_ADDRESS)  # discard state byte

	bus.write_byte(TMSM_ADDRESS, REG_GET_DATA)
	time.sleep(0.01)
	raw = [bus.read_byte(TMSM_ADDRESS) for _ in range(14)]

	temps = [struct.unpack_from('<h', bytes(raw[i*2:(i*2)+2]))[0] / 100.0
	         for i in range(MULTI_TEMPS)]
	dps   = [struct.unpack_from('<h', bytes(raw[(MULTI_TEMPS*2)+(i*2):(MULTI_TEMPS*2)+(i*2)+2]))[0] / 100.0
	         for i in range(MULTI_ZONES)]
	vwcs  = [dp_to_vwc(dp) for dp in dps]
	return temps, vwcs

try:
	import smbus2
	bus = smbus2.SMBus(1)

	# Verify sensor is present
	bus.write_byte(TMSM_ADDRESS, REG_READ_START)
	time.sleep(0.30)
	bus.read_byte(TMSM_ADDRESS)

	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1

	for x in range(0, iterations):
		temps, vwcs = tinovi_multi_read(bus)

		print("Tinovi Multi-Soil Moisture Sensor")
		for i, t in enumerate(temps):
			print("Temperature %d:  %.2f degC  (%.2f degF)" % (i+1, t, t*1.8+32))
		for i, v in enumerate(vwcs):
			print("VWC zone %d:     %.2f%%" % (i+1, v))
		print()

		temp_str = " ".join("%.2f" % t for t in temps)
		vwc_str  = " ".join("%.2f" % v for v in vwcs)
		line = temp_str + " " + vwc_str
		helper_functions.output(False, line, "tinovi_multi_soil")

		if test_mode == "true":
			time.sleep(10)
		else:
			break

except Exception as e:
	helper_functions.handleError(e, "tinovi_multi_soil")
