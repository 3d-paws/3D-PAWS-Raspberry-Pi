#!/usr/bin/env python3
"""
dyn_rain_cal.py  -  3D-PAWS tipping bucket dynamic (multi-rate) calibration

Two ways to weigh the water:

Load cell (default) - a SparkFun Qwiic Scale (NAU7802, I2C 0x2A) with a 5 kg load cell sits
under the gauge with one container on it. All water, from both buckets, collects there for the
whole session and the script reads the weight just before every tip, so there is nothing to
swap or type:
  set the drip to a target tips/min -> wait for STEADY -> 5 runs of 25 tips -> next rate.
The load cell is calibrated at the start (empty platform, then a known weight); the calibration
is saved in /home/pi/data/tests/loadcell_cal.json and offered again next time.

Manual (--manual) - buckets A and B are swapped under the gauge at each run boundary and
weighed on a kitchen scale; the weights are typed in.

At the end it shows the rim radius and the % error at every rate for each
possible sizing rate, asks which one to use, and saves everything.

Install:  /home/pi/3d_paws/scripts/sensors/dyn_rain_cal.py and nau7802.py
Results:  /home/pi/data/tests/dyn_rain_cal_<GaugeID>_<date_time>/

Usage (from /home/pi/3d_paws/scripts/sensors/):
  python3 dyn_rain_cal.py                     real gauge on the GPIO pin below, weighed by the load cell
  python3 dyn_rain_cal.py --manual            real gauge, buckets weighed by hand
  python3 dyn_rain_cal.py --calibrate-scale   only calibrate the load cell, then show live readings
  python3 dyn_rain_cal.py --sim               simulated gauge in real time (training)
  python3 dyn_rain_cal.py --sim --speed 60    simulated, 60x faster
  python3 dyn_rain_cal.py --sim --speed 300 --auto   fully automatic demo run (add --manual for the manual procedure)
  python3 dyn_rain_cal.py --gpt-range 4 6.5  accept 4-6.5 g/tip instead of 5-7.5, for a gauge with a smaller bucket

Stop the 3D-PAWS station software first if it is running on this Pi,
so it is not reading the same GPIO pin (turn off Tipping Bucket in the controller).

Load cell session:
  Enter            at "press Enter" once the drip is STEADY: starts run 1 (type 'force' to skip the check)
  y / n / Enter    at a FLAG prompt: keep / discard / take the recommended answer
                   - discard recommended: a missed or extra tip, the drip >10% off target, or the
                     scale reading dropping during the run (container bumped or lifted)
  Enter            at "Empty the container": after emptying it and putting it back. Asked only
                   between rates, when the next rate could pass the 5 kg limit.
  A run's weight is read at the tip after it ends. Runs outside 5-7.5 g/tip (or --gpt-range) are discarded
  automatically. Each discarded run adds one replacement run, including the last run of a rate.

Manual session:
  Enter            at "press Enter" once the drip is STEADY: starts run 1 (type 'force' to skip the check)
  <grams>          at a weigh prompt: the scale reading
  Enter            at "Empty bucket ... or press Enter": keep filling - the full weight becomes the
                   bucket's starting weight for its next run (empty it when the scale-limit warning shows)
  s                at a weigh prompt: correct the bucket's starting weight (e.g. it was emptied
                   but Enter was pressed), then re-enter the full weight
  d                at a weigh prompt: discard the run
  y / n / Enter    at a FLAG prompt: keep / discard / take the recommended answer
                   - discard recommended: a missed or extra tip, or the drip >10% off target
                   - keep recommended: drip 5-10% off target, or >2% from the other runs
  Weights outside 5-7.5 g/tip (or --gpt-range) are never stored. Each discarded run adds one replacement run
  while its rate is still running. Ctrl+C stops; everything recorded so far is kept.

Results: summary.txt and result.json (rim radius and % error at each rate), runs.csv (one row
per run, including why a run was flagged), tips.csv (every tip).
"""
import argparse
import collections
import csv
import datetime as dt
import json
import math
import os
import queue
import random
import statistics
import sys
import threading
import time

# ----------------------------------------------------------------- settings
TIP_GPIO = 23             # BCM pin the gauge signal is on (same pin as rain.py)
BOUNCE_S = 0.05           # switch debounce
LOCKOUT_S = 0.5           # ignore a second tip sooner than this (16.7 tips/min = 3.6 s)
DEFAULT_RATES = [12, 30, 60, 120, 200]   # mm/h
TIPS_PER_RUN = 25
RUNS_PER_RATE = 5
MIN_RUNS = 3              # WMO minimum
DENSITY = 0.998           # g/mL, room temperature
MM_PER_TIP = 0.2
STEADY_TIPS = 5           # last N tips must all be within tolerance
STEADY_TOL = 0.05         # +/- 5 %
FLAG_PCT = 2.0            # flag a run this far from the others
GPT_RANGE = (5.0, 7.5)    # acceptable grams per tip; outside this, re-enter or discard (tip volume rises at high rates).
                          # Change it for one gauge with --gpt-range MIN MAX
IDEAL_GPT = (5.5, 6.5)    # target grams per tip; rates outside it are marked in the final summary
DISCARD_OFF_PCT = 10.0    # a run averaging more than this % off the target rate defaults to discard
SCALE_MAX_G = 6000        # manual: scale capacity; warn before a bucket that keeps filling would exceed it
LOADCELL_MAX_G = 5000     # load cell capacity, container included
PRE_WINDOW_S = 1.0        # load cell: the weight before a tip is the median of the readings in this window...
PRE_GUARD_S = 0.1         # ...ending this long before the tip, so the tip's own splash isn't included
DISTURB_G = 10.0          # load cell: a drop this large between tips means the container was bumped or lifted
NO_TIP_WAIT_S = 15.0      # load cell: if no tip follows a run's last one (drip off), weigh it after this long
                          # (or two tip intervals, whichever is longer) from the scale's current reading
IRREGULAR = (0.6, 1.6)    # a tip interval outside these multiples of the run's median suggests a missed or extra tip
DATA_DIR = "/home/pi/data/tests"   # fixed path, so running with or without sudo saves to the same place


def tpm_for(mm_h):
    """Tips per minute for an intensity."""
    return mm_h / (60.0 * MM_PER_TIP)


def side_text(stats):
    """Side imbalance for printing; n/a when every run at the rate had an irregular tip."""
    return "n/a" if stats["side_imbalance_pct"] is None else f"{stats['side_imbalance_pct']:.1f}%"


# ----------------------------------------------------------------- clock
class Clock:
    """Monotonic seconds since start. In simulation, runs `speed` times faster."""

    def __init__(self, speed=1.0):
        self.t0 = time.monotonic()
        self.wall0 = dt.datetime.now()
        self.speed = speed

    def now(self):
        return (time.monotonic() - self.t0) * self.speed

    def stamp(self, t):
        return (self.wall0 + dt.timedelta(seconds=t)).isoformat(timespec="milliseconds")


# ----------------------------------------------------------------- tip sources
class GpioTips:
    """A tip on every falling edge, the same way rain.py counts. gpiozero was used before, but it reads
    the pin after the edge, so a fast tip whose reed switch had already reopened was lost (on a real
    gauge about every other tip went uncounted at 60 mm/h)."""

    def __init__(self, q, clock):
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(TIP_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(TIP_GPIO, GPIO.FALLING, callback=lambda channel: q.put(("tip", clock.now())),
                              bouncetime=int(BOUNCE_S * 1000))

    def set_target(self, tpm):
        pass


class SimGauge:
    """Simulated gauge. The 'operator' turns the bolt toward the target over a
    few tips. Tip volume grows with rate (water arriving during the swing), the
    two buckets differ by 1.6 %, and each tip scatters by 0.3 %."""

    def __init__(self, q, clock, speed):
        self.q, self.clock, self.speed = q, clock, speed
        self.target, self.tpm = None, 0.6
        self.masses = []
        self.log = []                  # (tip time, grams) for the simulated load cell
        self.rng = random.Random(3)
        threading.Thread(target=self._run, daemon=True).start()

    def set_target(self, tpm):
        self.target = tpm

    def _run(self):
        n = 0
        while True:
            if self.target:
                self.tpm += 0.45 * (self.target - self.tpm)
            tpm = self.tpm * (1 + self.rng.gauss(0, 0.01))
            interval = 60.0 / tpm
            time.sleep(interval / self.speed)
            v0 = 6.10 * (1.008 if n % 2 == 0 else 0.992)
            self.masses.append(v0 / (1 - 0.27 / interval) * (1 + self.rng.gauss(0, 0.003)))
            n += 1
            t = self.clock.now()
            self.log.append((t, self.masses[-1]))
            self.q.put(("tip", t))

    def grams(self, first, last):
        return sum(self.masses[first:last + 1])


class SimScale:
    """Simulated load cell: a 400 g container, and each tip's water lands on it DRAIN_S after the tip."""
    DRAIN_S = 1.5
    CONTAINER_G = 400.0

    def __init__(self, gauge, clock):
        self.gauge, self.clock = gauge, clock
        self.emptied = 0.0
        self.rng = random.Random(5)

    def _load(self, t):
        water = sum(m for tt, m in list(self.gauge.log) if tt + self.DRAIN_S <= t)
        return self.CONTAINER_G + water - self.emptied + self.rng.gauss(0, 0.05)

    def grams_before(self, t, window, guard):
        return self._load(t - guard)

    def grams_now(self):
        return self._load(self.clock.now())

    def empty(self):
        self.emptied += self.grams_now() - self.CONTAINER_G


def cal_path():
    """Where the load cell calibration is kept between sessions."""
    return os.path.join(DATA_DIR, "loadcell_cal.json")


# Typed answers are read on a separate thread and put on the same queue as tips,
# so the main loop handles keyboard input and bucket tips in the order they happen
def stdin_reader(q):
    for line in sys.stdin:
        q.put(("line", line.strip()))
    q.put(("eof", None))


# ----------------------------------------------------------------- session
# The calibration, step by step:
#   1. setup()          - gauge ID, rates to test, weigh both buckets dry
#   2. start_rate()     - operator sets the drip; water goes to waste until the tip rate is STEADY
#   3. _arm_handler()   - operator presses Enter; the next tip starts run 1 into bucket A
#   4. on_tip()         - counts tips; every 25 tips _end_run() swaps buckets A <-> B
#   5. _full_handler()  - operator weighs the full bucket; grams per tip for that run
#   6. _tare_after()    - bucket emptied and re-weighed, or Enter to keep filling it
#   7. _rate_summary()  - after all runs at a rate: mean mL per tip at that rate
#   8. results()        - table of mL/tip and % error for every rate; operator picks the
#                         sizing rate and the rim radius is saved with all the data
# With the load cell, steps 5-6 are replaced: every tip records the scale's weight just before it,
# _weigh_run() takes a run's grams from those weights at the tip after the run, and
# _finish_rate_if_ready() moves to the next rate once every run at this one is weighed and decided.
class Session:
    def __init__(self, args):
        self.args = args
        self.loadcell = not getattr(args, "manual", False)
        self.scale = None
        self.pre_w = []                # load cell: weight just before each tip (g), same index as tips
        self.pending = []              # load cell: runs that ended and are waiting for their weight
        self.clock = Clock(args.speed if args.sim else 1.0)
        self.q = queue.Queue()
        self.prompts = collections.deque()
        self.tips = []                 # tip times (s)
        self.rejected = 0
        self.runs = []                 # completed runs
        self.tare = {}
        self.tare_ok = {}
        self.rate_i = 0
        self.phase = "setup"
        self.run_no = 0
        self.run_start = None
        self.bucket = None
        self.steady = False
        self.drift_warned = False
        self.finished = False
        self.rate_done = {}

    # ---------------- output helpers
    def say(self, text=""):
        print(text, flush=True)

    def banner(self, text):
        line = "!" * (len(text) + 8)
        print(f"\a\n{line}\n!!  {text}  !!\n{line}\n", flush=True)

    def ask(self, text, handler, auto=None, scale=None):
        """Queue a prompt; handler(str) returns True when the answer is accepted.
        scale() gives the weight to show as a hint in simulation."""
        self.prompts.append({"text": text, "handler": handler, "auto": auto, "scale": scale, "shown": False})
        self._show_prompt()

    def ask_next(self, text, handler, auto=None, scale=None):
        """From inside a handler: queue a prompt right after the one being answered.
        It is shown once the current prompt is accepted."""
        self.prompts.insert(1, {"text": text, "handler": handler, "auto": auto, "scale": scale, "shown": False})

    def _show_prompt(self):
        if self.prompts and not self.prompts[0]["shown"]:
            p = self.prompts[0]
            p["shown"] = True
            hint = ""
            if self.args.sim and not self.args.auto and p.get("scale") is not None:
                hint = f"   [simulated scale reads {p['scale']()} g]"
            print(f">> {p['text']}{hint}", flush=True)
            if self.args.auto and p["handler"] == self._arm_handler and self.steady:
                self.q.put(("line", ""))
            elif self.args.auto and p["auto"] is not None:
                self.q.put(("line", str(p["auto"]() if callable(p["auto"]) else p["auto"])))

    # Prompts are answered one at a time; a rejected answer re-shows the same prompt
    def answer(self, line):
        if not self.prompts:
            return
        p = self.prompts[0]
        if p["handler"](line):
            self.prompts.remove(p)
        else:
            p["shown"] = False
        self._show_prompt()

    # ---------------- setup
    # Step 1: name the gauge, choose the rates, create the results folder and CSV files,
    # then ask for both buckets' dry weights (the first rate starts once both are entered)
    def setup(self):
        a = self.args
        self.gauge_id = a.gauge_id or input("Gauge ID: ").strip() or "unnamed"
        rates = a.rates or DEFAULT_RATES
        if not a.auto and not a.rates:
            while True:
                got = input(f"Rates in mm/h [{', '.join(map(str, rates))}] (Enter to accept): ").strip()
                if not got:
                    break
                try:
                    typed = [float(x) for x in got.replace(",", " ").split()]
                except ValueError:
                    typed = []
                if typed and all(r > 0 for r in typed):
                    rates = typed
                    break
                self.say("   Enter rates as positive numbers, e.g. 12 30 60 120 200")
        self.rates = rates
        # Results folder is named <GaugeID>_<date>_<time> so every session gets its own
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.dir = os.path.join(DATA_DIR, f"dyn_rain_cal_{self.gauge_id}_{stamp}")
        try:
            os.makedirs(self.dir, exist_ok=True)
        except PermissionError:
            sys.exit(f"Cannot write to {DATA_DIR}. Fix it once with:\n"
                     f"  sudo mkdir -p {DATA_DIR} && sudo chown pi:pi {DATA_DIR}")
        # tips.csv logs every tip; runs.csv gets one row per weighed run
        self.tips_csv = self._csv("tips.csv", ["tip", "time", "t_s", "interval_s", "tips_per_min",
                                               "phase", "rate_mm_h", "run", "scale_g"])
        self.runs_csv = self._csv("runs.csv", ["rate_mm_h", "target_tpm", "run", "bucket",
                                               "start_tip", "end_tip", "duration_s", "tips_per_min",
                                               "start_g", "end_g", "net_g", "g_per_tip",
                                               "ml_per_tip", "side_ratio", "off_target_pct", "irregular", "kept",
                                               "note"])
        self.say(f"\nSaving to {self.dir}")
        self.say("\nRate plan:")
        for r in rates:
            t = tpm_for(r)
            self.say(f"  {r:>6g} mm/h = {t:5.2f} tips/min, {TIPS_PER_RUN} tips per run = "
                     f"{TIPS_PER_RUN / t:5.1f} min, {RUNS_PER_RATE} runs")
        self.say()
        if self.loadcell:
            # No buckets to weigh: the container stays on the scale and the first rate starts now
            self.say(f"Scale reads {self.scale.grams_now():.0f} g (container plus anything in it). "
                     "All water collects in the container on the scale; no bucket swaps.")
            self.start_rate()
            return
        for b in ("A", "B"):
            self.ask(f"Weigh bucket {b} DRY and enter its weight in grams:",
                     self._tare_handler(b), auto=lambda: 550, scale=lambda: 550)

    def _csv(self, name, fields):
        f = open(os.path.join(self.dir, name), "w", newline="")
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        f.flush()
        return (f, w)

    def _write(self, which, row):
        f, w = which
        w.writerow(row)
        f.flush()

    @staticmethod
    def _num(line):
        try:
            return float(line)
        except ValueError:
            return None

    def _tare_handler(self, b):
        def h(line):
            v = self._num(line)
            if v is None or v <= 0:
                self.say("   Enter a number in grams.")
                return False
            self.tare[b], self.tare_ok[b] = v, True
            self.say(f"   Bucket {b} empty weight = {v:g} g")
            if self.phase == "setup" and all(self.tare_ok.get(x) for x in "AB"):
                self.start_rate()
            return True
        return h

    # ---------------- rate flow
    @property
    def rate(self):
        return self.rates[self.rate_i]

    @property
    def target(self):
        return tpm_for(self.rate)

    # Step 2: new rate - the operator adjusts the drip until the tip rate is within 5% of target
    def start_rate(self):
        self.phase = "setting"
        self.steady = False
        self.run_no = 0
        self.source.set_target(self.target)
        self.say(f"\n========== RATE {self.rate_i + 1} of {len(self.rates)}: {self.rate:g} mm/h ==========")
        band = (f"Adjust the drip bolt to {self.target:.2f} tips/min "
                f"({self.target * (1 - STEADY_TOL):.2f} to {self.target * (1 + STEADY_TOL):.2f}).")
        if not self.loadcell:
            self.say(band + " Water goes to the WASTE container.")
            self.ask("When the script says STEADY and bucket A is ready, press Enter "
                     "(the next tip starts run 1).", self._arm_handler)
            return
        self.say(band)
        # Empty only between rates, never during one, and only when this rate could pass the limit
        if self.scale.grams_now() + self._rate_need_g() > LOADCELL_MAX_G:
            self.ask(self._empty_text(), self._emptied_handler, auto="")
        self.ask("When the script says STEADY, press Enter (the next tip starts run 1).", self._arm_handler)

    # Most water one rate can add: every planned run plus two replacements, at the top of GPT_RANGE
    def _rate_need_g(self):
        return (RUNS_PER_RATE + 2) * TIPS_PER_RUN * GPT_RANGE[1]

    def _empty_text(self):
        return (f"The scale holds {self.scale.grams_now():.0f} g and this rate could add {self._rate_need_g():.0f} g, "
                f"over the {LOADCELL_MAX_G} g load cell limit. Empty the container, put it back on the scale, "
                "and press Enter.")

    def _emptied_handler(self, line):
        if hasattr(self.scale, "empty"):
            self.scale.empty()         # simulation
        load = self.scale.grams_now()
        if line.lower() != "go" and load + self._rate_need_g() > LOADCELL_MAX_G:
            self.say(f"   Scale still reads {load:.0f} g. Empty the container fully and press Enter, "
                     "or type 'go' to continue anyway.")
            return False
        self.say(f"   Scale reads {load:.0f} g.")
        return True

    # Step 3: once STEADY, Enter arms the run; the next tip starts run 1 ('force' skips the steady check)
    def _arm_handler(self, line):
        if line.lower() != "force" and not self.steady:
            self.say("   Not steady yet. Wait for STEADY, or type 'force' to start anyway.")
            return False
        if self.loadcell:
            self.phase = "armed"
            self.say("   Armed. The next tip starts run 1.")
            return True
        for b in "AB":
            if not self.tare_ok.get(b):
                self.say(f"   Bucket {b} needs its empty weight first.")
                return False
        self.phase = "armed"
        self.say("   Armed. Get bucket A in hand; swap it in when the next tip has drained.")
        return True

    # Step 4: called for every tip - log it, then check steadiness or count it toward the current run
    def on_tip(self, t):
        # A second pulse too soon after a tip is switch bounce, not a real tip
        if self.tips and t - self.tips[-1] < LOCKOUT_S:
            self.rejected += 1
            self.say(f"   (ignored a second pulse {1000 * (t - self.tips[-1]):.0f} ms after a tip)")
            return
        i = len(self.tips)
        # Load cell: the weight just before this tip holds the water of every earlier tip
        w = self.scale.grams_before(t, PRE_WINDOW_S, PRE_GUARD_S) if self.loadcell else None
        self.pre_w.append(w)
        self.tips.append(t)
        interval = t - self.tips[-2] if i else None
        rate = 60.0 / interval if interval else None
        row = {"tip": i, "time": self.clock.stamp(t), "t_s": round(t, 3),
               "interval_s": round(interval, 3) if interval else "",
               "tips_per_min": round(rate, 3) if rate else "", "phase": self.phase,
               "rate_mm_h": self.rate if self.phase != "setup" else "", "run": self.run_no or "",
               "scale_g": round(w, 2) if w is not None else ""}
        self._write(self.tips_csv, row)
        # A run that ended at the previous tip can be weighed now
        for run in [r for r in self.pending if r["end_tip"] < i]:
            self._weigh_run(run, self.pre_w[run["start_tip"] + 1:i + 1])

        if self.phase in ("setup", "done", "finishing"):
            return
        # Still setting the drip (or armed): check steadiness; an armed tip starts run 1
        if self.phase in ("setting", "armed"):
            self._steady_check(rate)
            if self.phase == "armed":
                self._begin_run(i, "A", first=True)
            return
        # running
        n = i - self.run_start
        tag = f"   run {self.run_no}/{self.runs_planned(self.rate_i)}  tip {n:>2}/{TIPS_PER_RUN}"
        self.say(f"{tag}   {rate:6.2f} tips/min" if rate else tag)
        self._drift_check(i, n)
        if n == TIPS_PER_RUN:
            self._end_run(i)

    # STEADY = the last 5 tips were all within 5% of the target tips/min
    def _steady_check(self, rate):
        if rate is None:
            return
        n = len(self.tips) - 1
        recent = [60.0 / (self.tips[k] - self.tips[k - 1]) for k in range(max(1, n - STEADY_TIPS + 1), n + 1)]
        ok = len(recent) >= STEADY_TIPS and all(abs(r / self.target - 1) <= STEADY_TOL for r in recent)
        within = sum(abs(r / self.target - 1) <= STEADY_TOL for r in recent)
        self.say(f"   {rate:6.2f} tips/min   target {self.target:.2f}   in band {within}/{STEADY_TIPS}"
                 + ("   STEADY" if ok else ""))
        if ok and not self.steady:
            self.steady = True
            self.say("   *** STEADY ***")
            if self.args.auto and self.prompts and self.prompts[0]["handler"] == self._arm_handler:
                self.q.put(("line", ""))
        elif not ok:
            self.steady = False

    # During a run: warn as soon as the last 5 tips drift more than 5% from the target, so the
    # drip can be adjusted before the run ends, and say when it is back on target
    def _drift_check(self, i, n):
        if n < STEADY_TIPS:
            return
        recent = STEADY_TIPS * 60.0 / (self.tips[i] - self.tips[i - STEADY_TIPS])
        off = (recent / self.target - 1) * 100
        if abs(off) > STEADY_TOL * 100 and not self.drift_warned:
            self.drift_warned = True
            self.say(f"   WARNING: drip has drifted to {recent:.2f} tips/min ({off:+.1f}% from {self.target:.2f}). "
                     "Adjust the bolt; a run that ends more than 5% off target will be flagged.")
        elif abs(off) <= STEADY_TOL * 100 and self.drift_warned:
            self.drift_warned = False
            self.say(f"   Drip back on target ({recent:.2f} tips/min).")

    # Runs at a rate end once RUNS_PER_RATE are valid; each discarded run adds exactly one more
    def valid_runs(self, ri):
        return sum(1 for r in self.runs if r["rate_index"] == ri and r["kept"] is not False)

    def runs_planned(self, ri):
        return RUNS_PER_RATE + sum(1 for r in self.runs if r["rate_index"] == ri and r["kept"] is False)

    # Start a run: tell the operator which bucket to swap in under the gauge
    def _begin_run(self, i, bucket, first=False):
        self.phase = "running"
        self.run_no += 1
        self.run_start = i
        self.drift_warned = False
        if self.loadcell:
            self.bucket = None
            self.say(f"   Run {self.run_no} started at {self.rate:g} mm/h")
            return
        self.bucket = bucket
        self.tare_ok[bucket] = False
        self.banner(f"SWITCH TO BUCKET {bucket} NOW  (run {self.run_no} at {self.rate:g} mm/h)")

    # After 25 tips: record the run's timing, swap to the other bucket (or to waste when
    # this rate has enough runs), and ask for the full weight of the bucket just used
    def _end_run(self, i):
        start, b = self.run_start, self.bucket
        dur = self.tips[i] - self.tips[start]
        # Side ratio: average time between tips on one side of the tipping bucket vs the other.
        # Sides are told apart by odd/even tip, so a missed or extra tip swaps them - for this run and
        # every later one. Imbalance is therefore summarized as a size, |ratio - 1|, which doesn't depend
        # on which side is which; a run with an irregular interval (side swap inside the run) is left out.
        ivs = [(k, self.tips[k] - self.tips[k - 1]) for k in range(start + 1, i + 1)]
        med = statistics.median(v for k, v in ivs)
        irregular = [v for k, v in ivs if not IRREGULAR[0] * med <= v <= IRREGULAR[1] * med]
        if irregular:
            side_ratio = None
            self.say(f"   NOTE: {len(irregular)} tip interval(s) in this run were far from the others "
                     "(possible missed or extra tip). You will be asked about it when this run is weighed.")
        else:
            even = [v for k, v in ivs if k % 2 == 0]
            odd = [v for k, v in ivs if k % 2 == 1]
            side_ratio = round(statistics.mean(even) / statistics.mean(odd), 4)
        tpm = TIPS_PER_RUN / dur * 60
        # How far the whole run's average was from the target; flagged at weighing if over 5%
        off_pct = (tpm / self.target - 1) * 100
        run = {"rate_mm_h": self.rate, "target_tpm": round(self.target, 3), "run": self.run_no,
               "bucket": b, "start_tip": start, "end_tip": i, "duration_s": round(dur, 2),
               "tips_per_min": round(tpm, 3), "side_ratio": side_ratio,
               "off_target_pct": round(off_pct, 2), "irregular": len(irregular),
               "kept": None, "rate_index": self.rate_i}
        self.runs.append(run)
        valid_so_far = self.valid_runs(self.rate_i)
        if self.loadcell:
            # Weighed at the next tip; the next run starts right away, or the rate waits for its last weight
            self.pending.append(run)
            if valid_so_far < RUNS_PER_RATE:
                self._begin_run(i, None)
            else:
                self.phase = "finishing"
                self.say("   That's the last run at this rate; it is weighed at the next tip.")
            return
        if valid_so_far < RUNS_PER_RATE:
            nxt = "B" if b == "A" else "A"
            if not self.tare_ok.get(nxt):
                self.banner(f"WARNING: bucket {nxt} has no empty weight yet")
            self._begin_run(i, nxt)
        else:
            self.banner("SWITCH TO THE WASTE CONTAINER NOW")
        self.ask(f"Weigh bucket {b} (run {run['run']} at {self.rate:g} mm/h) FULL, enter grams:",
                 self._full_handler(run), auto=self._auto_full(run), scale=self._auto_full(run))
        # Enough runs at this rate: move on to the next rate while the operator weighs
        if valid_so_far >= RUNS_PER_RATE:
            self.rate_done[self.rate_i] = True
            if self.rate_i + 1 < len(self.rates):
                self.rate_i += 1
                self.say("You can start setting the next drip rate while you weigh.")
                self.start_rate()
            else:
                self.phase = "done"

    # Simulation only: the weight the simulated scale would show for this run
    def _auto_full(self, run):
        return lambda: round(self.tare[run["bucket"]] +
                             self.source.grams(run["start_tip"] + 1, run["end_tip"]))

    # Step 5: full weight - net grams / 25 tips = grams per tip. A value outside GPT_RANGE is never
    # stored: re-enter it, correct the bucket's starting weight, or discard the run. A run with a
    # problem is flagged with a recommended keep/discard answer.
    def _full_handler(self, run):
        b = run["bucket"]

        def h(line):
            if line.lower() == "s":
                # Correct the starting weight (e.g. the bucket was emptied but Enter was pressed), then re-ask
                self.prompts.appendleft({"text": f"Enter bucket {b}'s weight before this run started (grams):",
                                         "handler": self._fix_start(b), "auto": None, "scale": None, "shown": False})
                return False
            if line.lower() == "d":
                self.say(f"   Run {run['run']} discarded without a weight.")
                self._discard(run)
                self.ask_next(f"Enter bucket {b}'s weight now; its next run starts from this (grams):",
                              self._tare_after(run))
                return True
            v = self._num(line)
            if v is None:
                self.say("   Enter a number in grams.")
                return False
            net = v - self.tare[b]
            gpt = net / TIPS_PER_RUN
            if not GPT_RANGE[0] <= gpt <= GPT_RANGE[1]:
                hint = ""
                if gpt < GPT_RANGE[0] / 2:
                    hint = (f" Was bucket {b} emptied before this run? Its starting weight is recorded as "
                            f"{self.tare[b]:g} g.")
                self.say(f"   That is {net:g} g = {gpt:.2f} g/tip, outside {GPT_RANGE[0]} to {GPT_RANGE[1]}.{hint}\n"
                         f"   Re-enter the full weight, type s to correct the starting weight, or d to discard this run.")
                return False
            run.update(end_g=v, start_g=self.tare[b], net_g=round(net, 1),
                       g_per_tip=round(gpt, 4), ml_per_tip=round(gpt / DENSITY, 4))
            self.say(f"   Run {run['run']}: {net:g} g = {gpt:.3f} g/tip at "
                     f"{run['tips_per_min']:.2f} tips/min")
            # Starting weight for the bucket's next run comes after any keep question
            full_note = ""
            if v + TIPS_PER_RUN * GPT_RANGE[1] > SCALE_MAX_G:
                full_note = f" WARNING: another run would pass the {SCALE_MAX_G} g scale limit - empty it."
            self.ask_next(f"Empty bucket {b} and enter its empty weight, or press Enter to keep "
                          f"filling it (its next run starts from {v:g} g):{full_note}",
                          self._tare_after(run), auto=self._auto_start(run), scale=lambda: f"{v:g}")
            reasons, discard_advised = self._flag_reasons(run, gpt)
            if reasons:
                self._ask_keep(run, reasons, discard_advised, first=True)
                return True
            run["kept"] = True
            return True
        return h

    # Reasons to flag a run. Discard is the default for an irregular tip (g/tip about 4% off)
    # or a drip more than DISCARD_OFF_PCT off target; otherwise keep is the default, since the
    # actual rate is recorded and a few % off target barely changes g/tip.
    def _flag_reasons(self, run, gpt):
        reasons = []
        discard_advised = False
        if run["irregular"]:
            reasons.append(f"{run['irregular']} irregular tip interval(s); a missed or extra tip "
                           "makes g/tip about 4% wrong")
            discard_advised = True
        if abs(run["off_target_pct"]) > STEADY_TOL * 100:
            reasons.append(f"drip averaged {run['off_target_pct']:+.1f}% from the target rate")
            if abs(run["off_target_pct"]) > DISCARD_OFF_PCT:
                discard_advised = True
        # Far from the other runs at this rate: worth a look, keeping is the default
        others = [r["g_per_tip"] for r in self.runs
                  if r["rate_index"] == run["rate_index"] and r is not run
                  and r.get("g_per_tip") and r["kept"] is not False]
        if len(others) >= 2:
            med = statistics.median(others)
            dev = (gpt / med - 1) * 100
            if abs(dev) > FLAG_PCT:
                reasons.append(f"{dev:+.1f}% from the other runs")
        return reasons, discard_advised

    # first=True: from inside a prompt handler (asked next); otherwise queued after any open prompts
    def _ask_keep(self, run, reasons, discard_advised, first=False, then=None):
        default = "n" if discard_advised else "y"
        choice = "[y/N] (Enter = discard)" if default == "n" else "[Y/n] (Enter = keep)"
        (self.ask_next if first else self.ask)(
            f"FLAG: run {run['run']}: " + "; ".join(reasons) + f". Keep it? {choice}",
            self._keep_handler(run, default, then), auto=default)

    # A flagged run can be kept or discarded. Enter takes the recommended answer (default).
    # then(run) is called once it is decided (load cell: save the run and maybe finish the rate).
    def _keep_handler(self, run, default="y", then=None):
        def h(line):
            if line == "":
                line = default
            if line.lower() in ("y", "yes"):
                run["kept"] = True
            elif line.lower() in ("n", "no"):
                self._discard(run)
            else:
                self.say("   Type y or n.")
                return False
            if then:
                then(run)
            return True
        return h

    # Discarding a run while its rate is still running adds one replacement run automatically
    # (the rate ends at RUNS_PER_RATE valid runs); after the rate has finished it can't be replaced.
    # With the load cell a rate doesn't finish until all its runs are decided, so this always applies.
    def _discard(self, run):
        run["kept"] = False
        ri = run["rate_index"]
        if ri == self.rate_i and self.phase in ("running", "finishing", "armed") and not self.rate_done.get(ri):
            self.say(f"   Run discarded; a replacement run will be added ({self.runs_planned(ri)} runs at this rate).")
        else:
            self.say("   Run discarded.")
            left = self.valid_runs(ri)
            if left < MIN_RUNS:
                rate = self.rates[ri]
                self.banner(f"{rate:g} mm/h now has only {left} valid run(s), fewer than {MIN_RUNS}. "
                            f"Repeat it later with --rates {rate:g}")

    # Replace a wrongly recorded starting weight; the full-weight prompt is then asked again
    def _fix_start(self, b):
        def h(line):
            v = self._num(line)
            if v is None or v <= 0:
                self.say("   Enter a number in grams.")
                return False
            self.tare[b] = v
            self.say(f"   Bucket {b} starting weight corrected to {v:g} g.")
            return True
        return h

    # Simulation --auto: alternate between keeping the bucket filling (Enter) and emptying it,
    # so both paths get exercised
    def _auto_start(self, run):
        return lambda: "" if run["run"] % 2 else 552    # 552 g = dry bucket plus a little residue

    # Step 6: the bucket's starting weight for its next run (emptied weight, or Enter to
    # keep filling); the finished run is saved, and a rate's summary prints once all its runs are in
    def _tare_after(self, run):
        b = run["bucket"]

        def h(line):
            # Enter = bucket not emptied: the full weight is the starting weight for its next run
            # (not available after a run discarded without a weight)
            v = run.get("end_g") if line == "" else self._num(line)
            if v is None or v <= 0:
                self.say("   Enter a number in grams.")
                return False
            self.tare[b], self.tare_ok[b] = v, True
            run["done"] = True
            self._write(self.runs_csv, {k: run.get(k) for k in self.runs_csv[1].fieldnames})
            self.say(f"   Bucket {b} starting weight for its next run = {v:g} g"
                     + ("  (not emptied)" if line == "" else ""))
            ri = run["rate_index"]
            if self.rate_done.get(ri) and all(r.get("done") for r in self.runs if r["rate_index"] == ri):
                self._rate_summary(ri)
                if self.phase == "done" and ri == len(self.rates) - 1:
                    self.results()
            return True
        return h

    # ---------------- load cell weighing
    # series = the weights before each tip from the run's first tip through the tip after its last one
    # (or the current reading when the drip stopped). Its first and last values bracket exactly the
    # run's water, and any drop in between means the container was bumped or lifted.
    def _weigh_run(self, run, series):
        self.pending.remove(run)
        if any(w is None for w in (series[0], series[-1])):
            run["note"] = "no scale reading"
            self.say(f"   Run {run['run']}: no reading from the load cell; run discarded.")
            self._discard(run)
            self._run_done(run)
            return
        start, end = series[0], series[-1]
        net = end - start
        gpt = net / TIPS_PER_RUN
        run.update(start_g=round(start, 2), end_g=round(end, 2), net_g=round(net, 2),
                   g_per_tip=round(gpt, 4), ml_per_tip=round(gpt / DENSITY, 4))
        self.say(f"   Run {run['run']} weighed: {net:.1f} g = {gpt:.3f} g/tip at {run['tips_per_min']:.2f} tips/min")
        # Out of range is never kept: with no typo possible, the scale or the setup was disturbed
        if not GPT_RANGE[0] <= gpt <= GPT_RANGE[1]:
            run["note"] = f"{gpt:.2f} g/tip outside {GPT_RANGE[0]}-{GPT_RANGE[1]}"
            self.say(f"   That is outside {GPT_RANGE[0]} to {GPT_RANGE[1]} g/tip, so the run is discarded. "
                     "Check that all the water reaches the container and nothing touches the scale.")
            self._discard(run)
            self._run_done(run)
            return
        reasons, discard_advised = self._flag_reasons(run, gpt)
        known = [w for w in series if w is not None]
        drop = max((a - b for a, b in zip(known, known[1:])), default=0.0)
        if drop > DISTURB_G:
            reasons.append(f"the scale reading dropped {drop:.0f} g during the run (container bumped or lifted?)")
            discard_advised = True
        if max(known) > LOADCELL_MAX_G:
            reasons.append(f"the scale passed its {LOADCELL_MAX_G} g limit")
            discard_advised = True
        if reasons:
            run["note"] = "; ".join(reasons)
            self._ask_keep(run, reasons, discard_advised, then=self._run_done)
            return
        run["kept"] = True
        self._run_done(run)

    # A weighed and decided run is saved; the rate may now be finished
    def _run_done(self, run):
        run["done"] = True
        self._write(self.runs_csv, {k: run.get(k) for k in self.runs_csv[1].fieldnames})
        self._finish_rate_if_ready(run["rate_index"])

    # Load cell: after the rate's last run, wait until every run at the rate is weighed and decided.
    # A discard then leaves too few valid runs, so a replacement starts at the next tip; otherwise the
    # rate's summary prints and the next rate (or the results) follows.
    def _finish_rate_if_ready(self, ri):
        if self.phase != "finishing" or ri != self.rate_i:
            return
        if any(r["kept"] is None for r in self.runs if r["rate_index"] == ri):
            return
        if self.valid_runs(ri) < RUNS_PER_RATE:
            self.phase = "armed"
            self.say("   The replacement run starts at the next tip.")
            return
        self.rate_done[ri] = True
        self._rate_summary(ri)
        if ri + 1 < len(self.rates):
            self.rate_i += 1
            self.start_rate()
        else:
            self.phase = "done"
            self.results()

    # Load cell, called while waiting for input: if the drip stopped after a run's last tip, there is
    # no next tip to weigh it at, so weigh it from the current reading once the water has drained
    def poll(self):
        now = self.clock.now()
        for run in list(self.pending):
            wait = max(NO_TIP_WAIT_S, 2 * 60.0 / run["tips_per_min"])
            if now - self.tips[run["end_tip"]] > wait:
                self.say("   No tip since the run ended; weighing it from the current reading.")
                self._weigh_run(run, self.pre_w[run["start_tip"] + 1:] + [self.scale.grams_now()])

    # ---------------- results
    def kept_runs(self, ri):
        return [r for r in self.runs if r["rate_index"] == ri and r.get("g_per_tip") and r["kept"]]

    # Step 7: mL per tip for a rate - with 5 or more runs, the highest and lowest are dropped
    def rate_stats(self, ri):
        runs = self.kept_runs(ri)
        if not runs:
            return None    # every run at this rate was discarded
        vals = sorted(r["ml_per_tip"] for r in runs)
        used = vals[1:-1] if len(vals) >= 5 else vals
        sides = [abs(r["side_ratio"] - 1) for r in runs if r["side_ratio"] is not None]
        mean = statistics.mean(used)
        return {"rate_mm_h": self.rates[ri], "n_runs": len(vals), "n_used": len(used),
                "ml_per_tip": mean,
                "spread_pct": (max(used) - min(used)) / mean * 100 if len(used) > 1 else 0.0,
                "tips_per_min": statistics.mean(r["tips_per_min"] for r in runs),
                "side_imbalance_pct": statistics.mean(sides) * 100 if sides else None}

    def _rate_summary(self, ri):
        s = self.rate_stats(ri)
        if s is None:
            self.say(f"\n-- {self.rates[ri]:g} mm/h done: NO valid runs. "
                     f"Repeat it later with --rates {self.rates[ri]:g}")
            return
        warn = "" if s["n_runs"] >= MIN_RUNS else f"   WARNING: fewer than {MIN_RUNS} valid runs"
        self.say(f"\n-- {s['rate_mm_h']:g} mm/h done: {s['ml_per_tip']:.4f} mL/tip "
                 f"(mean of {s['n_used']} of {s['n_runs']} runs, spread {s['spread_pct']:.2f}%), "
                 f"actual {s['tips_per_min']:.2f} tips/min, side imbalance "
                 f"{side_text(s)}{warn}")

    # Collector rim radius that makes one tip of this volume equal 0.2 mm of rain
    @staticmethod
    def radius_mm(ml_per_tip):
        return math.sqrt(ml_per_tip * 1000.0 / MM_PER_TIP / math.pi)

    # Step 8: print mL/tip for every rate and the % error at each rate for each possible
    # sizing rate, then ask which rate to size the rim at
    def results(self):
        # Rates where every run was discarded are listed but left out of the comparison
        all_stats = [self.rate_stats(i) for i in range(len(self.rates))]
        missing = [self.rates[i] for i, st in enumerate(all_stats) if st is None]
        stats = [st for st in all_stats if st is not None]
        if not stats:
            self.say("\nNo rate has any valid runs, so there is nothing to size the rim from.")
            self.finished = True
            return
        lines = [f"Gauge {self.gauge_id}   {dt.datetime.now():%Y-%m-%d %H:%M}",
                 f"{TIPS_PER_RUN} tips/run, density {DENSITY} g/mL, {MM_PER_TIP} mm/tip", "",
                 "Rate (mm/h)  tips/min  mL/tip   g/tip  runs  spread  side imbalance"]
        for s in stats:
            gpt = s["ml_per_tip"] * DENSITY
            ideal = "" if IDEAL_GPT[0] <= gpt <= IDEAL_GPT[1] else f"   outside ideal {IDEAL_GPT[0]}-{IDEAL_GPT[1]} g/tip"
            lines.append(f"{s['rate_mm_h']:>10g}  {s['tips_per_min']:8.2f}  {s['ml_per_tip']:.4f}  {gpt:5.2f}"
                         f"  {s['n_used']}/{s['n_runs']}  {s['spread_pct']:5.2f}%  "
                         f"{side_text(s):>6}{ideal}")
        for rate in missing:
            lines.append(f"{rate:>10g}  no valid runs - repeat with --rates {rate:g}")
        lines += ["", "% error at each rate (rows) if the rim is sized at (columns):"]
        head = f"{'Rate':>10}" + "".join(f" {'size@' + format(s['rate_mm_h'], 'g'):>11} " for s in stats)
        lines.append(head)
        for si in stats:
            row = f"{si['rate_mm_h']:>10g}"
            for sj in stats:
                row += f" {(sj['ml_per_tip'] / si['ml_per_tip'] - 1) * 100:+10.2f}% "
            lines.append(row)
        lines.append(f"{'radius mm':>10}" + "".join(f" {self.radius_mm(s['ml_per_tip']):11.2f} "
                                                   for s in stats))
        report = "\n".join(lines)
        self.say("\n" + report + "\n")
        self.report, self.stats = report, stats
        opts = ", ".join(f"{s['rate_mm_h']:g}" for s in stats)
        self.ask(f"Which rate (mm/h) should the rim be sized at? [{opts}]",
                 self._size_handler, auto=stats[0]["rate_mm_h"])

    # Final step: show the rim radius and errors for the chosen rate and save summary.txt and result.json
    def _size_handler(self, line):
        v = self._num(line)
        match = [s for s in self.stats if v is not None and abs(s["rate_mm_h"] - v) < 1e-6]
        if not match:
            self.say("   Enter one of the tested rates.")
            return False
        ref = match[0]
        r = self.radius_mm(ref["ml_per_tip"])
        out = [f"Sized at {ref['rate_mm_h']:g} mm/h: rim radius {r:.2f} mm "
               f"(diameter {2 * r:.2f} mm)", "", "Rate (mm/h)   error     within +/-5%"]
        errors = {}
        for s in self.stats:
            e = (ref["ml_per_tip"] / s["ml_per_tip"] - 1) * 100
            errors[s["rate_mm_h"]] = round(e, 3)
            out.append(f"{s['rate_mm_h']:>10g}   {e:+6.2f}%   {'yes' if abs(e) <= 5 else 'NO'}")
        text = "\n".join(out)
        self.say("\n" + text + "\n")
        with open(os.path.join(self.dir, "summary.txt"), "w") as f:
            f.write(self.report + "\n\n" + text + "\n")
        with open(os.path.join(self.dir, "result.json"), "w") as f:
            json.dump({"gauge_id": self.gauge_id, "tips_per_run": TIPS_PER_RUN,
                       "density_g_ml": DENSITY, "mm_per_tip": MM_PER_TIP,
                       "rates": self.stats, "sizing_rate_mm_h": ref["rate_mm_h"],
                       "rim_radius_mm": round(r, 3), "errors_pct": errors,
                       "gpt_range": list(GPT_RANGE), "ignored_pulses": self.rejected}, f, indent=2)
        self.say(f"Saved: {self.dir}/summary.txt, result.json, runs.csv, tips.csv")
        self.finished = True
        return True

    # ---------------- main loop
    # Tips come from the GPIO pin (or the simulator); answers come from the keyboard.
    # Both arrive on one queue and are handled in order until the results are saved.
    def run(self):
        a = self.args
        if a.sim:
            self.source = SimGauge(self.q, self.clock, a.speed)
            if self.loadcell:
                self.scale = SimScale(self.source, self.clock)
            self.say(f"SIMULATION at {a.speed:g}x speed" + (" (automatic)" if a.auto else "")
                     + (" with a simulated load cell" if self.loadcell else ""))
        else:
            if self.loadcell:
                self.scale = open_scale(self.clock.now)
                import nau7802
                nau7802.use_or_calibrate(self.scale, cal_path())
            self.source = GpioTips(self.q, self.clock)
            self.say(f"Reading tips on GPIO{TIP_GPIO}")
        self.setup()
        if not a.auto:
            threading.Thread(target=stdin_reader, args=(self.q,), daemon=True).start()
        while not self.finished:
            try:
                kind, val = self.q.get(timeout=0.5)
            except queue.Empty:
                if self.loadcell:
                    self.poll()
                continue
            if kind == "tip":
                self.on_tip(val)
            elif kind == "line":
                self.answer(val)
            elif kind == "eof":
                self.say("Input closed; stopping.")
                break


# The Qwiic Scale on the I2C bus; nau7802.py sits next to this script
def open_scale(now):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import nau7802
        return nau7802.LoadCell(now=now)
    except (ImportError, OSError) as e:
        sys.exit(f"Could not start the Qwiic Scale (NAU7802 at I2C 0x2A): {e}\n"
                 "Check the Qwiic cable and that I2C is enabled, or run with --manual to weigh buckets by hand.")


# --calibrate-scale: calibrate, then print the weight every second to check it (Ctrl+C stops)
def calibrate_scale_only():
    scale = open_scale(time.monotonic)
    import nau7802
    nau7802.calibrate(scale, cal_path())
    print("\nLive reading, Ctrl+C to stop:")
    try:
        while True:
            print(f"   {scale.grams_now():8.1f} g", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print()


def main():
    global GPT_RANGE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gauge-id")
    ap.add_argument("--rates", type=float, nargs="+", help="mm/h, e.g. --rates 12 30 60 120 200")
    ap.add_argument("--manual", action="store_true", help="swap and weigh buckets A and B by hand instead of the load cell")
    ap.add_argument("--calibrate-scale", action="store_true", help="only calibrate the load cell, then show live readings")
    ap.add_argument("--gpt-range", type=float, nargs=2, metavar=("MIN", "MAX"),
                    help=f"acceptable grams per tip (default {GPT_RANGE[0]:g} {GPT_RANGE[1]:g})")
    ap.add_argument("--sim", action="store_true", help="simulated gauge, no hardware")
    ap.add_argument("--speed", type=float, default=1.0, help="simulation speed-up")
    ap.add_argument("--auto", action="store_true", help="with --sim: answer prompts automatically")
    a = ap.parse_args()
    if a.auto and not a.sim:
        ap.error("--auto only works with --sim")
    if a.rates and any(r <= 0 for r in a.rates):
        ap.error("--rates must all be positive")
    if a.gpt_range:
        if not 0 < a.gpt_range[0] < a.gpt_range[1]:
            ap.error("--gpt-range needs MIN then MAX, both positive, e.g. --gpt-range 4 6.5")
        GPT_RANGE = tuple(a.gpt_range)
        print(f"Accepting {GPT_RANGE[0]:g} to {GPT_RANGE[1]:g} g/tip")
    if a.calibrate_scale:
        calibrate_scale_only()
        return
    s = Session(a)
    try:
        s.run()
    except KeyboardInterrupt:
        print(f"\nStopped. Data so far is in {getattr(s, 'dir', DATA_DIR)}")


if __name__ == "__main__":
    main()
