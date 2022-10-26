#!/usr/bin/python3
# Helper code for the various sensor scripts
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import datetime, re, sys, os

# Get script arguments
def getArguments():
	# Open the variables file, or make it if it doesn't exist
	variable_path = "/home/pi/Desktop/variables.txt" 
	if not os.path.exists(variable_path):
		with open(variable_path, 'w') as file:
			file.write("1,1,false,0,3d.chordsrt.com,1013.25,false,100000.0")
		os.chmod(variable_path, 0o777)
	with open(variable_path, 'r') as file:
		inputs = file.readline().split(",")
	# Get recording interval
	clean_interval = ''.join(i for i in inputs[0] if i.isdigit())
	if clean_interval != "":
		record_interval = int(clean_interval)
		if record_interval < 0 or record_interval > 60:
			record_interval = 1
	else:
		record_interval = 1
	# Get chords interval. If it's invalid, set it to 1
	clean_interval = ''.join(i for i in inputs[1] if i.isdigit())
	if clean_interval != "":
		chords_interval = int(clean_interval)
		if chords_interval < 0 or chords_interval > 60:
			chords_interval = 1
	else:
		chords_interval = 1
	# Get chords toggle; set to False if there's an issue with it
	chords_toggle = inputs[2].lower()
	if chords_toggle != "true" and chords_toggle != "false":
		chords_toggle = "false"
	# Get chords id; set to 0 if theere's an issue with it or if chords_toggle is false
	clean_chords_id = ''.join(i for i in inputs[3] if i.isdigit())
	if clean_chords_id != "":
		chords_id = int(clean_chords_id)
		if chords_id < 0:
			chords_id = 0
	else:
		chords_id = 0
	# Get chords link
	link = inputs[4]
	# Get pressure level; set to 1013.25 if there's an issue with it
	remove_nondecimal = re.compile(r'[^\d.]+')
	clean_pressure = remove_nondecimal.sub('', inputs[5])
	pressue_level = 1013.25
	if clean_pressure != "":
		pressue_level = float(clean_pressure)
	# Get test toggle; set to False if there's an issue with it
	test_toggle = inputs[6].lower()
	if test_toggle != "true" and test_toggle != "false":
		test_toggle = "false"
	# Get altitude; set to 100000 if there's an issue with it
	try:
		clean_altitude = remove_nondecimal.sub('', inputs[7])
		altitude = 100000.0
		if clean_altitude != "":
			altitude = float(clean_altitude)
	except:
		altitude = 100000.0
	return [record_interval, chords_interval, chords_toggle, chords_id, link, pressue_level, test_toggle, altitude]
	

# Print output and/or log it
def output(show, line, sensor, remote = None):
	inputs = getArguments()
	now = datetime.datetime.utcnow() + datetime.timedelta(minutes=1)
    # Open a file (name based on current date) and append data if the remainder of the current time divided by the interval is 0
	if now.minute % inputs[0] == 0 or inputs[6] == "true":
		time = "%4d %02d %02d %02d %02d" % (now.year, now.month, now.day, now.hour, now.minute)
		if inputs[6] == "true" or "test_" in sensor:
			if "test_" in sensor:
				sensor = sensor.replace("test_", "")
			filename = create_filename('data/tests/' + sensor + '/', '%s_%4d_%02d_%02d.dat' %(sensor, now.year, now.month, now.day))
			full_line = time + " " + str(now.second) + " " + line
		else:
			if sensor == "all":
				filename = create_filename('data/', 'recordings_%4d_%02d_%02d.dat' %(now.year, now.month, now.day))
				d = line
				full_line = "%4.4d %4.02d %4.02d %5.02d %4.02d %9.2f %9.2f %8.2f %8.2f %9.2f %9.2f %8.2f %8.2f %8.2f %9.2f %8.2f %8.2f %8.2f %10.2f %9.2f %9.2f %9.2f %11.2f" % (now.year, now.month, now.day, now.hour, now.minute, d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7], d[8], d[9], d[10], d[11], d[12], d[13], d[14], d[15], d[16], d[17])
			elif remote:
				filename = create_filename('data/', 'remote_%s_%4d_%02d_%02d.dat' %(sensor, now.year, now.month, now.day))
				full_line = time + " " + line
			else:
				filename = create_filename('data/temporary/', sensor + '.tmp')
				full_line = time + " " + line
		if os.path.exists(filename) or sensor != "all":
			file = open(filename, 'a')
			file.write(full_line + '\n')
		else:
			file = open(filename, 'a')
			file.write("year  mon  day  hour  min  bmp_temp  bmp_pres  bmp_slp  bmp_alt  bme_temp  bme_pres  bme_slp  bme_alt  bme_hum  htu_temp  htu_hum  mcp9808  tipping  vis_light  ir_light  uv_light  wind_dir  wind_speed\n")
			file.write(full_line + '\n')
		file.close()
	# Create stdio line and print to screen if show is True
	if show:
		print(full_line) #TODO if interval is more than 1 minute, this line will fail since full_line will never be created in the above if statement


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