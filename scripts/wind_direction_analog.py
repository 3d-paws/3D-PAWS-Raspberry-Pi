#!/usr/bin/python3
# Code to control the MCP3002 sensor. Write observations to disk
# and to web in intervals determined by input.txt
# Paul A. Kucera, Ph.D. and Joseph E. Rener
# UCAR
# Boulder, CO USA
# Email: pkucera@ucar.edu and jrener@ucar.edu
# Copyright (c) 2022 UCAR
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import spidev, time, datetime, RPi.GPIO as GPIO, helper_functions
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1000000


# Code for MCP3002
def analog_read(spi):
	cmd = 0b01100000
	spi_data = spi.xfer2([cmd,0])
	adc_data = ((spi_data[0] & 3) << 8) + spi_data[1]
	return adc_data


def run(test):
	print("Wind Direction Sensor - Analog")

	# Get inputs
	arguments = helper_functions.getArguments()
	record_interval = arguments[0]
	test_toggle = arguments[6]

	# Set up sensors
	spi = spidev.SpiDev()
	spi.open(0,0)
	GPIO.setwarnings(False)
	GPIO.setmode(GPIO.BOARD)
	GPIO.setup(13, GPIO.OUT)

	# Input of min/max from ADC taken from Calibration
	ADC_min = 103
	ADC_max = 920
	ADC_range = ADC_max - ADC_min

	# Check if this is a test (1) or real (0) and set interval appropriately
	command_test = False
	if test == 1:
		rest = 1
		command_test = True
	elif test_toggle == "true":
		rest = record_interval
		command_test = True
	else:
		rest = 60*record_interval

	# Read wind sensor data every second
	while True:
		try:
			# Report average either every minute or every second (if testing)
			for x in range (0, rest):
				# Read the channel
				reading = analog_read(spi)

				# Convert to deg from north
				if reading < ADC_min:
					wnddir = 0
				elif reading > ADC_max:
					wnddir = 360
				else:
					# Get ADC to relative zero
					ADC_rel = reading - ADC_min
					wnddir = ADC_rel*360.0/ADC_range

				# Record the first angle
				if x == 0:
					wnddir_sum = wnddir
					wnddir_prev = wnddir
				elif x < rest-1:
					delta_wnd = wnddir - wnddir_prev
					# Assign the next value
					if delta_wnd < -180.0:
						wnddir_sum = wnddir_sum + (wnddir_prev + delta_wnd + 360.0)
						wnddir_prev = wnddir_prev + delta_wnd + 360.0
					elif abs(delta_wnd) < 180.0:
						wnddir_sum = wnddir_sum + (wnddir_prev + delta_wnd)
						wnddir_prev = wnddir_prev + delta_wnd
					elif delta_wnd > 180:
						wnddir_sum = wnddir_sum + (wnddir_prev + delta_wnd - 360.0)
						wnddir_prev = wnddir_prev + delta_wnd - 360.0
					else:
						print("delta wind is 180 deg, undefined and not used")
				if x == rest-1:
					wnddir_avg = wnddir_sum/rest
					if wnddir_avg > 360.0:
						wnddir_avg = 360.0
					if wnddir_avg < 0.0:
						wnddir_avg = 0.0
						
					# Get current time for writing to file
					now = datetime.datetime.utcnow()

					# Handle script output
					line = "%d %.2f %.2f" % (reading, wnddir, wnddir_avg)		
					if command_test:
						helper_functions.output(True, line, "test_wind_direction")
					else:
						helper_functions.output(True, line, "wind_direction")

					# Wait until a second has passed since current run began, and run again
					time.sleep(rest)
		
		except Exception as e:
			helper_functions.handleError(e, "wind_direction")
			pass

	GPIO.cleanup()


#run the function as a test if this script is ran from the command line
if __name__ == "__main__":
    run(1)