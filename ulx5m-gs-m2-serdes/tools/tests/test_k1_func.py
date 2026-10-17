"""TASK-5559 K1-c: decades and per-level verdict of k1_func (pure parts)."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab'))
import k1_func as F  # noqa: E402


def rec(level, b, a, err=1, bits=2.5e10):
    r = {'level': level, 'before': {'ber': b, 'err': 5}, 'after': {'ber': a, 'err': err}}
    r['dec'] = F.decades(r['before'], r['after'], bits)
    return r


class K1Func(unittest.TestCase):
    def test_decades_zero_after_counts_one_error(self):
        self.assertAlmostEqual(F.decades({'ber': 1e-6, 'err': 9}, {'ber': 0.0, 'err': 0}, 1e10), 4.0)

    def test_level_works_only_on_all_damaged_reps(self):
        t = F.table([rec('eqa', 1e-6, 1e-9), rec('eqa', 2e-6, 1e-9), rec('eqa', 1e-5, 1e-8),
                     rec('cdr', 1e-6, 1e-9), rec('cdr', 1e-6, 1e-6), rec('cdr', 1e-6, 1e-9)])
        self.assertTrue(t['eqa']['works'])
        self.assertFalse(t['cdr']['works'])
        self.assertEqual(t['cdr']['win'], 2)

    def test_undamaged_rep_is_not_a_win(self):
        t = F.table([rec('rx', 1e-9, 1e-11), rec('rx', 1e-6, 1e-9), rec('rx', 1e-6, 1e-9)])
        self.assertFalse(t['rx']['works'])
        self.assertEqual(t['rx']['damaged'], 2)


if __name__ == '__main__':
    unittest.main()
