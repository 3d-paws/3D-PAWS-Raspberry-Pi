# Shared helpers for the direct I2C sensor drivers in this folder
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)


def crc8(data):
	"""Sensirion CRC-8 (polynomial 0x31, start 0xFF), used by the SHT3x and SHT4x."""
	crc = 0xFF
	for byte in data:
		crc ^= byte
		for _ in range(8):
			crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
	return crc


def read_bytes(bus, address, count):
	"""Plain I2C read of count bytes with no register address first (the SHT sensors answer this way)."""
	from smbus2 import i2c_msg
	msg = i2c_msg.read(address, count)
	bus.i2c_rdwr(msg)
	return list(msg)


def check_words(data):
	"""Sensirion replies: 16-bit words, each followed by its CRC. Returns the words or raises IOError."""
	words = []
	for i in range(0, len(data), 3):
		if crc8(data[i:i + 2]) != data[i + 2]:
			raise IOError("CRC error")
		words.append((data[i] << 8) | data[i + 1])
	return words


def sht_family(bus, address):
	"""Which Sensirion family answers at this address: "sht3x", "sht4x" or None. Both can sit at 0x44.
	SHT3x: the status register read (16-bit command 0xF32D) returns a word + CRC; the SHT4x has no such command.
	SHT4x: the serial number read (command 0x89) returns two words + CRCs; the SHT3x needs 16-bit commands."""
	import time
	try:
		bus.write_byte_data(address, 0xF3, 0x2D)
		time.sleep(0.002)
		check_words(read_bytes(bus, address, 3))
		return "sht3x"
	except (IOError, OSError):
		pass
	try:
		bus.write_byte(address, 0x89)
		time.sleep(0.002)
		check_words(read_bytes(bus, address, 6))
		return "sht4x"
	except (IOError, OSError):
		return None
