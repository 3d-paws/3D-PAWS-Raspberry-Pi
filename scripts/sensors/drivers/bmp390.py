# Bosch BMP390 (and BMP388) pressure and temperature, I2C 0x77 (Adafruit default) or 0x76 (SDO to GND)
# Raw readings are compensated with the chip's factory coefficients (NVM 0x31 to 0x45), using the
# floating-point formulas from the BMP390 datasheet (section 8.4), the same as Adafruit's BMP3XX library.
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import struct, time

REG_CHIP_ID = 0x00
REG_STATUS = 0x03              # bit 5 pressure ready, bit 6 temperature ready
REG_DATA = 0x04                # pressure XLSB, LSB, MSB, then temperature XLSB, LSB, MSB
REG_PWR_CTRL = 0x1B
REG_OSR = 0x1C
REG_CONFIG = 0x1F
REG_CALIB = 0x31               # 21 bytes
REG_CMD = 0x7E
CHIP_IDS = (0x60, 0x50)        # BMP390, BMP388

FORCED = 0x13                  # forced mode, pressure and temperature on
OSR = (0x01 << 3) | 0x03       # temperature x2, pressure x8


def coefficients(raw):
	"""The 21 calibration bytes, scaled as in the datasheet: (temperature, pressure) coefficient tuples."""
	c = struct.unpack("<HHbhhbbHHbbhbb", bytes(raw))
	t = (c[0] / 2 ** -8.0, c[1] / 2 ** 30.0, c[2] / 2 ** 48.0)
	p = ((c[3] - 2 ** 14.0) / 2 ** 20.0, (c[4] - 2 ** 14.0) / 2 ** 29.0, c[5] / 2 ** 32.0, c[6] / 2 ** 37.0,
	     c[7] / 2 ** -3.0, c[8] / 2 ** 6.0, c[9] / 2 ** 8.0, c[10] / 2 ** 15.0, c[11] / 2 ** 48.0,
	     c[12] / 2 ** 48.0, c[13] / 2 ** 65.0)
	return t, p


def compensate(adc_t, adc_p, tc, pc):
	"""Raw 24-bit readings to (degC, Pa)."""
	t1, t2, t3 = tc
	d = adc_t - t1
	t = d * t2 + d * d * t3
	p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11 = pc
	out1 = p5 + p6 * t + p7 * t ** 2 + p8 * t ** 3
	out2 = adc_p * (p1 + p2 * t + p3 * t ** 2 + p4 * t ** 3)
	out3 = adc_p ** 2 * (p9 + p10 * t) + adc_p ** 3 * p11
	return t, out1 + out2 + out3


class BMP390:
	NAME = "BMP390"
	ADDRESSES = (0x77, 0x76)
	QUANTITIES = ("temp_c", "pressure_hpa")

	def __init__(self, bus, address=0x77):
		self.bus, self.address = bus, address
		if self.bus.read_byte_data(address, REG_CHIP_ID) not in CHIP_IDS:
			raise IOError("not a BMP390")
		self.bus.write_byte_data(address, REG_CMD, 0xB6)                     # soft reset
		time.sleep(0.01)
		self.tc, self.pc = coefficients(self.bus.read_i2c_block_data(address, REG_CALIB, 21))
		self.bus.write_byte_data(address, REG_OSR, OSR)
		self.bus.write_byte_data(address, REG_CONFIG, 0x00)                  # no IIR filter

	def read(self):
		self.bus.write_byte_data(self.address, REG_PWR_CTRL, FORCED)
		end = time.monotonic() + 0.5
		while self.bus.read_byte_data(self.address, REG_STATUS) & 0x60 != 0x60:
			if time.monotonic() > end:
				raise IOError("BMP390 measurement timed out")
			time.sleep(0.005)
		d = self.bus.read_i2c_block_data(self.address, REG_DATA, 6)
		adc_p = (d[2] << 16) | (d[1] << 8) | d[0]
		adc_t = (d[5] << 16) | (d[4] << 8) | d[3]
		t, pa = compensate(adc_t, adc_p, self.tc, self.pc)
		return {"temp_c": t, "pressure_hpa": pa / 100.0}
