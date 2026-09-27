import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lab'))
import health_table as H


def health(board, **f):
    base = {'PLL_LOCKED': 1, 'PLL_CAP_FT_OF': 0, 'PLL_CAP_FT_UF': 0, 'PLL_CAP_FT': 435, 'RX_CDR_LOCKED': 1, 'RX_EQA_LOCKED': 1}
    base.update(f)
    return {'board': board, 'label': 'x r1', 'fields': base, 'phase_acc': [100, 150, 130]}


class Health(unittest.TestCase):
    def test_row_reads_0x55_flags_and_cdr(self):
        # 0x55 = PLL_LOCKED / CAP_FT_OF / CAP_FT_UF / CAP_FT (eyescan.py HEALTH_FIELDS); CDR lock is 0x2A
        r = H.row(health('m2', PLL_CAP_FT_OF=1, PLL_CAP_FT=509, RX_CDR_LOCKED=0))
        self.assertEqual(r, {'board': 'm2', 'lock': 1, 'of': 1, 'uf': 0, 'cap_ft': 509, 'cdr': 0, 'eqa': 1, 'phase_span': 50})

    def test_label_and_board_from_file_name(self):
        self.assertEqual(H.split_name('/x/t78_p2_60s_r2.health_gs.json'), ('t78_p2_60s', 2, 'gs'))

    def test_summary_counts_per_label_and_board(self):
        d = tempfile.mkdtemp()
        for k, cdr in ((1, 1), (2, 0), (3, 1)):
            json.dump(health('gs', RX_CDR_LOCKED=cdr, PLL_CAP_FT_OF=int(k == 2)), open(f'{d}/p_r{k}.health_gs.json', 'w'))
        s = H.summary([f'{d}/p_r{k}.health_gs.json' for k in (1, 2, 3)])
        self.assertEqual(s[('p', 'gs')], {'n': 3, 'lock': 3, 'of': 1, 'uf': 0, 'cdr': 2, 'eqa': 3, 'cap_ft': (435, 435)})


if __name__ == '__main__':
    unittest.main()
