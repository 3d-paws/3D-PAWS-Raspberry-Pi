#!/usr/bin/python3
# Driver for the SparkFun Qwiic Scale (NAU7802 24-bit load cell ADC), I2C address 0x2A, raw I2C with smbus2
# Used by dyn_rain_cal.py to weigh the water from every tip. Power-up sequence follows the NAU7802 datasheet
# (section 9.1) and SparkFun's Qwiic Scale Arduino library.
# Calibration (zero + counts per gram) is saved to a JSON file and reused between sessions.
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import collections, datetime as dt, json, os, statistics, threading, time

ADDRESS = 0x2A

# Registers
PU_CTRL = 0x00
CTRL1 = 0x01
CTRL2 = 0x02
ADCO_B2 = 0x12      # conversion result, 3 bytes, most significant first
ADC_CTRL = 0x15
PGA_PWR = 0x1C
REVISION = 0x1F

# PU_CTRL bits
RR = 0x01           # register reset
PUD = 0x02          # power up digital
PUA = 0x04          # power up analog
PUR = 0x08          # power up ready (read only)
CS = 0x10           # cycle start
CR = 0x20           # conversion ready (read only)
AVDDS = 0x80        # use the internal LDO for AVDD

# CTRL2 bits
CALS = 0x04         # start calibration, clears when done
CAL_ERR = 0x08

LDO_3V3 = 0b100     # CTRL1 bits 5:3
GAIN_128 = 0b111    # CTRL1 bits 2:0
RATES = {10: 0b000, 20: 0b001, 40: 0b010, 80: 0b011, 320: 0b111}   # samples per second -> CTRL2 bits 6:4
SAMPLE_RATE = 40    # slower is quieter; 40 gives about 30 readings between tips even at 200 mm/h

SETTLE_S = 3.0      # how long calibration readings are averaged
MAX_NOISE_G = 1.0   # calibration is rejected if readings scatter more than this


def to_signed24(b2, b1, b0):
	"""Three ADC bytes (two's complement, most significant first) to a signed integer."""
	value = (b2 << 16) | (b1 << 8) | b0
	return value - (1 << 24) if value & 0x800000 else value


class NAU7802:
	"""The chip itself: power up, configure for a load cell on channel 1, read raw counts."""

	def __init__(self, bus=1, address=ADDRESS, rate=SAMPLE_RATE):
		from smbus2 import SMBus
		self.bus, self.address = SMBus(bus), address
		self.rate = rate
		self._begin()

	def _read(self, reg):
		return self.bus.read_byte_data(self.address, reg)

	def _write(self, reg, value):
		self.bus.write_byte_data(self.address, reg, value)

	def _set_bits(self, reg, bits):
		self._write(reg, self._read(reg) | bits)

	def _wait_for(self, reg, bit, state, timeout, what):
		end = time.monotonic() + timeout
		while bool(self._read(reg) & bit) != state:
			if time.monotonic() > end:
				raise IOError("NAU7802: timed out waiting for " + what)
			time.sleep(0.001)

	def _begin(self):
		# Reset every register, then power up the digital and analog sections
		self._write(PU_CTRL, RR)
		time.sleep(0.01)
		self._write(PU_CTRL, 0)
		self._write(PU_CTRL, PUD | PUA)
		self._wait_for(PU_CTRL, PUR, True, 1.0, "power up")
		if self._read(REVISION) & 0x0F != 0x0F:
			raise IOError("The device at I2C 0x%02X is not a NAU7802" % self.address)
		# 3.3 V excitation from the internal LDO, gain 128, channel 1
		self._write(CTRL1, (LDO_3V3 << 3) | GAIN_128)
		self._set_bits(PU_CTRL, AVDDS)
		self._write(CTRL2, RATES[self.rate] << 4)
		# Datasheet power-on settings: turn off the ADC chopper clock, enable the PGA output capacitor
		self._set_bits(ADC_CTRL, 0x30)
		self._set_bits(PGA_PWR, 0x80)
		self._set_bits(PU_CTRL, CS)
		self.calibrate_afe()

	def calibrate_afe(self):
		"""The chip's internal offset calibration (not the grams calibration). Rerun after changing gain or rate."""
		self._set_bits(CTRL2, CALS)
		self._wait_for(CTRL2, CALS, False, 2.0, "internal calibration")
		if self._read(CTRL2) & CAL_ERR:
			raise IOError("NAU7802 internal calibration failed")

	def read_raw(self, timeout=1.0):
		"""Wait for the next conversion and return it in counts."""
		self._wait_for(PU_CTRL, CR, True, timeout, "a reading")
		return to_signed24(*self.bus.read_i2c_block_data(self.address, ADCO_B2, 3))


class LoadCell:
	"""Reads the NAU7802 continuously on a background thread and keeps the last 30 seconds of readings,
	so the weight just before any moment (such as a tip) can be looked up afterwards.
	now() must be the same clock the tip times come from."""

	def __init__(self, now=time.monotonic, cal=None, keep_s=30.0):
		self.chip = NAU7802()
		self.now = now
		self.cal = cal                  # {"zero": counts with nothing on the platform, "counts_per_g": ...}
		self.errors = 0
		self.samples = collections.deque(maxlen=int(SAMPLE_RATE * keep_s))
		self.lock = threading.Lock()
		threading.Thread(target=self._run, daemon=True).start()
		time.sleep(0.5)                 # first readings after the internal calibration

	def _run(self):
		while True:
			try:
				raw = self.chip.read_raw()
			except (IOError, OSError):
				self.errors += 1
				time.sleep(0.05)
				continue
			with self.lock:
				self.samples.append((self.now(), raw))

	def _raw_between(self, t0, t1):
		with self.lock:
			return [r for t, r in self.samples if t0 <= t <= t1]

	def raw_settled(self, seconds=SETTLE_S):
		"""Collect readings for a few seconds; returns (mean, standard deviation) in counts."""
		t0 = self.now()
		time.sleep(seconds)
		values = self._raw_between(t0, self.now())
		if len(values) < 2:
			raise IOError("No readings from the load cell")
		return statistics.mean(values), statistics.stdev(values)

	def grams(self, raw):
		return (raw - self.cal["zero"]) / self.cal["counts_per_g"]

	def grams_before(self, t, window, guard):
		"""Median weight over [t - window, t - guard], or None if there are no readings that far back."""
		values = self._raw_between(t - window, t - guard)
		if not values:
			with self.lock:
				values = [r for tt, r in self.samples if tt <= t][-5:]
		return self.grams(statistics.median(values)) if values else None

	def grams_now(self, window=0.5):
		return self.grams_before(self.now(), window, 0.0)


# ----------------------------------------------------------------- calibration
def load_cal(path):
	try:
		with open(path) as f:
			cal = json.load(f)
		return cal if cal.get("counts_per_g") else None
	except (OSError, ValueError):
		return None


def save_cal(path, cal):
	try:
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path, "w") as f:
			json.dump(cal, f, indent=2)
		return True
	except OSError:
		return False


def calibrate(scale, path, ask=input, say=print):
	"""Zero with an empty platform, then a known weight gives counts per gram. Saved to path."""
	say("\nLOAD CELL CALIBRATION")
	while True:
		ask("Remove everything from the scale platform (including the container), then press Enter: ")
		say("   Reading...")
		zero, zero_sd = scale.raw_settled()
		got = ask("Place a known weight on the platform (500 g or more is best) and enter its weight in grams: ")
		try:
			mass = float(got)
		except ValueError:
			mass = 0
		if mass <= 0:
			say("   Enter the weight in grams, e.g. 1000. Starting over.")
			continue
		say("   Reading...")
		loaded, loaded_sd = scale.raw_settled()
		counts_per_g = (loaded - zero) / mass
		if abs(counts_per_g) < 1:
			say("   The reading barely changed. Check the load cell wiring and that the weight is on the platform. Starting over.")
			continue
		noise_g = max(zero_sd, loaded_sd) / abs(counts_per_g)
		if noise_g > MAX_NOISE_G:
			say("   Readings scattered by %.1f g. Make sure nothing touches the platform or cable and the table is still. Starting over." % noise_g)
			continue
		break
	cal = {"zero": zero, "counts_per_g": counts_per_g, "mass_g": mass, "noise_g": round(noise_g, 3),
	       "date": dt.datetime.now().isoformat(timespec="seconds")}
	scale.cal = cal
	saved = save_cal(path, cal)
	say("   %.1f counts per gram, readings steady to about %.2f g." % (counts_per_g, noise_g))
	say("   Saved to " + path if saved else "   Could not save to %s; this calibration is used for this session only." % path)
	say("   Scale now reads %.1f g (should be %g)." % (scale.grams_now(), mass))
	return cal


def use_or_calibrate(scale, path, ask=input, say=print):
	"""Use the saved calibration unless the operator asks to redo it; calibrate if there is none."""
	cal = load_cal(path)
	if cal:
		got = ask("Load cell calibrated %s with a %g g weight. Press Enter to use it, or type c to recalibrate: "
		          % (cal.get("date", "?")[:10], cal.get("mass_g", 0))).strip().lower()
		if got != "c":
			scale.cal = cal
			return cal
	return calibrate(scale, path, ask, say)
