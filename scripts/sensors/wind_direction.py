#!/usr/bin/python3
# Code to control the wind direction sensors
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import math, time, helper_functions


# Input of min/max from ADC taken from Calibration
ADC_min = 103
ADC_max = 920
ADC_range = ADC_max - ADC_min


# Code for MCP3002
def analog_read(spi):
	cmd = 0b01100000
	spi_data = spi.xfer2([cmd,0])
	adc_data = ((spi_data[0] & 3) << 8) + spi_data[1]
	return adc_data


def i2c(bus, address):
    # Get low and hi angles
    high = bus.read_byte_data(address, 0x0c)
    low = bus.read_byte_data(address, 0x0d)
    # Determine wind direction
    angle = high << 8
    angle = angle | low
    angle = int(angle) * 0.0879
    r = (angle * 71) / 4068.0
    NS_vector = math.cos(r)
    EW_vector = math.sin(r)
    angle = (math.atan2(EW_vector, NS_vector)*4068.0)/71.0
    # Adjust if necessary
    if angle < 0:
        angle = 360 + angle
    return angle


def analog():
    # Read the channel
    reading = analog_read(spi)
    if reading < ADC_min:
        angle = 0
    elif reading > ADC_max:
        angle = 360
    else:
        # Get ADC to relative zero
        ADC_rel = reading - ADC_min
        angle = ADC_rel*360.0/ADC_range
    return angle


# Determine i2c or analog, and set up
try:
    sensor = "i2c"
    import smbus
    bus = smbus.SMBus(0)
    address = 0x36
    test = bus.read_byte_data(address, 0x0c)
except:
    sensor = "analog"
    import spidev, RPi.GPIO as GPIO
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 1000000
    spi = spidev.SpiDev()
    spi.open(0,0)
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(13, GPIO.OUT)


# Run
print("Wind Direction Sensor - " + sensor)

# Check if this is a test and set interval appropriately
test, samples, iterations = helper_functions.getTest()

# Run once... or if in test mode, run every 10 seconds during the interval
for i in range (0, iterations):
    try:
        total = 0
        for x in range (0, samples):
            if sensor == "i2c":
                total += i2c(bus, address)
            else:
                total += analog()
            time.sleep(1)

        # Calculate average wind direction for i2c
        average = total/samples

        # Handle script output
        if average == 0:
            average = -999.99
        line = "%.2f" % (average)
        if test:
            helper_functions.output(True, line, "test_wind_direction")
        else:
            helper_functions.output(True, line, "wind_direction")
    
    except Exception as e:
        helper_functions.handleError(e, "wind_direction")
        pass

