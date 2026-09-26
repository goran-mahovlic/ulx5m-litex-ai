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

    def test_robust_ber_drops_corrupted_back_channel_frames(self):
        # at 5 Gb/s the m2 counters reach gs over a link with ~10 % BER: single status lines carry garbage
        # (TASK-5066 saw gs->m2 BER 1.92). The robust BER only sums plausible 1 s deltas.
        L = [mk(t25=i * 25_000_000, tcnt=i * 1_000_000, words=i * 1_000_000, errb=i * 40,
                pwords=i * 1_000_000, perrb=i * 400, pframes=i) for i in range(11)]
        L[5] = mk(t25=5 * 25_000_000, tcnt=5_000_000, words=5_000_000, errb=200,
                  pwords=0xFFFF_FFFF_FFFF, perrb=0xFFFF_FFF0, pframes=5)
        r = summary(L[0], L[-1], L)
        self.assertAlmostEqual(r['gs_to_m2']['ber_robust'], 400 / 40e6)
        self.assertEqual(r['gs_to_m2']['robust_secs'], 8)          # 2 of 10 deltas touch the bad line
        self.assertAlmostEqual(r['m2_to_gs']['ber_robust'], 40 / 40e6)
        self.assertEqual(r['m2_to_gs']['robust_secs'], 10)

if __name__ == '__main__':
    unittest.main()
