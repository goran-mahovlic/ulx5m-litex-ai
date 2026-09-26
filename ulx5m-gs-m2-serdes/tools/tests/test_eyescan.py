import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import eyescan as E


class Codes(unittest.TestCase):
    def test_signed5(self):
        self.assertEqual(E.s5_code(-16), 0x10); self.assertEqual(E.s5_code(15), 0x0F); self.assertEqual(E.s5_code(-1), 0x1F)
        for v in range(-16, 16):
            self.assertEqual(E.s5_value(E.s5_code(v)), v)
        with self.assertRaises(ValueError):
            E.s5_code(16)

    def test_signed6(self):
        for v in range(-32, 32):
            self.assertEqual(E.s6_value(E.s6_code(v)), v)

    def test_register_words(self):
        # TH_MON2 in 0x05[10:6]; its override is 0x06[11] (vendor map serdestool 56aa48b: RX_TH_MON2_OVR +
        # RX_AFE_OFFSET_OVR), NOT 0x05[11] (unused) - TUNING_5G.md §5.1. MON_PH_OFFSET 0x15[5:0]; window 0x14[15:4]
        self.assertEqual(E.th2_write(-3), (0x05, 0x1D << 6, 0x07C0))
        self.assertEqual(E.th2_ovr_write(1), (0x06, 1 << 11, 0x0800))
        self.assertEqual(E.th2_ovr_write(0), (0x06, 0, 0x0800))
        self.assertEqual(E.ph_write(-1), (0x15, 0x3F, 0x3F))
        self.assertEqual(E.start_write(512), (0x14, (512 << 4) | 1, 0xFFF1))

    def test_scan_prep(self):
        # the monitor runs only with DFE adaption on and EQA_LOCK_CFG bit1 (select monitor output for capturing)
        self.assertEqual(E.scan_prep({'RX_EN_EQA': 0, 'RX_EQA_LOCK_CFG': 0xC}), {'RX_EN_EQA': 1, 'RX_EQA_LOCK_CFG': 0xE})
        self.assertEqual(E.scan_prep({'RX_EN_EQA': 1, 'RX_EQA_LOCK_CFG': 0xE}), {})

    def test_counts(self):
        words = [10, 1, 20, 2, 30, 3, 40, 4]      # 0x16..0x1D
        c = E.counts(words)
        self.assertEqual(c['11S'], (10, 1)); self.assertEqual(c['110S'], (40, 4))
        self.assertEqual(E.point_ber(c), (1 + 2 + 3 + 4) / 110.0)
        self.assertEqual(E.point_ber(E.counts([0] * 8)), None)


class SweepProcedure(unittest.TestCase):
    # TUNING_5G.md §3 sweep procedure: after every JTAG field write re-run termination calibration (W/C bits
    # 0x3C[0], 0x02[0]) and reset the DFE through 0x2B (EQA_RESET_OVR + EQA_RESET, then release the override)
    def test_recal_steps_dfe(self):
        self.assertEqual(E.recal_steps(), [{'TX_CALIB_EN': 1}, {'RX_CALIB_EN': 1},
                                           {'RX_EQA_RESET_OVR': 1, 'RX_EQA_RESET': 1}, {'RX_EQA_RESET_OVR': 0}])

    def test_recal_steps_rx(self):
        self.assertEqual(E.recal_steps(rx=True)[2:], [{'RX_RESET_OVR': 1, 'RX_RESET': 1}, {'RX_RESET_OVR': 0}])


class Health(unittest.TestCase):
    GOOD = {'PLL_LOCKED': 1, 'PLL_CAP_FT_OF': 0, 'PLL_CAP_FT_UF': 0, 'PLL_BISC_TIMER_DONE': 1, 'PLL_BISC_CP_VALID': 1,
            'RX_CALIB_DONE': 1, 'TX_CALIB_DONE': 1, 'RX_CDR_LOCKED': 1, 'RX_EQA_LOCKED': 1, 'RX_EN_EQA': 1}

    def test_all_good(self):
        v = E.health_verdict(self.GOOD, [100, 102, 99, 101])
        self.assertEqual(v['problems'], []); self.assertEqual(v['freq_acc_span'], 3)

    def test_flags(self):
        bad = dict(self.GOOD, PLL_CAP_FT_OF=1, TX_CALIB_DONE=0)
        self.assertEqual(E.health_verdict(bad, [5, 5])['problems'], ['PLL_CAP_FT_OF', 'TX_CALIB_DONE=0'])

    def test_eqa_lock_only_matters_with_dfe_on(self):
        self.assertEqual(E.health_verdict(dict(self.GOOD, RX_EN_EQA=0, RX_EQA_LOCKED=0), [1])['problems'], [])
        self.assertEqual(E.health_verdict(dict(self.GOOD, RX_EQA_LOCKED=0), [1])['problems'], ['RX_EQA_LOCKED=0'])

    def test_freq_acc_signed(self):
        # RX_CDR_FREQ_ACC_VAL is 15 bit two's complement: 0x7FFF = -1, so -1..+1 is a span of 2, not 32766
        self.assertEqual(E.health_verdict(self.GOOD, [0x7FFF, 1])['freq_acc_span'], 2)


class Margin(unittest.TestCase):
    def grid(self, open_ph, open_th):
        # open eye: zero errors inside the box, 50 % errors outside
        pts = {}
        for th in range(-8, 8):
            for ph in range(-16, 16):
                bad = not (open_ph[0] <= ph <= open_ph[1] and open_th[0] <= th <= open_th[1])
                pts[(th, ph)] = {k: ((500, 500) if bad else (1000, 0)) for k in E.CLASSES}
        return pts

    def test_open_eye(self):
        m = E.margin(self.grid((-5, 6), (-3, 2)), target=1e-3)
        self.assertEqual(m['width_codes'], 12); self.assertEqual(m['height_codes'], 6)
        self.assertEqual(m['center_phase'], 0)

    def test_closed_eye(self):
        m = E.margin(self.grid((99, 99), (99, 99)), target=1e-3)
        self.assertEqual(m['width_codes'], 0); self.assertEqual(m['height_codes'], 0)

    def test_zero_error_floor(self):
        # a point with 0 errors in N samples counts as BER < 1/N, below the target when N is large
        m = E.margin(self.grid((-2, 2), (-1, 1)), target=1e-2)
        self.assertEqual(m['width_codes'], 5)


if __name__ == '__main__':
    unittest.main()
