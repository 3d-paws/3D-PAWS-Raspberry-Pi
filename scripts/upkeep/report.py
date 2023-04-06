#!/usr/bin/python
# Code to control the BMP280 and BME280 I2C sensors. Write observations to disk
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import datetime, os, time, helper_functions
time.sleep(5)


#Get variables
variables = helper_functions.getVariables()
test_toggle = variables[0]
chords_id = variables[1]
chords_link = variables[2]
now = datetime.datetime.utcnow()


def checkFile(sensor):
    location = "/home/pi/data/temporary/" + sensor + ".tmp"
    if os.path.exists(location):
        f = open(location, "r+")
        info = f.readline().split()
        f.close()
        os.remove(location)
        return info
    return False


if test_toggle == "false":
    #data = [bmp_temp, bmp_pressure, bmp_slp, bmp_altitude, bme_temp, bme_pressure, bme_slp, bme_altitude, bme_humidity, htu21d_temp, htu21d_humidity, mcp9808, rain, si1145_vis, si1145_ir, si1145_uv, wind_direction, wind_speed]
    data = [-999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99]
    url = "http://%s/measurements/url_create?instrument_id=%d" % (chords_link, chords_id)

    bmp = checkFile("bmp")
    if bmp:
        data[0] = float(bmp[5])
        data[1] = float(bmp[6])
        data[2] = float(bmp[7])
        data[3] = float(bmp[8])
        if data[0] != -999.99:  
            url += "&bmp_temp=%05.1f&bmp_pressure=%07.2f&bmp_slp=%07.2f&bmp_altitude=%07.2f" % (data[0], data[1], data[2], data[3])
            
    bme = checkFile("bme")
    if bme:
        data[4] = float(bme[5])
        data[5] = float(bme[6])
        data[6] = float(bme[7])
        data[7] = float(bme[8])
        data[8] = float(bme[9])
        if data[4] != -999.99:  
            url += "&bme_temp=%05.1f&bme_pressure=%07.2f&bme_slp=%07.2f&bme_altitude=%07.2f&bme_humidity=%07.2f" % (data[4], data[5], data[6], data[7], data[8])
            
    htu21d = checkFile("htu21d")
    if htu21d:
        data[9] = float(htu21d[5])
        data[10] = float(htu21d[6])
        if data[9] != -999.99:  
            url += "&htu21d_temp=%05.1f&htu21d_humidity=%04.1f" %(data[9], data[10])
            
    mcp9808 = checkFile("mcp9808")
    if mcp9808:
        data[11] = float(mcp9808[5])
        if data[11] != -999.99:  
            url += "&mcp9808=%05.1f" % (data[11])

    rain = checkFile("rain")
    if rain:
        data[12] = float(rain[5])
        if data[12] != -999.99:  
            url += "&rain=%04.2f" % (data[12])
            
    si1145 = checkFile("si1145")
    if si1145:
        data[13] = float(si1145[5])
        data[14] = float(si1145[6])
        data[15] = float(si1145[7])
        if data[13] != -999.99:  
            url += "&si1145_vis=%010.1f&si1145_ir=%010.1f&si1145_uv=%010.1f" % (data[13], data[14], data[15])
            
    wind_direction = checkFile("wind_direction")
    if wind_direction:
        data[16] = float(wind_direction[5])
        if data[16] != -999.99:  
            url += "&wind_direction=%05.1f" % (data[16])

    wind_speed = checkFile("wind_speed")
    if wind_speed:
        data[17] = float(wind_speed[5])
        if data[17] != -999.99:  
            url += "&wind_speed=%04.2f" % (data[17])


    #save to daily file if data is being recorded
    if not all(ele == data[0] for ele in data):
        helper_functions.output(False, data, "all")
        helper_functions.output(False, url, "chords")