#!/usr/bin/python
# Code to update the cron
# Joseph E. Rener
# NCAR/RAL
# Boulder, CO USA
# Email: jrener@ucar.edu
# Copyright (c) 2022 UCAR
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import os
from crontab import CronTab
cron = CronTab(user='root')
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

update2 = cron.new(command='python3 /home/pi/3d_paws/scripts/upkeep/update_helper.py >> /tmp/update_helper.log 2>&1')
update2.every_reboot()

report = cron.new(command='python3 /home/pi/3d_paws/scripts/upkeep/report.py >> /tmp/report.log 2>&1')
report.minute.every(1)

relay = cron.new(command='python3 /home/pi/3d_paws/scripts/upkeep/relay.py >> /tmp/relay.log 2>&1')
relay.setall('0 0 * * *') #Every midnight
relay.set_comment("relay")
relay.enable(True if "relay" in active else False)

link = cron.new(command='ln -s /dev/i2c-1 /dev/i2c-0')
link.every_reboot()
link.set_comment("Resets device link")

#sensor crons
bm = cron.new(command='python3 /home/pi/3d_paws/scripts/sensors/bmp_bme.py >> /tmp/bmp.log 2>&1')
bm.minute.every(1)
bm.set_comment("BMP/BME")
bm.enable(True if "BMP/BME" in active else False)

htu = cron.new(command='python3 /home/pi/3d_paws/scripts/sensors/htu21d.py >> /tmp/htu21d.log 2>&1')
htu.minute.every(1)
htu.set_comment("HTU21D")
htu.enable(True if "HTU21D" in active else False)

mcp = cron.new(command='python3 /home/pi/3d_paws/scripts/sensors/mcp9808.py >> /tmp/mcp9808.log 2>&1')
mcp.minute.every(1)
mcp.set_comment("MCP9808")
mcp.enable(True if "MCP9808" in active else False)

si = cron.new(command='python3 /home/pi/3d_paws/scripts/sensors/si1145.py >> /tmp/si1145.log')
si.minute.every(1)
si.set_comment("SI1145")
si.enable(True if "SI1145" in active else False)

rain = cron.new(command='python3 /home/pi/3d_paws/scripts/sensors/rain.py >> /tmp/rain.log 2>&1')
rain.every_reboot()
rain.set_comment("Tipping Bucket")
rain.enable(True if "Tipping Bucket" in active else False)

wind_dir = cron.new(command='python3 /home/pi/3d_paws/scripts/sensors/wind_direction.py >> /tmp/wind_direction.log 2>&1')
wind_dir.every_reboot()
wind_dir.set_comment("Wind Direction")
wind_dir.enable(True if "Wind Direction" in active else False)

wind_spd = cron.new(command='python3 /home/pi/3d_paws/scripts/sensors/wind_speed.py >> /tmp/wind_speed.log 2>&1')
wind_spd.every_reboot()
wind_spd.set_comment("Wind Speed")
wind_spd.enable(True if "Wind Speed" in active else False)

#backup cron
backup = cron.new(command='lftp -f /home/pi/3d_paws/scripts/comms/mirror_to_ral_ftp >> /tmp/mirror_to_ral_ftp.log 2>&1')
backup.minute.every(5)
backup.set_comment("RAL FTP")
backup.enable(True if "RAL FTP" in active else False)


cron.write()
print("Cron successfully updated. Printing results now...")
print()
cron = CronTab(user='root')
for job in cron:
    print(job)
    print()


print("Checking for variables.txt...")
variable_path = "/home/pi/Desktop/variables.txt" 
if os.path.exists(variable_path):
    print("variables.txt found.")
else:
    print("Creating variables.txt...")
    with open(variable_path, 'w') as file:
        file.write(variables)
    os.chmod(variable_path, 0o777)
    print("Envionment successfully updated.")
print()