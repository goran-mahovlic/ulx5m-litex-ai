"""TASK-5559 K2: Clopper-Pearson lower bound and Fisher test (numbers from CALIBRATION_OPTIONS_20261017_v2 §2.1)."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab'))
import k2_table as T  # noqa: E402


class K2Stats(unittest.TestCase):
    def test_cp_lower_matches_plan(self):
        self.assertAlmostEqual(T.lbeta_cdf_lower(28, 30), 0.805, places=3)
        self.assertAlmostEqual(T.lbeta_cdf_lower(15, 15), 0.819, places=3)
        self.assertAlmostEqual(T.lbeta_cdf_lower(16, 20), 0.601, places=2)
        self.assertEqual(T.lbeta_cdf_lower(0, 20), 0.0)

    def test_fisher(self):
        self.assertLess(T.fisher_greater(16, 20, 7, 20), 0.05)      # 0.8 vs 0.35 over 20 each: significant
        self.assertGreater(T.fisher_greater(9, 20, 7, 20), 0.2)
        self.assertAlmostEqual(T.fisher_greater(0, 5, 0, 5), 1.0)


if __name__ == '__main__':
    unittest.main()
