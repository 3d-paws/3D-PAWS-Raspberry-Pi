#!/usr/bin/env python3
"""
Tests for scripts/sensors/drivers/ and scripts/sensors/shield_test.py, with a fake I2C bus that answers
like each chip. Run from the project folder (no hardware):
  python3 -m unittest tests/test_shield.py -v
"""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "sensors"))
import drivers                                   # noqa: E402
from drivers import i2c_util, bmp390, mcp9808   # noqa: E402
import shield_test                               # noqa: E402


def sensirion(t_word, rh_word):
    out = []
    for w in (t_word, rh_word):
        b = [w >> 8, w & 0xFF]
        out += b + [i2c_util.crc8(b)]
    return out


class FakeBus:
    """SHT45 at 0x44, SHT31 at 0x45, MCP9808 at 0x18, BMP581 at 0x47, BMP390 at 0x77 (by default).
    `sht` says which Sensirion family is at each address; each answers only its own commands."""

    def __init__(self, temps=None, present=(0x44, 0x45, 0x18, 0x47, 0x77), sht=None):
        self.t = {0x44: 21.5, 0x45: 21.7, 0x18: 21.25, 0x47: 21.6, 0x77: 21.5}
        self.t.update(temps or {})
        self.sht = sht or {0x44: "sht4x", 0x45: "sht3x"}
        self.present = set(present)
        self.pending = {}
        self.corrupt = False
        # BMP390 coefficients chosen so that t = (adc_t - T1 * 256) * T2 / 2^30 and p = P5 * 8 + adc_p / 1024
        self.calib = struct.pack("<HHbhhbbHHbbhbb", 0x6000, 0x4000, 0, 2 ** 14 + 2 ** 10, 2 ** 14, 0, 0,
                                 10000, 0, 0, 0, 0, 0, 0)

    def _here(self, a):
        if a not in self.present:
            raise OSError(121, "Remote I/O error")

    def write_byte(self, a, v):
        self._here(a)
        self.pending.pop(a, None)
        if self.sht.get(a) == "sht4x" and v == 0xFD:
            self.pending[a] = sensirion(round((self.t[a] + 45) / 175 * 65535), round((40.0 + 6) / 125 * 65535))
        elif self.sht.get(a) == "sht4x" and v == 0x89:
            self.pending[a] = sensirion(0x1234, 0x5678)                       # serial number
        elif self.sht.get(a) == "sht3x":
            pass                                                              # half a 16-bit command: no reply

    def write_byte_data(self, a, reg, v):
        self._here(a)
        self.pending.pop(a, None)
        if self.sht.get(a) == "sht4x":
            raise OSError(121, "Remote I/O error")                            # 0xF3 / 0x24 aren't SHT4x commands
        if self.sht.get(a) == "sht3x" and reg == 0x24:
            self.pending[a] = sensirion(round((self.t[a] + 45) / 175 * 65535), round(42.0 / 100 * 65535))
        elif self.sht.get(a) == "sht3x" and (reg, v) == (0xF3, 0x2D):
            self.pending[a] = sensirion(0x8010, 0)[:3]                        # status word

    def read_raw(self, a, n):
        self._here(a)
        if a not in self.pending:
            raise OSError(121, "Remote I/O error")                            # nothing to send: NACK
        data = self.pending.pop(a)
        if self.corrupt:
            data[2] ^= 0xFF
        return data[:n]

    def read_byte_data(self, a, reg):
        self._here(a)
        if a == 0x47 and reg == 0x01:
            return 0x50
        if a == 0x77:
            return {0x00: 0x60, 0x03: 0x70}[reg]
        return 0

    def read_i2c_block_data(self, a, reg, n):
        self._here(a)
        if a == 0x18:
            raw = int(round(self.t[a] * 16)) & 0x1FFF
            return {0x05: [raw >> 8, raw & 0xFF], 0x06: [0x00, 0x54], 0x07: [0x04, 0x00]}[reg]
        if a == 0x47:
            v = int(round(self.t[a] * 65536)) & 0xFFFFFF if reg == 0x1D else int(84591.0 * 64)
            return [v & 0xFF, (v >> 8) & 0xFF, v >> 16]
        if a == 0x77:
            if reg == 0x31:
                return list(self.calib)
            adc_t = int(round(0x6000 * 256 + self.t[a] * 2 ** 30 / 0x4000))
            adc_p = (84591 - 80000) * 1024
            return [adc_p & 0xFF, (adc_p >> 8) & 0xFF, adc_p >> 16, adc_t & 0xFF, (adc_t >> 8) & 0xFF, adc_t >> 16]
        raise OSError(121, "Remote I/O error")


class FakeBusTest(unittest.TestCase):
    """Drivers read the fake bus's Sensirion replies instead of a real I2C read."""

    def setUp(self):
        self.bus = FakeBus()
        self.orig = i2c_util.read_bytes
        i2c_util.read_bytes = lambda bus, a, n: bus.read_raw(a, n)

    def tearDown(self):
        i2c_util.read_bytes = self.orig


class DriverTests(FakeBusTest):

    def test_sht45(self):
        r = drivers.SHT45(self.bus).read()
        self.assertAlmostEqual(r["temp_c"], 21.5, places=2)
        self.assertAlmostEqual(r["rh_pct"], 40.0, places=2)

    def test_sht31_formula_differs_from_sht45_for_humidity(self):
        r = drivers.SHT31(self.bus, 0x45).read()
        self.assertAlmostEqual(r["temp_c"], 21.7, places=2)
        self.assertAlmostEqual(r["rh_pct"], 42.0, places=2)

    def test_sht31_and_sht45_told_apart_at_0x44(self):
        sht31_here = FakeBus(sht={0x44: "sht3x"}, present=(0x44,))
        self.assertEqual(i2c_util.sht_family(sht31_here, 0x44), "sht3x")
        self.assertEqual(i2c_util.sht_family(self.bus, 0x44), "sht4x")
        self.assertAlmostEqual(drivers.SHT31(sht31_here, 0x44).read()["temp_c"], 21.5, places=2)
        with self.assertRaisesRegex(IOError, "an SHT3x answered"):
            drivers.SHT45(sht31_here, 0x44)
        with self.assertRaisesRegex(IOError, "an SHT4x answered"):
            drivers.SHT31(self.bus, 0x44)

    def test_crc_error_is_an_ioerror(self):
        s = drivers.SHT45(self.bus)
        self.bus.corrupt = True
        with self.assertRaises(IOError):
            s.read()

    def test_crc_matches_the_sensirion_datasheet_example(self):
        self.assertEqual(i2c_util.crc8([0xBE, 0xEF]), 0x92)

    def test_mcp9808_positive_and_negative(self):
        self.assertAlmostEqual(drivers.MCP9808(self.bus).read()["temp_c"], 21.25)
        self.assertAlmostEqual(mcp9808.to_celsius(0x1F, 0xF0), -1.0)          # sign bit set
        self.assertAlmostEqual(mcp9808.to_celsius(0xE1, 0x94), 25.25)         # alert flags ignored

    def test_bmp581(self):
        r = drivers.BMP581(self.bus).read()
        self.assertAlmostEqual(r["temp_c"], 21.6, places=3)
        self.assertAlmostEqual(r["pressure_hpa"], 845.91, places=2)

    def test_bmp390_compensation(self):
        r = drivers.BMP390(self.bus).read()
        self.assertAlmostEqual(r["temp_c"], 21.5, places=3)
        self.assertAlmostEqual(r["pressure_hpa"], 845.91, places=2)

    def test_missing_chip_raises(self):
        bus = FakeBus(present=())
        for cls in drivers.MODELS.values():
            with self.assertRaises((IOError, OSError)):
                cls(bus, cls.ADDRESSES[0])


class ComparisonTests(FakeBusTest):

    def test_differences_from_the_reference(self):
        c = shield_test.Comparison(self.bus, shield_test.DEFAULT)
        values = c.read_all()
        self.assertEqual(c.ref, "sht45@0x44")
        self.assertEqual(c.refs()["pressure_hpa"], "bmp390@0x77")       # the SHT45 has no pressure
        self.assertAlmostEqual(c.stats[("sht31@0x45", "temp_c")].mean(), 0.2, places=2)
        self.assertAlmostEqual(c.stats[("mcp9808@0x18", "temp_c")].mean(), -0.25, places=2)
        table = c.table(values, shield_test.dt.datetime(2026, 11, 6, 9, 0))
        self.assertIn("sht45@0x44 (ref)", table)
        self.assertIn("+0.20", table)

    def test_choosing_the_reference(self):
        c = shield_test.Comparison(self.bus, shield_test.DEFAULT, ref="bmp581@0x47")
        c.read_all()
        self.assertEqual(c.refs()["temp_c"], "bmp581@0x47")
        self.assertAlmostEqual(c.stats[("sht45@0x44", "temp_c")].mean(), -0.1, places=2)

    def test_missing_sensor_is_listed_not_fatal(self):
        bus = FakeBus(present=(0x44, 0x47))
        c = shield_test.Comparison(bus, shield_test.DEFAULT)
        self.assertEqual([label for label, _ in c.sensors], ["sht45@0x44", "bmp581@0x47"])
        self.assertEqual(len(c.missing), 3)

    def test_sht31_alone_at_0x44_is_found_by_the_default_set(self):
        bus = FakeBus(sht={0x44: "sht3x"}, present=(0x44, 0x47))
        c = shield_test.Comparison(bus, shield_test.DEFAULT)
        self.assertEqual([label for label, _ in c.sensors], ["sht31@0x44", "bmp581@0x47"])
        self.assertTrue(any(m.startswith("sht45") for m in c.missing))

    def test_both_sht_models_with_the_sht31_at_0x45(self):
        c = shield_test.Comparison(self.bus, ["sht45", "sht31"])
        self.assertEqual([label for label, _ in c.sensors], ["sht45@0x44", "sht31@0x45"])

    def test_running_mean_and_sd(self):
        st = shield_test.Stats()
        for x in (0.1, 0.3, 0.2):
            st.add(x)
        self.assertAlmostEqual(st.mean(), 0.2)
        self.assertAlmostEqual(st.sd(), 0.1)

    def test_labels_and_bad_specs(self):
        self.assertEqual(shield_test.parse_spec("sht31@0x45=outside"), ("sht31", 0x45, "outside"))
        self.assertEqual(shield_test.parse_spec("sht45"), ("sht45", None, None))
        with self.assertRaises(ValueError):
            shield_test.parse_spec("sht45@0x50")
        with self.assertRaises(ValueError):
            shield_test.parse_spec("bme999@0x77")


if __name__ == "__main__":
    unittest.main()
