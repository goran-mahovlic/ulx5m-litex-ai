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
        # TH_MON2 in 0x05[10:6] + override bit 11; MON_PH_OFFSET in 0x15[5:0]; CFG window in 0x14[15:4]
        self.assertEqual(E.th2_write(-3), (0x05, (0x1D << 6) | (1 << 11), 0x0FC0))
        self.assertEqual(E.ph_write(-1), (0x15, 0x3F, 0x3F))
        self.assertEqual(E.start_write(512), (0x14, (512 << 4) | 1, 0xFFF1))

    def test_counts(self):
        words = [10, 1, 20, 2, 30, 3, 40, 4]      # 0x16..0x1D
        c = E.counts(words)
        self.assertEqual(c['11S'], (10, 1)); self.assertEqual(c['110S'], (40, 4))
        self.assertEqual(E.point_ber(c), (1 + 2 + 3 + 4) / 110.0)
        self.assertEqual(E.point_ber(E.counts([0] * 8)), None)


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
