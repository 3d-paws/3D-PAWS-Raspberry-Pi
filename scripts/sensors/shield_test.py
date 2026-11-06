#!/usr/bin/env python3
"""
shield_test.py  -  read several temperature, humidity and pressure sensors side by side

Reads every configured sensor in the same second, shows a live table that refreshes like `watch`
(each sensor's reading and its difference from the reference sensor, plus the average difference since
the start), and logs every round to one CSV. For radiation shield tests and for checking sensor models
against each other. Uses the direct I2C drivers in drivers/ (no Adafruit libraries).

Usage (from /home/pi/3d_paws/scripts/sensors/):
  python3 shield_test.py                       default set, refresh every 10 s, log to a results folder
  python3 shield_test.py --every 30            refresh and log every 30 s
  python3 shield_test.py --ref bmp581@0x47     differences from the BMP581 instead of the first sensor
  python3 shield_test.py --sensors sht45@0x44=inside sht31@0x45=outside
  python3 shield_test.py --once                one reading, no refresh, no log
  python3 shield_test.py --scan                which supported sensors answer, at which addresses

Sensors are model@address, optionally =label. Models: sht45, sht31, bmp390, bmp581, mcp9808.
Default set (one of each on one bus): sht45@0x44 sht31@0x45 bmp390@0x77 bmp581@0x47 mcp9808@0x18.
The SHT31 must be at 0x45 (ADR pin high) next to an SHT45, which is fixed at 0x44.
A sensor that doesn't answer at the start is listed as not found and left out.

Results: /home/pi/data/tests/shield_test_<date_time>/readings.csv and summary.txt (written at Ctrl+C).
"""
import argparse
import csv
import datetime as dt
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drivers

DATA_DIR = "/home/pi/data/tests"
DEFAULT = ["sht45@0x44", "sht31@0x45", "bmp390@0x77", "bmp581@0x47", "mcp9808@0x18"]
COLUMNS = [("temp_c", "Temp C", "%7.2f", "%+6.2f"), ("rh_pct", "RH %", "%6.1f", "%+5.1f"),
           ("pressure_hpa", "hPa", "%8.2f", "%+6.2f")]


def parse_spec(spec):
    """'sht31@0x45=outside' -> (model, address, label)."""
    label = None
    if "=" in spec:
        spec, label = spec.split("=", 1)
    model, _, addr = spec.partition("@")
    model = model.lower()
    if model not in drivers.MODELS:
        raise ValueError("unknown model %s (known: %s)" % (model, ", ".join(sorted(drivers.MODELS))))
    cls = drivers.MODELS[model]
    address = int(addr, 16) if addr else cls.ADDRESSES[0]
    if address not in cls.ADDRESSES:
        raise ValueError("%s can't be at 0x%02X (possible: %s)" % (model, address,
                         ", ".join("0x%02X" % a for a in cls.ADDRESSES)))
    return model, address, label or "%s@0x%02X" % (model, address)


class Stats:
    """Running mean and standard deviation of one sensor's difference from the reference."""

    def __init__(self):
        self.n, self.total, self.squares = 0, 0.0, 0.0

    def add(self, x):
        self.n += 1
        self.total += x
        self.squares += x * x

    def mean(self):
        return self.total / self.n if self.n else None

    def sd(self):
        if self.n < 2:
            return None
        return math.sqrt(max(0.0, (self.squares - self.total ** 2 / self.n) / (self.n - 1)))


class Comparison:
    def __init__(self, bus, specs, ref=None):
        self.sensors, self.missing = [], []
        for spec in specs:
            model, address, label = parse_spec(spec)
            try:
                self.sensors.append((label, drivers.MODELS[model](bus, address)))
            except (IOError, OSError) as e:
                self.missing.append("%s (%s)" % (label, e))
        if not self.sensors:
            raise IOError("none of the sensors answered")
        labels = [label for label, _ in self.sensors]
        if ref and ref not in labels:
            raise ValueError("reference %s is not one of the sensors found: %s" % (ref, ", ".join(labels)))
        self.ref = ref or labels[0]
        self.stats = {}
        self.rounds = 0
        self.errors = 0

    def refs(self):
        """The reference sensor for each quantity: --ref if it measures it, else the first that does."""
        out = {}
        for q, *_ in COLUMNS:
            have = [label for label, s in self.sensors if q in s.QUANTITIES]
            if have:
                out[q] = self.ref if self.ref in have else have[0]
        return out

    def read_all(self):
        values = {}
        for label, s in self.sensors:
            try:
                values[label] = s.read()
            except (IOError, OSError):
                values[label] = {}
                self.errors += 1
        self.rounds += 1
        for q, ref in self.refs().items():
            if q not in values[ref]:
                continue
            for label, s in self.sensors:
                if label != ref and q in values[label]:
                    self.stats.setdefault((label, q), Stats()).add(values[label][q] - values[ref][q])
        return values

    def table(self, values, now):
        refs = self.refs()
        width = max(len(label) for label, _ in self.sensors) + 6
        head = "%-*s" % (width, "Sensor") + "".join("%9s %7s" % (name, "diff") for _, name, _, _ in COLUMNS)
        lines = ["Sensor comparison  %s   round %d, %d read errors" % (now.strftime("%Y-%m-%d %H:%M:%S"),
                                                                       self.rounds, self.errors), "", head]
        for label, s in self.sensors:
            row = "%-*s" % (width, label + (" (ref)" if label == self.ref else ""))
            for q, _, fmt, dfmt in COLUMNS:
                v = values[label].get(q)
                r = values[refs[q]].get(q) if q in refs else None
                if v is None:
                    row += "%9s %7s" % ("", "")
                elif label == refs[q] or r is None:
                    row += "%9s %7s" % (fmt % v, "")
                else:
                    row += "%9s %7s" % (fmt % v, dfmt % (v - r))
            lines.append(row)
        lines += ["", "Average difference since the start (standard deviation):"]
        for label, s in self.sensors:
            parts = []
            for q, name, _, dfmt in COLUMNS:
                st = self.stats.get((label, q))
                if st and st.n:
                    sd = st.sd()
                    parts.append("%s %s%s" % (name, dfmt % st.mean(), " (%.2f)" % sd if sd is not None else ""))
            if parts:
                lines.append("  %-*s %s   vs %s" % (width - 2, label, "   ".join(parts),
                                                     ", ".join(sorted(set(refs[q] for q, *_ in COLUMNS
                                                                          if (label, q) in self.stats)))))
        if self.missing:
            lines += ["", "Not found: " + "; ".join(self.missing)]
        return "\n".join(lines)


def scan(bus):
    print("Supported sensors that answer:")
    found = 0
    for model, cls in sorted(drivers.MODELS.items()):
        for address in cls.ADDRESSES:
            try:
                cls(bus, address)
                print("  %s@0x%02X" % (model, address))
                found += 1
            except (IOError, OSError):
                pass
    if not found:
        print("  none")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sensors", nargs="+", default=DEFAULT, help="model@address[=label] ...")
    ap.add_argument("--ref", help="label of the reference sensor (default: the first one found)")
    ap.add_argument("--every", type=float, default=10.0, help="seconds between readings (default 10)")
    ap.add_argument("--once", action="store_true", help="one reading, no refresh, no log")
    ap.add_argument("--no-log", action="store_true", help="monitor without writing a results folder")
    ap.add_argument("--scan", action="store_true", help="list which supported sensors answer")
    a = ap.parse_args()
    try:
        for x in a.sensors:
            parse_spec(x)
    except ValueError as e:
        ap.error(str(e))
    from smbus2 import SMBus
    bus = SMBus(1)
    if a.scan:
        scan(bus)
        return
    try:
        c = Comparison(bus, a.sensors, a.ref)
    except (IOError, ValueError) as e:
        sys.exit(str(e))
    if a.once:
        print(c.table(c.read_all(), dt.datetime.now()))
        return

    writer, folder = None, None
    if not a.no_log:
        folder = os.path.join(DATA_DIR, "shield_test_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
        try:
            os.makedirs(folder, exist_ok=True)
        except PermissionError:
            sys.exit("Cannot write to %s. Run with sudo, or fix it once with:\n"
                     "  sudo mkdir -p %s && sudo chown pi:pi %s" % (DATA_DIR, DATA_DIR, DATA_DIR))
        f = open(os.path.join(folder, "readings.csv"), "w", newline="")
        cols = [(label, q) for label, s in c.sensors for q, *_ in COLUMNS if q in s.QUANTITIES]
        writer = csv.writer(f)
        writer.writerow(["time"] + ["%s_%s" % (label, q) for label, q in cols])

    clear = "\033[2J\033[H" if sys.stdout.isatty() else ""
    start = time.monotonic()
    try:
        while True:
            now = dt.datetime.now()
            values = c.read_all()
            if writer:
                writer.writerow([now.isoformat(timespec="seconds")] +
                                ["" if values[label].get(q) is None else round(values[label][q], 3) for label, q in cols])
                f.flush()
            footer = "\nEvery %g s. %s Ctrl+C to stop." % (a.every, "Logging to %s." % folder if folder else "Not logging.")
            print(clear + c.table(values, now) + "\n" + footer, flush=True)
            # wait for the next multiple of --every since the start, so readings don't drift later
            time.sleep(max(0.0, a.every - (time.monotonic() - start) % a.every))
    except KeyboardInterrupt:
        print()
    if folder:
        f.close()
        if not c.rounds:
            return
        with open(os.path.join(folder, "summary.txt"), "w") as out:
            out.write(c.table(values, now) + "\n")
        print("Saved %s/readings.csv and summary.txt" % folder)


if __name__ == "__main__":
    main()
