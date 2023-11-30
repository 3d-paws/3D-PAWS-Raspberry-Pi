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


#check cron
print("Checking cron...")
active = []
report_interval = 1
chords_interval = 1
for job in cron:
    minute = str(job.minute)
    if job.is_enabled():
        active.append(job.comment)
    if job.comment == "report" and minute != "*":
        report_interval = int(minute.split("/")[1])
    if job.comment == "chords" and minute != "*":
        chords_interval = int(minute.split("/")[1])
print("Updating cron...")
cron.remove_all()


#basic functionality crons
update = cron.new(command='python3 /home/pi/update_3d_paws.py >> /tmp/update_3d_paws.log 2>&1')
update.setall('0 1 * * 1') #Monday at 1am

update2 = cron.new(command='python3 ' + root_path + 'upkeep/update_helper.py >> /tmp/update_helper.log 2>&1')
update2.every_reboot()

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

report = cron.new(command='python3 ' + root_path + 'upkeep/report.py >> /tmp/report.log 2>&1')
report.minute.every(report_interval)
report.set_comment("report")

chords = cron.new(command='python3 ' + root_path + 'upkeep/chords.py >> /tmp/chords.log 2>&1')
chords.minute.every(chords_interval)
chords.set_comment("chords")
chords.enable(True if "chords" in active else False)


#sensor crons
bm = cron.new(command='python3 ' + root_path + 'sensors/bmp_bme.py >> /tmp/bmp.log 2>&1')
bm.minute.every(report_interval)
bm.set_comment("BMP/BME sensor")
bm.enable(True if "BMP/BME sensor" in active else False)

humidity = cron.new(command='python3 ' + root_path + 'sensors/humidity.py >> /tmp/humidity.log 2>&1')
humidity.minute.every(report_interval)
humidity.set_comment("Humidity sensor")
humidity.enable(True if "Humidity sensor" in active else False)

mcp = cron.new(command='python3 ' + root_path + 'sensors/mcp9808.py >> /tmp/mcp9808.log 2>&1')
mcp.minute.every(report_interval)
mcp.set_comment("MCP9808 sensor")
mcp.enable(True if "MCP9808 sensor" in active else False)

si = cron.new(command='python3 ' + root_path + 'sensors/si1145.py >> /tmp/si1145.log')
si.minute.every(report_interval)
si.set_comment("SI1145 sensor")
si.enable(True if "SI1145 sensor" in active else False)

rain = cron.new(command='python3 ' + root_path + 'sensors/rain.py >> /tmp/rain.log 2>&1')
rain.minute.every(report_interval)
rain.set_comment("Tipping Bucket sensor")
rain.enable(True if "Tipping Bucket sensor" in active else False)

wind_dir = cron.new(command='python3 ' + root_path + 'sensors/wind_direction.py >> /tmp/wind_direction.log 2>&1')
wind_dir.minute.every(report_interval)
wind_dir.set_comment("Wind Direction sensor")
wind_dir.enable(True if "Wind Direction sensor" in active else False)

wind_spd = cron.new(command='python3 ' + root_path + 'sensors/wind_speed.py >> /tmp/wind_speed.log 2>&1')
wind_spd.minute.every(report_interval)
wind_spd.set_comment("Wind Speed sensor")
wind_spd.enable(True if "Wind Speed sensor" in active else False)


#Write the cron and print it
cron.write()
print("Cron successfully updated. Printing results now...")
print()
cron = CronTab(user='root')
for job in cron:
    print(job)
    print()


#Update ral_backup
ral_path = "/home/pi/ral_backup" 
inputs = helper_functions.getVariables()
id = str(inputs[1])
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