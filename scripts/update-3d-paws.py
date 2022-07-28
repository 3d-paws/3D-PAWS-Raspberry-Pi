#!/usr/bin/python
# Code to update 3d paws software
# Joseph E. Rener
# NCAR/RAL
# Boulder, CO USA
# Email: jrener@ucar.edu
# Copyright (c) 2022 UCAR
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)
#This file should ALWAYS be placed in /home/pi on new systems. 

#To stop updates: change environement.py so it will turn off the cron for update-3d-paws.py, thus stopping updates on all current stations. Wait for this update to be pushed out before
#committing the changes that aren't reverse compatable. Change environement.py back before setting up new stations so that they'll still be able to update.

import os, sys, time, urllib.request


#checks for internet connection
def connect():
    try:
        urllib.request.urlopen('http://google.com')
        print("Internet found.")
        print()
        if not os.path.exists("time_check.txt"):
            print("Setting the Real Time Clock...")
            result = os.system("sudo hwclock -w")
            if result == 0:
                with open("time_check.txt", 'w') as file:
                    file.write("RTC successfully set. Do not delete this file unless you need to reset the RTC.")
                print("RTC successfully set.")
            else:
                print("Failed to set RTC. It is likely not connected.")
            print()
        return True
    except:
        return False


def cleanup(situation): 
    if os.path.exists("3d-paws"):
        if os.path.exists("3d-paws-old"):
            print("Finalizing changes...")
            run_command("sudo rm -rf 3d-paws-old", situation)
        print("Update complete!")
        print("Restarting...")
        time.sleep(4)
        os.system("sudo reboot")
    else:
        if os.path.exists("3d-paws-old"):
            print("Rolling back changes...")
            run_command("sudo mv 3d-paws-old 3d-paws", situation)


#runs a command in terminal and checks for issues; extra: 1 = git error, 2 = error while fixing error
def run_command(command, extra=None):
    code = os.system(command)
    if code != 0:
        if extra == 1:
            print("ERROR: Failed to connect to git with exit code %d. Attempting to fix..." %code)
            run_command("sudo apt-get install git")
            run_command(command, 2)
        elif extra != 2:
            print("ERROR: Failed with exit code %d. Attempting to fix (this could take some time)..." %code)
            run_command("sudo apt-get update", 2)
            run_command("sudo apt full-upgrade", 2)
            print("Pi OS successfully updated. Trying failed step again...")
            run_command(command, 2)
        elif extra == 2:
            print("ERROR: Could not solve the issue. Command '%s' failed with exit code %d. Please go to https://github.com/3d-paws/3d-paws for detailed instructions, or contact Joey at jrener@ucar.edu for assistance." %(command, code))
            print()
            cleanup(2)
            print("Update failed.")
            sys.exit()


#check for internet
print("Checking for internet...")
if not connect():
    print("No internet connection found. You must be connected to the internet in order to update software.")
    print()
    sys.exit()
#download
print("Downloading 3D PAWS software package...")
if os.path.exists("3d-paws"):
    run_command("sudo mv 3d-paws 3d-paws-old")
run_command("sudo git clone https://github.com/3d-paws/3d-paws", 1)
print("Download complete.")
print()
#permissions
print("Updating permissions...")
run_command("sudo chmod -R a+rwx 3d-paws/")
print("Permissions successfully updated.")
print()
#install
print("Installing dependencies (this could take some time)...")
run_command("sudo python3 3d-paws/setup.py install")
print("Dependencies successfully installed.")
print()
#cron
print("Updating cron...")
run_command("sudo python3 3d-paws/environment.py")
print("Cron successfully updated.")
print()
#finish
cleanup(None)