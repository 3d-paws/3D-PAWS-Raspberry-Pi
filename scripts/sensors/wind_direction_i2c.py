#!/usr/bin/python3
# Code to control the wind direction I2C sensor. Write observations to disk
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import smbus, math, time, helper_functions

def run(bus, address, command):
    print("Wind Direction Sensor - i2c")

    #Get variables
    variables = helper_functions.getVariables()
    test_toggle = variables[0]
    interval = helper_functions.getCron()[0]

    # Check if this is a test and set interval appropriately
    test = True
    if len(sys.argv) > 1:
        samples = int(sys.argv[1])
        iterations = int((interval*60/samples)-1)
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
            total = 0
            for x in range (0, samples):
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

                # Wait
                time.sleep(1)

            # Calculate average wind direction
            average = total/samples

            # Handle script output
            line = "%.2f %.2f" % (angle, average)
            if test:
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