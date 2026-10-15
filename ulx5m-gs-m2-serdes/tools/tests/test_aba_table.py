import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lab'))
import aba_table as T


def _w(d, name, m2gs, gsm2, seg=None):
    tot = {'kind': 'total', 'secs': 300.0,
           'm2_to_gs': {'errb': 0 if m2gs == 0 else 7, 'ber': m2gs, 'ber_95_upper': 3e-11 if m2gs == 0 else None},
           'gs_to_m2': {'errb': 0 if gsm2 == 0 else 7, 'ber': gsm2, 'ber_95_upper': 3e-11 if gsm2 == 0 else None},
           'segments': seg or []}
    open(os.path.join(d, name + '.jsonl'), 'w').write('{"kind": "baseline"}\n' + json.dumps(tot) + '\n')


class AbaTable(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        for r, (a1, b, a2) in enumerate(((4e-8, 4e-9, 6e-8), (2e-8, 1e-8, 2e-8), (8e-8, 2e-9, 0)), 1):
            _w(self.d, 'r%d_A1' % r, a1, 1e-9); _w(self.d, 'r%d_B_gs_tapw2' % r, b, 1e-9); _w(self.d, 'r%d_A2' % r, a2, 2e-9)

    def test_rows_per_load_and_step(self):
        rows = T.table(self.d)
        self.assertEqual([r['load'] for r in rows], [1, 2, 3])
        self.assertEqual(rows[0]['m2_to_gs'], {'A1': 4e-8, 'B': 4e-9, 'A2': 6e-8})
        self.assertEqual(rows[2]['m2_to_gs']['A2'], 3e-11)          # 0 errors -> 95 % upper bound
        self.assertTrue(rows[2]['m2_to_gs_zero']['A2'])

    def test_gain_is_geomean_of_a_over_b(self):
        rows = T.table(self.d)
        self.assertAlmostEqual(rows[0]['gain_m2_to_gs'], (4e-8 * 6e-8) ** 0.5 / 4e-9)
        self.assertAlmostEqual(rows[1]['gain_m2_to_gs'], 2.0)

    def test_medians_per_step(self):
        med = T.medians(T.table(self.d))
        self.assertEqual(med['m2_to_gs']['A1'], 4e-8)
        self.assertEqual(med['m2_to_gs']['B'], 4e-9)
        self.assertEqual(med['gs_to_m2']['A2'], 2e-9)
        self.assertAlmostEqual(med["m2_to_gs"]["A"], (2e-8 + 4e-8) / 2)   # all six A values pooled

    def test_missing_step_is_none(self):
        os.unlink(os.path.join(self.d, 'r3_A2.jsonl'))
        rows = T.table(self.d)
        self.assertIsNone(rows[2]['m2_to_gs']['A2'])
        self.assertAlmostEqual(rows[2]['gain_m2_to_gs'], 8e-8 / 2e-9)

    def test_markdown_has_median_row(self):
        md = T.markdown(T.table(self.d))
        self.assertIn('| median |', md)
        self.assertIn('4.0e-09', md)

    def test_quick30_reference_after_c143_c144_repair(self):
        # REGOC quick30 15.10. 18:51 (after Goran's C143/C144 repair): the reference for TASK-5527 step 2
        self.assertEqual(T.REF['quick30'], {'gs_to_m2': 8.9e-9, 'm2_to_gs': 8.9e-11})

    def test_b_label_in_header(self):
        md = T.markdown(T.table(self.d), b_label='recept R1')
        self.assertIn('M2→GS B (recept R1)', md)
        self.assertIn('GS→M2 B (recept R1)', md)


if __name__ == '__main__':
    unittest.main()


class Robust(unittest.TestCase):
    """lab28 r1_A1: m2->gs at ~1e-2 corrupts the m2 counters carried in the gs UART line (back channel)."""
    S = [  # trimmed real lab28 r1_A1 snapshots
        {'t': 5.6, 'words': 5129626901, 'errb': 2598288626, 'pwords': 5102941428, 'perrb': 4949},
        {'t': 67.7, 'words': 7024940409, 'errb': 3607066143, 'pwords': 7022890068, 'perrb': 5602},
        {'t': 129.6, 'words': 8921067778, 'errb': 321640225, 'pwords': 12153280884, 'perrb': 6756},
        {'t': 191.6, 'nouart': True},
        {'t': 254.7, 'words': 12868184036, 'errb': 2337617170, 'pwords': 12887538516, 'perrb': 13080},
        {'t': 300.0, 'words': 13956045601, 'errb': 2908207088, 'pwords': 14015971220, 'perrb': 9044},
    ]

    def test_own_counter_wrap_is_kept(self):
        r = T.robust(self.S)['m2_to_gs']
        self.assertEqual(r['errb'], 4604885758)            # = ber_long total (one real 32-bit wrap)
        self.assertEqual(r['skipped'], 0)
        self.assertGreater(r['ber'], 1e-2)

    def test_corrupt_peer_snapshots_are_skipped(self):
        r = T.robust(self.S)['gs_to_m2']
        self.assertEqual(r['skipped'], 2)                # pwords jump at 129.6, perrb going back at 300.0
        self.assertEqual(r['errb'], 5602 - 4949 + 13080 - 5602)
        self.assertLess(r['ber'], 1e-7)

    def test_clean_series_equals_plain_sum(self):
        s = [{'t': 0, 'words': 0, 'errb': 0, 'pwords': 0, 'perrb': 0},
             {'t': 60, 'words': 10 ** 9, 'errb': 40, 'pwords': 10 ** 9, 'perrb': 4}]
        r = T.robust(s)
        self.assertEqual((r['m2_to_gs']['errb'], r['gs_to_m2']['errb']), (40, 4))
        self.assertAlmostEqual(r['gs_to_m2']['ber'], 4 / (40.0 * 10 ** 9))


class Dropped(unittest.TestCase):
    def test_markdown_lists_dropped_peer_snapshots(self):
        d = tempfile.mkdtemp()
        lines = [json.dumps(dict(s, kind='snap')) for s in Robust.S]
        for st in ('r1_A1', 'r1_B_gs_tapw2', 'r1_A2'):
            open(os.path.join(d, st + '.jsonl'), 'w').write('\n'.join(lines) + '\n')
        md = T.markdown(T.table(d))
        self.assertIn('r1 A1 GS→M2 ×2', md)
        self.assertNotIn('M2→GS ×', md.split('dropped')[1])


class OwnWrap(unittest.TestCase):
    def test_own_counter_wraps_from_below_2_31_at_high_ber(self):
        s = [{'t': 0, 'words': 0, 'errb': 2 * 10 ** 9, 'pwords': 0, 'perrb': 0},          # 4e-2: 3e9 errors per 1.9e9 words
             {'t': 60, 'words': 19 * 10 ** 8, 'errb': (5 * 10 ** 9) % (1 << 32), 'pwords': 19 * 10 ** 8, 'perrb': 10}]
        r = T.robust(s)['m2_to_gs']
        self.assertEqual((r['skipped'], r['errb']), (0, 3 * 10 ** 9))
