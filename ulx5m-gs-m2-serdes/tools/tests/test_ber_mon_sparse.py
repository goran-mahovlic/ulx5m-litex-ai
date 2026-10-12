import os, sys, types, unittest
sys.modules.setdefault('serial', types.ModuleType('serial'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ber_parse import FIELDS, parse
from ber_mon import sparse_summary, clear_confirmed

def mk(**kw):
    return parse('B ' + ' '.join(('%0*X' % (b // 4, kw.get(n, 0) & ((1 << b) - 1))) for n, b in FIELDS))

def line(i, words_s=31_250_000, errb=0, perrb=0):
    return mk(t25=i * 25_000_000, tcnt=i * words_s, rcnt=i * words_s, words=i * words_s, pwords=i * words_s,
              errb=errb, perrb=perrb, flg=0x80, pflg=0x80, pframes=i)

class Sparse(unittest.TestCase):
    """TASK-5483: gs UART drops out for seconds at a time; the fabric counters are cumulative since the clear,
    so BER needs one line right after the clear and one at the end, not a continuous stream."""

    def test_ber_from_cumulative_counters_and_wall_clock(self):
        first, tail = line(1), [line(300, errb=125, perrb=12), line(301, errb=125, perrb=12), line(302, errb=125, perrb=12)]
        r = sparse_summary(first, tail, 301.0)
        self.assertEqual(r['secs'], 301.0)                       # t25 wraps every 171.8 s -> wall clock
        self.assertEqual(r['mode'], 'sparse')
        self.assertEqual(r['m2_to_gs']['words'], 302 * 31_250_000)
        self.assertAlmostEqual(r['m2_to_gs']['ber'], 125 / (40.0 * 302 * 31_250_000))
        self.assertAlmostEqual(r['gs_to_m2']['ber'], 12 / (40.0 * 302 * 31_250_000))
        self.assertAlmostEqual(r['gs_tx_rate_bps'], 2.5e9)   # 80 line bits per word, from consecutive tail lines

    def test_fabric_secs_from_words_not_wall_clock(self):
        # the DirtyJTAG CDC delivers gs lines late: 20 s wall clock, the end line holds ~10 s of words
        r = sparse_summary(line(1), [line(10), line(11)], 20.0)
        self.assertAlmostEqual(r['fabric_secs'], 11.0)
        self.assertTrue(r['end_after_clear'])
        self.assertFalse(sparse_summary(line(5), [line(3)], 20.0)['end_after_clear'])

    def test_m2_counter_restart_is_flagged(self):
        # seen 12.10. 18:20: gs counted 61 s of words, the m2 back channel only 0.2 s (m2 counters restarted)
        end = line(61); end['pwords'] = 6_322_526
        r = sparse_summary(line(1), [end], 61.0)
        self.assertTrue(r['gs_to_m2']['words_short'])
        self.assertFalse(sparse_summary(line(1), [line(61)], 61.0)['gs_to_m2']['words_short'])

    def test_single_end_line_gives_ber_without_rates(self):
        r = sparse_summary(line(1), [line(60, errb=4)], 60.0)
        self.assertAlmostEqual(r['m2_to_gs']['ber'], 4 / (40.0 * 60 * 31_250_000))
        self.assertEqual(r['gs_tx_rate_bps'], 0.0)
        self.assertEqual(r['uart_end_lines'], 1)

    def test_clear_confirmed_only_for_small_counters(self):
        self.assertTrue(clear_confirmed(line(2)))                 # 2 s after the clear
        self.assertFalse(clear_confirmed(line(60)))               # counters were not cleared
        self.assertFalse(clear_confirmed(None))

if __name__ == '__main__':
    unittest.main()
