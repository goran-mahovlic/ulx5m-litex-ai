"""TASK-5542 (uputa #347): calib_aba.py - automatic revert, A/B/A ratios, K verdict."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab'))
import calib_aba as C  # noqa: E402

B = 5.6e10


def st(kind, name, e1, e2, load='l1'):
    return {'kind': kind, 'name': name, 'load': load, 'err': {'m2_to_gs': e1, 'gs_to_m2': e2},
            'bits': {'m2_to_gs': B, 'gs_to_m2': B}}


class T(unittest.TestCase):
    def test_commands_and_revert(self):
        self.assertEqual(C.commands('RX_EQA_CKP_OFFSET=0;recal'), ['set RX_EQA_CKP_OFFSET=0', 'recal'])
        self.assertEqual(C.commands('freeze RX_TAPW=-2'), ['freeze RX_TAPW=-2'])
        self.assertEqual(C.fields_of('TX_SEL_PRE=0 TX_SEL_POST=0'), ['TX_SEL_PRE', 'TX_SEL_POST'])
        self.assertEqual(C.fields_of('freeze RX_TAPW=2'), [])
        self.assertEqual(C.revert_cmd('TX_AMP=8', {'TX_AMP': 12}), 'TX_AMP=12')
        self.assertEqual(C.revert_cmd('RX_EQA_CKP_OFFSET=0;recal', {'RX_EQA_CKP_OFFSET': 1}), 'RX_EQA_CKP_OFFSET=1;recal')
        self.assertEqual(C.revert_cmd('freeze RX_TAPW=2', {}), 'restore')
        self.assertEqual(C.revert_cmd('recal', {}), 'recal')

    def test_eqarst_is_not_recal(self):
        cs = C.commands('RX_EQA_CKP_OFFSET=0;eqarst')
        self.assertEqual(cs[0], 'set RX_EQA_CKP_OFFSET=0')
        self.assertTrue(all('CALIB' not in c and 'recal' not in c for c in cs))
        self.assertEqual(C.revert_cmd('RX_EQA_CKP_OFFSET=0;eqarst', {'RX_EQA_CKP_OFFSET': 1}), 'RX_EQA_CKP_OFFSET=1;eqarst')
        self.assertEqual(C.fields_of('eqarst'), [])

    def test_no_plan_point_strobes_calibration(self):
        for p in C.PLAN:
            self.assertNotIn('recal', p[3], p)

    def test_boards(self):
        self.assertEqual(C.boards('*', 'gs'), ('gs', 'm2'))
        self.assertEqual(C.boards('rx', 'gs'), ('gs',))
        self.assertEqual(C.boards('rx', 'both'), ('gs', 'm2'))

    def test_ratio_uses_both_neighbouring_a(self):
        rows = [st('A', 'A0', 100, 10), st('B', 'amp10', 25, 10), st('A', 'A1', 400, 10)]
        r = C.point_ratios(rows)['amp10']
        self.assertAlmostEqual(r['m2_to_gs'], 8.0)              # gmean(100, 400) = 200 -> /25
        self.assertAlmostEqual(r['gs_to_m2'], 1.0)

    def test_zero_errors_half_count(self):
        rows = [st('A', 'A0', 10, 0), st('B', 'x', 0, 0), st('A', 'A1', 10, 0)]
        self.assertAlmostEqual(C.point_ratios(rows)['x']['m2_to_gs'], 20.0)

    def test_verdict(self):
        win = [{'m2_to_gs': 3, 'gs_to_m2': 1, 'sum': 2.5}] * 3
        self.assertEqual(C.verdict(win)[0], 'WIN')
        hurt = [{'m2_to_gs': 10, 'gs_to_m2': 0.3, 'sum': 3}] * 3
        self.assertEqual(C.verdict(hurt)[0], 'NEUTRAL')            # a direction loses > x2
        self.assertEqual(C.verdict([{'m2_to_gs': 0.2, 'gs_to_m2': 0.2, 'sum': 0.2}] * 3)[0], 'WORSE')
        mixed = [{'m2_to_gs': 5, 'gs_to_m2': 1, 'sum': 5}, {'m2_to_gs': 1, 'gs_to_m2': 1, 'sum': 1},
                 {'m2_to_gs': 0.9, 'gs_to_m2': 1, 'sum': 0.9}]
        self.assertEqual(C.verdict(mixed)[0], 'NEUTRAL')           # median over loads, one good load is not enough

    def test_table_metric_errw(self):
        import json
        import tempfile
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'x.jsonl')
        rows = [st('A', 'A0', 400, 0), st('B', 'amp8', 40, 0), st('A', 'A1', 400, 0)]
        for r, w in zip(rows, (10, 10, 10)):
            r['errw'] = {'m2_to_gs': w, 'gs_to_m2': 0}
        with open(p, 'w') as f:
            f.write(''.join(json.dumps(r) + '\n' for r in rows))
        self.assertAlmostEqual(C.table(p)[1]['amp8'][1]['m2_to_gs'], 10.0)       # bit errors: x10 better
        self.assertAlmostEqual(C.table(p, 'errw')[1]['amp8'][1]['m2_to_gs'], 1.0)  # same number of bad words

    def test_plan_names_unique(self):
        names = [p[1] for p in C.PLAN]
        self.assertEqual(len(names), len(set(names)))


if __name__ == '__main__':
    unittest.main()
