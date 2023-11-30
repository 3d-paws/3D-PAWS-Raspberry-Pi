#!/usr/bin/python3
# Helper code for the various sensor scripts
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import datetime, re, sys, os, board, busio

# Get script arguments
def getVariables():
	# Open the variables file, or make it if it doesn't exist
	variable_path = "/home/pi/Desktop/variables.txt" #variables = "false,0,3d.chordsrt.com,1013.25,100000.0" -> test_toggle, chords_id, link, pressue_level, altitude
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
		full_line = "%4.4d %4.02d %4.02d %5.02d %4.02d %4d %10.2f %10.2f %9.2f %9.2f %9.2f %9.2f %8.2f %8.2f %8.2f %10.2f %9.2f %9.2f %9.2f %11.2f" % (now.year, now.month, now.day, now.hour, now.minute, interval, d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7], d[8], d[9], d[10], d[11], d[12], d[13])
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
		file.write(full_line)
	else:
		file = open(filename, 'a')
		if os.path.getsize(filename) == 0 and sensor == "all":
			try:
				import adafruit_bmp3xx
				i2c = board.I2C()
				adafruit_bmp3xx.BMP3XX_I2C(i2c)
				bm = "bmp3"
			except:
				try:
					import adafruit_bmp280
					i2c = busio.I2C(board.SCL, board.SDA)
					adafruit_bmp280.Adafruit_BMP280_I2C(i2c)
					bm = "bmp2"
				except:
					import adafruit_bme280
					i2c = board.I2C()
					adafruit_bme280.Adafruit_BME280_I2C(i2c)
					bm = "bme2"
			try:
				from adafruit_htu21d import HTU21D
				sensor = HTU21D(i2c)
				hum = "htu"
			except:
				import adafruit_sht31d
				sensor = adafruit_sht31d.SHT31D(i2c)
				hum = "sht"
			file.write(f"year  mon  day  hour  min  int  {bm}_temp  {bm}_pres  {bm}_slp  {bm}_alt  bme2_hum  {hum}_temp  {hum}_hum  mcp9808  tipping  vis_light  ir_light  uv_light  wind_dir  wind_speed\n")
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


# Set rest interval for test mode
def getTest():
	# Defaults
	test = True
	iterations = 1000000
	# Get Variables
	interval = getCron()[0]
	test_toggle = getVariables()[0]
	# Check what kind of testing this is
	if len(sys.argv) > 1: 
		rest = int(sys.argv[1])
	elif os.isatty(sys.stdin.fileno()):
		rest = 10
	elif test_toggle == "true":
		rest = 10
		iterations = (interval*6)-1
	else:
		test = False
		rest = 60*interval - 1
		iterations = 1
	return [test, rest, iterations]


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