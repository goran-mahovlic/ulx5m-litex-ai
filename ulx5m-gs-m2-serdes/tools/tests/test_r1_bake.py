"""R1 recipe baked into the bitstream (TASK-5549, recipe from TASK-5542 chain4).

R1 = CAL0 (RX/TX_CALIB_OVR=1, RX/TX_CALIB_VAL=0) + TX_SEL_PRE 0 + RX_EQA_CKP_OFFSET 0, so far written over JTAG after
every load. New top parameters OV_CALIB (both RX and TX termination code, -1 = calibration result) and
OV_EQA_CKP_OFFSET (-1 = 1 as before) carry it into CC_SERDES; TX_SEL_PRE uses the existing OV_TX_SEL_PRE.
-1 must keep every older bit identical (only the CC_SERDES fields named here may move). Yosys elaboration only.
"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_cdr_cki_param import CELLS, YOSYS, serdes_params

R1 = {'OV_CALIB': 0, 'OV_TX_SEL_PRE': 0, 'OV_EQA_CKP_OFFSET': 0}
R1_FIELDS = ['RX_CALIB_OVR', 'RX_EQA_CKP_OFFSET', 'TX_CALIB_OVR', 'TX_SEL_PRE']   # *_CALIB_VAL stays 0


@unittest.skipUnless(os.path.exists(YOSYS) and os.path.exists(CELLS), 'yosys / gatemate cells_bb.v not found')
class R1Bake(unittest.TestCase):
    BASE = {'PROFILE': 1, 'TX_NEG': 1, 'N1': 1, 'N2': 5, 'N3': 5, 'OUTDIV': 2, 'OV_TX_AMP': 12}

    def test_default_keeps_calibration_and_offset(self):
        for top in ('gs', 'm2'):
            p = serdes_params(top, self.BASE)
            self.assertEqual((p['RX_CALIB_OVR'], p['TX_CALIB_OVR'], p['RX_EQA_CKP_OFFSET'], p['TX_SEL_PRE']),
                             (0, 0, 1, 5), top)

    def test_r1_moves_only_its_fields(self):
        for top in ('gs', 'm2'):
            a, b = serdes_params(top, self.BASE), serdes_params(top, dict(self.BASE, **R1))
            self.assertEqual(sorted(k for k in a if a[k] != b[k]), R1_FIELDS, top)
            self.assertEqual((b['RX_CALIB_OVR'], b['RX_CALIB_VAL'], b['TX_CALIB_OVR'], b['TX_CALIB_VAL']), (1, 0, 1, 0))
            self.assertEqual((b['TX_SEL_PRE'], b['RX_EQA_CKP_OFFSET'], b['TX_AMP']), (0, 0, 12), top)

    def test_calib_code_reaches_both_directions(self):
        p = serdes_params('gs', dict(self.BASE, OV_CALIB=4))
        self.assertEqual((p['RX_CALIB_OVR'], p['RX_CALIB_VAL'], p['TX_CALIB_OVR'], p['TX_CALIB_VAL']), (1, 4, 1, 4))


if __name__ == '__main__':
    unittest.main()
