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

    def test_ber_40_bits_per_word(self):
        self.assertEqual(A.ber({'words': 10, 'errb': 4}), 4 / 400.0)
        self.assertEqual(A.ber({'words': 0, 'errb': 0}), 0.5)      # no sync = as bad as it gets

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
