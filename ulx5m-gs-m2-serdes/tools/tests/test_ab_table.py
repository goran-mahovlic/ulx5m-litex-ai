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

    def test_sync_fraction(self):
        # 5 G: BER is counted only while synced (1e-5 ... 0.5 of the time), so a point is ranked by BOTH the BER and
        # the synced share of the word clock (TASK-5070: e2_g0_p24 0.43 vs PROFILE 2 base e2_g0_p12 6e-4)
        r = run(0.25 * 60 * 62.5e6, 0, 60 * 62.5e6, 0); r['gs_tx_rate_bps'] = 5e9
        self.assertAlmostEqual(A.run_sync(r, 'm2_to_gs'), 0.25)
        self.assertAlmostEqual(A.run_sync(r, 'gs_to_m2'), 1.0)
        self.assertIsNone(A.run_sync(run(10, 0, 10, 0), 'gs_to_m2'))    # no rate recorded -> unknown
        bad = run(10, 0, 1.33e11, 0); bad['gs_tx_rate_bps'] = 5e9
        self.assertIsNone(A.run_sync(bad, 'gs_to_m2'))                  # corrupted counter -> unknown, not > 1
        m = A.point([r, dict(r, gs_tx_rate_bps=5e9), bad])
        self.assertAlmostEqual(m['m2_to_gs_sync'], 0.25)                # median over known runs only
        self.assertAlmostEqual(m['gs_to_m2_sync'], 1.0)
        # a corrupted counter is not pooled into the bit count either (TASK-5073 t73b r3: 6.2e14 bits in 60 s)
        self.assertEqual(m['gs_to_m2_bits'], 2 * 40 * 60 * 62.5e6)

    def test_rank_by_sync_then_ber(self):
        # TASK-5073: points are ranked by median synced share gs->m2 (desc) first, BER gs->m2 (asc) second
        def pt(sync, b):
            return {'gs_to_m2_sync': sync, 'gs_to_m2': b}
        pts = {'e': pt(1e-3, 1e-2), 'a': pt(0.4, 5e-2), 'b': pt(0.4, 1e-2), 'x': pt(None, 1e-3)}
        self.assertEqual(A.rank(pts), ['b', 'a', 'e', 'x'])              # unknown sync goes last

    def test_run_rows_per_load(self):
        # one row per load (label, k, BER and synced share per direction) for the 5 points x 3 loads table
        r = run(0.25 * 60 * 62.5e6, 0, 60 * 62.5e6, 4 * 40); r['gs_tx_rate_bps'] = 5e9
        rows = A.run_rows({'p': [r]})
        self.assertEqual(len(rows), 1)
        lab, k, b_gm, s_gm, b_mg, s_mg = rows[0]
        self.assertEqual((lab, k), ('p', 1))
        self.assertAlmostEqual(s_mg, 0.25)
        self.assertAlmostEqual(b_gm, 4 * 40 / (40.0 * 60 * 62.5e6))


if __name__ == '__main__':
    unittest.main()
