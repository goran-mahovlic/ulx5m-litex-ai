import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lab'))
import eye_cc_report as R


class Report(unittest.TestCase):
    def test_diag_rows(self):
        t = ('INFO:  eye measurement diagnostics\n  [PASS] CDR locked                   RX_CDR_LOCKED=1\n'
             '  [FAIL] exception                  TimeoutError: stuck\n')
        t += '  [FAIL] counters respond to threshold @phase +0: wrong@0=0/0\n'
        self.assertEqual(R.diag_rows(t)[2], ('counters respond to threshold', 'FAIL', '@phase +0: wrong@0=0/0'))
        self.assertEqual(R.diag_rows(t)[:2], [('CDR locked', 'PASS', 'RX_CDR_LOCKED=1'), ('exception', 'FAIL', 'TimeoutError: stuck')])

    def test_ber_total(self):
        with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False) as f:
            f.write('{"kind": "snap"}\nnot json\n')
            f.write(json.dumps({'kind': 'total', 'm2_to_gs': {'errb': 5, 'ber': 1e-9, 'ber_95_upper': None},
                                'gs_to_m2': {'errb': 0, 'ber': 0.0, 'ber_95_upper': 3e-11}}) + '\n')
        got = R.ber_total(f.name); os.unlink(f.name)
        self.assertEqual(got['m2_to_gs'], 1e-9)
        self.assertEqual(got['gs_to_m2'], 3e-11)          # 0 errors -> 95 % upper bound
        self.assertEqual(got['gs_to_m2_err'], 0)


    def test_steps_in_order(self):
        d = tempfile.mkdtemp()
        for i, n in enumerate(('A0', 'amp16', 'A_amp16')):
            p = os.path.join(d, n + '.jsonl'); open(p, 'w').write('{}\n'); os.utime(p, (1000 + i, 1000 + i))
        self.assertEqual(R.steps_in_order(d), ['A0', 'amp16', 'A_amp16'])


if __name__ == '__main__':
    unittest.main()
