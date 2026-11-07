# Microchip MCP9808 temperature, I2C 0x18 to 0x1F (A0 to A2 pins); 0x18 is the default
# Move it off 0x18 if the Adafruit DS2484 1-Wire bridge (0x18) is on the same bus.
# Ambient temperature register 0x05: 13-bit two's complement, 0.0625 degC per count
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

REG_AMBIENT = 0x05
REG_MANUFACTURER = 0x06        # reads 0x0054
REG_DEVICE = 0x07              # upper byte 0x04
REG_RESOLUTION = 0x08          # 0x03 = 0.0625 degC (the power-on default)


def to_celsius(upper, lower):
	upper &= 0x1F                                      # drop the three alert flag bits
	t = (upper & 0x0F) * 16 + lower / 16.0
	return t - 256 if upper & 0x10 else t


class MCP9808:
	NAME = "MCP9808"
	ADDRESSES = tuple(range(0x18, 0x20))
	QUANTITIES = ("temp_c",)

	def __init__(self, bus, address=0x18):
		self.bus, self.address = bus, address
		man = self.bus.read_i2c_block_data(address, REG_MANUFACTURER, 2)
		dev = self.bus.read_i2c_block_data(address, REG_DEVICE, 2)
		if (man[0] << 8 | man[1]) != 0x0054 or dev[0] != 0x04:
			raise IOError("not an MCP9808")
		self.bus.write_byte_data(address, REG_RESOLUTION, 0x03)

	def read(self):
		upper, lower = self.bus.read_i2c_block_data(self.address, REG_AMBIENT, 2)
		return {"temp_c": to_celsius(upper, lower)}
