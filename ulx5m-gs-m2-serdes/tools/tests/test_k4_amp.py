"""TASK-5559 K4a: AMP pair table over repeated readapt draws."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab'))
import k4_amp as A  # noqa: E402

B = 5e10


def v(load, pair, e_mg, e_gm):
    return {'kind': 'visit', 'load': load, 'pair': list(pair), 'err': {'m2_to_gs': e_mg, 'gs_to_m2': e_gm},
            'bits': {'m2_to_gs': B, 'gs_to_m2': B}, 'set_fail': []}


class K4Amp(unittest.TestCase):
    def test_median_and_win(self):
        recs = []
        for ld in ('l1', 'l2'):
            recs += [v(ld, (12, 12), 100, 5), v(ld, (12, 12), 50, 3), v(ld, (12, 12), 200, 1),
                     v(ld, (10, 10), 10, 6), v(ld, (10, 10), 20, 2), v(ld, (10, 10), 0, 4)]
        t = A.table(recs)
        self.assertEqual(t[(12, 12)]['worse'], 'm2_to_gs')
        self.assertAlmostEqual(t[(12, 12)]['median']['m2_to_gs'], 100 / B)
        self.assertTrue(t[(10, 10)]['beats_base_every_load'])
        self.assertAlmostEqual(t[(10, 10)]['pooled']['m2_to_gs'], 60 / (6 * B))

    def test_one_bad_load_blocks_win(self):
        recs = [v('l1', (12, 12), 100, 0), v('l1', (8, 12), 10, 0), v('l2', (12, 12), 100, 0), v('l2', (8, 12), 80, 0)]
        self.assertFalse(A.table(recs)[(8, 12)]['beats_base_every_load'])

    def test_set_fail_visit_dropped(self):
        r = v('l1', (12, 12), 1, 1)
        r['set_fail'] = [{'board': 'gs'}]
        self.assertEqual(A.table([r]), {})


if __name__ == '__main__':
    unittest.main()


class K4AmpDrop(unittest.TestCase):
    def test_first_window_dropped(self):
        r = v('l1', (12, 12), 2527, 46)
        r['win'] = [{'m2_to_gs': 2527, 'gs_to_m2': 40}, {'m2_to_gs': 0, 'gs_to_m2': 3}, {'m2_to_gs': 0, 'gs_to_m2': 3},
                    {'m2_to_gs': 0, 'gs_to_m2': 0}]
        d = A.drop_first(r)
        self.assertEqual(d['err'], {'m2_to_gs': 0, 'gs_to_m2': 6})
        self.assertAlmostEqual(d['bits']['m2_to_gs'], B * 0.75)


class K4b(unittest.TestCase):
    def test_point_fields_base_plus_override(self):
        f = A.point_fields(next(p for p in A.POINTS if p[0] == 'static'))
        self.assertEqual((f['gs']['TX_AMP'], f['m2']['TX_AMP']), (8, 12))
        self.assertEqual((f['gs']['RX_EN_EQA'], f['m2']['RX_AFE_PEAK'], f['m2']['RX_AFE_GAIN']), (0, 15, 8))
        f = A.point_fields(next(p for p in A.POINTS if p[0] == 'm2post12'))
        self.assertEqual((f['m2']['TX_SEL_POST'], f['gs']['TX_SEL_POST'], f['gs']['RX_EN_EQA']), (12, 5, 1))

    def test_table_keys_points(self):
        recs = []
        for ld in ('l1', 'l2'):
            for name, e in (('base', 100), ('m2post8', 10)):
                r = v(ld, (8, 12), e, 0)
                r['point'] = name
                recs.append(r)
        t = A.table(recs)
        self.assertTrue(t['m2post8']['beats_base_every_load'])
        self.assertFalse(t['base']['beats_base_every_load'])
