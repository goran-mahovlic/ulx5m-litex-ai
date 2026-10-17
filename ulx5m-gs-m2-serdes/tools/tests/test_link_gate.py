"""TASK-5542: link quality gate (CALIBRATION_REVIEW_20261016 §4) - UART window accounting, Q/C verdicts, attempt loop."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab'))
import link_gate as G  # noqa: E402

WPS = 31.25e6                    # 2.5 G word rate


def line(t, e=0, pe=0, loss=0, ploss=0, synced=1, psynced=1, words=None, pwords=None, rate=1.0, ew=0, pew=0):
    """A parsed gs status line at host time t s (fabric time = host time, both checkers synced)."""
    w = int(t * WPS * rate) if words is None else words
    return {'_t': float(t), 't25': int(t * 25e6) & G.M32, 'tcnt': int(t * WPS) & G.M32, 'rcnt': int(t * WPS) & G.M32,
            'words': w, 'errb': e, 'pwords': w if pwords is None else pwords, 'perrb': pe,
            'loss': loss, 'ploss': ploss, 'synced': synced, 'psynced': psynced, 'errw': ew, 'perrw': pew,
            'code': ew, 'pcode': pew}


class Source:
    """Fake UART: list of lines or None (1 s of silence)."""
    def __init__(self, items):
        self.items = list(items)

    def next_line(self):
        return self.items.pop(0) if self.items else G.EOF


def lines(t0, t1, err_at=(), perr_at=(), step=1):
    out, e, pe = [], 0, 0
    for t in range(t0, t1 + 1, step):
        e += err_at.count(t)
        pe += perr_at.count(t)
        out.append(line(t, e, pe))
    return out


class TestMeasure(unittest.TestCase):
    def test_clean_q_passes(self):
        r = G.measure(Source(lines(100, 112)), secs=10, win=10, wps=WPS, early_max=8)
        self.assertEqual(r['status'], 'done')
        self.assertEqual(G.sum_dir(r['windows'], 'm2_to_gs')['errb'], 0)
        self.assertGreater(G.sum_dir(r['windows'], 'gs_to_m2')['words'], 9 * WPS)

    def test_early_exit_on_errors(self):
        r = G.measure(Source(lines(0, 20, err_at=[2] * 9)), secs=10, win=10, wps=WPS, early_max=8)
        self.assertEqual(r['status'], 'early')
        self.assertLess(r['secs'], 4)

    def test_corrupt_m2_line_is_skipped_not_counted(self):
        L = lines(0, 12)
        bad = dict(L[5], pwords=L[5]['pwords'] + 10 ** 12, perrb=10 ** 6)   # back-channel garbage
        L[5] = bad
        r = G.measure(Source(L), secs=10, win=10, wps=WPS, early_max=8)
        self.assertEqual(r['status'], 'done')
        self.assertEqual(r['rejected'], 1)
        self.assertEqual(G.sum_dir(r['windows'], 'gs_to_m2')['errb'], 0)

    def test_uart_gap_extends_window_and_long_silence_is_nouart(self):
        L = lines(0, 3) + [None] * 20 + lines(25, 40)
        r = G.measure(Source(L), secs=30, win=10, wps=WPS, early_max=None, silence=60)
        self.assertEqual(r['status'], 'done')
        self.assertTrue(any(w['t1'] - w['t0'] > 15 for w in r['windows']))
        r2 = G.measure(Source(lines(0, 3) + [None] * 70), secs=30, win=10, wps=WPS, early_max=None, silence=60)
        self.assertEqual(r2['status'], 'nouart')

    def test_checker_restart_detected(self):
        L = [line(t, words=int((t + 3600) * WPS), pwords=int(t * WPS)) for t in range(0, 6)] + \
            [line(t, words=int((t - 5) * WPS), pwords=int(t * WPS)) for t in range(6, 20)]   # gs checker restarts after 1 h
        r = G.measure(Source(L), secs=15, win=10, wps=WPS, early_max=None)
        self.assertTrue(r['restart'])

    def test_sync_fraction_and_dloss(self):
        L = lines(0, 4) + [line(t, loss=1) for t in range(5, 12)]
        r = G.measure(Source(L), secs=10, win=10, wps=WPS, early_max=None)
        self.assertEqual(G.sum_dir(r['windows'], 'm2_to_gs')['dloss'], 1)
        self.assertAlmostEqual(G.sync_frac(r['windows'], 'gs_to_m2'), 1.0, places=4)


class TestMetric(unittest.TestCase):
    def test_k_hit_counts_40_bits_but_one_word(self):
        L = [line(t) for t in range(0, 4)] + [line(t, e=40, ew=1) for t in range(4, 13)]
        rb = G.measure(Source(L), secs=10, win=10, wps=WPS, early_max=8)
        self.assertEqual(rb['status'], 'early')
        rw = G.measure(Source(list(L)), secs=10, win=10, wps=WPS, early_max=8, metric='errw')
        self.assertEqual(rw['status'], 'done')
        q = G.q_verdict(rw, 8, metric='errw')
        self.assertEqual((q['verdict'], q['err']['m2_to_gs'], q['all']['m2_to_gs']['errb']), ('PASS', 1, 40))


class TestRecipe(unittest.TestCase):
    def test_r1_and_eqarst_have_no_calib_strobe(self):
        self.assertEqual(G.R1, ['TX_SEL_PRE=0', 'RX_EQA_CKP_OFFSET=0'])
        self.assertTrue(all('CALIB' not in c and 'recal' not in c for c in G.EQARST))
        self.assertIn('RX_CALIB_VAL=0', G.CAL0)


class TestVerdicts(unittest.TestCase):
    def w(self, e_m2gs, e_gsm2=0, dloss=0, n=1):
        return [{'t0': i * 10, 't1': i * 10 + 10, 'syncmin': 1,
                 'm2_to_gs': {'words': 10 * WPS, 'errb': e_m2gs if i == 0 else 0, 'dloss': dloss, 'expected': 10 * WPS},
                 'gs_to_m2': {'words': 10 * WPS, 'errb': e_gsm2 if i == 0 else 0, 'dloss': 0, 'expected': 10 * WPS}}
                for i in range(n)]

    def test_q_threshold_8(self):
        self.assertEqual(G.q_verdict({'status': 'done', 'windows': self.w(8)}, 8)['verdict'], 'PASS')
        self.assertEqual(G.q_verdict({'status': 'done', 'windows': self.w(9)}, 8)['verdict'], 'FAIL')
        self.assertEqual(G.q_verdict({'status': 'done', 'windows': self.w(0, dloss=1)}, 8)['verdict'], 'FAIL')
        self.assertEqual(G.q_verdict({'status': 'nouart', 'windows': []}, 8)['verdict'], 'UNDECIDED')

    def test_c_burst_window_fails(self):
        ws = self.w(0, n=6)
        self.assertEqual(G.c_verdict({'status': 'done', 'windows': ws}, 60, 20, 0.999999)['verdict'], 'PASS')
        ws[3]['m2_to_gs']['errb'] = 21
        v = G.c_verdict({'status': 'done', 'windows': ws}, 60, 20, 0.999999)
        self.assertEqual(v['verdict'], 'FAIL')
        self.assertIn('burst', v['reason'])

    def test_c_total_over_60_fails(self):
        ws = self.w(0, n=6)
        for x in ws:
            x['gs_to_m2']['errb'] = 11
        self.assertEqual(G.c_verdict({'status': 'done', 'windows': ws}, 60, 20, 0.999999)['verdict'], 'FAIL')

    def test_ladder(self):
        self.assertEqual([G.level_for(n, ['L3']) for n in (1, 2, 10)], ['L3', 'L3', 'L3'])
        self.assertEqual([G.level_for(n, ['L3', 'L1', 'L3']) for n in (1, 2, 3, 4)], ['L3', 'L1', 'L3', 'L3'])

    def test_prev_err_after_health_fail(self):
        self.assertEqual(G.prev_err({'q': None, 'c': None, 'verdict': 'FAIL'}), {})
        self.assertEqual(G.prev_err(None), {})
        self.assertEqual(G.bad_rx(G.prev_err({'q': None})), 'both')
        self.assertEqual(G.prev_err({'q': {'err': {'m2_to_gs': 3}}, 'c': None}), {'m2_to_gs': 3})

    def test_peer_parse(self):
        self.assertTrue(G.peer_parse('rx: PEER 200/200 distinct=200  expect=peer -> PASS', 200)['pass'])
        self.assertFalse(G.peer_parse('rx: PEER 930/1000 distinct=900 expect=peer -> FAIL', 1000, 0.99)['pass'])
        r = G.peer_parse('rx: PEER 995/1000 distinct=990 expect=peer -> FAIL', 1000, 0.99)
        self.assertEqual((r['pass'], r['peer']), (True, 995))
        self.assertFalse(G.peer_parse('rx: PEER 199/200 -> FAIL', 200, 1.0)['pass'])
        self.assertEqual(G.peer_parse('TIMEOUT', 200)['peer'], 0)

    def test_peer_err_picks_bad_receiver_after_health_fail(self):
        # TASK-5550: at 5 G attempts fail on health (no Q), so L2rx must pick the receiver from the PEER misses:
        # PEER read on gs = what gs receives = m2_to_gs
        rec = {'q': None, 'c': None, 'peer': {'gs': {'peer': 990, 'n': 1000}, 'm2': {'peer': 774, 'n': 1000}}}
        self.assertEqual(G.peer_err(rec), {'m2_to_gs': 10, 'gs_to_m2': 226})
        self.assertEqual(G.bad_rx(G.rx_err(rec)), 'm2')
        self.assertEqual(G.peer_err({'q': None}), {})
        self.assertEqual(G.rx_err({'q': {'err': {'m2_to_gs': 30, 'gs_to_m2': 1}}, 'peer': rec['peer']}),
                         {'m2_to_gs': 30, 'gs_to_m2': 1})

    def test_bad_receiver(self):
        self.assertEqual(G.bad_rx({'m2_to_gs': 50, 'gs_to_m2': 2}), 'gs')
        self.assertEqual(G.bad_rx({'m2_to_gs': 1, 'gs_to_m2': 30}), 'm2')
        self.assertEqual(G.bad_rx({'m2_to_gs': 30, 'gs_to_m2': 30}), 'both')


class FakeRig:
    """Outcome per attempt: 'P' pass, 'F' fail at Q, 'C' fail at C, 'U' UART silent, 'H' health fail."""
    def __init__(self, plan):
        self.plan = list(plan)
        self.levels = []

    def attempt(self, n, level, prev):
        self.levels.append(level)
        o = self.plan.pop(0)
        rec = {'attempt': n, 'level': level, 't_link_s': 18.0, 'health': {}, 'peer': {}}
        rec['q'] = {'verdict': {'P': 'PASS', 'C': 'PASS', 'F': 'FAIL', 'U': 'UNDECIDED', 'H': None}[o],
                    'err': {'m2_to_gs': 40 if o == 'F' else 1, 'gs_to_m2': 0}}
        rec['c'] = {'verdict': 'PASS' if o == 'P' else ('FAIL' if o == 'C' else None)}
        rec['verdict'] = {'P': 'PASS', 'C': 'FAIL', 'F': 'FAIL', 'U': 'UNDECIDED', 'H': 'FAIL'}[o]
        return rec


class TestLoop(unittest.TestCase):
    def test_pass_on_third(self):
        rig = FakeRig('FCP')
        recs, res = G.gate_loop(rig.attempt, max_attempts=10, max_undecided=3, ladder=['L3'])
        self.assertEqual(res['verdict'], 'PASS')
        self.assertEqual(res['attempts'], 3)
        self.assertEqual(len(recs), 3)

    def test_ten_failures(self):
        rig = FakeRig('F' * 10)
        recs, res = G.gate_loop(rig.attempt, max_attempts=10, max_undecided=3, ladder=['L3'])
        self.assertEqual(res['verdict'], 'GATE_FAILED')
        self.assertEqual(res['attempts'], 10)

    def test_undecided_not_counted_but_limited(self):
        rig = FakeRig('UUP')
        recs, res = G.gate_loop(rig.attempt, max_attempts=10, max_undecided=3, ladder=['L3'])
        self.assertEqual((res['verdict'], res['attempts'], res['undecided']), ('PASS', 1, 2))
        rig = FakeRig('UUU' + 'P')
        recs, res = G.gate_loop(rig.attempt, max_attempts=10, max_undecided=3, ladder=['L3'])
        self.assertEqual(res['verdict'], 'STOP_UART')

    def test_stats(self):
        runs = [{'verdict': 'PASS', 'attempts': 1}, {'verdict': 'PASS', 'attempts': 3},
                {'verdict': 'GATE_FAILED', 'attempts': 10}]
        recs = [{'verdict': 'PASS'}, {'verdict': 'FAIL'}, {'verdict': 'FAIL'}, {'verdict': 'PASS'}] + \
            [{'verdict': 'FAIL'}] * 10
        s = G.stats(runs, recs)
        self.assertEqual(s['runs'], 3)
        self.assertEqual(s['runs_pass'], 2)
        self.assertEqual(s['attempts_to_pass'], [1, 3])
        self.assertAlmostEqual(s['attempt_pass_frac'], 2 / 14)


class TestDiag(unittest.TestCase):
    def test_diag_ber_from_windows_first_dropped(self):
        # TASK-5550: a FAILED-health attempt still gets a BER from delta windows (first window dropped)
        src = Source(lines(0, 30, err_at=[2, 2, 2] + [15] * 4, perr_at=[25]))
        d = G.diag_summary(G.measure(src, 30, 10, WPS), ('gs_to_m2', 'm2_to_gs'))
        self.assertEqual(d['err']['m2_to_gs'], 4)
        self.assertEqual(d['err']['gs_to_m2'], 1)
        self.assertEqual(d['windows_used'], 2)
        self.assertAlmostEqual(d['ber']['m2_to_gs'], 4 / (20 * WPS * 40), places=15)
        lo, hi = d['ci95']['m2_to_gs']
        self.assertTrue(lo < d['ber']['m2_to_gs'] < hi)

    def test_diag_without_windows(self):
        d = G.diag_summary({'status': 'nouart', 'windows': []}, ('gs_to_m2',))
        self.assertEqual(d['status'], 'nouart')
        self.assertIsNone(d['ber']['gs_to_m2'])


class TestBursts(unittest.TestCase):
    def test_bursts_scaled_to_window(self):
        ws = [{'t0': 0, 't1': 30, 'm2_to_gs': {'errb': 61, 'words': 30 * WPS}, 'gs_to_m2': {'errb': 0, 'words': 30 * WPS}},
              {'t0': 30, 't1': 60, 'm2_to_gs': {'errb': 59, 'words': 30 * WPS}, 'gs_to_m2': {'errb': 0, 'words': 30 * WPS}}]
        b = G.bursts(ws, per10=20)
        self.assertEqual(b['m2_to_gs'], [0])
        self.assertEqual(b['gs_to_m2'], [])


if __name__ == '__main__':
    unittest.main()


class TestK0SetCheck(unittest.TestCase):
    """TASK-5559 K0-b: a JTAG set must read back what was asked, else the attempt is SET_FAIL and the gate stops."""
    def test_set_ok(self):
        self.assertEqual(G.set_check('board=gs set TX_AMP=12 TX_SEL_PRE=0', 0, 'TX_AMP=12 TX_SEL_PRE=0'), [])

    def test_set_readback_differs(self):
        self.assertEqual(G.set_check('board=gs set RX_EQA_CKP_OFFSET=1', 1, 'RX_EQA_CKP_OFFSET=0'),
                         ['RX_EQA_CKP_OFFSET want 0 got 1'])

    def test_set_hex_and_rc(self):
        self.assertEqual(G.set_check('board=m2 set RX_EQA_CKP_LF=131', 0, 'RX_EQA_CKP_LF=0x83'), [])
        self.assertEqual(G.set_check('board=m2 set RX_EQA_CKP_LF=131', 1, 'RX_EQA_CKP_LF=0x83'), ['exit 1'])

    def test_set_no_output(self):
        self.assertEqual(G.set_check('TIMEOUT', 0, 'TX_AMP=12'), ['TX_AMP want 12 got None'])

    def test_gate_stops_on_set_fail(self):
        recs, res = G.gate_loop(lambda n, lv, p: {'verdict': 'SET_FAIL'}, 10, 3, ['L3'])
        self.assertEqual((res['verdict'], len(recs)), ('SET_FAIL', 1))


class TestK0Readapt(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(G.readapt_cmds('eqa'), ['set RX_EQA_RESET_OVR=1 RX_EQA_RESET=1', 'set RX_EQA_RESET_OVR=0 RX_EQA_RESET=0'])
        self.assertEqual(G.readapt_cmds('cdr')[0], 'set RX_CDR_RESET_OVR=1 RX_CDR_RESET=1')
        self.assertEqual(G.readapt_cmds('rx')[0], 'set RX_RESET_OVR=1 RX_RESET=1')
        self.assertEqual(G.readapt_cmds('none'), [])
        self.assertEqual(G.EQARST, G.readapt_cmds('eqa'))

    def test_raw_parse(self):
        self.assertEqual(G.parse_raw('board=gs RAW 0x01=0063 0x03=A3A3 0x04=2101 0x2B=0000'),
                         {'0x01': 0x63, '0x03': 0xA3A3, '0x04': 0x2101, '0x2B': 0})


class TestK0RawRoundTrip(unittest.TestCase):
    def test_eyescan_raw_line_parses(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
        import eyescan
        line_ = eyescan.fmt_raw('gs', [(0x01, 0x63), (0x03, 0xA3A3), (0x2B, 0)])
        self.assertEqual(G.parse_raw(line_), {'0x01': 0x63, '0x03': 0xA3A3, '0x2B': 0})
