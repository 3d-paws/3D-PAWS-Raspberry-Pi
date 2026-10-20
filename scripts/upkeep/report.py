#!/usr/bin/python
# Code to control the BMP280 and BME280 I2C sensors. Write observations to disk
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import sys
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import datetime, os, time, helper_functions
time.sleep(5)


#Get variables
variables = helper_functions.getVariables()
test_toggle = variables[0]
chords_id = variables[1]
chords_link = variables[2]
now = datetime.datetime.utcnow()


def checkFile(sensor):
    location = "/home/pi/data/temporary/" + sensor + ".tmp"
    if os.path.exists(location):
        f = open(location, "r+")
        info = f.readline().split()
        f.close()
        os.remove(location)
        return info
    return False


# Read a Particle parity sensor's temporary file and save the reading to its daily .dat file
def checkParticleFile(sensor):
    info = checkFile(sensor)
    if info:
        values = info[5:]
        if values[0] == sensor:
            values = values[1:]
        if sensor == "ds18b20":
            temps = dict(v.split("=") for v in values)
            values = [temps.get("dst%d" % ch, -999.99) for ch in range(8)]
        elif sensor == "multigas":
            gases = dict(v.split("=") for v in values)
            values = [gases.get(gas, -999.99) for gas in helper_functions.MULTIGAS_GASES]
        helper_functions.recordSensor(sensor, values)
    return info


def QC(value, min, max):
    value = float(value)
    if value <= max and value >= min:
        return value
    return -999.99


# Add a value to the CHORDS url using the Particle short name, skipping values that failed QC
def add(name, value, min=None, max=None):
    global url
    value = float(value)
    if min is not None:
        value = QC(value, min, max)
        if value == -999.99:
            return
    url += "&%s=%.2f" % (name, value)


# Sum the rain column of a daily recordings file (rain is column 15)
def dailyRain(day):
    location = "/home/pi/data/recordings_%4d_%02d_%02d.dat" % (day.year, day.month, day.day)
    total = 0.0
    if os.path.exists(location):
        with open(location, "r") as f:
            for line in f:
                values = line.split()
                try:
                    if float(values[14]) >= 0:
                        total += float(values[14])
                except (IndexError, ValueError):
                    pass  # header line
    return total


if test_toggle == "false":
    #data = [bm_temp, bm_pressure, bm_slp, bm_altitude, bme2_humidity, hum_temp, hum_humidity, mcp9808, rain, si1145_vis, si1145_ir, si1145_uv, wind_direction, wind_speed]
    data = [-999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99, -999.99]
    url = "http://%s/measurements/url_create?instrument_id=%d" % (chords_link, chords_id)

    # Sensor numbering follows the Particle firmware: a BMP581 or SHT45 becomes sensor 2 when a BMP280 or SHT31 is also connected
    bm = checkFile("bm")
    if bm:
        data[0] = QC(bm[6], -40, 60)
        data[1] = QC(bm[7], 300, 1100)
        data[2] = float(bm[8])
        data[3] = float(bm[9])
        if data[0] != -999.99 and data[1] != -999.99:
            add("bp1", data[1])
            add("bt1", data[0])
            add("mslp", data[2])

    bmp581 = checkParticleFile("bmp581")
    if bmp581:
        n = 2 if bm else 1
        add("bp%d" % n, bmp581[7], 300, 1100)
        add("bt%d" % n, bmp581[6], -40, 60)
        if not bm:
            add("mslp", bmp581[8], 300, 1100)

    humidity = checkFile("humidity")
    if humidity:
        prefix = "s"
        if humidity[5] == "htu":
            prefix = "h"
        data[5] = QC(humidity[6], -40, 60)
        data[6] = QC(humidity[7], 0, 100)
        if data[5] != -999.99:
            add("%st1" % prefix, data[5])
            add("%sh1" % prefix, data[6], 0, 100)

    sht45 = checkParticleFile("sht45")
    if sht45:
        n = 2 if humidity and humidity[5] != "htu" else 1
        add("st%d" % n, sht45[6], -40, 60)
        add("sh%d" % n, sht45[7], 0, 100)

    hdc302x = checkParticleFile("hdc302x")
    if hdc302x:
        add("hdt1", hdc302x[5], -40, 60)
        add("hdh1", hdc302x[6], 0, 100)

    hih8000 = checkParticleFile("hih8000")
    if hih8000:
        add("ht2", hih8000[5], -40, 60)
        add("hh2", hih8000[6], 0, 100)

    lps35hw = checkParticleFile("lps35hw")
    if lps35hw:
        add("lpp1", lps35hw[5], 300, 1100)
        add("lpt1", lps35hw[6], -40, 60)

    mcp9808 = checkFile("mcp9808")
    if mcp9808:
        data[7] = QC(mcp9808[5], -40, 60)
        if data[7] != -999.99:
            add("mt1", data[7])

    rain = checkFile("rain")
    if rain:
        data[8] = QC(rain[5], 0, 60)
        if data[8] != -999.99:
            # Daily totals roll over at 00:00 UTC, the same as the Particle default
            add("rg", data[8])
            add("rgt", dailyRain(now) + data[8])
            add("rgp", dailyRain(now - datetime.timedelta(days=1)))

    si1145 = checkFile("si1145")
    if si1145:
        data[9] = QC(si1145[5], 0, 2000)
        data[10] = QC(si1145[6], 0, 16000)
        data[11] = QC(si1145[7], 0, 1000)
        if data[9] != -999.99:
            add("sv1", data[9])
            add("si1", data[10], 0, 16000)
            add("su1", data[11], 0, 1000)

    veml7700 = checkParticleFile("veml7700")
    if veml7700:
        add("vlx", veml7700[5], 0, 150000)

    b_lux_v30b = checkParticleFile("b_lux_v30b")
    if b_lux_v30b:
        add("blx", b_lux_v30b[5], 0, 200000)

    # Named like the Particle SensorTesting firmware (sensor 1)
    bh1750 = checkParticleFile("bh1750")
    if bh1750:
        add("dfrl1", bh1750[5], 0, 70000)

    pyranometer = checkParticleFile("pyranometer")
    if pyranometer:
        add("sr", pyranometer[5], 0, 2000)

    pm25aqi = checkParticleFile("pm25aqi")
    if pm25aqi:
        url += "&pm1e10=%d&pm1e25=%d&pm1e100=%d" % (float(pm25aqi[5]), float(pm25aqi[6]), float(pm25aqi[7]))

    maxbotix = checkParticleFile("maxbotix")
    if maxbotix:
        add("sg", maxbotix[5])

    tinovi_leaf = checkParticleFile("tinovi_leaf")
    if tinovi_leaf:
        add("tlww", tinovi_leaf[5])
        add("tlwt", tinovi_leaf[6], -40, 60)

    tinovi_soil = checkParticleFile("tinovi_soil")
    if tinovi_soil:
        add("tsme25", tinovi_soil[5])
        add("tsmec", tinovi_soil[6])
        add("tsmt", tinovi_soil[7], -40, 60)
        add("tsmvwc", tinovi_soil[8])

    # 2 temperatures followed by 5 soil moisture zones
    tinovi_multi_soil = checkParticleFile("tinovi_multi_soil")
    if tinovi_multi_soil:
        for i in range(2):
            add("tmsmt%d" % (i+1), tinovi_multi_soil[5+i], -40, 60)
        for i in range(5):
            add("tmsms%d" % (i+1), tinovi_multi_soil[7+i])

    # Already labeled dst<channel>=<temp>
    ds18b20 = checkParticleFile("ds18b20")
    if ds18b20:
        for reading in ds18b20[5:]:
            name, value = reading.split("=")
            add(name, value, -40, 60)

    # SEN66, gas, and weighing rain gauge names follow the Particle SensorTesting firmware (sensor 1)
    sen66 = checkParticleFile("sen66")
    if sen66:
        add("s66-Pm1p0-1", sen66[5], 0, 1000)
        add("s66-Pm2p5-1", sen66[6], 0, 1000)
        add("s66-Pm4p0-1", sen66[7], 0, 1000)
        add("s66-Pm10p0-1", sen66[8], 0, 1000)
        add("s66-h-1", sen66[9], 0, 100)
        add("s66-t-1", sen66[10], -40, 60)
        add("s66-voc-1", sen66[11], 1, 500)
        add("s66-nox-1", sen66[12], 1, 500)
        add("s66-co2-1", sen66[13], 0, 40000)

    # Already labeled <gas>=<value>
    multigas = checkParticleFile("multigas")
    if multigas:
        for reading in multigas[5:]:
            gas, value = reading.split("=")
            add("dfrg-%s-1" % gas, value, 0, 10000)

    weighing_rain = checkParticleFile("weighing_rain")
    if weighing_rain:
        add("wrg-1", weighing_rain[5], 0, 1000)

    wind_direction = checkFile("wind_direction")
    if wind_direction:
        data[12] = QC(wind_direction[5], 0, 360)
        if data[12] != -999.99:
            add("wd", data[12])

    wind_speed = checkFile("wind_speed")
    if wind_speed:
        data[13] = QC(wind_speed[5], 0, 103)
        if data[13] != -999.99:
            add("ws", data[13])

    #save to daily file if data is being recorded
    if not all(ele == data[0] for ele in data):
        helper_functions.output(False, data, "all")
    if "&" in url:
        helper_functions.output(False, url, "chords")
