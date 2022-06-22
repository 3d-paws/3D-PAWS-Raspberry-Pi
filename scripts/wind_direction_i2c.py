#!/usr/bin/python3
# Code to control the wind direction I2C sensor. Write observations to disk
# and to web in intervals determined by input.txt
# Joseph E. Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Copyright (c) 2022 UCAR
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import smbus, math, time, datetime, helper_functions

def run(bus, address, test):
    print("Wind Direction Sensor - i2c")

    # Get inputs
    arguments = helper_functions.getArguments()
    record_interval = arguments[0]
    test_toggle = arguments[6]

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

    # Read sensor each second
    while True:
        try:
            total = 0
            for x in range (0, rest):
                then = float(time.time())
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

                # Add to total to be averaged later
                total += angle

                # Wait until a second has passed since current run began, and run again
                now = float(time.time())
                diff = now-then
                sleep_time = 1-diff
                if sleep_time > 0:
                    time.sleep(sleep_time)

            # Calculate average wind direction
            average = total/rest

            # Get current time for writing to file
            now = datetime.datetime.utcnow()

            # Handle script output
            line = "%.2f %.2f" % (angle, average)
            if command_test:
                helper_functions.output(True, line, "test_wind_direction")
            else:
                helper_functions.output(True, line, "wind_direction")

        # Return an error if there was one
        except Exception as e:
            helper_functions.handleError(e, "wind_direction")
            pass


#run the function as a test if this script is ran from the command line
if __name__ == "__main__":
    bus = smbus.SMBus(0)
    address = 0x36
    run(bus, address, 1)