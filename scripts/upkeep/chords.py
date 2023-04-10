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

    url += "&key=21DE6A8A"
    try:
        requests.get(url=url)
    except:
        pass