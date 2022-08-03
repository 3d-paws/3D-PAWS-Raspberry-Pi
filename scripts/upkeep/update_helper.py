#!/usr/bin/python
# Code to update the updater
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import os

if os.path.exists("/home/pi/update_3d_paws.py"):
    os.system("sudo rm /home/pi/update_3d_paws.py")

os.system("sudo cp /home/pi/3d_paws/scripts/upkeep/update_3d_paws.py /home/pi/update_3d_paws.py")
os.chmod("/home/pi/update_3d_paws.py", 0o777)