#!/usr/bin/python
# Code to report to chords
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import requests, os, time
path = "/home/pi/data/temporary/chords.tmp"

time.sleep(10)

if os.path.exists(path):
    #Get url
    with open(path,'r+') as file:
        url = file.readline().replace("/n","")
        file.truncate(0)

    #url = "http://%s/measurements/url_create?instrument_id=%d&bmp_temp=%05.1f&bmp_pressure=%07.2f&bmp_slp=%07.2f&bmp_altitude=%07.2f&bme_temp=%05.1f&bme_pressure=%07.2f&bme_slp=%07.2f&bme_altitude=%07.2f&bme_humidity=%07.2f&htu21d_temp=%05.1f&htu21d_humidity=%04.1f&mcp9808=%05.1f&rain=%04.2f&si1145_vis=%010.1f&si1145_ir=%010.1f&si1145_uv=%010.1f&wind_direction=%05.1f&wind_speed=%04.2f&key=21DE6A8A" % (chords_link, chords_id, data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7], data[8], data[9], data[10], data[11], data[12], data[13], data[14], data[15], data[16], data[17])	
    url += "&key=21DE6A8A"
    try:
        requests.get(url=url)
    except:
        pass