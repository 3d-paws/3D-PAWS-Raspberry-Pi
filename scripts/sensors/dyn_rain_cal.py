#!/usr/bin/env python3
"""
dyn_rain_cal.py  -  3D-PAWS tipping bucket dynamic (multi-rate) calibration

Walks the operator through the manual-weighing procedure:
  set the drip to a target tips/min -> wait for STEADY -> 5 runs of 25 tips,
  swapping buckets A and B at each run boundary -> enter weights -> next rate.
At the end it shows the rim radius and the % error at every rate for each
possible sizing rate, asks which one to use, and saves everything.

Install:  /home/pi/3d_paws/scripts/sensors/dyn_rain_cal.py
Results:  /home/pi/data/tests/dyn_rain_cal_<GaugeID>_<date_time>/

Usage (from /home/pi/3d_paws/scripts/sensors/):
  python3 dyn_rain_cal.py                     real gauge on the GPIO pin below
  python3 dyn_rain_cal.py --sim               simulated gauge in real time (training)
  python3 dyn_rain_cal.py --sim --speed 60    simulated, 60x faster
  python3 dyn_rain_cal.py --sim --speed 300 --auto   fully automatic demo run

Stop the 3D-PAWS station software first if it is running on this Pi,
so it is not reading the same GPIO pin (turn off Tipping Bucket in the controller).

During a session:
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
  Weights outside 5-7.5 g/tip are never stored. Each discarded run adds one replacement run
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
GPT_RANGE = (5.0, 7.5)    # acceptable grams per tip; outside this, re-enter or discard (tip volume rises at high rates)
IDEAL_GPT = (5.5, 6.5)    # target grams per tip; rates outside it are marked in the final summary
DISCARD_OFF_PCT = 10.0    # a run averaging more than this % off the target rate defaults to discard
SCALE_MAX_G = 6000        # scale capacity; warn before a bucket that keeps filling would exceed it
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
    def __init__(self, q, clock):
        from gpiozero import Button
        self.btn = Button(TIP_GPIO, pull_up=True, bounce_time=BOUNCE_S)
        self.btn.when_pressed = lambda: q.put(("tip", clock.now()))

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
            self.q.put(("tip", self.clock.now()))

    def grams(self, first, last):
        return sum(self.masses[first:last + 1])


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
class Session:
    def __init__(self, args):
        self.args = args
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
                                               "phase", "rate_mm_h", "run"])
        self.runs_csv = self._csv("runs.csv", ["rate_mm_h", "target_tpm", "run", "bucket",
                                               "start_tip", "end_tip", "duration_s", "tips_per_min",
                                               "start_g", "end_g", "net_g", "g_per_tip",
                                               "ml_per_tip", "side_ratio", "off_target_pct", "irregular", "kept"])
        self.say(f"\nSaving to {self.dir}")
        self.say("\nRate plan:")
        for r in rates:
            t = tpm_for(r)
            self.say(f"  {r:>6g} mm/h = {t:5.2f} tips/min, {TIPS_PER_RUN} tips per run = "
                     f"{TIPS_PER_RUN / t:5.1f} min, {RUNS_PER_RATE} runs")
        self.say()
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
        self.say(f"Adjust the drip bolt to {self.target:.2f} tips/min "
                 f"({self.target * (1 - STEADY_TOL):.2f} to {self.target * (1 + STEADY_TOL):.2f}). "
                 "Water goes to the WASTE container.")
        self.ask("When the script says STEADY and bucket A is ready, press Enter "
                 "(the next tip starts run 1).", self._arm_handler)

    # Step 3: once STEADY, Enter arms the run; the next tip starts run 1 ('force' skips the steady check)
    def _arm_handler(self, line):
        if line.lower() != "force" and not self.steady:
            self.say("   Not steady yet. Wait for STEADY, or type 'force' to start anyway.")
            return False
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
        self.tips.append(t)
        interval = t - self.tips[-2] if i else None
        rate = 60.0 / interval if interval else None
        row = {"tip": i, "time": self.clock.stamp(t), "t_s": round(t, 3),
               "interval_s": round(interval, 3) if interval else "",
               "tips_per_min": round(rate, 3) if rate else "", "phase": self.phase,
               "rate_mm_h": self.rate if self.phase != "setup" else "", "run": self.run_no or ""}
        self._write(self.tips_csv, row)

        if self.phase in ("setup", "done"):
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
        self.bucket = bucket
        self.drift_warned = False
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
                     "(possible missed or extra tip). You will be asked about it when you weigh this run.")
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
            others = [r["g_per_tip"] for r in self.runs
                      if r["rate_index"] == run["rate_index"] and r is not run
                      and r.get("g_per_tip") and r["kept"] is not False]
            # Starting weight for the bucket's next run comes after any keep question
            full_note = ""
            if v + TIPS_PER_RUN * GPT_RANGE[1] > SCALE_MAX_G:
                full_note = f" WARNING: another run would pass the {SCALE_MAX_G} g scale limit - empty it."
            self.ask_next(f"Empty bucket {b} and enter its empty weight, or press Enter to keep "
                          f"filling it (its next run starts from {v:g} g):{full_note}",
                          self._tare_after(run), auto=self._auto_start(run), scale=lambda: f"{v:g}")
            # Reasons to flag the run. Discard is the default for an irregular tip (g/tip about 4% off)
            # or a drip more than DISCARD_OFF_PCT off target; otherwise keep is the default, since the
            # actual rate is recorded and a few % off target barely changes g/tip.
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
            if len(others) >= 2:
                med = statistics.median(others)
                dev = (gpt / med - 1) * 100
                if abs(dev) > FLAG_PCT:
                    reasons.append(f"{dev:+.1f}% from the other runs")
            if reasons:
                default = "n" if discard_advised else "y"
                choice = "[y/N] (Enter = discard)" if default == "n" else "[Y/n] (Enter = keep)"
                self.ask_next(f"FLAG: run {run['run']}: " + "; ".join(reasons) + f". Keep it? {choice}",
                              self._keep_handler(run, default), auto=default)
                return True
            run["kept"] = True
            return True
        return h

    # A flagged run can be kept or discarded. Enter takes the recommended answer (default).
    def _keep_handler(self, run, default="y"):
        def h(line):
            if line == "":
                line = default
            if line.lower() in ("y", "yes"):
                run["kept"] = True
                return True
            if line.lower() in ("n", "no"):
                self._discard(run)
                return True
            self.say("   Type y or n.")
            return False
        return h

    # Discarding a run while its rate is still running adds one replacement run automatically
    # (the rate ends at RUNS_PER_RATE valid runs); after the rate has finished it can't be replaced
    def _discard(self, run):
        run["kept"] = False
        ri = run["rate_index"]
        if ri == self.rate_i and self.phase == "running" and not self.rate_done.get(ri):
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
                       "ignored_pulses": self.rejected}, f, indent=2)
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
            self.say(f"SIMULATION at {a.speed:g}x speed" + (" (automatic)" if a.auto else ""))
        else:
            self.source = GpioTips(self.q, self.clock)
            self.say(f"Reading tips on GPIO{TIP_GPIO}")
        self.setup()
        if not a.auto:
            threading.Thread(target=stdin_reader, args=(self.q,), daemon=True).start()
        while not self.finished:
            kind, val = self.q.get()
            if kind == "tip":
                self.on_tip(val)
            elif kind == "line":
                self.answer(val)
            elif kind == "eof":
                self.say("Input closed; stopping.")
                break


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gauge-id")
    ap.add_argument("--rates", type=float, nargs="+", help="mm/h, e.g. --rates 12 30 60 120 200")
    ap.add_argument("--sim", action="store_true", help="simulated gauge, no hardware")
    ap.add_argument("--speed", type=float, default=1.0, help="simulation speed-up")
    ap.add_argument("--auto", action="store_true", help="with --sim: answer prompts automatically")
    a = ap.parse_args()
    if a.auto and not a.sim:
        ap.error("--auto only works with --sim")
    if a.rates and any(r <= 0 for r in a.rates):
        ap.error("--rates must all be positive")
    s = Session(a)
    try:
        s.run()
    except KeyboardInterrupt:
        print(f"\nStopped. Data so far is in {getattr(s, 'dir', DATA_DIR)}")


if __name__ == "__main__":
    main()
