#!/usr/bin/python3
# Code to control DFRobot MultiGasSensor probes (O2, CO, H2S, NO2, O3, CL2, NH3, H2, HCL, SO2, HF, PH3). Write observations to disk
# Finds every gas sensor at I2C addresses 0x74-0x77 and reports the average of 1 second samples over the recording interval,
# with DFRobot's temperature compensation, like the Particle SensorTesting firmware
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time, math
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import helper_functions
from smbus2 import SMBus

ADDRESSES = [0x74, 0x75, 0x76, 0x77]   # Set with the A0/A1 switches on the sensor

# Sensor command codes
CHANGE_ACQUIRE_MODE = 0x78
PASSIVE_MODE = 0x04
GET_GAS_CONCENTRATION = 0x86
GET_TEMP = 0x87

# Gas type byte reported by the sensor -> name used in tags and files
GAS_TYPES = {0x05: "o2", 0x04: "co", 0x03: "h2s", 0x2C: "no2", 0x2A: "o3", 0x31: "cl2",
	0x02: "nh3", 0x06: "h2", 0x2E: "hcl", 0x2B: "so2", 0x33: "hf", 0x45: "ph3"}


# Two's complement of the sum of bytes 1-6
def checksum(frame):
	return (~sum(frame[1:7]) + 1) & 0xFF


# Send a 9 byte command frame and read the 9 byte reply; None if the reply fails its checksum
def transfer(bus, address, cmd, arg=0x00):
	frame = [0xFF, 0x01, cmd, arg, 0, 0, 0, 0, 0]
	frame[8] = checksum(frame)
	bus.write_i2c_block_data(address, 0, frame)
	time.sleep(0.1)
	reply = bus.read_i2c_block_data(address, 0, 9)
	return reply if checksum(reply) == reply[8] else None


# Onboard thermistor reading in degrees C
def readTemp(bus, address):
	reply = transfer(bus, address, GET_TEMP)
	adc = (reply[2] << 8) + reply[3]
	volts = 3 * adc / 1024.0
	resistance = volts * 10000 / (3 - volts)
	return 1 / (1 / (273.15 + 25) + 1 / 3380.13 * math.log(resistance / 10000)) - 273.15


# DFRobot's temperature compensation (from their library); None when the temperature is outside the compensated range
def compensate(gas, con, t):
	if gas == "o2":
		return con
	if gas == "co":
		if -20 < t <= 20: return con / (0.005 * t + 0.9)
		if 20 < t <= 40: return con / (0.005 * t + 0.9) - (0.3 * t - 6)
	elif gas == "h2s":
		if -20 < t <= 20: return con / (0.005 * t + 0.92)
		if 20 < t <= 60: return con / (0.015 * t - 0.3)
	elif gas == "no2":
		if -20 < t <= 0: return con / (0.005 * t + 0.9) - (-0.0025 * t + 0.005)
		if 0 < t <= 20: return con / (0.005 * t + 0.9) - (0.005 * t + 0.005)
		if 20 < t <= 40: return con / (0.005 * t + 0.9) - (0.0025 * t + 0.1)
	elif gas == "o3":
		if -20 < t <= 0: return con / (0.015 * t + 1.1) - 0.05
		if 0 < t <= 20: return con / 1.1 - 0.01 * t
		if 20 < t <= 40: return con / 1.1 - (-0.005 * t + 0.3)
	elif gas == "cl2":
		if -20 < t <= 0: return con / (0.015 * t + 1.1) - (-0.0025 * t)
		if 0 < t <= 20: return con / 1.1 - 0.005 * t
		if 20 < t <= 40: return con / 1.1 - (-0.005 * t + 0.3)
	elif gas == "nh3":
		if -20 < t <= 0: return con / (0.006 * t + 0.95) - (-0.006 * t + 0.25)
		if 0 < t <= 20: return con / (0.006 * t + 0.95) - (-0.012 * t + 0.25)
		if 20 < t <= 40: return con / (0.005 * t + 1.08) - (-0.1 * t + 2)
	elif gas == "h2":
		if -20 < t <= 20: return con / (0.74 * t + 0.007) - 5
		if 20 < t <= 40: return con / (0.025 * t + 0.3) - 5
		if 40 < t <= 60: return con / (0.001 * t + 0.9) - (0.75 * t - 25)
	elif gas == "hf":
		if -20 < t <= 0: return con - (-0.0025 * t)
		if 0 < t <= 20: return con + 0.1
		if 20 < t <= 40: return con - (0.0375 * t - 0.85)
	elif gas == "ph3":
		if -20 < t <= 40: return con / (0.005 * t + 0.9)
	elif gas == "hcl":
		if -20 < t <= 0: return con - (-0.0075 * t - 0.1)
		if 0 < t <= 20: return con + 0.1
		if 20 < t < 50: return con - (-0.01 * t + 0.1)
	elif gas == "so2":
		if -40 < t <= 40: return con / (0.006 * t + 0.95)
		if 40 < t <= 60: return con / (0.006 * t + 0.95) - (0.05 * t - 2)
	return None


# Returns (gas name, compensated concentration) or None if the reading failed
def readGas(bus, address):
	reply = transfer(bus, address, GET_GAS_CONCENTRATION)
	if reply is None:
		return None
	con = float((reply[2] << 8) + reply[3]) * {0: 1.0, 1: 0.1, 2: 0.01}.get(reply[5], 1.0)
	gas = GAS_TYPES.get(reply[4])
	if gas is None:
		return None
	value = compensate(gas, con, readTemp(bus, address))
	if value is None:
		return gas, None
	return gas, max(0.0, value)


# Find gas sensors and switch them to answer-on-request mode
def findSensors(bus):
	sensors = []
	for address in ADDRESSES:
		try:
			reply = transfer(bus, address, CHANGE_ACQUIRE_MODE, PASSIVE_MODE)
			reading = readGas(bus, address)
		except OSError:
			continue
		if reply is not None and reading is not None:
			sensors.append(address)
	return sensors


try:
	test, rest, iterations = helper_functions.getTest()
	# Finish a few seconds before the next cron run starts
	if not test:
		rest = max(10, rest - 4)

	with SMBus(1) as bus:
		addresses = findSensors(bus)
		if not addresses:
			raise IOError("No DFRobot gas sensors found at I2C addresses 0x74-0x77")
		for x in range(0, iterations):
			samples = {}
			end = time.time() + rest
			while time.time() < end:
				for address in addresses:
					try:
						reading = readGas(bus, address)
					except OSError:
						continue
					if reading and reading[1] is not None:
						samples.setdefault(reading[0], []).append(reading[1])
				time.sleep(1)
			if not samples:
				print("Gas sensors: no valid readings (temperature may be outside the compensated range)")
				continue

			print("DFRobot Gas Sensors (average over %d s)" % rest)
			averages = {}
			for gas in helper_functions.MULTIGAS_GASES:
				if gas in samples:
					averages[gas] = sum(samples[gas]) / len(samples[gas])
					print("%-4s %8.2f %s" % (gas.upper(), averages[gas], "%vol" if gas == "o2" else "ppm"))
			print()

			line = " ".join("%s=%.2f" % (gas, value) for gas, value in averages.items())
			helper_functions.output(False, line, "multigas")

except Exception as e:
	helper_functions.handleError(e, "multigas")
