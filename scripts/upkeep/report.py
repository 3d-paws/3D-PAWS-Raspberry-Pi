#!/usr/bin/python
# Code to control the BMP280 and BME280 I2C sensors. Write observations to disk
# Joseph E. Rener
# NCAR/RAL
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import datetime, os, helper_functions


# Get script arguments
arguments = helper_functions.getArguments()
record_interval = arguments[0]
chords_interval = arguments[1]
chords_toggle = arguments[2]
chords_id = arguments[3]
chords_link = arguments[4]
test_toggle = arguments[6]
now = datetime.datetime.utcnow()


def checkFile(sensor):
    location = "/home/pi/data/temporary/" + sensor + ".tmp"
    if os.path.exists(location):
        f = open(location, "r+")
        info = f.readline().split()
        next_line = f.readline()
        if next_line:
            f.truncate(0)
            f.write(next_line)
            f.close()
        else:
            f.close()
            os.remove(location)
        return info
    return False


if now.minute % record_interval == 0 and test_toggle == "false":
    #data = [bmp_temp, bmp_pressure, bmp_slp, bmp_altitude, bme_temp, bme_pressure, bme_slp, bme_altitude, bme_humidity, htu21d_temp, htu21d_humidity, mcp9808, rain, si1145_vis, si1145_ir, si1145_uv, wind_direction, wind_speed]
    data = [-999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99]

    bmp = checkFile("bmp")
    if bmp:
        data[0] = float(bmp[5])
        data[1] = float(bmp[6])
        data[2] = float(bmp[7])
        data[3] = float(bmp[8])
    bme = checkFile("bme")
    if bme:
        data[4] = float(bme[5])
        data[5] = float(bme[6])
        data[6] = float(bme[7])
        data[7] = float(bme[8])
        data[8] = float(bme[9])
    htu21d = checkFile("htu21d")
    if htu21d:
        data[9] = float(htu21d[5])
        data[10] = float(htu21d[6])
    mcp9808 = checkFile("mcp9808")
    if mcp9808:
        data[11] = float(mcp9808[5])
    rain = checkFile("rain")
    if rain:
        data[12] = float(rain[5])
    si1145 = checkFile("si1145")
    if si1145:
        data[13] = float(si1145[5])
        data[14] = float(si1145[6])
        data[15] = float(si1145[7])
    wind_direction = checkFile("wind_direction")
    if wind_direction:
        data[16] = float(wind_direction[6])
    wind_speed = checkFile("wind_speed")
    if wind_speed:
        data[17] = float(wind_speed[5])

    #save to daily file if data is being recorded
    if not all(ele == data[0] for ele in data):
        helper_functions.output(False, data, "all")

    #report to chords if it's time to
    url = "http://%s/measurements/url_create?instrument_id=%d&bmp_temp=%05.1f&bmp_pressure=%07.2f&bmp_slp=%07.2f&bmp_altitude=%07.2f&bme_temp=%05.1f&bme_pressure=%07.2f&bme_slp=%07.2f&bme_altitude=%07.2f&bme_humidity=%07.2f&htu21d_temp=%05.1f&htu21d_humidity=%04.1f&mcp9808=%05.1f&rain=%04.2f&si1145_vis=%010.1f&si1145_ir=%010.1f&si1145_uv=%010.1f&wind_direction=%05.1f&wind_speed=%04.2f&key=21DE6A8A" % (chords_link, chords_id, data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7], data[8], data[9], data[10], data[11], data[12], data[13], data[14], data[15], data[16], data[17])
    helper_functions.reportCHORDS(chords_toggle, now.minute, chords_interval, url)