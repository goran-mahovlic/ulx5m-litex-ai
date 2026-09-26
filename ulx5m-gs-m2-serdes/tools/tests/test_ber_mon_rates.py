import os, sys, types, unittest
sys.modules.setdefault('serial', types.ModuleType('serial'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ber_parse import FIELDS, parse
from ber_mon import summary

def mk(**kw):
    return parse('B ' + ' '.join(('%0*X' % (b // 4, kw.get(n, 0) & ((1 << b) - 1))) for n, b in FIELDS))

class R(unittest.TestCase):
    def test_300s_run_across_t25_wrap(self):
        L = [mk(t25=i * 25_000_000, tcnt=i * 3_750_000, rcnt=i * 3_750_000, words=i * 3_750_000,
                pwords=i * 3_750_000, flg=0x80, pflg=0x80, pframes=i) for i in range(301)]
        r = summary(L[0], L[-1], L)
        self.assertAlmostEqual(r['secs'], 300.0)
        self.assertAlmostEqual(r['gs_tx_rate_bps'], 300e6)
        self.assertAlmostEqual(r['m2_tx_rate_bps'], 300e6)
        self.assertEqual(r['m2_to_gs']['words'], 300 * 3_750_000)

if __name__ == '__main__':
    unittest.main()
