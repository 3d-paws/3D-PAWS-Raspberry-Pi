#!/usr/bin/python
# Code to update the cron
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import os, sys
from crontab import CronTab
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import helper_functions
cron = CronTab(user='root')
root_path = "/home/pi/3d_paws/scripts/"
variables = "1,1,false,0,3d.chordsrt.com,1013.25,false,100000.0" #record_interval, chords_interval, chords_toggle, chords_id, link, pressue_level, test_toggle, altitude


print("Checking cron...")
active = []
for job in cron:
    if job.is_enabled():
        active.append(job.comment)

print("Updating cron...")
cron.remove_all()


#basic functionality crons
update = cron.new(command='python3 /home/pi/update_3d_paws.py >> /tmp/update_3d_paws.log 2>&1')
update.setall('0 1 * * 1') #Monday at 1am

update2 = cron.new(command='python3 ' + root_path + 'upkeep/update_helper.py >> /tmp/update_helper.log 2>&1')
update2.every_reboot()

report = cron.new(command='python3 ' + root_path + 'upkeep/report.py >> /tmp/report.log 2>&1')
report.minute.every(1)

relay = cron.new(command='python3 ' + root_path + 'upkeep/relay.py >> /tmp/relay.log 2>&1')
relay.setall('0 0 * * *') #Every midnight
relay.set_comment("relay")
relay.enable(True if "relay" in active else False)

link = cron.new(command='ln -s /dev/i2c-1 /dev/i2c-0')
link.every_reboot()
link.set_comment("Resets device link")

backup = cron.new(command='lftp -f /home/pi/ral_backup >> /tmp/ral_backup.log 2>&1')
backup.minute.every(5)
backup.set_comment("RAL FTP")
backup.enable(True if "RAL FTP" in active else False)


#sensor crons
bm = cron.new(command='python3 ' + root_path + 'sensors/bmp_bme.py >> /tmp/bmp.log 2>&1')
bm.minute.every(1)
bm.set_comment("BMP/BME")
bm.enable(True if "BMP/BME" in active else False)

htu = cron.new(command='python3 ' + root_path + 'sensors/htu21d.py >> /tmp/htu21d.log 2>&1')
htu.minute.every(1)
htu.set_comment("HTU21D")
htu.enable(True if "HTU21D" in active else False)

mcp = cron.new(command='python3 ' + root_path + 'sensors/mcp9808.py >> /tmp/mcp9808.log 2>&1')
mcp.minute.every(1)
mcp.set_comment("MCP9808")
mcp.enable(True if "MCP9808" in active else False)

si = cron.new(command='python3 ' + root_path + 'sensors/si1145.py >> /tmp/si1145.log')
si.minute.every(1)
si.set_comment("SI1145")
si.enable(True if "SI1145" in active else False)

rain = cron.new(command='python3 ' + root_path + 'sensors/rain.py >> /tmp/rain.log 2>&1')
rain.every_reboot()
rain.set_comment("Tipping Bucket")
rain.enable(True if "Tipping Bucket" in active else False)

wind_dir = cron.new(command='python3 ' + root_path + 'sensors/wind_direction.py >> /tmp/wind_direction.log 2>&1')
wind_dir.every_reboot()
wind_dir.set_comment("Wind Direction")
wind_dir.enable(True if "Wind Direction" in active else False)

wind_spd = cron.new(command='python3 ' + root_path + 'sensors/wind_speed.py >> /tmp/wind_speed.log 2>&1')
wind_spd.every_reboot()
wind_spd.set_comment("Wind Speed")
wind_spd.enable(True if "Wind Speed" in active else False)


#Write the cron and print it
cron.write()
print("Cron successfully updated. Printing results now...")
print()
cron = CronTab(user='root')
for job in cron:
    print(job)
    print()


#Check for variables.txt, and create it if it doesn't exist
print("Checking for variables.txt...")
variable_path = "/home/pi/Desktop/variables.txt" 
if os.path.exists(variable_path):
    print("variables.txt found.")
else:
    print("Creating variables.txt...")
    with open(variable_path, 'w') as file:
        file.write(variables)
    os.chmod(variable_path, 0o777)
    print("File successfully created.")
print()


#Update ral_backup
ral_path = "/home/pi/ral_backup" 
inputs = helper_functions.getArguments()
id = str(inputs[3])
if os.path.exists(ral_path):
    print("Updating ral_backup...")
    os.system("sudo rm " + ral_path)
    update_ral = True
else:
    print("Creating ral_backup...")
    update_ral = False
with open(ral_path, 'w') as file:
    file.write("connect ftp://ftp.rap.ucar.edu")
    file.write("\n")
    file.write("mirror -R --newer-than=now-7days /home/pi/data/ /incoming/irap/pkucera/weather_stations/3D_PAWS_" + id +"/")
os.chmod(ral_path, 0o777)
if update_ral:
    print("File successfully updated.")
else:
    print("File successfully created.")
print()


#Update desktop icon
print("Updating desktop icon...")
icon_path = "/home/pi/Desktop/3d_paws"
icon_path2 = "/home/pi/Desktop/3d-paws"
if os.path.exists(icon_path):
    os.system("sudo rm " + icon_path)
if os.path.exists(icon_path2):
    os.system("sudo rm " + icon_path2)
os.system("sudo cp /home/pi/3d_paws/desktop.txt /home/pi/Desktop/3d_paws")
print("Icon successfully updated.")
print()


print("Envionment successfully updated.")
print()