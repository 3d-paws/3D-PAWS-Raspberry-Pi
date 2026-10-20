#!/usr/bin/python3
# Terminal version of the dashboard (works over ssh): latest reading and a 24-hour text chart for every sensor that is turned on
# Run with:  sudo python3 /home/pi/3d_paws/scripts/gui/dashboard_terminal.py
# Add --once to print the dashboard one time and exit instead of refreshing
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import datetime, os, shutil, sys, textwrap, time
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashboard_data import HOURS, REFRESH_SECONDS, collectTiles, formatValue, ago

# Fall back to plain characters if the terminal can't show Unicode block characters
try:
    "▁█⚠°".encode(sys.stdout.encoding or "ascii")
    BARS, WARN = "▁▂▃▄▅▆▇█", "⚠"
except UnicodeEncodeError:
    BARS, WARN = "_.-:=+*#", "!"
    sys.stdout.reconfigure(errors="replace")

COLOR = sys.stdout.isatty()


def style(text, code):
    return "\033[%sm%s\033[0m" % (code, text) if COLOR else text


# Average the readings into equal time slots across the last 24 hours; blank where nothing was recorded
def sparkline(tile, width):
    end = datetime.datetime.utcnow()
    start = end - datetime.timedelta(hours=HOURS)
    slots = [[] for _ in range(width)]
    for when, value in tile["points"]:
        i = int((when - start).total_seconds() / (HOURS * 3600.0) * width)
        slots[min(max(i, 0), width - 1)].append(value)
    values = [sum(s) / len(s) if s else None for s in slots]
    if tile["kind"] == "direction":
        low, high = 0.0, 360.0
    else:
        # Range of the actual readings, not the slot averages
        low, high = min(v for _, v in tile["points"]), max(v for _, v in tile["points"])
        if tile["kind"] == "rain":
            low = 0.0
    chars = ""
    for v in values:
        if v is None:
            chars += " "
        elif high - low < 1e-9:
            chars += BARS[len(BARS) // 2]
        else:
            chars += BARS[int((v - low) / (high - low) * (len(BARS) - 1) + 0.5)]
    return chars, "%s to %s" % (formatValue(tile, low, axis=True), formatValue(tile, high, axis=True))


def render():
    groups, test_mode = collectTiles()
    columns = shutil.get_terminal_size((80, 24)).columns
    now = datetime.datetime.utcnow().strftime("%H:%M:%S")
    mode = "Test mode: showing test readings" if test_mode else "Sensors that are turned on, last %d hours" % HOURS
    lines = [style("3D-PAWS Dashboard", "1")]
    header = "%s  ·  updated %s UTC  ·  charts run from %d h ago (left) to now (right)" % (mode, now, HOURS)
    lines += [style(l, "2") for l in textwrap.wrap(header, columns)]
    if not groups:
        lines.append("")
        message = "No sensors are turned on. Turn sensors on in the 3D-PAWS Controller to see their readings here."
        if os.geteuid() != 0:
            message = "Can't tell which sensors are turned on. Run this with sudo: sudo python3 " + os.path.abspath(__file__)
        lines += textwrap.wrap(message, columns)
    # label | value + unit | time or warning | chart | range; the chart moves to its own line on narrow terminals
    label_width, value_width, status_width = 22, 14, 28
    fixed = 2 + label_width + value_width + status_width
    for name, tiles in groups:
        lines.append("")
        lines.append(style(name.replace(" sensor", ""), "1"))
        for tile in tiles:
            if tile.get("waiting"):
                lines.append("  " + style("On, but nothing recorded in the last %d hours" % HOURS, "2"))
                continue
            when, value = tile["points"][-1]
            reading = formatValue(tile, value)
            if tile["unit"] and tile["kind"] != "direction":
                reading += " " + tile["unit"]
            if tile["stale"]:
                status = style(("%s Last reading %s" % (WARN, ago(when))).ljust(status_width), "33")
            else:
                status = style(when.strftime("%H:%M UTC").ljust(status_width), "2")
            row = "  " + tile["label"].ljust(label_width) + style(reading.ljust(value_width), "1") + status
            chart_width = columns - fixed - 20
            if chart_width >= 12:
                chart, span = sparkline(tile, chart_width)
                lines.append(row + style(chart, "34") + "  " + style(span, "2"))
            else:
                lines.append(row.rstrip())
                chart, span = sparkline(tile, max(10, columns - 24))
                lines.append("    " + style(chart, "34") + "  " + style(span, "2"))
    return "\n".join(lines)


def main():
    if "--once" in sys.argv:
        print(render())
        return
    try:
        while True:
            screen = render()
            footer = style("Refreshes every %d s. Press Ctrl+C to quit." % REFRESH_SECONDS, "2")
            # Clear the screen and draw the whole dashboard at once to avoid flicker
            sys.stdout.write("\033[2J\033[H" + screen + "\n\n" + footer + "\n")
            sys.stdout.flush()
            time.sleep(REFRESH_SECONDS)
    except KeyboardInterrupt:
        print()


if __name__ == '__main__':
    main()
