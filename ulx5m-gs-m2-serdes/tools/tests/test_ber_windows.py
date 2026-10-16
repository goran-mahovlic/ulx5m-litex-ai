"""TASK-5538 (uputa #345): BER from snapshot deltas, first window dropped, exact Poisson 95 % interval."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab'))
import ber_windows as B  # noqa: E402


def snap(t, w, e, pw, pe, loss=0, ploss=0):
    return {'t': t, 'words': w, 'errb': e, 'pwords': pw, 'perrb': pe, 'loss': loss, 'ploss': ploss,
            'synced': 1, 'psynced': 1}


class T(unittest.TestCase):
    def test_garwood_known_values(self):
        lo, hi = B.poisson_ci(0)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 3.689, places=3)
        lo, hi = B.poisson_ci(10)
        self.assertAlmostEqual(lo, 4.795, places=3)
        self.assertAlmostEqual(hi, 18.390, places=2)

    def test_deltas_not_cumulative(self):
        s = [snap(0, 1000, 500, 1000, 50), snap(30, 2000, 501, 2000, 50), snap(60, 3000, 503, 3000, 51)]
        ws = B.windows(s)
        self.assertEqual([w['m2_to_gs']['errb'] for w in ws], [1, 2])
        self.assertEqual([w['gs_to_m2']['errb'] for w in ws], [0, 1])

    def test_skip_first_window_and_loss_wrap(self):
        s = [snap(0, 0, 0, 0, 0, loss=30), snap(30, 1000, 900, 1000, 9, loss=31),
             snap(60, 2000, 902, 2000, 9, loss=1), snap(90, 3000, 903, 3000, 10, loss=1)]
        t = B.summarize(B.windows(s)[1:])
        self.assertEqual(t['n'], 2)
        self.assertEqual(t['m2_to_gs']['errb'], 3)            # the 900 link-up errors are dropped
        self.assertEqual(t['m2_to_gs']['dloss'], 2)           # 31 -> 1 is +2 mod 32
        self.assertAlmostEqual(t['m2_to_gs']['ber'], 3 / (2000 * B.PAYLOAD_BITS))
        lo, hi = t['m2_to_gs']['ci95']
        self.assertTrue(lo < t['m2_to_gs']['ber'] < hi)

    def test_no_window_after_skip_is_reported_not_crashed(self):
        import io, json, tempfile, contextlib
        with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False) as f:
            f.write(json.dumps(dict(snap(0, 0, 0, 0, 0), kind='baseline')) + '\n')
            f.write(json.dumps(dict(snap(30, 1000, 9, 1000, 1), kind='snap')) + '\n')
        out = io.StringIO()
        sys.argv = ['ber_windows.py', f.name]
        with contextlib.redirect_stdout(out):
            rc = B.main()
        self.assertEqual(rc, 3)
        self.assertIn('NO WINDOW after skip', out.getvalue())


if __name__ == '__main__':
    unittest.main()
