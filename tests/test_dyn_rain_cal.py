#!/usr/bin/env python3
"""
Tests for scripts/sensors/dyn_rain_cal.py - the run counting, flagging and weighing logic.

Run from the project folder (no hardware, takes about a second):
  python3 -m unittest tests/test_dyn_rain_cal.py -v

Sessions are driven by feeding tip times straight to the script and answering its prompts the
way an operator would, so a whole calibration runs instantly instead of in real time.
"""
import argparse
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "sensors", "dyn_rain_cal.py")
spec = importlib.util.spec_from_file_location("dyn_rain_cal", SCRIPT)
drc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drc)


class FakeGauge:
    """Stands in for the GPIO pin; tips are fed to the session by the test."""

    def set_target(self, tpm):
        pass


class Operator:
    """Runs a session: feeds evenly spaced tips at the target rate and answers every prompt."""

    def __init__(self, rates=(60,), gpt=6.0, keep_filling=True, missed=(), flag_answer=""):
        self.tmp = tempfile.TemporaryDirectory()
        drc.DATA_DIR = self.tmp.name
        args = argparse.Namespace(sim=False, auto=False, speed=1.0, gauge_id="TEST", rates=list(rates), manual=True)
        self.s = drc.Session(args)
        self.s.source = FakeGauge()
        self.gpt, self.keep_filling, self.missed, self.flag_answer = gpt, keep_filling, set(missed), flag_answer
        self.out = io.StringIO()
        with contextlib.redirect_stdout(self.out):
            self.s.setup()
            self.s.answer("550")
            self.s.answer("550")

    def answer_prompts(self):
        s = self.s
        while s.prompts:
            text = s.prompts[0]["text"]
            if text.startswith("When the script says STEADY"):
                if not s.steady:
                    return
                s.answer("")
            elif "FULL" in text:
                bucket = text.split()[2]
                s.answer(str(round(s.tare[bucket] + drc.TIPS_PER_RUN * self.gpt)))
            elif text.startswith("Empty bucket"):
                s.answer("" if self.keep_filling else "552")
            elif text.startswith("Funnel check"):
                s.answer(getattr(self, "funnel_answer", ""))
            elif text.startswith("FLAG"):
                s.answer(self.flag_answer)
            elif text.startswith("Which rate"):
                s.answer(format(s.stats[0]["rate_mm_h"], "g"))
            else:
                raise AssertionError("Unexpected prompt: " + text)

    def run(self, max_tips=5000):
        """Feed tips until the session finishes. Tip numbers in `missed` happen but aren't detected."""
        s, t = self.s, 0.0
        with contextlib.redirect_stdout(self.out):
            for tip in range(max_tips):
                self.answer_prompts()
                if s.finished:
                    return self
                t += 60.0 / s.target
                if tip not in self.missed:
                    s.on_tip(t)
        raise AssertionError("Session did not finish")

    def runs_at(self, ri=0):
        return [r for r in self.s.runs if r["rate_index"] == ri]

    def close(self):
        for f, _ in (self.s.tips_csv, self.s.runs_csv):
            f.close()
        self.tmp.cleanup()


class Test(unittest.TestCase):
    """Closes each session's files and temporary folder after the test."""

    def operator(self, **kwargs):
        op = Operator(**kwargs)
        self.addCleanup(op.close)
        return op

    def bare_session(self):
        """A session already running at 60 mm/h, for testing one prompt at a time."""
        op = self.operator()
        s = op.s
        s.phase, s.tare = "running", {"A": 553.0, "B": 550.0}
        return op, s


class FakeScale:
    """Stands in for the load cell: a 400 g container plus gpt grams for every tip so far, including
    tips the gauge didn't detect. bump() takes water off from the next tip on (container lifted)."""

    def __init__(self, op, container=400.0):
        self.op, self.container = op, container
        self.removed = 0.0

    def _load(self):
        tips = len(self.op.s.tips) + sum(1 for m in self.op.missed if m < self.op.fed)
        if self.op.side_g:
            return self.container + sum(self.op.side_g[k % 2] for k in range(tips)) - self.removed
        return self.container + self.op.gpt * tips - self.removed

    def grams_before(self, t, window, guard):
        return self._load()

    def grams_now(self):
        return self._load()

    def empty(self):
        self.removed += self._load() - self.container

    def bump(self, grams):
        self.removed += grams


class LoadCellOperator(Operator):
    """Runs a load cell session: no bucket prompts, the scale weighs every run."""

    def __init__(self, rates=(60,), gpt=6.0, missed=(), flag_answer="", container=400.0, bumps=None, stop_at_last_run=False,
                 sides=(1.0, 1.0), bounces=(), side_g=None, sensors=None, funnel_answer=""):
        self.tmp = tempfile.TemporaryDirectory()
        drc.DATA_DIR = self.tmp.name
        args = argparse.Namespace(sim=False, auto=False, speed=1.0, gauge_id="TEST", rates=list(rates), manual=False)
        self.s = drc.Session(args)
        self.s.source = FakeGauge()
        self.gpt, self.missed, self.flag_answer = gpt, set(missed), flag_answer
        self.bumps = bumps or {}       # tip number -> grams lifted off just before it
        self.stop_at_last_run = stop_at_last_run   # the drip is turned off right after the last run
        self.sides = sides             # each bucket side's fill time as a multiple of the average gap
        self.bounces = set(bounces)    # tip numbers followed 2.4 s later by a false pulse
        self.side_g = side_g           # grams each bucket side dumps, alternating; None = gpt for every tip
        self.fed = 0
        self.s.scale = FakeScale(self, container)
        self.s.sensors = sensors
        self.funnel_answer = funnel_answer
        self.out = io.StringIO()
        with contextlib.redirect_stdout(self.out):
            self.s.setup()

    def answer_prompts(self):
        s = self.s
        while s.prompts:
            text = s.prompts[0]["text"]
            if text.startswith("When the script says STEADY"):
                if not s.steady:
                    return
                s.answer("")
            elif text.startswith("The scale holds"):
                s.answer("")
            elif text.startswith("Funnel check"):
                s.answer(getattr(self, "funnel_answer", ""))
            elif text.startswith("FLAG"):
                s.answer(self.flag_answer)
            elif text.startswith("Which rate"):
                s.answer(format(s.stats[0]["rate_mm_h"], "g"))
            else:
                raise AssertionError("Unexpected prompt: " + text)

    def run(self, max_tips=5000):
        s, t = self.s, 0.0
        with contextlib.redirect_stdout(self.out):
            for tip in range(max_tips):
                self.answer_prompts()
                if s.finished:
                    return self
                t += 60.0 / s.target
                if self.stop_at_last_run and s.phase == "finishing" and s.rate_i == len(s.rates) - 1:
                    s.clock.now = lambda: t + 1000.0     # drip off: time passes with no tips
                    s.poll()
                    self.answer_prompts()
                    return self
                t += 60.0 / s.target * (self.sides[tip % 2] - 1)
                if tip in self.bumps:
                    s.scale.bump(self.bumps[tip])
                if s.full_warned and not getattr(self, "emptied_on_banner", False):
                    self.emptied_on_banner = True          # the operator empties it when told to
                    s.scale.empty()
                self.fed = tip + 1
                if tip not in self.missed:
                    s.on_tip(t)
                if tip in self.bounces:
                    s.on_tip(t + 2.4)
        raise AssertionError("Session did not finish")


def make_run(n=1, off=0.0, irregular=0, bucket="A"):
    return {"rate_index": 0, "run": n, "bucket": bucket, "off_target_pct": off, "irregular": irregular,
            "tips_per_min": 5.0, "kept": None, "side_ratio": 1.0, "density_g_ml": drc.DENSITY}


class SessionTests(Test):

    def test_clean_session_finishes_with_five_runs_and_saves_results(self):
        op = self.operator(rates=(60,)).run()
        runs = op.runs_at(0)
        self.assertEqual(len(runs), drc.RUNS_PER_RATE)
        self.assertTrue(all(r["kept"] for r in runs))
        with open(os.path.join(op.s.dir, "result.json")) as f:
            result = json.load(f)
        self.assertAlmostEqual(result["rates"][0]["ml_per_tip"], 6.0 / drc.DENSITY, places=3)
        for name in ("summary.txt", "runs.csv", "tips.csv"):
            self.assertTrue(os.path.exists(os.path.join(op.s.dir, name)))

    def test_missed_tip_is_discarded_and_replaced_exactly_once(self):
        # Tip 40 falls inside run 2 (run 1 starts after ~6 setting tips)
        op = self.operator(rates=(60,), missed=(40,)).run()
        runs = op.runs_at(0)
        discarded = [r for r in runs if r["kept"] is False]
        self.assertEqual(len(discarded), 1)
        self.assertGreater(discarded[0]["irregular"], 0)
        self.assertEqual(len(runs), drc.RUNS_PER_RATE + 1)
        self.assertEqual(sum(1 for r in runs if r["kept"]), drc.RUNS_PER_RATE)

    def test_keep_filling_carries_the_end_weight_to_the_next_run(self):
        op = self.operator(rates=(60,), keep_filling=True).run()
        a_runs = [r for r in op.runs_at(0) if r["bucket"] == "A"]
        for previous, following in zip(a_runs, a_runs[1:]):
            self.assertEqual(following["start_g"], previous["end_g"])

    def test_emptying_uses_the_typed_empty_weight(self):
        op = self.operator(rates=(60,), keep_filling=False).run()
        later = [r for r in op.runs_at(0) if r["run"] > 2]
        self.assertTrue(all(r["start_g"] == 552 for r in later))

    def test_two_rates_both_summarized(self):
        op = self.operator(rates=(30, 60)).run()
        self.assertEqual([st["rate_mm_h"] for st in op.s.stats], [30, 60])


class WeighingTests(Test):

    def ask_full(self, s, run):
        s.runs.append(run)
        s.prompts.clear()
        s.ask("Weigh bucket A FULL, enter grams:", s._full_handler(run))

    def test_out_of_range_weight_is_never_stored_even_if_repeated(self):
        op, s = self.bare_session()
        run = make_run()
        with contextlib.redirect_stdout(op.out):
            self.ask_full(s, run)
            s.answer("553")      # 0 g net
            s.answer("553")      # same again: used to be stored
        self.assertIsNone(run.get("g_per_tip"))
        self.assertIn("emptied", op.out.getvalue())

    def test_starting_weight_can_be_corrected(self):
        op, s = self.bare_session()
        s.tare["A"] = 703.0      # bucket was emptied to 553 g but Enter was pressed
        run = make_run()
        with contextlib.redirect_stdout(op.out):
            self.ask_full(s, run)
            for line in ("703", "s", "553", "703"):
                s.answer(line)
        self.assertEqual(run["start_g"], 553.0)
        self.assertAlmostEqual(run["g_per_tip"], 6.0)

    def test_d_discards_and_requires_a_typed_weight(self):
        op, s = self.bare_session()
        run = make_run()
        with contextlib.redirect_stdout(op.out):
            self.ask_full(s, run)
            s.answer("900")
            s.answer("d")
            s.answer("")         # Enter isn't a weight here
            s.answer("560")
        self.assertIs(run["kept"], False)
        self.assertEqual(s.tare["A"], 560.0)

    def flag_default(self, off=0.0, irregular=0):
        op, s = self.bare_session()
        run = make_run(off=off, irregular=irregular)
        with contextlib.redirect_stdout(op.out):
            self.ask_full(s, run)
            s.answer("703")      # 150 g = 6.0 g/tip
            flags = [p for p in s.prompts if p["text"].startswith("FLAG")]
            if not flags:
                return run["kept"], None
            s.answer("")         # Enter = recommended answer
        return run["kept"], flags[0]["text"]

    def test_on_target_run_is_not_flagged(self):
        kept, flag = self.flag_default(off=1.0)
        self.assertIsNone(flag)
        self.assertTrue(kept)

    def test_five_to_ten_percent_off_target_defaults_to_keep(self):
        kept, flag = self.flag_default(off=7.0)
        self.assertIn("Enter = keep", flag)
        self.assertTrue(kept)

    def test_over_ten_percent_off_target_defaults_to_discard(self):
        kept, flag = self.flag_default(off=12.0)
        self.assertIn("Enter = discard", flag)
        self.assertIs(kept, False)

    def test_irregular_tip_defaults_to_discard(self):
        kept, flag = self.flag_default(irregular=1)
        self.assertIn("missed or extra tip", flag)
        self.assertIs(kept, False)

    def test_scale_limit_warning(self):
        op, s = self.bare_session()
        s.tare["A"] = 5700.0
        run = make_run()
        with contextlib.redirect_stdout(op.out):
            self.ask_full(s, run)
            s.answer("5850")
        self.assertTrue(any("scale limit" in p["text"] for p in s.prompts))


class LoadCellTests(Test):

    def lc_operator(self, **kwargs):
        op = LoadCellOperator(**kwargs)
        self.addCleanup(op.close)
        return op

    def test_clean_session_weighs_every_run_from_the_scale(self):
        op = self.lc_operator(rates=(60,)).run()
        runs = op.runs_at(0)
        self.assertEqual(len(runs), drc.RUNS_PER_RATE)
        self.assertTrue(all(r["kept"] for r in runs))
        self.assertTrue(all(abs(r["g_per_tip"] - 6.0) < 1e-9 for r in runs))
        self.assertNotIn("BUCKET", op.out.getvalue())
        with open(os.path.join(op.s.dir, "result.json")) as f:
            self.assertAlmostEqual(json.load(f)["rates"][0]["ml_per_tip"], 6.0 / drc.DENSITY, places=3)

    def test_runs_are_back_to_back_and_weighed_at_the_next_tip(self):
        op = self.lc_operator(rates=(60,)).run()
        runs = op.runs_at(0)
        for previous, following in zip(runs, runs[1:]):
            self.assertEqual(following["start_tip"], previous["end_tip"])
            self.assertAlmostEqual(following["start_g"], previous["end_g"])

    def test_missed_tip_in_the_last_run_is_still_replaced(self):
        # Manual mode can't replace the last run of a rate; with the load cell the rate waits for it.
        # Run 5 covers tips of about 106-130, so tip 120 is inside it
        op = self.lc_operator(rates=(60,), missed=(120,)).run()
        runs = op.runs_at(0)
        self.assertIs(runs[4]["kept"], False)
        self.assertEqual(len(runs), drc.RUNS_PER_RATE + 1)
        self.assertEqual(sum(1 for r in runs if r["kept"]), drc.RUNS_PER_RATE)

    def test_bumped_container_defaults_to_discard(self):
        op = self.lc_operator(rates=(60,), bumps={40: 20.0}).run()
        bumped = [r for r in op.runs_at(0) if "dropped" in (r.get("note") or "")]
        self.assertEqual(len(bumped), 1)
        self.assertIs(bumped[0]["kept"], False)
        self.assertEqual(sum(1 for r in op.runs_at(0) if r["kept"]), drc.RUNS_PER_RATE)

    def test_unequal_bucket_sides_still_read_steady(self):
        # The wxtools gauge: one side fills in about 1.2x the average gap, the other in 0.8x
        op = self.lc_operator(rates=(60,), sides=(1.2, 0.8)).run()
        self.assertIn("STEADY", op.out.getvalue())
        self.assertNotIn("drifted", op.out.getvalue())
        self.assertEqual(sum(1 for r in op.runs_at(0) if r["kept"]), drc.RUNS_PER_RATE)
        self.assertEqual(len(op.runs_at(0)), drc.RUNS_PER_RATE)

    def test_bucket_sides_weighed_and_reported(self):
        self.addCleanup(setattr, drc, "GPT_RANGE", drc.GPT_RANGE)
        drc.GPT_RANGE = (4.0, 6.5)     # --gpt-range 4 6.5, as for the real gauge
        op = self.lc_operator(rates=(60,), gpt=4.7, sides=(1.2, 0.8), side_g=(5.5, 3.9)).run()
        st = op.s.stats[0]
        self.assertAlmostEqual(st["side_heavy_g"], 5.5, places=6)
        self.assertAlmostEqual(st["side_light_g"], 3.9, places=6)
        self.assertAlmostEqual(st["side_mass_diff_pct"], (5.5 / 3.9 - 1) * 100, places=6)
        with open(os.path.join(op.s.dir, "summary.txt")) as f:
            self.assertIn("heavier side", f.read())
        with open(os.path.join(op.s.dir, "result.json")) as f:
            self.assertAlmostEqual(json.load(f)["rates"][0]["side_heavy_g"], 5.5, places=6)

    def test_manual_mode_has_no_bucket_side_table(self):
        op = self.operator(rates=(60,)).run()
        self.assertIsNone(op.s.stats[0]["side_heavy_g"])
        self.assertNotIn("heavier side", op.out.getvalue())

    def test_bucket_bounce_during_a_run_is_ignored(self):
        op = self.lc_operator(rates=(60,), bounces=(40, 80)).run()
        self.assertEqual(op.s.rejected, 2)
        self.assertEqual(len(op.runs_at(0)), drc.RUNS_PER_RATE)
        self.assertTrue(all(r["kept"] for r in op.runs_at(0)))

    def test_out_of_range_run_is_discarded_without_asking(self):
        op = self.lc_operator(rates=(60,))
        s = op.s
        with contextlib.redirect_stdout(op.out):
            run = dict(make_run(), start_tip=0, end_tip=25, bucket=None)
            s.runs.append(run)
            s.pending.append(run)
            s._weigh_run(run, [400.0] * 25 + [450.0])      # 50 g = 2 g/tip
        self.assertIs(run["kept"], False)
        self.assertFalse(any(p["text"].startswith("FLAG") for p in s.prompts))

    def test_gpt_range_option_keeps_a_small_bucket(self):
        # A 4.75 g/tip gauge: every run is out of range at the default 5-7.5, kept with --gpt-range 4 6.5
        default = drc.GPT_RANGE
        self.addCleanup(setattr, drc, "GPT_RANGE", default)
        drc.GPT_RANGE = (4.0, 6.5)
        op = self.lc_operator(rates=(60,), gpt=4.75).run()
        self.assertEqual(sum(1 for r in op.runs_at(0) if r["kept"]), drc.RUNS_PER_RATE)
        self.assertEqual(len(op.runs_at(0)), drc.RUNS_PER_RATE)

    def test_gpt_range_must_be_min_then_max(self):
        argv = sys.argv
        sys.argv = ["dyn_rain_cal.py", "--sim", "--gpt-range", "6.5", "4"]
        try:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                drc.main()
        finally:
            sys.argv = argv

    def test_container_emptied_between_rates_when_near_the_limit(self):
        op = self.lc_operator(rates=(30, 60), container=3500.0).run()
        self.assertIn("Empty the container", op.out.getvalue())
        self.assertEqual([st["rate_mm_h"] for st in op.s.stats], [30, 60])

    def test_calibration_results_include_the_gauges_balance(self):
        op = self.lc_operator(rates=(60,))
        bal = os.path.join(drc.DATA_DIR, "balance_TEST_20261104_090000")
        os.makedirs(bal)
        final = {"round": 2, "time": "2026-11-04T09:30:00", "left_avg_ml": 6.01, "right_avg_ml": 6.12,
                 "diff_pct": 1.8, "balanced": True, "stops": "L 3.0 R 3.5"}
        with open(os.path.join(bal, "balance.json"), "w") as f:
            json.dump({"method": "load cell, 5 tips per side", "limit_pct": 5.0, "final": final,
                       "rounds": [final, final]}, f)
        op.run()
        with open(os.path.join(op.s.dir, "result.json")) as f:
            self.assertEqual(json.load(f)["balance"]["final"]["diff_pct"], 1.8)
        with open(os.path.join(op.s.dir, "summary.txt")) as f:
            self.assertIn("differ by 1.8%", f.read())

    def test_container_filled_while_setting_the_drip_is_emptied_before_run_1(self):
        # 3650 g passes the check at the rate start, but the setting tips push it over before arming
        op = self.lc_operator(rates=(60,), container=3650.0).run()
        out = op.out.getvalue()
        self.assertIn("Empty the container", out)
        self.assertLess(out.index("Empty the container"), out.index("Run 1 started"))
        self.assertEqual(sum(1 for r in op.runs_at(0) if r["kept"]), drc.RUNS_PER_RATE)

    def test_nearly_full_during_runs_asks_to_empty_and_the_run_is_replaced(self):
        # A small pretend capacity so the container fills during the runs
        self.addCleanup(setattr, drc, "LOADCELL_MAX_G", drc.LOADCELL_MAX_G)
        drc.LOADCELL_MAX_G = 1100
        op = self.lc_operator(rates=(60,))
        op.s._rate_need_g = lambda: 0
        op.run()
        self.assertIn("CONTAINER NEARLY FULL", op.out.getvalue())
        runs = op.runs_at(0)
        self.assertEqual(sum(1 for r in runs if r["kept"]), drc.RUNS_PER_RATE)
        self.assertEqual(sum(1 for r in runs if r["kept"] is False), 1)

    def test_no_empty_prompt_with_room_to_spare(self):
        op = self.lc_operator(rates=(30, 60)).run()
        self.assertNotIn("Empty the container", op.out.getvalue())

    def test_last_run_weighed_when_the_drip_is_turned_off(self):
        op = self.lc_operator(rates=(60,), stop_at_last_run=True).run()
        self.assertTrue(op.s.finished)
        self.assertEqual(sum(1 for r in op.runs_at(0) if r["kept"]), drc.RUNS_PER_RATE)
        self.assertIn("weighing it from the current reading", op.out.getvalue())


class BalanceTests(unittest.TestCase):
    """--balance: the load cell in place of the pipettors (worksheet phase 2)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        drc.DATA_DIR = self.tmp.name

    def session(self, left_g, right_g, first="L", unseen=None):
        """Runs one round: the bucket alternates sides starting with `first`, one tip a minute."""
        args = argparse.Namespace(sim=False, auto=False, speed=1.0, gauge_id="BAL")
        b = drc.BalanceSession(args)
        b.source = FakeGauge()
        water = [0.0]
        b.scale = type("S", (), {"grams_before": lambda self, t, w, g: 400.0 + water[0]})()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            b.setup()
            b.answer(first)
            order = (left_g, right_g) if first == "L" else (right_g, left_g)
            for k in range(2 * drc.BALANCE_TIPS_PER_SIDE + 2):
                if k != unseen:                # a tip the switch missed still dumps its water
                    b.on_tip(60.0 * (k + 1))
                water[0] += order[k % 2]       # this tip's water reaches the scale before the next tip
        return b, out.getvalue()

    def test_percent_difference_is_the_worksheet_formula(self):
        self.assertAlmostEqual(drc.pct_difference(5.5, 5.7), 0.2 / 5.6 * 100)

    def test_worksheet_example_1_left_light_lower_the_right_stop(self):
        ok, advice = drc.balance_advice(5.2, 5.6)
        self.assertFalse(ok)
        self.assertIn("Lower the right stop", advice)

    def test_worksheet_example_2_left_heavy_raise_the_right_stop(self):
        ok, advice = drc.balance_advice(6.6, 6.1)
        self.assertFalse(ok)
        self.assertIn("Raise the right stop", advice)

    def test_within_5_percent_but_too_small_still_needs_adjusting(self):
        ok, advice = drc.balance_advice(5.2, 5.3)
        self.assertFalse(ok)
        self.assertIn("5.5 and 6.5", advice)

    def test_balanced(self):
        ok, _ = drc.balance_advice(5.9, 6.1)
        self.assertTrue(ok)

    def test_round_measures_each_side_and_names_them(self):
        # The wxtools gauge: 5.5 g on one side, 3.9 g on the other, left filling first
        b, out = self.session(left_g=5.5, right_g=3.9, first="L")
        r = b.rounds[0]
        self.assertAlmostEqual(r["left_avg_ml"], 5.5 / drc.DENSITY, places=2)
        self.assertAlmostEqual(r["right_avg_ml"], 3.9 / drc.DENSITY, places=2)
        self.assertFalse(r["balanced"])
        self.assertIn("% difference", out)

    def test_right_filling_first_keeps_the_names_right(self):
        b, _ = self.session(left_g=5.5, right_g=3.9, first="R")
        self.assertAlmostEqual(b.rounds[0]["left_avg_ml"], 5.5 / drc.DENSITY, places=2)

    def test_missed_tip_repeats_the_round(self):
        b, out = self.session(left_g=6.0, right_g=6.1, unseen=4)
        self.assertEqual(b.rounds, [])
        self.assertIn("missed or extra tip", out)
        self.assertEqual(b.state, "side")       # asks which side is filling again

    def test_bounce_ignored(self):
        args = argparse.Namespace(sim=False, auto=False, speed=1.0, gauge_id="BAL")
        b = drc.BalanceSession(args)
        b.source = FakeGauge()
        b.scale = type("S", (), {"grams_before": lambda self, t, w, g: 400.0})()
        with contextlib.redirect_stdout(io.StringIO()):
            b.setup()
            b.answer("L")
            b.on_tip(60.0)
            b.on_tip(61.0)
        self.assertEqual(len(b.times), 1)

    def test_saved_and_picked_up_by_the_calibration(self):
        b, _ = self.session(left_g=6.0, right_g=6.1)
        with contextlib.redirect_stdout(io.StringIO()):
            b.answer("L 3.0 R 3.5")
            b.answer("q")
        found = drc.latest_balance("BAL")
        self.assertEqual(found["final"]["stops"], "L 3.0 R 3.5")
        self.assertTrue(found["final"]["balanced"])
        self.assertIsNone(drc.latest_balance("OTHER"))


class FakeSensors:
    """Laboratory sensors with fixed readings; water at 21.4 C as in the certificate example."""
    water_name = "fake bridge"

    def __init__(self, water_c=21.4):
        self.water_c = water_c

    def read(self, label=""):
        return {"label": label, "time": "2026-11-04T09:00:00", "water_c": self.water_c,
                "air_c": 22.5, "rh_pct": 37.0, "pressure_hpa": 835.2}


class CertificateDataTests(Test):
    """What the calibration records for the certificate (WMO-No. 8 Annex 6.A)."""

    def session(self, sensors=None, funnel="", rates=(60,)):
        op = LoadCellOperator(rates=rates, sensors=sensors, funnel_answer=funnel)
        self.addCleanup(op.close)
        op.run()
        with open(os.path.join(op.s.dir, "result.json")) as f:
            return op, json.load(f)

    def test_density_formula_matches_the_certificate_design(self):
        self.assertAlmostEqual(drc.water_density(21.4), 0.99791, places=5)

    def test_density_comes_from_the_water_temperature(self):
        op, res = self.session(sensors=FakeSensors(21.4))
        run = res["runs"][0]
        self.assertAlmostEqual(run["density_g_ml"], 0.99791, places=5)
        self.assertAlmostEqual(run["ml_per_tip"], 6.0 / 0.99791, places=3)
        self.assertEqual([c["label"] for c in res["conditions"]], ["start", "60 mm/h", "end"])
        self.assertEqual(res["water_sensor"], "fake bridge")

    def test_no_sensors_falls_back_to_the_fixed_density(self):
        op, res = self.session()
        self.assertEqual(res["conditions"], [])
        self.assertAlmostEqual(res["runs"][0]["density_g_ml"], drc.DENSITY)
        with open(os.path.join(op.s.dir, "summary.txt")) as f:
            self.assertIn("fixed, no water temperature", f.read())

    def test_funnel_answer_recorded_per_rate(self):
        op, res = self.session(funnel="y")
        self.assertEqual(res["funnel_storage"], {"60": True})
        with open(os.path.join(op.s.dir, "summary.txt")) as f:
            self.assertIn("water backed up at 60 mm/h", f.read())

    def test_every_run_has_times_and_intensities(self):
        op, res = self.session()
        runs = res["runs"]
        self.assertEqual(len(runs), drc.RUNS_PER_RATE)
        for r in runs:
            self.assertTrue(r["start_time"] and r["end_time"])
            # 25 tips in T seconds is 18000 / T mm/h
            self.assertAlmostEqual(r["im_mm_h"], 18000.0 / r["duration_s"], places=2)
            # every tip holds the same water and the rim was sized from these runs, so e is zero
            self.assertAlmostEqual(r["e_pct"], 0.0, places=2)
            self.assertAlmostEqual(r["ir_mm_h"], r["im_mm_h"], places=1)

    def test_error_matches_the_sizing_identity(self):
        # e = (V_S / V_run - 1) x 100, the handoff's simplification
        op, res = self.session(rates=(30, 60))
        sized = [st for st in res["rates"] if st["rate_mm_h"] == res["sizing_rate_mm_h"]][0]["ml_per_tip"]
        for r in res["runs"]:
            self.assertAlmostEqual(r["e_pct"], (sized / r["ml_per_tip"] - 1) * 100, places=1)

    def test_sht45_crc_matches_the_datasheet_example(self):
        path = os.path.join(os.path.dirname(__file__), "..", "scripts", "sensors", "cal_conditions.py")
        spec = importlib.util.spec_from_file_location("cal_conditions", path)
        cc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cc)
        self.assertEqual(cc.sht4x_crc([0xBE, 0xEF]), 0x92)


MC_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "sensors", "make_certificate.py")
mc_spec = importlib.util.spec_from_file_location("make_certificate", MC_PATH)
mc = importlib.util.module_from_spec(mc_spec)
mc_spec.loader.exec_module(mc)


class CertificateTests(Test):
    """make_certificate.py: the numbers on the certificate and when it is a DRAFT."""

    def folder(self, rates=(60,), balance=None, **kw):
        op = LoadCellOperator(rates=rates, sensors=FakeSensors(), **kw)
        self.addCleanup(op.close)
        mc.DATA_DIR = drc.DATA_DIR
        if balance is not None:
            bal = os.path.join(drc.DATA_DIR, "balance_TEST_20261104_080000")
            os.makedirs(bal)
            final = {"round": 1, "time": "2026-11-04T08:30:00", "left_avg_ml": 6.0, "right_avg_ml": 6.05,
                     "diff_pct": 0.8, "balanced": balance, "stops": ""}
            with open(os.path.join(bal, "balance.json"), "w") as f:
                json.dump({"method": "load cell, 5 tips per side", "limit_pct": 5.0, "final": final, "rounds": [final]}, f)
        op.run()
        return op.s.dir

    def complete_info(self, **measured):
        info, _ = mc.load_info()
        info.update(operator="W. Nicewonger", reviewer="A. Reviewer", special_conditions="None noted",
                    equipment=[["Net mass", "TAL220B with NAU7802", "SN 1"], ["Mass reference", "F2 set", "Cert 9"]])
        info["measured"].update(mass_step_error_pct=0.05, evaporation_g_per_h=0.4, **measured)
        with open(mc.info_path(), "w") as f:
            json.dump(info, f)
        return mc.load_info()[0]

    def test_numbers_and_draft_reasons_for_an_incomplete_session(self):
        d = mc.analyze(self.folder(), mc.load_info()[0])
        self.assertEqual(len(d["stats"]), 1)
        self.assertAlmostEqual(d["stats"][0]["e"], 0.0, places=6)          # sized here, every tip equal
        reasons = " | ".join(d["draft"])
        for text in ("rim diameter not measured", "evaporation not measured", "step error",
                     "no bucket balance", "placeholders", "requires at least 5"):
            self.assertIn(text, reasons)
        self.assertNotIn("water temperature not measured", reasons)       # FakeSensors gives 21.4 C

    def test_complete_session_is_numbered_once(self):
        folder = self.folder(rates=(12, 30, 60, 120, 170), balance=True)
        info = self.complete_info(rim_diameter_mm=200.0, rim_diameter_uncertainty_mm=0.05)
        d = mc.analyze(folder, info)
        self.assertEqual(d["draft"], [])
        first = mc.certificate_number(folder, info, False)
        self.assertEqual(first, "3DPAWS-RG-0001")
        self.assertEqual(mc.certificate_number(folder, mc.load_info()[0], False), first)     # rebuild keeps it
        self.assertEqual(mc.load_info()[0]["next_certificate_number"], 2)

    def test_draft_is_not_numbered(self):
        folder = self.folder()
        self.assertEqual(mc.certificate_number(folder, mc.load_info()[0], True), "DRAFT (not numbered)")
        self.assertFalse(os.path.exists(os.path.join(folder, "certificate.json")))

    def test_measured_rim_shifts_every_error_by_the_area_ratio(self):
        folder = self.folder()
        design = mc.analyze(folder, mc.load_info()[0])
        d_design = 2 * design["radius"]
        info = self.complete_info(rim_diameter_mm=d_design * 1.01)
        d = mc.analyze(folder, info)
        self.assertAlmostEqual(d["stats"][0]["e"], (1.01 ** 2 - 1) * 100, places=3)

    def test_unbalanced_bucket_keeps_it_a_draft(self):
        d = mc.analyze(self.folder(balance=False), mc.load_info()[0])
        self.assertTrue(any("bucket balance outside" in x for x in d["draft"]))

    def test_flow_steadiness_ignores_unequal_bucket_sides(self):
        times = {k: 12.0 * (k // 2) * 2 + (14.4 if k % 2 else 0.0) for k in range(30)}   # sides 14.4 s and 9.6 s
        self.assertAlmostEqual(mc.flow_steadiness_pct(times, 0, 26), 0.0, places=9)

    def test_fit_matches_a_known_quadratic(self):
        xs = [10.0, 30.0, 60.0, 120.0, 170.0]
        coef = mc.polyfit(xs, [0.1 + 0.97 * x + 4e-4 * x * x for x in xs], 2)
        for got, want in zip(coef, [4e-4, 0.97, 0.1]):
            self.assertAlmostEqual(got, want, places=9)

    def test_pdf_builds(self):
        try:
            import reportlab, matplotlib  # noqa: F401
        except ImportError:
            self.skipTest("reportlab and matplotlib are not installed here")
        folder = self.folder(rates=(12, 30, 60, 120, 170), balance=True)
        d = mc.analyze(folder, mc.load_info()[0])
        out = os.path.join(folder, "certificate.pdf")
        mc.build_pdf(d, out, "DRAFT (not numbered)")
        self.assertGreater(os.path.getsize(out), 20000)


class ScaleCalibrationTests(unittest.TestCase):

    def setUp(self):
        path = os.path.join(os.path.dirname(__file__), "..", "scripts", "sensors", "nau7802.py")
        spec = importlib.util.spec_from_file_location("nau7802", path)
        self.nau = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.nau)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "loadcell_cal.json")

    class FakeCell:
        """Raw counts: 12000 with nothing on, 430 counts per gram, a little scatter."""
        def __init__(self, readings):
            self.readings, self.cal = list(readings), None

        def raw_settled(self, seconds=0):
            return self.readings.pop(0), 40.0

        def grams_now(self):
            return 1000.0

    def test_signed_24_bit(self):
        self.assertEqual(self.nau.to_signed24(0x7F, 0xFF, 0xFF), 8388607)
        self.assertEqual(self.nau.to_signed24(0xFF, 0xFF, 0xFF), -1)
        self.assertEqual(self.nau.to_signed24(0x80, 0x00, 0x00), -8388608)

    def test_calibration_counts_per_gram_and_saved(self):
        cell = self.FakeCell([12000.0, 12000.0 + 430 * 1000])
        answers = iter(["", "1000"])
        cal = self.nau.calibrate(cell, self.path, ask=lambda _: next(answers), say=lambda _: None)
        self.assertAlmostEqual(cal["counts_per_g"], 430.0)
        self.assertAlmostEqual(self.nau.load_cal(self.path)["zero"], 12000.0)

    def test_no_change_with_the_weight_on_starts_over(self):
        cell = self.FakeCell([12000.0, 12000.0, 12000.0, 12000.0 + 430 * 500])
        answers = iter(["", "1000", "", "500"])
        cal = self.nau.calibrate(cell, self.path, ask=lambda _: next(answers), say=lambda _: None)
        self.assertAlmostEqual(cal["counts_per_g"], 430.0)

    def test_saved_calibration_reused_unless_c(self):
        self.nau.save_cal(self.path, {"zero": 1.0, "counts_per_g": 430.0, "mass_g": 1000, "date": "2026-10-27"})
        cell = self.FakeCell([])
        self.nau.use_or_calibrate(cell, self.path, ask=lambda _: "", say=lambda _: None)
        self.assertEqual(cell.cal["counts_per_g"], 430.0)


class ResultTests(Test):

    def test_side_imbalance_does_not_cancel_when_sides_swap(self):
        op, s = self.bare_session()
        s.runs = [dict(make_run(n), kept=True, g_per_tip=6.0, ml_per_tip=6.0 / drc.DENSITY, side_ratio=sr)
                  for n, sr in ((1, 1.02), (2, 0.98), (3, 1.02))]
        self.assertAlmostEqual(s.rate_stats(0)["side_imbalance_pct"], 2.0, places=6)

    def test_rate_with_every_run_discarded_does_not_crash(self):
        op, s = self.bare_session()
        s.rates = [30, 60]
        s.runs = [dict(make_run(n), kept=False) for n in (1, 2, 3)]
        s.runs += [dict(make_run(n), rate_index=1, kept=True, g_per_tip=6.0, ml_per_tip=6.0 / drc.DENSITY)
                   for n in (1, 2, 3)]
        with contextlib.redirect_stdout(op.out):
            s.results()
        self.assertEqual([st["rate_mm_h"] for st in s.stats], [60])
        self.assertIn("no valid runs", op.out.getvalue())

    def test_ideal_band_marked_in_final_table(self):
        op, s = self.bare_session()
        s.rates = [12, 200]
        s.runs = [dict(make_run(n), rate_index=ri, kept=True, g_per_tip=g, ml_per_tip=g / drc.DENSITY)
                  for ri, g in ((0, 6.1), (1, 6.8)) for n in (1, 2, 3)]
        with contextlib.redirect_stdout(op.out):
            s.results()
        lines = [l for l in op.out.getvalue().splitlines() if l.strip().startswith(("12 ", "200 "))]
        self.assertNotIn("outside ideal", lines[0])
        self.assertIn("outside ideal", lines[1])

    def test_negative_rates_rejected(self):
        argv = sys.argv
        sys.argv = ["dyn_rain_cal.py", "--sim", "--rates", "0", "30"]
        try:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                drc.main()
        finally:
            sys.argv = argv


if __name__ == "__main__":
    unittest.main()
