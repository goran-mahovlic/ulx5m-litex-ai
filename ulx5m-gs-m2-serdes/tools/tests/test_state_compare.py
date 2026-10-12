import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lab'))
from state_compare import span, table

def h(board, cap, span_=0):
    return {'board': board, 'fields': {'PLL_CAP_FT': cap}, 'freq_acc_span': span_}

class T(unittest.TestCase):
    def test_span(self):
        self.assertEqual(span([442, 450, 446]), '442–450')
        self.assertEqual(span([7, 7]), '7')
        self.assertEqual(span([None]), '-')

    def test_table_rows_per_board_and_group(self):
        t = table([('28.09', [h('gs', 442), h('gs', 450), h('m2', 512)]), ('12.10', [h('gs', 502), h('m2', 505)])])
        self.assertIn('| 28.09 (n=2/1) | 12.10 (n=1/1) |', t[0])
        self.assertIn('| PLL_CAP_FT | gs | 442–450 | 502 |', t)
        self.assertIn('| FREQ_ACC_SPAN | m2 | 0 | 0 |', t)

if __name__ == '__main__':
    unittest.main()
