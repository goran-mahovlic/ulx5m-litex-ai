import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lab'))
from sweep_table import row

def side(words, errb, ber, ub):
    return {'words': words, 'errb': errb, 'ber': ber, 'ber_95_upper': ub}

class T(unittest.TestCase):
    def test_zero_errors_row(self):
        r = {'gs_tx_rate_bps': 300e6, 'm2_tx_rate_bps': 300e6, 'secs': 300.4,
             'gs_to_m2': side(1125251037, 0, 0.0, 3 / 4.5e10), 'm2_to_gs': side(1125251196, 0, 0.0, 3 / 4.5e10)}
        s = row('sweep_od4_s1', r)
        self.assertIn('| 300.0 / 300.0 |', s)
        self.assertIn('0 (< 6.7e-11)', s)
        self.assertIn('| 300 s |', s)

    def test_errors_and_no_data(self):
        r = {'gs_tx_rate_bps': 2.5e9, 'm2_tx_rate_bps': 0, 'secs': 120,
             'gs_to_m2': side(0, 0, None, None), 'm2_to_gs': side(10**9, 40, 1e-9, None)}
        s = row('x', r)
        self.assertIn('no data', s)
        self.assertIn('1.00e-09', s)

if __name__ == '__main__':
    unittest.main()
