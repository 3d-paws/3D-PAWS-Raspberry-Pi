# Sensirion SHT45 (SHT4x) temperature and humidity, I2C 0x44 (0x45 and 0x46 on other SHT4x part numbers)
# An SHT31 can also be at 0x44, so the chip is identified (serial number read) before it is used.
# Command 0xFD: high precision, no heater, about 9 ms; reply = temperature word + CRC, humidity word + CRC
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import time
from . import i2c_util


class SHT45:
	NAME = "SHT45"
	ADDRESSES = (0x44, 0x45, 0x46)
	QUANTITIES = ("temp_c", "rh_pct")

	def __init__(self, bus, address=0x44):
		self.bus, self.address = bus, address
		family = i2c_util.sht_family(bus, address)
		if family != "sht4x":
			raise IOError("not an SHT45" + (" (an SHT3x answered)" if family else ""))
		self.read()

	def read(self):
		self.bus.write_byte(self.address, 0xFD)
		time.sleep(0.01)
		t, rh = i2c_util.check_words(i2c_util.read_bytes(self.bus, self.address, 6))
		return {"temp_c": -45 + 175 * t / 65535.0,
		        "rh_pct": min(100.0, max(0.0, -6 + 125 * rh / 65535.0))}
