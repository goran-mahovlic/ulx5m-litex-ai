import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lab'))
import ab_table as A


def run(words_mg, errb_mg, words_gm, errb_gm):
    return {'secs': 60, 'm2_to_gs': {'words': words_mg, 'errb': errb_mg, 'code_err': 0, 'loss': 0, 'synced': 1},
            'gs_to_m2': {'words': words_gm, 'errb': errb_gm, 'code_err': 0, 'loss': 0, 'synced': 1}}


class AB(unittest.TestCase):
    def test_label_of(self):
        # <label>_r<k>.json -> label (repeat rule: >= 3 loads per point, TUNING_5G.md §3)
        self.assertEqual(A.label_of('/x/e1_tdr0_r2.json'), 'e1_tdr0')
        self.assertEqual(A.label_of('e2_g0_p16_r10.json'), 'e2_g0_p16')

    def test_is_run(self):
        # abrun.sh writes <label>_r<k>.health_<board>.json next to the run; a *_r*.json glob catches both
        self.assertTrue(A.is_run('/x/e1_det0_r1.json'))
        self.assertFalse(A.is_run('/x/e1_det0_r1.health_gs.json'))

    def test_ber_40_bits_per_word(self):
        self.assertEqual(A.ber({'words': 10, 'errb': 4}), 4 / 400.0)
        self.assertEqual(A.ber({'words': 0, 'errb': 0}), 0.5)      # no sync = as bad as it gets

    def test_impossible_ber_is_capped(self):
        # 5 Gb/s: m2 counters come back over a link with ~10 % BER and can be corrupted (seen: BER 1.92).
        # ber_robust from ber_mon.py is NOT used: on the boards it also returned a false 1.7e-4 (e2_g1_p0).
        self.assertEqual(A.ber({'words': 10, 'errb': 4000, 'ber_robust': 1e-3}), 0.5)
        self.assertEqual(A.ber({'words': 10, 'errb': 4, 'ber_robust': 1e-9}), 4 / 400.0)

    def test_impossible_word_count_is_invalid(self):
        # e2_g2_p0 (5 G): 1.3e11 words in 60 s = corrupted back-channel counter (max 62.5e6 words/s) -> BER 0.5
        r = run(10, 0, 1.33e11, 4000)
        r['gs_tx_rate_bps'] = 5e9
        self.assertEqual(A.run_ber(r, 'gs_to_m2'), 0.5)
        self.assertEqual(A.run_ber(r, 'm2_to_gs'), 0.0)
        # the counters start at the clear, a few s before the first status line: 64 s of words in a 60 s run is fine
        ok = run(64 * 31.25e6, 0, 64 * 31.25e6, 0); ok['gs_tx_rate_bps'] = 2.5e9
        self.assertEqual(A.run_ber(ok, 'gs_to_m2'), 0.0)

    def test_median(self):
        rs = [run(100, 4, 100, 0), run(100, 40, 100, 0), run(100, 0, 100, 400)]
        m = A.point(rs)
        self.assertEqual(m['n'], 3)
        self.assertEqual(m['m2_to_gs'], 4 / 4000.0)                    # median of 0, 4, 40 errors
        self.assertEqual(m['gs_to_m2'], 0.0)
        self.assertEqual(m['gs_to_m2_max'], 400 / 4000.0)

    def test_zero_errors_bound(self):
        # all runs clean: report the 95 % upper bound 3/N over the pooled bits
        m = A.point([run(1000, 0, 1000, 0)] * 3)
        self.assertEqual(m['m2_to_gs'], 0.0)
        self.assertAlmostEqual(m['m2_to_gs_ub95'], 3.0 / (3 * 1000 * 40))


if __name__ == '__main__':
    unittest.main()
