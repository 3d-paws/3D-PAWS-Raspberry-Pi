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


def QC(value, min, max):
    value = float(value)
    if value <= max and value >= min:
        return value
    return -999.99


if test_toggle == "false":
    #data = [bm_temp, bm_pressure, bm_slp, bm_altitude, bme2_humidity, hum_temp, hum_humidity, mcp9808, rain, si1145_vis, si1145_ir, si1145_uv, wind_direction, wind_speed]
    data = [-999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99]
    url = "http://%s/measurements/url_create?instrument_id=%d" % (chords_link, chords_id)

    bm = checkFile("bm")
    if bm:
        v = bm[5]
        data[0] = QC(bm[6], -40, 60)
        data[1] = QC(bm[7], 300, 1100)
        data[2] = float(bm[8])
        data[3] = float(bm[9])
        if v == "bme2":
            data[4] = QC(bm[10], 0, 100)
        if data[0] != -999.99 and data[1] != -999.99 and data[2] != -999.99 and data[3] != -999.99:  
            url += "&%s_temp=%05.1f&%s_pressure=%07.2f&%s_slp=%07.2f&%s_altitude=%07.2f" % (v, data[0], v, data[1], v, data[2], v, data[3])
            if v == "bme2":
                url += "&bme_humidity=%07.2f" % (data[4])
            
    humidity = checkFile("humidity")
    if humidity:
        version = "sth31d"
        if humidity[5]  == "htu":
            version = "htu21d"
        data[5] = QC(humidity[6], -40, 60)
        data[6] = QC(humidity[7], 0, 100)
        if data[5] != -999.99:  
            url += "&%s_temp=%05.1f&%s_humidity=%04.1f" %(v, data[5], v, data[6])
            
    mcp9808 = checkFile("mcp9808")
    if mcp9808:
        data[7] = QC(mcp9808[5], -40, 60)
        if data[7] != -999.99:  
            url += "&mcp9808=%05.1f" % (data[11])

    rain = checkFile("rain")
    if rain:
        data[8] = QC(rain[5], 0, 60)
        if data[8] != -999.99:  
            url += "&rain=%04.2f" % (data[8])
            
    si1145 = checkFile("si1145")
    if si1145:
        data[9] = QC(si1145[5], 0, 2000)
        data[10] = QC(si1145[6], 0, 16000)
        data[11] = QC(si1145[7], 0, 1000)
        if data[9] != -999.99:  
            url += "&si1145_vis=%010.1f&si1145_ir=%010.1f&si1145_uv=%010.1f" % (data[9], data[10], data[11])
            
    wind_direction = checkFile("wind_direction")
    if wind_direction:
        data[12] = QC(wind_direction[5], 0, 360)
        if data[12] != -999.99:  
            url += "&wind_direction=%05.1f" % (data[12])

    wind_speed = checkFile("wind_speed")
    if wind_speed:
        data[13] = QC(wind_speed[5], 0, 103)
        if data[13] != -999.99:  
            url += "&wind_speed=%04.2f" % (data[13])

    #save to daily file if data is being recorded
    if not all(ele == data[0] for ele in data):
        helper_functions.output(False, data, "all")
        helper_functions.output(False, url, "chords")