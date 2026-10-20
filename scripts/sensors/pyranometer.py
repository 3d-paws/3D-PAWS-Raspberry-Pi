#!/usr/bin/python3
# Code to read the SP Lite2 Pyranometer (Kipp & Zonen) via ADS1115 ADC. Write observations to disk
# ADS1115 uses GAIN_SIXTEEN (±0.256V, LSB = 7.8125 µV) for the tiny pyranometer output signal.
# Wiring: SP Lite2 Red → ADS1115 A0, SP Lite2 Blue → ADS1115 A1, Shield → GND
# Calibration constants are read from /home/pi/Desktop/pyranometer_cal.txt (two lines):
#   Line 1: sr_cal (µV per W/m² from sensor label, e.g. 75.0)
#   Line 2: sr_dark_offset (raw ADS1115 count baseline in darkness, e.g. 0.0)
# If the file does not exist, defaults of 75.0 / 0.0 are used.
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time, os
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import board, busio, helper_functions

CAL_FILE      = "/home/pi/Desktop/pyranometer_cal.txt"
LSB_uV        = 7.8125   # µV per ADS1115 count at GAIN_SIXTEEN
SAMPLES       = 16

def load_calibration():
	sr_cal         = 75.0
	sr_dark_offset = 0.0
	if os.path.exists(CAL_FILE):
		try:
			with open(CAL_FILE, 'r') as f:
				lines = f.read().splitlines()
			sr_cal         = float(lines[0].strip())
			sr_dark_offset = float(lines[1].strip())
		except Exception:
			pass
	return sr_cal, sr_dark_offset

try:
	import adafruit_ads1x15.ads1115 as ADS
	from adafruit_ads1x15.analog_in import AnalogIn

	i2c = board.I2C()
	ads = ADS.ADS1115(i2c)
	ads.gain = 16  # GAIN_SIXTEEN: ±0.256V — maximises resolution for tiny pyranometer signal

	sr_cal, sr_dark_offset = load_calibration()

	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1

	for x in range(0, iterations):
		# Differential read A0-A1, average SAMPLES readings
		raw_sum = 0
		for _ in range(SAMPLES):
			chan = AnalogIn(ads, ADS.P0, ADS.P1)
			raw_sum += chan.value
			time.sleep(0.005)

		avg_counts = raw_sum / SAMPLES - sr_dark_offset
		V_uV       = avg_counts * LSB_uV
		irradiance = max(0.0, V_uV / sr_cal) if sr_cal != 0.0 else 0.0

		print("SP Lite2 Pyranometer")
		print("Avg counts:    %.2f"    % (raw_sum / SAMPLES))
		print("Irradiance:    %.4f W/m²" % irradiance)
		print()

		line = "%.4f" % irradiance
		helper_functions.output(False, line, "pyranometer")

		if test_mode == "true":
			time.sleep(10)
		else:
			break

except Exception as e:
	helper_functions.handleError(e, "pyranometer")
