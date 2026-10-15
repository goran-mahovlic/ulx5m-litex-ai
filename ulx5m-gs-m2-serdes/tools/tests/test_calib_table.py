import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lab'))
import calib_table as C

PT = ("PT gs_tapw2 | board=gs RX_CDR_LOCKED=1 RX_EQA_LOCKED=1 RX_TH_MON=15 RX_OFFSET=2 RX_EQA_TAPW=2 | 25.2 gs->m2 "
      "BER=0.0 (<2.3999850087336416e-10) m2->gs BER=3.199980144763198e-10 (<None) restarts={'m2_to_gs': 0} snaps=1")


class CalibTable(unittest.TestCase):
    def test_parse_pt_line(self):
        p = C.parse_line(PT)
        self.assertEqual(p['label'], 'gs_tapw2')
        self.assertAlmostEqual(p['m2_to_gs'], 3.2e-10, places=12)
        self.assertEqual(p['gs_to_m2'], 0.0)
        self.assertAlmostEqual(p['gs_to_m2_upper'], 2.4e-10, places=12)
        self.assertEqual(p['secs'], 25.2)

    def test_none_ber_and_non_pt(self):
        self.assertIsNone(C.parse_line('JTAG start m2: rx: PEER 200/200'))
        p = C.parse_line("PT x | board=gs | 15.4 gs->m2 BER=None (<None) m2->gs BER=None (<None) restarts={} snaps=1")
        self.assertIsNone(p['m2_to_gs'])

    def test_ratio_to_reference(self):
        rows = [C.parse_line(PT.replace('gs_tapw2', 'A0').replace('m2->gs BER=3.199980144763198e-10',
                                                                     'm2->gs BER=3.2e-08')), C.parse_line(PT)]
        md = C.markdown(rows)
        self.assertIn('| gs_tapw2 |', md)
        self.assertIn('×100', md)   # A0 3.2e-8 / 3.2e-10, reference = last A row above


if __name__ == '__main__':
    unittest.main()
