import os, sys, unittest, importlib.util
H = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(H, '..'))
from ber_parse import FIELDS, parse, rate, ber

def mk(**kw):
    return 'B ' + ' '.join(('%0*X' % (b // 4, kw.get(n, 0))) for n, b in FIELDS) + '\r\n'

class P(unittest.TestCase):
    def test_same_layout_as_gateware(self):
        p = os.path.join(H, '..', '..', 'gateware', 'ber', 'gen_report_fmt.py')
        s = importlib.util.spec_from_file_location('g', p); g = importlib.util.module_from_spec(s); s.loader.exec_module(g)
        self.assertEqual(FIELDS, g.FIELDS)
        self.assertEqual(len(mk()), len(g.line_chars()))

    def test_parse_flags_cfg(self):
        d = parse(mk(flg=0x83, words=10**9, cfg=(0 << 5) | (1 << 4) | (3 << 2), pflg=0xC0))
        self.assertEqual((d['synced'], d['self_seen'], d['loss']), (1, 0, 3))
        self.assertEqual((d['psynced'], d['pself_seen']), (1, 1))
        self.assertEqual((d['loopback_sel'], d['rx_pol'], d['outdiv']), (0, 1, 4))
        self.assertEqual(d['words'], 10**9)

    def test_garbage(self):
        self.assertIsNone(parse('B 12 34'))
        self.assertIsNone(parse('hello'))

    def test_rate_300M(self):
        a = parse(mk(t25=0, tcnt=0)); b = parse(mk(t25=25_000_000, tcnt=3_750_000))
        self.assertAlmostEqual(rate(a, b, 'tcnt'), 300e6)
        a = parse(mk(t25=0xFFFFFF00, tcnt=0xFFFFFFF0)); b = parse(mk(t25=25_000_000 - 0x100, tcnt=3_750_000 - 0x10))
        self.assertAlmostEqual(rate(a, b, 'tcnt'), 300e6)          # 32-bit wrap

    def test_ber(self):
        self.assertEqual(ber(0, 10**9), (0.0, 3.0 / 4e10))
        self.assertEqual(ber(4, 10**9)[0], 1e-10)

if __name__ == '__main__':
    unittest.main()
