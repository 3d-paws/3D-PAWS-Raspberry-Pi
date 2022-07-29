#!/usr/bin/python
# Code to update the updater
# Joseph E. Rener
# NCAR/RAL
# Boulder, CO USA
# Email: jrener@ucar.edu
# Copyright (c) 2022 UCAR
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import os

if os.path.exists("/home/pi/update_3d_paws.py"):
    os.system("sudo rm /home/pi/update_3d_paws.py")

os.system("sudo cp update_3d_paws.py /home/pi/update_3d_paws.py")