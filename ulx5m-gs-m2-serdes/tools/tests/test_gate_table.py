"""TASK-5542: gate_table.py - per-run rows, group statistics (attempts to a pass, per level), soak from deltas."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab'))
import gate_table as T  # noqa: E402

B = 1.25e10


def att(n, level, v, qerr=(0, 0), cerr=(0, 0), stage='q'):
    q = {'verdict': 'PASS' if v == 'PASS' or stage == 'c' else 'FAIL', 'err': {'m2_to_gs': qerr[0], 'gs_to_m2': qerr[1]},
         'bits': {'m2_to_gs': B, 'gs_to_m2': B}}
    c = None
    if v == 'PASS' or stage == 'c':
        c = {'verdict': v, 'err': {'m2_to_gs': cerr[0], 'gs_to_m2': cerr[1]}, 'bits': {'m2_to_gs': 6 * B, 'gs_to_m2': 6 * B}}
    return {'attempt': n, 'level': level, 'verdict': v, 't_link_s': 17.0, 'q': q, 'c': c, 'set': []}


def write(d, name, rows):
    with open(os.path.join(d, name + '.jsonl'), 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')


class T1(unittest.TestCase):
    def test_groups_and_levels(self):
        d = tempfile.mkdtemp()
        write(d, 'b1', [att(1, 'L3', 'PASS', cerr=(6, 0)), {'kind': 'gate', 'verdict': 'PASS', 'attempts': 1}])
        write(d, 'b2', [att(1, 'L3', 'FAIL', qerr=(40, 0)), att(2, 'L3', 'FAIL', stage='c', cerr=(70, 0)),
                        att(3, 'L3', 'PASS'), {'kind': 'gate', 'verdict': 'PASS', 'attempts': 3}])
        write(d, 'k3_1', [att(1, 'L3', 'FAIL', qerr=(40, 0)), att(2, 'L1', 'PASS'),
                          {'kind': 'gate', 'verdict': 'PASS', 'attempts': 2}])
        md, rows, gs, by_run = T.render(d)
        self.assertIn('| b2 | 1 | L3 |', T.attempt_rows(by_run))
        self.assertEqual(gs['b']['pass'], 2)
        self.assertEqual(gs['b']['attempts_to_pass'], [1, 3])
        self.assertEqual(gs['b']['first_pass'], (1, 2))
        self.assertEqual(gs['b']['attempt_pass'], (2, 4))
        self.assertEqual(gs['k3']['levels'], {'L3': [0, 1], 'L1': [1, 1]})
        self.assertIn('`qcP`', md)
        self.assertIn('8.0e-11', md)                 # b1 C: 6 errors / 7.5e10 bits

    def test_soak_drops_first_window_and_counts_bursts(self):
        d = tempfile.mkdtemp()
        rows, w, e = [], 0, 0
        for i in range(8):
            rows.append({'kind': 'baseline' if i == 0 else 'snap', 't': 10.0 * i, 'words': w, 'errb': e,
                         'pwords': w, 'perrb': 0, 'loss': 0, 'ploss': 0, 'synced': 1, 'psynced': 1})
            w += 312500000
            e += {0: 500, 3: 30}.get(i, 1)           # link-up window 500 errors (dropped), one burst of 30
        write(d, 'x_soak', rows)
        t = T.soak_summary(os.path.join(d, 'x_soak.jsonl'))
        self.assertEqual(t['n'], 6)
        self.assertEqual(t['m2_to_gs']['errb'], 35)
        self.assertEqual(t['bursts']['m2_to_gs'], 1)
        self.assertEqual(t['burst_err']['m2_to_gs'], 30)


if __name__ == '__main__':
    unittest.main()
