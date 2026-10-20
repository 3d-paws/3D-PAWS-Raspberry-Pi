#!/usr/bin/python3
# Reads the last 24 hours of readings for every sensor that is turned on; shared by the dashboard window and the terminal view
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import datetime, os
from crontab import CronTab
import helper_functions

DATA_PATH = '/home/pi/data/'
REFRESH_SECONDS = 30
HOURS = 24
MISSING = -999.0

def field(label, unit, daily, test, decimals=1, kind="line", scale=1.0):
    # daily/test = column of the value, counting from the first value after the timestamp (and interval, in daily files)
    return {"label": label, "unit": unit, "daily": daily, "test": test, "decimals": decimals, "kind": kind, "scale": scale}


def temp(daily, test, label="Temperature"):
    return field(label, "°C", daily, test)


def humidity(daily, test):
    return field("Relative humidity", "%", daily, test)


def pressure(daily, test, label="Station pressure"):
    return field(label, "hPa", daily, test)


# GUI name (cron comment), daily file prefix, test folder, fields
SENSORS = [
    ("BMP/BME sensor", "recordings", "bm", [temp(0, 0), pressure(1, 1), pressure(2, 2, "Sea level pressure")]),
    ("BMP581 sensor", "bmp581", "bmp581", [temp(0, 0), pressure(1, 1), pressure(2, 2, "Sea level pressure")]),
    ("Humidity sensor", "recordings", "humidity", [temp(5, 0), humidity(6, 1)]),
    ("SHT45 sensor", "sht45", "sht45", [temp(0, 0), humidity(1, 1)]),
    ("MCP9808 sensor", "recordings", "mcp9808", [temp(7, 0)]),
    ("DS18B20 sensor", "ds18b20", "ds18b20", [temp(ch, ch, "Probe %d temperature" % ch) for ch in range(8)]),
    ("Wind Speed sensor", "recordings", "wind_speed", [field("Wind speed", "m/s", 13, 0)]),
    ("Wind Direction sensor", "recordings", "wind_direction", [field("Wind direction", "°", 12, 0, 0, "direction")]),
    ("Tipping Bucket sensor", "recordings", "rain", [field("Rain, last 24 h", "mm", 8, 0, 2, "rain")]),
    ("SI1145 sensor", "recordings", "si1145", [field("Visible light", "", 9, 0, 0), field("Infrared light", "", 10, 1, 0), field("UV index", "", 11, 2, 2, scale=0.01)]),
    ("B-LUX-V30B sensor", "b_lux_v30b", "b_lux_v30b", [field("Light", "lux", 0, 0, 0)]),
    ("SEN0562 Light sensor", "bh1750", "bh1750", [field("Light", "lux", 0, 0, 0)]),
    ("PM25AQI sensor", "pm25aqi", "pm25aqi", [field("PM1.0", "µg/m³", 0, 0, 0), field("PM2.5", "µg/m³", 1, 1, 0), field("PM10", "µg/m³", 2, 2, 0)]),
    ("Maxbotix Distance sensor", "maxbotix", "maxbotix", [field("Distance", "mm", 0, 0, 0)]),
    ("SEN66 sensor", "sen66", "sen66",
        [field(label, "µg/m³", i, i) for i, label in enumerate(["PM1.0", "PM2.5", "PM4.0", "PM10"])]
        + [temp(5, 5), humidity(4, 4), field("VOC index", "", 6, 6, 0), field("NOx index", "", 7, 7, 0), field("CO₂", "ppm", 8, 8, 0)]),
    ("Multigas sensor", "multigas", "multigas",
        [field(gas.upper(), "%" if gas == "o2" else "ppm", i, i, 2) for i, gas in enumerate(helper_functions.MULTIGAS_GASES)]),
    ("Weighing Rain Gauge sensor", "weighing_rain", "weighing_rain", [field("Rain (weight), 24 h", "g", 0, 0, 2, "rain")]),
]


def isNumber(text):
    try:
        float(text)
        return True
    except ValueError:
        return False


# Split a data file line into (time, [values]); handles daily files and test files
def parseLine(line):
    parts = line.split()
    if len(parts) < 2 or parts[0] == "year":
        return None
    try:
        if "_" in parts[0]:
            # Test file: 2026-10-05_17:24:43 <values>
            when = datetime.datetime.strptime(parts[0], "%Y-%m-%d_%H:%M:%S")
            values = parts[1:]
        else:
            # Daily file: year mon day hour min interval <values>
            when = datetime.datetime(*[int(p) for p in parts[0:5]])
            values = parts[6:]
    except ValueError:
        return None
    if values and "=" in values[0]:
        # Test lines labeled dst<channel>=<temp> (DS18B20) or <gas>=<value> (multigas)
        labeled = dict(v.split("=") for v in values)
        if values[0].startswith("dst"):
            names = ["dst%d" % ch for ch in range(8)]
        else:
            names = helper_functions.MULTIGAS_GASES
        values = [labeled.get(name, str(MISSING)) for name in names]
    elif values and not isNumber(values[0]):
        # Drop a leading sensor name such as "bmp" or "sht45"
        values = values[1:]
    return when, values


# Read the rows from the last 24 hours for one sensor; files are cached so recordings_*.dat is read once per refresh
def readRows(prefix, folder, test_mode, cache):
    now = datetime.datetime.utcnow()
    start = now - datetime.timedelta(hours=HOURS)
    rows = []
    for day in sorted(set([start.date(), now.date()])):
        stamp = day.strftime("%Y_%m_%d")
        if test_mode:
            path = DATA_PATH + "tests/%s/%s_%s.dat" % (folder, folder, stamp)
        else:
            path = DATA_PATH + "%s_%s.dat" % (prefix, stamp)
        if path not in cache:
            cache[path] = []
            if os.path.exists(path):
                with open(path) as f:
                    cache[path] = [row for row in (parseLine(line) for line in f) if row]
        rows += [row for row in cache[path] if row[0] >= start]
    return rows


# Comment of every cron job that is turned on
def activeSensors():
    try:
        return [job.comment for job in CronTab(user='root') if job.is_enabled()]
    except Exception:
        return []


# Build the tile data for every sensor that is turned on
def collectTiles():
    test_mode = helper_functions.getVariables()[0] == "true"
    interval = helper_functions.getCron()[0]
    stale_after = datetime.timedelta(minutes=max(3, interval * 3))
    gap = datetime.timedelta(minutes=max(10, interval * 3))
    now = datetime.datetime.utcnow()
    active = activeSensors()
    cache = {}
    groups = []
    for name, prefix, folder, fields in SENSORS:
        if name not in active:
            continue
        rows = readRows(prefix, folder, test_mode, cache)
        tiles = []
        for f in fields:
            col = f["test"] if test_mode else f["daily"]
            points = []
            for when, values in rows:
                if len(values) > col and isNumber(values[col]) and float(values[col]) > MISSING:
                    points.append((when, float(values[col]) * f["scale"]))
            if not points:
                continue
            tile = dict(f)
            if f["kind"] == "rain":
                # Chart the running total so the tile shows how much fell over the day
                total = 0.0
                running = []
                for when, value in points:
                    total += value
                    running.append((when, total))
                points = running
            tile["points"] = points
            tile["stale"] = now - points[-1][0] > stale_after
            tile["gap"] = gap
            tiles.append(tile)
        if not tiles:
            tiles.append({"label": "Waiting for the first reading", "waiting": True})
        groups.append((name, tiles))
    return groups, test_mode


def formatValue(tile, value, axis=False):
    if tile["kind"] == "direction" and axis:
        return "%d°" % value
    if tile["kind"] == "direction":
        compass = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((value % 360) / 45.0 + 0.5) % 8]
        return "%d° %s" % (value, compass)
    return "{:,.{d}f}".format(value, d=tile["decimals"])


def ago(when):
    minutes = int((datetime.datetime.utcnow() - when).total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 120:
        return "%d min ago" % minutes
    return "%d h ago" % (minutes // 60)
