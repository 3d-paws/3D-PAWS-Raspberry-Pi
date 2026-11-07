# Bosch BMP581 pressure and temperature, I2C 0x47 (Adafruit default) or 0x46 (SDO to GND)
# Same register settings as the station's bmp581.py: 16x pressure, 2x temperature oversampling, forced mode
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import time

REG_CHIP_ID = 0x01
REG_TEMP_DATA = 0x1D           # 3 bytes, XLSB first, signed, degC = raw / 65536
REG_PRESS_DATA = 0x20          # 3 bytes, XLSB first, Pa = raw / 64
REG_STATUS = 0x28
REG_OSR_CONFIG = 0x36
REG_ODR_CONFIG = 0x37
REG_CMD = 0x7E
CHIP_IDS = (0x50, 0x51)


class BMP581:
	NAME = "BMP581"
	ADDRESSES = (0x47, 0x46)
	QUANTITIES = ("temp_c", "pressure_hpa")

	def __init__(self, bus, address=0x47):
		self.bus, self.address = bus, address
		if self.bus.read_byte_data(address, REG_CHIP_ID) not in CHIP_IDS:
			raise IOError("not a BMP581")
		self.bus.write_byte_data(address, REG_CMD, 0xB6)                     # soft reset
		time.sleep(0.01)
		self.bus.write_byte_data(address, REG_OSR_CONFIG, 0x40 | (0x04 << 3) | 0x01)

	def read(self):
		self.bus.write_byte_data(self.address, REG_ODR_CONFIG, 0x80 | 0x02)  # one forced measurement
		time.sleep(0.1)
		t = self.bus.read_i2c_block_data(self.address, REG_TEMP_DATA, 3)
		p = self.bus.read_i2c_block_data(self.address, REG_PRESS_DATA, 3)
		raw_t = (t[2] << 16) | (t[1] << 8) | t[0]
		if raw_t & 0x800000:
			raw_t -= 1 << 24
		return {"temp_c": raw_t / 65536.0,
		        "pressure_hpa": ((p[2] << 16) | (p[1] << 8) | p[0]) / 64.0 / 100.0}
