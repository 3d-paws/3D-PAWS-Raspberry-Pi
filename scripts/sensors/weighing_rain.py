#!/usr/bin/python3
# Code to control a weighing rain gauge built on the DFRobot Gravity HX711 I2C weight sensor (KIT0176). Write observations to disk
# Samples the weight every second and reports the grams of water gained since the last report, like the Particle
# SensorTesting firmware. A sudden drop of 100 g or more is treated as the gauge emptying (tipping), not negative rain.
# The baseline is saved between runs so no rain is lost while cron restarts the script.
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time, os, json, struct, math
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import helper_functions
from smbus2 import SMBus, i2c_msg

ADDRESSES = [0x64, 0x65, 0x66, 0x67]   # Set with the A0/A1 switches on the sensor; the first one found is used
STATE_FILE = "/home/pi/data/weighing_rain_state.json"
DEFAULT_CALIBRATION = 2210.0           # DFRobot's default counts per gram, used if the board has no calibration stored

TIP_DROP_G = 100.0     # A drop at least this large means the gauge emptied
NOISE_FLOOR_G = 0.5    # Smaller increases are treated as sensor flutter
MIN_G = 0.0            # Readings outside this range are ignored
MAX_G = 1000.0

# HX711 board registers
REG_GET_RAW = 0x66
REG_GET_CALIBRATION = 0x67
REG_GET_PEEL_FLAG = 0x69
REG_CLEAR_STATE = 0x65
REG_INIT = 0x70


def readReg(bus, address, reg, length):
	bus.i2c_rdwr(i2c_msg.write(address, [reg]))
	time.sleep(0.022)
	msg = i2c_msg.read(address, length)
	bus.i2c_rdwr(msg)
	return list(msg)


def readRaw(bus, address):
	data = readReg(bus, address, REG_GET_RAW, 4)
	if data[0] != 0x12:
		return None
	return ((data[1] << 16) | (data[2] << 8) | data[3]) ^ 0x800000


# Average of several raw readings, like the DFRobot library
def averageRaw(bus, address, times=12):
	values = [v for v in (readRaw(bus, address) for _ in range(times)) if v is not None]
	return sum(values) / len(values) if values else None


def readCalibration(bus, address):
	value = struct.unpack('>f', bytes(readReg(bus, address, REG_GET_CALIBRATION, 4)))[0]
	return value if math.isfinite(value) and value > 0 else DEFAULT_CALIBRATION


# 1 = the tare (peel) button was pressed, 2 = the board was recalibrated with its CAL button
def peelFlag(bus, address):
	flag = readReg(bus, address, REG_GET_PEEL_FLAG, 1)[0]
	return 1 if flag in (0x01, 129) else 2 if flag == 0x02 else 0


def findSensor(bus):
	for address in ADDRESSES:
		try:
			bus.i2c_rdwr(i2c_msg.write(address, [REG_INIT, REG_CLEAR_STATE]))
			if readRaw(bus, address) is not None:
				return address
		except OSError:
			continue
	raise IOError("No HX711 weight sensor found at I2C addresses 0x64-0x67")


def loadState(test):
	# Test runs start fresh so they never disturb the saved baseline used for recording
	if not test and os.path.exists(STATE_FILE):
		try:
			with open(STATE_FILE) as f:
				return json.load(f)
		except ValueError:
			pass
	return None


def saveState(state, test):
	if not test:
		with open(STATE_FILE, 'w') as f:
			json.dump(state, f)


# Weight in grams relative to the saved zero point
def grams(bus, address, state):
	raw = averageRaw(bus, address)
	if raw is None:
		return None
	return (raw - state["zero_raw"]) / state["calibration"]


def newState(bus, address):
	zero = averageRaw(bus, address, 20)
	return {"zero_raw": zero, "calibration": readCalibration(bus, address), "baseline": 0.0, "last": 0.0, "pending": 0.0}


# Once a second: track increases and catch the gauge emptying (dfrwrg_TipCheck in the firmware)
def tipCheck(bus, address, state, flutter):
	flag = peelFlag(bus, address)
	if flag == 1:
		# Tare button pressed: start over from the current weight
		state.update(newState(bus, address))
		flutter[:] = []
		return
	if flag == 2:
		state["calibration"] = readCalibration(bus, address)
	reading = grams(bus, address, state)
	if reading is None or reading > MAX_G:
		return
	delta = reading - state["last"]
	if delta <= -TIP_DROP_G:
		# The gauge emptied: count what had collected since the baseline
		if state["last"] > state["baseline"]:
			state["pending"] += state["last"] - state["baseline"]
		print("Gauge emptied: %.2f g of rain counted before the drop" % state["pending"])
		if reading < MIN_G:
			# Emptied below the starting zero point (it was set with water in the gauge): re-zero here
			pending = state["pending"]
			state.update(newState(bus, address))
			state["pending"] = pending
		else:
			state["baseline"] = reading
			state["last"] = reading
		flutter[:] = []
		return
	if reading < MIN_G:
		return
	flutter.append(reading - state["baseline"])
	if delta >= NOISE_FLOOR_G:
		state["last"] = reading


# End of the interval: rain since the last report, then reset the baseline (dfrwrg_read in the firmware)
def report(bus, address, state, flutter):
	reading = grams(bus, address, state)
	if reading is None:
		return None
	if reading > state["baseline"]:
		delta = reading - state["baseline"]
		median = sorted(flutter)[len(flutter) // 2] if flutter else 0.0
		if delta <= NOISE_FLOOR_G and median <= 0.15:
			delta = 0.0
		state["pending"] += delta
	rain = state["pending"]
	state["baseline"] = reading
	state["last"] = reading
	state["pending"] = 0.0
	return rain


try:
	test, rest, iterations = helper_functions.getTest()
	# Finish a few seconds before the next cron run starts so two runs never share the saved baseline
	if not test:
		rest = max(10, rest - 4)

	with SMBus(1) as bus:
		address = findSensor(bus)
		state = loadState(test)
		if state is None:
			state = newState(bus, address)
			print("Weighing rain gauge: new zero point set; rain is counted from now")
		for x in range(0, iterations):
			flutter = []
			end = time.time() + rest
			while time.time() < end:
				tipCheck(bus, address, state, flutter)
				time.sleep(1)
			rain = report(bus, address, state, flutter)
			saveState(state, test)
			if rain is None:
				print("Weighing rain gauge: no valid reading")
				continue

			print("Weighing Rain Gauge")
			print("Rain since last report:  %.2f g" % rain)
			print("Current weight:          %.2f g" % state["last"])
			print()

			line = "%.2f" % rain
			helper_functions.output(False, line, "weighing_rain")

except Exception as e:
	helper_functions.handleError(e, "weighing_rain")
