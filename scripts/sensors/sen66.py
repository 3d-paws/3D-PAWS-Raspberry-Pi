#!/usr/bin/python3
# Code to control the Sensirion SEN66 air quality sensor (PM1.0/2.5/4.0/10, humidity, temperature, VOC, NOx, CO2). Write observations to disk
# Reports the average of 1 second samples over the recording interval, like the Particle SensorTesting firmware
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import helper_functions
from smbus2 import SMBus, i2c_msg

ADDRESS = 0x6B   # Fixed I2C address

# Sensirion command codes
SET_ALTITUDE = 0x6736
START_MEASUREMENT = 0x0021
READ_MEASURED_VALUES = 0x0300
GET_DATA_READY = 0x0202
READ_DEVICE_STATUS = 0xD206

# Device status flags (Sensirion SEN66 driver); errors stay set until the sensor is reset
STATUS_FLAGS = {4: "fan error (fan blocked or broken)", 6: "humidity/temperature sensor error", 7: "gas (VOC/NOx) sensor error",
	9: "CO2 sensor error", 11: "particulate matter sensor error", 21: "fan speed warning (fan is running more than 10% off its target speed)"}


# Sensirion CRC-8: polynomial 0x31, initial value 0xFF
def crc(data):
	value = 0xFF
	for byte in data:
		value ^= byte
		for _ in range(8):
			value = ((value << 1) ^ 0x31) & 0xFF if value & 0x80 else (value << 1) & 0xFF
	return value


# Send a 16-bit command, followed by 16-bit arguments that each carry a CRC byte
def command(bus, cmd, words=(), delay=0.02):
	data = [cmd >> 8, cmd & 0xFF]
	for word in words:
		pair = [word >> 8, word & 0xFF]
		data += pair + [crc(pair)]
	bus.i2c_rdwr(i2c_msg.write(ADDRESS, data))
	time.sleep(delay)


def readWords(bus, count):
	msg = i2c_msg.read(ADDRESS, count * 3)
	bus.i2c_rdwr(msg)
	raw = list(msg)
	words = []
	for i in range(count):
		pair = raw[i*3:i*3+2]
		if crc(pair) != raw[i*3+2]:
			raise IOError("SEN66 CRC check failed")
		words.append((pair[0] << 8) | pair[1])
	return words


# Altitude can only be set while the sensor is idle, and starting fails if it is already measuring.
# Both errors are ignored so a sensor that is already running keeps going and keeps its VOC/NOx history.
def start(bus, altitude):
	try:
		command(bus, SET_ALTITUDE, [max(0, min(3000, int(altitude)))])
	except OSError:
		pass
	try:
		command(bus, START_MEASUREMENT, delay=0.05)
	except OSError:
		pass
	# The sensor only answers data-ready while it is measuring, and the fan only runs while it is measuring
	try:
		command(bus, GET_DATA_READY)
		readWords(bus, 1)
	except OSError:
		raise IOError("SEN66 did not start measuring, so its fan will not run")
	checkStatus(bus)


# Print any fan or sensor faults the SEN66 reports
def checkStatus(bus):
	command(bus, READ_DEVICE_STATUS)
	high, low = readWords(bus, 2)
	status = (high << 16) | low
	for bit, problem in STATUS_FLAGS.items():
		if status & (1 << bit):
			print("SEN66 WARNING: " + problem)


# Returns [pm1.0, pm2.5, pm4.0, pm10, humidity, temperature, voc, nox, co2]; None where the sensor has no value yet
def read(bus):
	command(bus, READ_MEASURED_VALUES)
	w = readWords(bus, 9)
	def unsigned(word, scale):
		return None if word == 0xFFFF else word / scale
	def signed(word, scale):
		return None if word == 0x7FFF else (word - 0x10000 if word & 0x8000 else word) / scale
	return [unsigned(w[0], 10.0), unsigned(w[1], 10.0), unsigned(w[2], 10.0), unsigned(w[3], 10.0),
		signed(w[4], 100.0), signed(w[5], 200.0), signed(w[6], 10.0), signed(w[7], 10.0), unsigned(w[8], 1.0)]


try:
	test, rest, iterations = helper_functions.getTest()
	# Finish a few seconds before the next cron run starts
	if not test:
		rest = max(10, rest - 4)
	altitude = helper_functions.getVariables()[4]

	with SMBus(1) as bus:
		start(bus, altitude)
		for x in range(0, iterations):
			samples = []
			end = time.time() + rest
			while time.time() < end:
				samples.append(read(bus))
				time.sleep(1)
			averages = []
			for i in range(9):
				values = [s[i] for s in samples if s[i] is not None]
				averages.append(sum(values) / len(values) if values else None)
			if all(v is None for v in averages):
				print("SEN66: no readings yet - the sensor needs a few seconds after it starts")
				continue
			pm1, pm25, pm4, pm10, rh, tempC, voc, nox, co2 = [v if v is not None else -999.99 for v in averages]

			print("SEN66 Sensor (average of %d samples)" % len(samples))
			print("PM1.0:        %.2f µg/m³" % pm1)
			print("PM2.5:        %.2f µg/m³" % pm25)
			print("PM4.0:        %.2f µg/m³" % pm4)
			print("PM10:         %.2f µg/m³" % pm10)
			print("Humidity:     %.2f %%" % rh)
			print("Temperature:  %.2f degC" % tempC)
			print("VOC index:    %.2f" % voc)
			print("NOx index:    %.2f" % nox)
			print("CO2:          %.0f ppm" % co2)
			print()

			line = "%.2f %.2f %.2f %.2f %.2f %.2f %.2f %.2f %.2f" % (pm1, pm25, pm4, pm10, rh, tempC, voc, nox, co2)
			helper_functions.output(False, line, "sen66")

except Exception as e:
	helper_functions.handleError(e, "sen66")
