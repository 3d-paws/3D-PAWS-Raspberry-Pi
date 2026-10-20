#!/usr/bin/python3
# Code to read Dallas DS18B20 temperature probes via DS2482S-800 8-channel I2C-to-1Wire bridge.
# Write observations to disk.
# DS2482S-800 I2C address: 0x1F
# Scans all 8 channels at startup; only channels with a detected probe are read each interval.
# Output line format: dst0=<T> dst1=<T> ... (only for channels that have a sensor)
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import helper_functions

DS2482_ADDR   = 0x1F

# DS2482-800 commands
DS2482_RESET  = 0xF0
DS2482_SRP    = 0xE1   # Set Read Pointer
DS2482_WCFG   = 0xD2   # Write Configuration
DS2482_CHSL   = 0xC3   # Channel Select
DS2482_1WRS   = 0xB4   # 1-Wire Reset
DS2482_1WWB   = 0xA5   # 1-Wire Write Byte
DS2482_1WRB   = 0x96   # 1-Wire Read Byte

# Status register read pointer and bit masks
DS2482_PTR_STATUS = 0xF0
DS2482_PTR_DATA   = 0xE1
DS2482_1WB        = 0x01   # 1-Wire Busy
DS2482_PPD        = 0x02   # Presence Pulse Detected

# Channel select byte lookup (index = channel number 0-7)
CHSL_BYTES = [0xF0, 0xE1, 0xD2, 0xC3, 0xB4, 0xA5, 0x96, 0x87]

# DS18B20 ROM commands
DS18B20_SKIP_ROM       = 0xCC
DS18B20_CONVERT_T      = 0x44
DS18B20_READ_SCRATCHPAD = 0xBE


def _read_status(bus):
	bus.write_byte_data(DS2482_ADDR, DS2482_SRP, DS2482_PTR_STATUS)
	return bus.read_byte(DS2482_ADDR)


def _wait_busy(bus, timeout=1.0):
	start = time.time()
	while time.time() - start < timeout:
		status = _read_status(bus)
		if not (status & DS2482_1WB):
			return status
		time.sleep(0.001)
	raise TimeoutError("DS2482 1-Wire busy timeout")


def _1wire_reset(bus):
	bus.write_byte(DS2482_ADDR, DS2482_1WRS)
	status = _wait_busy(bus)
	return bool(status & DS2482_PPD)


def _1wire_write(bus, byte_val):
	bus.write_byte_data(DS2482_ADDR, DS2482_1WWB, byte_val)
	_wait_busy(bus)


def _1wire_read(bus):
	bus.write_byte(DS2482_ADDR, DS2482_1WRB)
	_wait_busy(bus)
	bus.write_byte_data(DS2482_ADDR, DS2482_SRP, DS2482_PTR_DATA)
	return bus.read_byte(DS2482_ADDR)


def select_channel(bus, channel):
	bus.write_byte_data(DS2482_ADDR, DS2482_CHSL, CHSL_BYTES[channel])
	time.sleep(0.001)


def read_ds18b20(bus, channel):
	select_channel(bus, channel)
	if not _1wire_reset(bus):
		return None

	_1wire_write(bus, DS18B20_SKIP_ROM)
	_1wire_write(bus, DS18B20_CONVERT_T)
	time.sleep(0.75)   # Wait for 12-bit conversion

	_1wire_reset(bus)
	_1wire_write(bus, DS18B20_SKIP_ROM)
	_1wire_write(bus, DS18B20_READ_SCRATCHPAD)

	data = [_1wire_read(bus) for _ in range(9)]
	raw = (data[1] << 8) | data[0]
	if raw & 0x8000:
		raw -= 65536
	return raw / 16.0


def probe_channels(bus):
	"""Return list of channel indices that have a DS18B20 probe."""
	found = []
	for ch in range(8):
		try:
			select_channel(bus, ch)
			if _1wire_reset(bus):
				found.append(ch)
		except Exception:
			pass
	return found


try:
	import smbus2
	bus = smbus2.SMBus(1)

	# Reset DS2482
	bus.write_byte(DS2482_ADDR, DS2482_RESET)
	time.sleep(0.005)

	# Enable active pull-up (APU bit) in configuration register
	# Config byte: upper nibble = ~lower nibble, lower nibble = APU (0x01)
	cfg = 0x01
	bus.write_byte_data(DS2482_ADDR, DS2482_WCFG, (cfg | ((~cfg & 0x0F) << 4)))

	active_channels = probe_channels(bus)
	if not active_channels:
		raise RuntimeError("DS2482S-800: no DS18B20 probes found on any channel")

	print("DS18B20 probes found on channels: %s" % active_channels)

	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1

	for x in range(0, iterations):
		readings = {}
		for ch in active_channels:
			try:
				t = read_ds18b20(bus, ch)
				readings[ch] = t if t is not None else -999.9
			except Exception:
				readings[ch] = -999.9

		print("Dallas DS18B20 Sensors (via DS2482S-800)")
		for ch, t in readings.items():
			tF = t * 1.8 + 32 if t != -999.9 else -999.9
			print("  Channel %d:  %.2f degC  (%.2f degF)" % (ch, t, tF))
		print()

		line = " ".join("dst%d=%.2f" % (ch, t) for ch, t in readings.items())
		helper_functions.output(False, line, "ds18b20")

		if test_mode == "true":
			time.sleep(10)
		else:
			break

except Exception as e:
	helper_functions.handleError(e, "ds18b20")
