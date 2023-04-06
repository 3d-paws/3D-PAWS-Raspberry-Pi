#!/usr/bin/python3
# Code to determine which wind direction sensor is being used
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys, smbus, wind_direction_analog, wind_direction_i2c

def run(command):
    try:
        bus = smbus.SMBus(0)
        address = 0x36
        test = bus.read_byte_data(address, 0x0c)
        wind_direction_i2c.run(bus, address, command)
    except:
        wind_direction_analog.run(command)


#run the function as a test if this script is ran from the command line
if sys.stdin and sys.stdin.isatty():
    run(1)
else:
    run(0)