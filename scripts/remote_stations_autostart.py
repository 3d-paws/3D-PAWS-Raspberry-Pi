#!/usr/bin/env python3
# Code to run the remote rain daemon on restart
# Joseph E. Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Copyright (c) 2022 UCAR
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

#to use this file, vi ~/.config/lxsession/LXDE-pi/autostart and add @sudo /usr/bin/python3 /home/pi/3d-paws/scripts/remote_stations_autostart.py

import os

if os.path.exists('/home/pi/3d-paws/logs/remote_stations_check'):
    os.system('sudo pkill -f remote_stations_server') #stop the remote station daemon (to prevent duplicates)
    os.system('sudo /home/pi/3d-paws/scripts/comms/rf95/remote_stations_server -d') #start the remote station daemon