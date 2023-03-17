#!/usr/bin/python3
# Helper code for the various sensor scripts
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import datetime, re, sys, os

# Get script arguments
def getVariables():
	# Open the variables file, or make it if it doesn't exist
	variable_path = "/home/pi/Desktop/variables.txt" 
	if not os.path.exists(variable_path):
		with open(variable_path, 'w') as file:
			file.write("false,0,3d.chordsrt.com,1013.25,false,100000.0")
		os.chmod(variable_path, 0o777)
	with open(variable_path, 'r') as file:
		inputs = file.readline().split(",")
	# Get test toggle; set to False if there's an issue with it
	test_toggle = inputs[0].lower()
	if test_toggle != "true" and test_toggle != "false":
		test_toggle = "false"
	# Get chords id; set to 0 if theere's an issue with it or if chords_toggle is false
	clean_chords_id = ''.join(i for i in inputs[1] if i.isdigit())
	if clean_chords_id != "":
		chords_id = int(clean_chords_id)
		if chords_id < 0:
			chords_id = 0
	else:
		chords_id = 0
	# Get chords link
	link = inputs[2]
	# Get pressure level; set to 1013.25 if there's an issue with it
	remove_nondecimal = re.compile(r'[^\d.]+')
	clean_pressure = remove_nondecimal.sub('', inputs[3])
	pressue_level = 1013.25
	if clean_pressure != "":
		pressue_level = float(clean_pressure)
	# Get altitude; set to 100000 if there's an issue with it
	try:
		clean_altitude = remove_nondecimal.sub('', inputs[4])
		altitude = 100000.0
		if clean_altitude != "":
			altitude = float(clean_altitude)
	except:
		altitude = 100000.0
	return [test_toggle, chords_id, link, pressue_level, altitude]


def getCron():
	from crontab import CronTab
	cron = CronTab(user='root')
	interval = 1
	chords = 1
	for job in cron:
		minute = str(job.minute)
		if "report" in job.comment and minute != "*":
			interval = int(minute.split("/")[1])
		elif "chords" in job.comment:
			chords_toggle = job.is_enabled()
			if minute != "*":
				chords = int(minute.split("/")[1])
	return [interval, chords, chords_toggle]
	

# Print output and/or log it
def output(show, line, sensor, remote = None):
	inputs = getVariables()
	interval = getCron()[0]
	now = datetime.datetime.utcnow() #+ datetime.timedelta(minutes=1)
	time = "%4d %02d %02d %02d %02d" % (now.year, now.month, now.day, now.hour, now.minute)
    # Open a file (name based on current date) and format data
	if sensor == "all":
		filename = create_filename('data/', 'recordings_%4d_%02d_%02d.dat' %(now.year, now.month, now.day))
		d = line
		full_line = "%4.4d %4.02d %4.02d %5.02d %4.02d %4d %9.2f %9.2f %8.2f %8.2f %9.2f %9.2f %8.2f %8.2f %8.2f %9.2f %8.2f %8.2f %8.2f %10.2f %9.2f %9.2f %9.2f %11.2f" % (now.year, now.month, now.day, now.hour, now.minute, interval, d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7], d[8], d[9], d[10], d[11], d[12], d[13], d[14], d[15], d[16], d[17])
	elif sensor == "chords":
		filename = create_filename('data/temporary/', 'chords.tmp')
		full_line = line
	elif inputs[0] == "true" or "test_" in sensor:
		if "test_" in sensor:
			sensor = sensor.replace("test_", "")
		filename = create_filename('data/tests/' + sensor + '/', '%s_%4d_%02d_%02d.dat' %(sensor, now.year, now.month, now.day))
		full_line = time + " " + str(now.second) + " " + line
	elif remote:
		filename = create_filename('data/', 'remote_%s_%4d_%02d_%02d.dat' %(sensor, now.year, now.month, now.day))
		full_line = time + " " + line
	else:
		filename = create_filename('data/temporary/', sensor + '.tmp')
		full_line = time + " " + line
	# Save to the file
	if sensor == "chords":
		file = open(filename, 'w')
	else:
		file = open(filename, 'a')
	if os.path.getsize(filename) == 0 and sensor == "all":
		file.write("year  mon  day  hour  min  int  bmp_temp  bmp_pres  bmp_slp  bmp_alt  bme_temp  bme_pres  bme_slp  bme_alt  bme_hum  htu_temp  htu_hum  mcp9808  tipping  vis_light  ir_light  uv_light  wind_dir  wind_speed\n")
	file.write(full_line + '\n')
	file.close()
	# Print to screen if show is True
	if show:
		print(full_line)


def create_filename(folder, file):
	path = "/home/pi/" + folder
	if not os.path.exists(path):
		os.makedirs(path)
	filename = path + file
	return filename


# Format and print errors
def handleError(e, sensor):
	now = datetime.datetime.utcnow()
	error_formatting = "%4d/%02d/%02d %02d:%02d - Error: %s on line {}".format(sys.exc_info()[-1].tb_lineno)
	message = e.args[0]
	error = error_formatting % (now.year, now.month, now.day, now.hour, now.minute, message)
	print(error)
	filename = create_filename('3d_paws/logs/', sensor + '.log')
	line = error + '\n'
	file = open(filename, 'w')
	file.write(line)
	file.close()