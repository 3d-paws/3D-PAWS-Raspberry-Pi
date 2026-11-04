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
                 sides=(1.0, 1.0), bounces=(), side_g=None):
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
                self.fed = tip + 1
                if tip not in self.missed:
                    s.on_tip(t)
                if tip in self.bounces:
                    s.on_tip(t + 2.4)
        raise AssertionError("Session did not finish")


def make_run(n=1, off=0.0, irregular=0, bucket="A"):
    return {"rate_index": 0, "run": n, "bucket": bucket, "off_target_pct": off, "irregular": irregular,
            "tips_per_min": 5.0, "kept": None, "side_ratio": 1.0}


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

    def test_no_empty_prompt_with_room_to_spare(self):
        op = self.lc_operator(rates=(30, 60)).run()
        self.assertNotIn("Empty the container", op.out.getvalue())

    def test_last_run_weighed_when_the_drip_is_turned_off(self):
        op = self.lc_operator(rates=(60,), stop_at_last_run=True).run()
        self.assertTrue(op.s.finished)
        self.assertEqual(sum(1 for r in op.runs_at(0) if r["kept"]), drc.RUNS_PER_RATE)
        self.assertIn("weighing it from the current reading", op.out.getvalue())


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
