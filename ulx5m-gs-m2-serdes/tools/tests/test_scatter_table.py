import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lab'))
import scatter_table as S


class Spearman(unittest.TestCase):
    def test_monotone(self):
        self.assertAlmostEqual(S.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(S.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)

    def test_ties_and_constant(self):
        self.assertIsNone(S.spearman([5, 5, 5], [1, 2, 3]))          # constant field -> no correlation defined
        self.assertAlmostEqual(S.spearman([1, 1, 2], [1, 1, 2]), 1.0)


class Row(unittest.TestCase):
    def test_row_from_load(self):
        start = {'m2': {'fields': {'RX_OFFSET': 7, 'PLL_CAP_FT': 509}, 'phase_acc': [10, 12], 'afe_offset': 8, 'raw': {'0x0B': 5}},
                 'gs': {'fields': {'RX_OFFSET': 1, 'PLL_CAP_FT': 499}, 'phase_acc': [3], 'afe_offset': 8, 'raw': {'0x0B': 6}}}
        ber = {'gs_to_m2': {'errb': 40, 'words': 1000}, 'm2_to_gs': {'errb': 0, 'words': 1000}}
        r = S.row(start, ber)
        self.assertEqual(r['m2.RX_OFFSET'], 7); self.assertEqual(r['gs.PLL_CAP_FT'], 499)
        self.assertEqual(r['m2.phase_acc'], 11); self.assertEqual(r['gs.raw0x0B'], 6)
        self.assertAlmostEqual(r['ber_gs_to_m2'], 1e-3); self.assertEqual(r['ber_m2_to_gs'], 0.0)

    def test_nouart(self):
        r = S.row({'m2': {'fields': {}}, 'gs': {'fields': {}}}, None)
        self.assertIsNone(r['ber_gs_to_m2'])


if __name__ == '__main__':
    unittest.main()
