"""TASK-5559 K4: margin per direction, lever labels per direction, win rule (>= 1 AMP step on 3/3 loads)."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab'))
import k4_margin as M  # noqa: E402


def st(ok_m2gs, ok_gsm2):
    return {'ok': {'m2_to_gs': ok_m2gs, 'gs_to_m2': ok_gsm2}}


def run(load, name, mg, mm, invalid=False):
    r = dict(zip(('name', 'm2', 'gs'), next(x for x in M.RUNS if x[0] == name)))
    return {'kind': 'run', 'load': load, 'name': name, 'invalid': invalid,
            'labels': {k: M.lever_label((name, r['m2'], r['gs']), k) for k in ('m2_to_gs', 'gs_to_m2')},
            'margin': {'m2_to_gs': mg, 'gs_to_m2': mm}}


class K4(unittest.TestCase):
    def test_margin_stops_at_first_fail(self):
        steps = [(12, st(True, True)), (10, st(True, False)), (8, st(False, False)), (6, st(True, False))]
        self.assertEqual(M.margin(steps, 'm2_to_gs'), 10)
        self.assertEqual(M.margin(steps, 'gs_to_m2'), 12)
        self.assertIsNone(M.margin([(12, st(False, True))], 'm2_to_gs'))

    def test_labels_split_levers_by_direction(self):
        r = next(x for x in M.RUNS if x[0] == 'm2post8_gspost0')
        self.assertEqual(M.lever_label(r, 'm2_to_gs'), 'm2.TX_SEL_POST=8')
        self.assertEqual(M.lever_label(r, 'gs_to_m2'), 'gs.TX_SEL_POST=0')
        r = next(x for x in M.RUNS if x[0] == 'm2post6_m2peak16')
        self.assertEqual(M.lever_label(r, 'gs_to_m2'), 'm2.RX_AFE_PEAK=16')
        self.assertEqual(M.lever_label(next(x for x in M.RUNS if x[0] == 'm2post12'), 'gs_to_m2'), 'base')

    def test_win_needs_one_step_on_three_loads(self):
        recs = []
        for ld, mg in (('l1', 8), ('l2', 8), ('l3', 10)):
            recs += [run(ld, 'base', 12, 10), run(ld, 'm2post12', mg, 10)]
        t = M.table(recs)
        o = t[('m2_to_gs', 'm2.TX_SEL_POST=12')]
        self.assertEqual(o['gain_steps'], [2, 2, 1])
        self.assertTrue(o['win'])
        self.assertNotIn(('gs_to_m2', 'base'), [k for k in t if k[1] == 'base' and t[k]['win']])

    def test_none_margin_is_worst(self):
        recs = []
        for ld in ('l1', 'l2', 'l3'):
            recs += [run(ld, 'base', 12, 12), run(ld, 'gspeak16', None, 12)]
        o = M.table(recs)[('m2_to_gs', 'gs.RX_AFE_PEAK=16')]
        self.assertEqual(o['gain_steps'], [-1, -1, -1])
        self.assertFalse(o['win'])


if __name__ == '__main__':
    unittest.main()
