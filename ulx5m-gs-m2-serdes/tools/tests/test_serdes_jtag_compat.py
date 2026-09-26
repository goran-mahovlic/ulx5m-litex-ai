import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import serdes_jtag as sj


class F:
    def rd_regfile(self, idx, addr): return ('rd', idx, addr)
    def wr_regfile(self, idx, addr, data, mask): return ('wr', idx, addr, data, mask)


class Compat(unittest.TestCase):
    """serdestool 56aa48b put idx first; our tools call without idx, upstream code calls with it."""
    def setUp(self):
        self.f = F(); sj._idx0_compat(self.f)

    def test_our_style(self):
        self.assertEqual(self.f.rd_regfile(addr=0x5C), ('rd', 0, 0x5C))
        self.assertEqual(self.f.wr_regfile(addr=1, data=2, mask=3), ('wr', 0, 1, 2, 3))

    def test_upstream_style(self):
        self.assertEqual(self.f.rd_regfile(0, addr=0x5C), ('rd', 0, 0x5C))
        self.assertEqual(self.f.rd_regfile(0, 0x14), ('rd', 0, 0x14))
        self.assertEqual(self.f.wr_regfile(idx=0, addr=1, data=2, mask=3), ('wr', 0, 1, 2, 3))


if __name__ == '__main__':
    unittest.main()
