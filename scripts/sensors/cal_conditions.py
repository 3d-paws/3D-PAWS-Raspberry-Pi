#!/usr/bin/python3
# Laboratory conditions for the rain gauge calibration (dyn_rain_cal.py), WMO-No. 8 Annex 6.A:
# water temperature (DS18B20 on a 1-Wire bridge), air temperature and humidity (SHT45), pressure (BMP581).
# Raw I2C with smbus2, so it doesn't depend on the Adafruit library versions on the station.
# The station's own ds18b20.py and bmp581.py start logging when imported, so their register code is repeated here.
# Any sensor that is missing or fails reads as None; the calibration then records it as not measured.
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import datetime as dt, time

# 1-Wire bridges for the water temperature probe, tried in this order. The DS2482S-800 has 8 channels;
# the Adafruit DS2484 (planned replacement) has one and no channel select. The DS2484 entry is untested.
BRIDGES = [("DS2482S-800", 0x1F, True), ("DS2484", 0x18, False)]
WATER_CHANNEL = None       # DS2482S-800 channel of the water probe; None = the first channel with a probe

SHT45_ADDRESS = 0x44
BMP581_ADDRESSES = [0x47, 0x46]

# 1-Wire bridge commands (the same on the DS2482 family and the DS2484)
OW_RESET_BRIDGE = 0xF0
OW_SET_POINTER = 0xE1
OW_WRITE_CONFIG = 0xD2
OW_CHANNEL_SELECT = 0xC3   # DS2482S-800 only
OW_RESET = 0xB4
OW_WRITE_BYTE = 0xA5
OW_READ_BYTE = 0x96
PTR_STATUS = 0xF0
PTR_DATA = 0xE1
STATUS_BUSY = 0x01
STATUS_PRESENCE = 0x02
CHANNEL_CODES = [0xF0, 0xE1, 0xD2, 0xC3, 0xB4, 0xA5, 0x96, 0x87]


class OneWireBridge:
	def __init__(self, bus, name, address, channels):
		self.bus, self.name, self.address, self.channels = bus, name, address, channels
		self.bus.write_byte(address, OW_RESET_BRIDGE)
		time.sleep(0.005)
		cfg = 0x01                                   # active pull-up
		self.bus.write_byte_data(address, OW_WRITE_CONFIG, cfg | ((~cfg & 0x0F) << 4))
		self.channel = None
		if channels:
			found = [ch for ch in range(8) if self._select(ch) and self._reset()]
			if not found:
				raise IOError("%s: no DS18B20 on any channel" % name)
			self.channel = WATER_CHANNEL if WATER_CHANNEL is not None else found[0]
		elif not self._reset():
			raise IOError("%s: no DS18B20 found" % name)

	def _status(self):
		self.bus.write_byte_data(self.address, OW_SET_POINTER, PTR_STATUS)
		return self.bus.read_byte(self.address)

	def _wait(self):
		end = time.monotonic() + 1.0
		while time.monotonic() < end:
			status = self._status()
			if not status & STATUS_BUSY:
				return status
			time.sleep(0.001)
		raise IOError("%s: 1-Wire busy timeout" % self.name)

	def _select(self, channel):
		try:
			self.bus.write_byte_data(self.address, OW_CHANNEL_SELECT, CHANNEL_CODES[channel])
			time.sleep(0.001)
			return True
		except OSError:
			return False

	def _reset(self):
		self.bus.write_byte(self.address, OW_RESET)
		return bool(self._wait() & STATUS_PRESENCE)

	def _write(self, byte):
		self.bus.write_byte_data(self.address, OW_WRITE_BYTE, byte)
		self._wait()

	def _read(self):
		self.bus.write_byte(self.address, OW_READ_BYTE)
		self._wait()
		self.bus.write_byte_data(self.address, OW_SET_POINTER, PTR_DATA)
		return self.bus.read_byte(self.address)

	def temperature(self):
		"""One DS18B20 reading in degC (12-bit, about 0.75 s)."""
		if self.channels:
			self._select(self.channel)
		if not self._reset():
			raise IOError("%s: probe not answering" % self.name)
		self._write(0xCC)                            # skip ROM
		self._write(0x44)                            # convert
		time.sleep(0.75)
		self._reset()
		self._write(0xCC)
		self._write(0xBE)                            # read scratchpad
		data = [self._read() for _ in range(9)]
		raw = (data[1] << 8) | data[0]
		if raw & 0x8000:
			raw -= 65536
		return raw / 16.0


def sht4x_crc(data):
	crc = 0xFF
	for byte in data:
		crc ^= byte
		for _ in range(8):
			crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
	return crc


class Conditions:
	"""Reads whichever of the sensors are present. read() returns a dict with None for anything missing."""

	def __init__(self, bus_number=1):
		from smbus2 import SMBus
		self.bus = SMBus(bus_number)
		self.water = None
		self.water_name = None
		for name, address, channels in BRIDGES:
			try:
				self.water = OneWireBridge(self.bus, name, address, channels)
				self.water_name = name + (" channel %d" % self.water.channel if channels else "")
				break
			except (IOError, OSError):
				continue
		self.bmp = None
		for address in BMP581_ADDRESSES:
			try:
				if self.bus.read_byte_data(address, 0x01) in (0x50, 0x51):
					self.bus.write_byte_data(address, 0x7E, 0xB6)      # soft reset
					time.sleep(0.01)
					self.bus.write_byte_data(address, 0x36, 0x40 | (0x04 << 3) | 0x01)
					self.bmp = address
					break
			except OSError:
				continue

	def water_c(self):
		try:
			return round(self.water.temperature(), 3) if self.water else None
		except (IOError, OSError):
			return None

	def sht45(self):
		"""(degC, %RH) in high precision mode, or (None, None)."""
		from smbus2 import i2c_msg
		try:
			self.bus.write_byte(SHT45_ADDRESS, 0xFD)
			time.sleep(0.01)
			msg = i2c_msg.read(SHT45_ADDRESS, 6)
			self.bus.i2c_rdwr(msg)
			d = list(msg)
			if sht4x_crc(d[0:2]) != d[2] or sht4x_crc(d[3:5]) != d[5]:
				return None, None
			t = -45 + 175 * ((d[0] << 8) | d[1]) / 65535.0
			rh = min(100.0, max(0.0, -6 + 125 * ((d[3] << 8) | d[4]) / 65535.0))
			return round(t, 2), round(rh, 1)
		except OSError:
			return None, None

	def pressure_hpa(self):
		if self.bmp is None:
			return None
		try:
			self.bus.write_byte_data(self.bmp, 0x37, 0x80 | 0x02)  # forced mode, one measurement
			time.sleep(0.1)
			p = self.bus.read_i2c_block_data(self.bmp, 0x20, 3)
			return round(((p[2] << 16) | (p[1] << 8) | p[0]) / 64.0 / 100.0, 2)
		except OSError:
			return None

	def read(self, label=""):
		air, rh = self.sht45()
		return {"label": label, "time": dt.datetime.now().isoformat(timespec="seconds"),
		        "water_c": self.water_c(), "air_c": air, "rh_pct": rh, "pressure_hpa": self.pressure_hpa()}
