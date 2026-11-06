# Sensirion SHT31 (SHT3x) temperature and humidity, I2C 0x44, or 0x45 with the ADR pin high
# Use 0x45 when an SHT45 (fixed at 0x44) is on the same bus.
# Command 0x2400: single shot, high repeatability, no clock stretching, up to 15.5 ms
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import time
from . import i2c_util


class SHT31:
	NAME = "SHT31"
	ADDRESSES = (0x44, 0x45)
	QUANTITIES = ("temp_c", "rh_pct")

	def __init__(self, bus, address=0x45):
		self.bus, self.address = bus, address
		self.read()

	def read(self):
		self.bus.write_byte_data(self.address, 0x24, 0x00)
		time.sleep(0.016)
		t, rh = i2c_util.check_words(i2c_util.read_bytes(self.bus, self.address, 6))
		return {"temp_c": -45 + 175 * t / 65535.0,
		        "rh_pct": min(100.0, max(0.0, 100 * rh / 65535.0))}
