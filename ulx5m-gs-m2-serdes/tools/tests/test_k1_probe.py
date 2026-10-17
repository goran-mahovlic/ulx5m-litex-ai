"""TASK-5559 K1-c probe: deltas of the received direction and the per-level verdict (pure parts)."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab'))
import k1_probe as P  # noqa: E402


def L(errb=0, loss=0, synced=1, perrb=0, ploss=0, psynced=1):
    return {'words': 0, 'errb': errb, 'loss': loss, 'synced': synced, 'pwords': 0, 'perrb': perrb, 'ploss': ploss,
            'psynced': psynced}


class K1Probe(unittest.TestCase):
    def test_deltas_gs_rx_loss_wraps(self):
        d = P.deltas(L(loss=31, errb=5), [L(loss=31, errb=5), L(loss=0, errb=45, synced=0), L(loss=0, errb=45)], 'm2_to_gs')
        self.assertEqual(d, {'lines': 3, 'dloss': 1, 'derr': 40, 'synced_min': 0})

    def test_deltas_other_direction_untouched(self):
        d = P.deltas(L(), [L(loss=2, errb=80)], 'gs_to_m2')
        self.assertEqual((d['dloss'], d['derr']), (0, 0))

    def rec(self, b, lv, dloss=0, derr=0):
        return {'board': b, 'level': lv, 'd': {'lines': 8, 'dloss': dloss, 'derr': derr, 'synced_min': 1}}

    def test_verdict_needs_quiet_control_and_all_reps(self):
        v = P.verdict([self.rec('gs', 'none'), self.rec('gs', 'rx', 1), self.rec('gs', 'rx', 1),
                       self.rec('gs', 'eqa', 0, 3), self.rec('gs', 'eqa', 0, 0)])
        self.assertTrue(v['gs:rx']['executes'])
        self.assertFalse(v['gs:eqa']['executes'])
        self.assertFalse(v['gs:none']['executes'])

    def test_noisy_control_blocks(self):
        v = P.verdict([self.rec('m2', 'none', 0, 2), self.rec('m2', 'cdr', 1)])
        self.assertFalse(v['m2:cdr']['executes'])


if __name__ == '__main__':
    unittest.main()
