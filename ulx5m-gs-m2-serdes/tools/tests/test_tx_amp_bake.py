"""OV_TX_AMP top parameter -> CC_SERDES TX_AMP (TASK-5531: lab39 recept upečen u bitstream).

lab39 set TX_AMP 12 on both TX over JTAG after every load. For a flash boot without JTAG the value has to be the
power-up value of the regfile, i.e. the CC_SERDES parameter. -1 (default) must keep the PROFILE value (31 in PROFILE 1),
so every older bit rebuilds byte for byte (checked: gs 36f09752, m2 b1b98a5d). Yosys elaboration only, no P&R.
"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_cdr_cki_param import CELLS, YOSYS, serdes_params


@unittest.skipUnless(os.path.exists(YOSYS) and os.path.exists(CELLS), 'yosys / gatemate cells_bb.v not found')
class TxAmpBake(unittest.TestCase):
    BASE = {'PROFILE': 1, 'TX_NEG': 1, 'N1': 1, 'N2': 5, 'N3': 5, 'OUTDIV': 2}

    def test_default_keeps_profile_amp(self):
        for top in ('gs', 'm2'):
            self.assertEqual(serdes_params(top, self.BASE)['TX_AMP'], 31, top)

    def test_amp12_reaches_the_serdes_and_nothing_else_moves(self):
        for top in ('gs', 'm2'):
            a, b = serdes_params(top, self.BASE), serdes_params(top, dict(self.BASE, OV_TX_AMP=12))
            self.assertEqual(b['TX_AMP'], 12, top)
            diff = sorted(k for k in a if a[k] != b[k])
            self.assertEqual(diff, ['TX_AMP'], top)

    def test_cdr_set_acc_power_up_is_zero(self):
        # the lab39 SET_ACC 2->0 pulse ends at 0 = the bitstream value; with CKI 0 the frequency integrator is off
        for top in ('gs', 'm2'):
            p = serdes_params(top, dict(self.BASE, OV_TX_AMP=12))
            self.assertEqual((p['RX_CDR_SET_ACC_CONFIG'], p['RX_CDR_CKI'], p['RX_CDR_FREQ_ACC']), (0, 0, 0), top)


if __name__ == '__main__':
    unittest.main()
