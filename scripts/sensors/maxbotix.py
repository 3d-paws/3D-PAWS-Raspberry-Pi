#!/usr/bin/python3
# Code to control Maxbotix ultrasonic distance sensors via ADS1115 ADC. Write observations to disk
# Connects sensor analog output to ADS1115 channel A0 (single-ended, GAIN_ONE ±4.096V).
# Sensor type is set by MAXBOTIX_RANGE_M below (5 or 10 metres).
#   5m sensors (MB7360/MB7369/MB7380/MB7389): distance_mm = (V / Vcc) * 5120
#  10m sensors (MB7363/MB7366/MB7383/MB7386): distance_mm = (V / Vcc) * 10240
# Set MAXBOTIX_RANGE_M = 5 for 5-metre sensors, 10 for 10-metre sensors.
# Vcc must match the voltage powering the sensor (default 3.3V for Raspberry Pi).
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, time
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import board, busio, helper_functions

MAXBOTIX_RANGE_M = 5   # Change to 10 for 10-metre sensors
VCC = 3.3              # Sensor supply voltage in volts

try:
	import adafruit_ads1x15.ads1115 as ADS
	from adafruit_ads1x15.analog_in import AnalogIn

	i2c = board.I2C()
	ads = ADS.ADS1115(i2c)
	ads.gain = 1  # GAIN_ONE: ±4.096V full scale
	chan = AnalogIn(ads, ADS.P0)

	variables = helper_functions.getVariables()
	test_mode = variables[0]
	interval = helper_functions.getCron()[0]
	iterations = (interval*6)-1

	for x in range(0, iterations):
		# Average 16 samples to reduce noise
		samples = [AnalogIn(ads, ADS.P0).voltage for _ in range(16)]
		voltage = sum(samples) / len(samples)

		scale_mm = MAXBOTIX_RANGE_M * 1024
		distance_mm = (voltage / VCC) * scale_mm

		print("Maxbotix Distance Sensor (%dm range)" % MAXBOTIX_RANGE_M)
		print("Voltage:      %.4f V"  % voltage)
		print("Distance:     %.2f mm" % distance_mm)
		print()

		line = "%.2f" % distance_mm
		helper_functions.output(False, line, "maxbotix")

		if test_mode == "true":
			time.sleep(10)
		else:
			break

except Exception as e:
	helper_functions.handleError(e, "maxbotix")
