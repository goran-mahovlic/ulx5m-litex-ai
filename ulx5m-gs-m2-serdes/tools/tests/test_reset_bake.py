"""Reset sequence + EQA loop fields baked into the bitstream (TASK-5559 K0-c, CALIBRATION_OPTIONS_20261017_v2 §3.1).

B0' = PROFILE 1 + AMP 12 + OV_CALIB 0 + OV_TX_SEL_PRE 0 (RX_EQA_CKP_OFFSET stays 1).
B1  = B0' + OV_WAIT_CDR_LOCK 1 (cc_serdes_params.vh had RX_WAIT_CDR_LOCK hard 0).
B2  = B1 + OV_EQA_RESET_TIME 16, OV_CDR_RESET_TIME 16, OV_PMA_RESET_TIME 8.
K4/K5 levers: OV_EN_EQA (B-static), OV_EQA_CKP_LF / OV_EQA_CKP_HF. -1 keeps every older bit identical.
"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_cdr_cki_param import CELLS, YOSYS, serdes_params

BASE = {'PROFILE': 1, 'TX_NEG': 1, 'N1': 1, 'N2': 5, 'N3': 5, 'OUTDIV': 2, 'OV_TX_AMP': 12}
B0 = dict(BASE, OV_CALIB=0, OV_TX_SEL_PRE=0)
B1 = dict(B0, OV_WAIT_CDR_LOCK=1)
B2 = dict(B1, OV_EQA_RESET_TIME=16, OV_CDR_RESET_TIME=16, OV_PMA_RESET_TIME=8)


def moved(a, b):
    return sorted(k for k in a if a[k] != b[k])


@unittest.skipUnless(os.path.exists(YOSYS) and os.path.exists(CELLS), 'yosys / gatemate cells_bb.v not found')
class ResetBake(unittest.TestCase):
    def test_default_keeps_old_reset_fields(self):
        p = serdes_params('gs', BASE)
        self.assertEqual((p['RX_WAIT_CDR_LOCK'], p['RX_EQA_RESET_TIME'], p['RX_CDR_RESET_TIME'], p['RX_PMA_RESET_TIME'],
                          p['RX_EN_EQA'], p['RX_EQA_CKP_LF'], p['RX_EQA_CKP_HF'], p['RX_EQA_CKP_OFFSET']),
                         (0, 3, 3, 3, 1, 0xA3, 0xA3, 1))

    def test_b0_moves_cal_and_pre_only(self):
        for top in ('gs', 'm2'):
            self.assertEqual(moved(serdes_params(top, BASE), serdes_params(top, B0)),
                             ['RX_CALIB_OVR', 'TX_CALIB_OVR', 'TX_SEL_PRE'], top)

    def test_b1_moves_wait_cdr_lock_only(self):
        for top in ('gs', 'm2'):
            a, b = serdes_params(top, B0), serdes_params(top, B1)
            self.assertEqual(moved(a, b), ['RX_WAIT_CDR_LOCK'], top)
            self.assertEqual(b['RX_WAIT_CDR_LOCK'], 1)

    def test_b2_moves_three_reset_times(self):
        for top in ('gs', 'm2'):
            a, b = serdes_params(top, B1), serdes_params(top, B2)
            self.assertEqual(moved(a, b), ['RX_CDR_RESET_TIME', 'RX_EQA_RESET_TIME', 'RX_PMA_RESET_TIME'], top)
            self.assertEqual((b['RX_EQA_RESET_TIME'], b['RX_CDR_RESET_TIME'], b['RX_PMA_RESET_TIME']), (16, 16, 8))

    def test_static_rx_and_ckp_levers(self):
        a = serdes_params('m2', B0)
        b = serdes_params('m2', dict(B0, OV_EN_EQA=0, OV_AFE_PEAK=15, OV_AFE_GAIN=8))
        self.assertEqual(moved(a, b), ['RX_AFE_GAIN', 'RX_AFE_PEAK', 'RX_EN_EQA'])
        c = serdes_params('gs', dict(B0, OV_EQA_CKP_LF=0x83, OV_EQA_CKP_HF=0xC3))
        self.assertEqual(moved(serdes_params('gs', B0), c), ['RX_EQA_CKP_HF', 'RX_EQA_CKP_LF'])


if __name__ == '__main__':
    unittest.main()
