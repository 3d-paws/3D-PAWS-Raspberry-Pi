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
        args = argparse.Namespace(sim=False, auto=False, speed=1.0, gauge_id="TEST", rates=list(rates))
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
