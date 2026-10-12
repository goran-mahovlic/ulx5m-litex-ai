import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lab'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import ber_long as L


def snap(t, w, e, pw, pe):
    return {'t': t, 'words': w, 'errb': e, 'pwords': pw, 'perrb': pe}


class Segments(unittest.TestCase):
    def test_interval_ber_from_cumulative(self):
        s = [snap(0, 0, 0, 0, 0), snap(300, 1000, 40, 2000, 0), snap(600, 3000, 40, 4000, 8)]
        seg = L.segments(s)
        self.assertEqual(len(seg), 2)
        self.assertAlmostEqual(seg[0]['m2_to_gs'], 40 / (1000 * 40.0))
        self.assertEqual(seg[0]['gs_to_m2'], 0.0)
        self.assertEqual(seg[1]['m2_to_gs'], 0.0)
        self.assertAlmostEqual(seg[1]['gs_to_m2'], 8 / (2000 * 40.0))
        self.assertFalse(seg[1]['restart'])

    def test_errb_32bit_wrap(self):
        s = [snap(0, 0, 0xFFFFFFF0, 0, 0), snap(1, 100, 0x10, 100, 0)]
        self.assertAlmostEqual(L.segments(s)[0]['m2_to_gs'], 0x20 / (100 * 40.0))

    def test_word_counter_going_back_is_a_restart_counted_from_zero(self):
        s = [snap(0, 0, 0, 0, 0), snap(300, 5000, 0, 5000, 0), snap(600, 100, 4, 9000, 0)]
        seg = L.segments(s)
        self.assertTrue(seg[1]['restart'])
        self.assertEqual(seg[1]['restarts'], ['m2_to_gs'])
        self.assertAlmostEqual(seg[1]['m2_to_gs'], 4 / (100 * 40.0))   # words since the restart


class Total(unittest.TestCase):
    def test_total_sums_intervals_from_a_nonzero_baseline(self):
        s = [snap(0, 500, 7, 500, 9), snap(3600, 10 ** 11 + 500, 7, 10 ** 11 + 500, 409)]
        t = L.total(s)
        self.assertEqual(t['m2_to_gs']['ber'], 0.0)
        self.assertAlmostEqual(t['m2_to_gs']['ber_95_upper'], 3.0 / (10 ** 11 * 40))
        self.assertAlmostEqual(t['gs_to_m2']['ber'], 400 / (10 ** 11 * 40.0))
        self.assertEqual(t['secs'], 3600)
        self.assertFalse(t['restart'])

    def test_total_across_a_restart(self):
        s = [snap(0, 0, 0, 0, 0), snap(1, 50, 2, 50, 0), snap(2, 10, 1, 60, 0)]
        t = L.total(s)
        self.assertEqual(t['restarts']['m2_to_gs'], 1); self.assertEqual(t['restarts']['gs_to_m2'], 0)
        self.assertEqual(t['m2_to_gs']['words'], 60); self.assertEqual(t['m2_to_gs']['errb'], 3)


class Plausible(unittest.TestCase):
    def line(self, t25, w, pw, tcnt):
        return {'t25': t25, 'words': w, 'pwords': pw, 'tcnt': tcnt}

    def test_picks_last_line_whose_both_counters_advance_plausibly(self):
        a = self.line(0, 1000, 1000, 0); b = self.line(25_000_000, 1000 + 31_000_000, 1000 + 31_000_000, 31_250_000)
        c = self.line(50_000_000, 1000 + 62_000_000, 2 ** 40, 62_500_000)     # corrupted pwords in the back channel
        self.assertIs(L.plausible([a, b, c]), b)

    def test_none_when_no_consecutive_pair(self):
        self.assertIsNone(L.plausible([self.line(0, 1, 1, 0)]))


if __name__ == '__main__':
    unittest.main()
