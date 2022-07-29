#!/usr/bin/python3
# Code to determine which wind direction sensor is being used
# Joseph E. Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Copyright (c) 2022 UCAR
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import smbus, wind_direction_analog, wind_direction_i2c

try:
    bus = smbus.SMBus(0)
    address = 0x36
    test = bus.read_byte_data(address, 0x0c)
    wind_direction_i2c.run(bus, address, 0)
except:
    wind_direction_analog.run(0)
    