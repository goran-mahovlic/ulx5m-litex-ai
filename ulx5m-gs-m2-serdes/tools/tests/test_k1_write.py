"""TASK-5559 K1: k1_write.Steps on fake regfiles (one with H-a write protection, one plain RAM)."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab'))
import k1_write as K  # noqa: E402


class Fake:
    """Regfile: 0x03 = 0xA3A3, 0x04 = 0x2101 (EN_EQA 1, LOCKED 1, OFFSET 1). protect: CKP fields drop writes while
    EN_EQA=1. strobe_clears: a write with a W/C bit set in 0x2B clears the whole 0x2B word."""
    def __init__(self, protect, strobe_clears=False):
        self.m = {0x01: 0x0063, 0x03: 0xA3A3, 0x04: 0x2101, 0x2B: 0x0000}
        self.protect, self.strobe_clears = protect, strobe_clears

    def rd(self, a):
        return self.m.get(a, 0)

    def wr(self, a, d, m):
        if self.protect and a in (0x03, 0x04) and (self.m[0x04] >> 8) & 1:
            m &= ~0x00FF if a == 0x04 else 0
        if a == 0x2B:
            if self.strobe_clears and d & m & 0x0AAA:
                self.m[a] = 0
                return
            m &= ~0x0AAA                                  # W/C bits read 0
        self.m[a] = (self.m.get(a, 0) & ~m) | (d & m)


def run(f):
    return K.Steps(f.rd, f.wr, sleep=lambda s: None, n=3).run()


class K1Write(unittest.TestCase):
    def test_protected_regfile_gives_h_a(self):
        r = run(Fake(protect=True))
        v = r['verdict']
        self.assertFalse(v['offset_writable_eqa1'])
        self.assertTrue(v['offset_writable_eqa0'] and v['lf_writable_eqa0'])
        self.assertEqual((v['offset_after_en1'], v['lf_after_en1']), ('held', 'held'))
        self.assertTrue(v['H_a'])
        self.assertTrue(v['ctl_0x01_writable'])
        self.assertEqual((r['end']['0x03'], r['end']['0x04']), ('0xA3A3', '0x2101'))   # put back

    def test_plain_ram_is_not_h_a(self):
        v = run(Fake(protect=False))['verdict']
        self.assertTrue(v['offset_writable_eqa1'])
        self.assertFalse(v['H_a'])

    def test_x2b_override_alone_vs_strobe(self):
        v = run(Fake(protect=True, strobe_clears=True))['verdict']
        self.assertTrue(v['x2b_ovr_alone'])
        self.assertFalse(v['x2b_ovr_with_strobe'])

    def test_hold(self):
        self.assertEqual(K.hold([2, 2, 2], 2, 0xFF), 'held')
        self.assertEqual(K.hold([2, 1, 1], 2, 0xFF), 'lost')
        self.assertEqual(K.hold([1, 1], 2, 0xFF), 'never')


if __name__ == '__main__':
    unittest.main()
