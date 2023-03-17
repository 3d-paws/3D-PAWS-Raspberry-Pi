#!/usr/bin/python3
# Code to control the MCP3002 sensor. Write observations to disk
# Paul A. Kucera, Ph.D. and Joseph Rener
# UCAR
# Boulder, CO USA
# Email: pkucera@ucar.edu and jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import spidev, time, RPi.GPIO as GPIO, helper_functions
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1000000


# Code for MCP3002
def analog_read(spi):
	cmd = 0b01100000
	spi_data = spi.xfer2([cmd,0])
	adc_data = ((spi_data[0] & 3) << 8) + spi_data[1]
	return adc_data


def run(command):
	print("Wind Direction Sensor - Analog")

	#Get variables
	variables = helper_functions.getVariables()
	test_toggle = variables[0]
	interval = helper_functions.getCron()[0]

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

	# Check if this is a test and set samples appropriately
	test = True
	if len(sys.argv) > 1:
		samples = int(sys.argv[1])
		iterations = (interval*60/samples)-1
	elif command == 1 or test_toggle == "true":
		samples = 10
		iterations = (interval*6)-1
	else:
		test = False
		samples = 60*interval - 1
		iterations = 1

	# Run once... or if in test mode, run every 10 seconds during the interval
	for i in range (0, iterations):
		try:
			for x in range (0, samples):
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
				elif x < samples-1:
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
				elif x == samples-1:
					wnddir_avg = wnddir_sum/samples
					if wnddir_avg > 360.0:
						wnddir_avg = 360.0
					if wnddir_avg < 0.0:
						wnddir_avg = 0.0

					# Handle script output
					line = "%d %.2f %.2f" % (reading, wnddir, wnddir_avg)		
					if test:
						helper_functions.output(True, line, "test_wind_direction")
					else:
						helper_functions.output(True, line, "wind_direction")

					time.sleep(1)
		
		except Exception as e:
			helper_functions.handleError(e, "wind_direction")
			GPIO.cleanup()
			pass


#run the function as a test if this script is ran from the command line
if __name__ == "__main__":
    run(1)