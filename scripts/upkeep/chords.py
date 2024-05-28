#!/usr/bin/python
# Code to report to chords
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import datetime
import requests, os, time
path = "/home/pi/data/temporary/chords.tmp"

time.sleep(10)

if os.path.exists(path):
    #Get url
    with open(path,'r+') as file:
        url = file.readline()
        file.truncate(0)

    now = datetime.datetime.now(datetime.timezone.utc)
    url += "&key=21DE6A8A" 
    #url += "&at=%4d-%02d-%02dT%02d:%02d:%02d" % (now.year, now.month, now.day, now.hour, now.minute, now.second)
    try:
        requests.get(url=url)
    except:
        pass