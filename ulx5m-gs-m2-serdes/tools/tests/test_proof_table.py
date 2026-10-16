import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lab'))
import proof_table as P

OUT = """LOAD t1_l1 t_link=41.9s ok=1 polls=1 gs RX_OFFSET=2 m2 RX_OFFSET=7
PEER t1_l1 m2: rx: PEER 200/200 distinct=200  expect=peer -> PASS | gs: rx: PEER 200/200 distinct=200  expect=peer -> PASS
BER t1_l1_A TOTAL secs=60.9 gs->m2 BER=1.3e-11 (<None) m2->gs BER=4.2e-08 (<None) restarts={'m2_to_gs': 0, 'gs_to_m2': 0} snaps=1
BER t1_l1_g2_g1m0 TOTAL secs=60.1 gs->m2 BER=0.0 (<4e-11) m2->gs BER=3.2e-08 (<None) restarts={'m2_to_gs': 0, 'gs_to_m2': 0} snaps=1
RESULT t1_l1 rejected (G2, failed g1 m0)
LOAD t2_l1 t_link=47.6s ok=1 polls=1 gs RX_OFFSET=2 m2 RX_OFFSET=7
PEER t2_l1 m2: rx: PEER 200/200 distinct=200  expect=peer -> PASS | gs: rx: PEER 200/200 distinct=200  expect=peer -> PASS
BER t2_l1_A TOTAL secs=60.4 gs->m2 BER=4.9e-10 (<None) m2->gs BER=6.2e-11 (<None) restarts={'m2_to_gs': 0, 'gs_to_m2': 0} snaps=1
RESULT t2_l1 accepted=first
TRIAL t1 loads=1 accepted=0 01:38:30
LOAD soak_l1 t_link=46.5s ok=1 polls=1 gs RX_OFFSET=2 m2 RX_OFFSET=7
PEER soak_l1 m2: rx: PEER 199/200 distinct=199  expect=peer -> FAIL | gs: rx: PEER 200/200 distinct=200  expect=peer -> PASS
BER soak_l1_A TOTAL secs=60.1 gs->m2 BER=4.4e-09 (<None) m2->gs BER=1.5e-08 (<None) restarts={'m2_to_gs': 0, 'gs_to_m2': 0} snaps=1
BER soak_l1_g2_g1m1 TOTAL secs=60.0 gs->m2 BER=1e-10 (<None) m2->gs BER=5e-10 (<None) restarts={'m2_to_gs': 0, 'gs_to_m2': 0} snaps=1
RESULT soak_l1 accepted=G2 (failed g1 m1)
"""


def snap(t, w, e, pw, pe):
    return {'t': t, 'words': w, 'errb': e, 'pwords': pw, 'perrb': pe}


class ProofTable(unittest.TestCase):
    def test_parse_attempts(self):
        a = P.parse(OUT)
        self.assertEqual([x['tag'] for x in a], ['t1_l1', 't2_l1', 'soak_l1'])
        self.assertEqual(a[0]['trial'], 't1')
        self.assertAlmostEqual(a[0]['t_link'], 41.9)
        self.assertEqual((a[0]['gs_off'], a[0]['m2_off']), (2, 7))
        self.assertTrue(a[0]['peer_ok'])
        self.assertFalse(a[2]['peer_ok'])
        self.assertAlmostEqual(a[0]['A']['m2_to_gs'], 4.2e-8)
        self.assertEqual(a[0]['G2']['gs_to_m2'], 0.0)
        self.assertAlmostEqual(a[0]['G2']['gs_to_m2_upper'], 4e-11)
        self.assertEqual(a[0]['result'], 'rejected')
        self.assertEqual(a[1]['result'], 'first')
        self.assertIsNone(a[1]['G2'])
        self.assertEqual(a[2]['result'], 'G2')

    def test_summary_counts(self):
        s = P.summary(P.parse(OUT))
        self.assertEqual(s['loads'], 3)
        self.assertEqual(s['peer_ok'], 2)
        self.assertEqual(s['first'], 1)
        self.assertEqual(s['g2'], 1)
        self.assertEqual((s['t_link_min'], s['t_link_max']), (41.9, 47.6))

    def test_hourly_buckets_and_clean_intervals(self):
        bits = P.PAYLOAD_BITS
        sn = [snap(0, 0, 0, 0, 0), snap(1800, 1000, 0, 1000, 5), snap(3600, 2000, 4, 2000, 5),
              snap(5400, 3000, 4, 3000, 5)]
        h = P.buckets(sn, 3600)
        self.assertEqual(len(h), 2)
        self.assertAlmostEqual(h[0]['m2_to_gs'], 4 / (2000.0 * bits))
        self.assertAlmostEqual(h[0]['gs_to_m2'], 5 / (2000.0 * bits))
        self.assertEqual(h[1]['m2_to_gs'], 0.0)
        c = P.clean_intervals(sn)
        self.assertEqual(c['m2_to_gs'], (2, 3))
        self.assertEqual(c['gs_to_m2'], (2, 3))

    def test_poisson_interval(self):
        lo, hi = P.poisson95(10000, 1e13)
        self.assertLess(lo, 1e-9)
        self.assertGreater(hi, 1e-9)
        self.assertAlmostEqual(hi / 1e-9, 1.0196, places=2)
        self.assertEqual(P.poisson95(0, 1e12), (0.0, 3e-12))


if __name__ == '__main__':
    unittest.main()
