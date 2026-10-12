import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import eyeprobe as P

FIELDS = {'RX_CALIB_EN': (0x02, 0, 0), 'RX_CALIB_DONE': (0x02, 1, 1), 'RX_PRBS_OVR': (0x2A, 4, 4),
          'RX_PRBS_SEL': (0x2A, 7, 5), 'RX_PRBS_CNT_RESET': (0x2A, 9, 9), 'TX_PRBS_OVR': (0x40, 5, 5),
          'TX_PRBS_SEL': (0x40, 8, 6), 'TX_LOOPBACK_OVR': (0x40, 10, 10), 'TX_PMA_LOOPBACK': (0x40, 1, 0),
          'RX_PRBS_LOCKED': (0x1F, 15, 15), 'RX_PRBS_ERR_CNT': (0x1F, 14, 0), 'RX_CDR_LOCKED': (0x0B, 15, 15),
          'RX_EQA_LOCKED': (0x04, 13, 13)}


class Chip(object):
    """Fake regfile. rule(chip) -> True when an EN rising edge followed by >= delay s should fill the counters."""

    def __init__(self, rule=lambda c: False, delay=0.5, wc_works=True, bits31_rw=True, prbs_lock=True):
        self.r = dict((a, 0) for a in range(0x80))
        self.r[0x14] = 0x2001                       # EYE_EN=1 from the bitstream, window 0x200
        self.r[0x0B] = 1 << 15; self.r[0x04] = 1 << 13
        self.rule, self.delay, self.wc, self.b31, self.lock = rule, delay, wc_works, bits31_rw, prbs_lock
        self.t, self.edge_t, self.writes = 0.0, None, []

    def sleep(self, s):
        self.t += s
        if self.edge_t is not None and self.t - self.edge_t >= self.delay and self.rule(self):
            for i in range(8):
                self.r[0x16 + i] = 100 + i

    def rd_regfile(self, a):
        if a == 0x1F:
            return (1 << 15) if self.lock and self.r[0x2A] & 0x10 and self.r[0x40] & 0x20 else 0
        return self.r[a]

    def wr_regfile(self, a, d, m):
        self.writes.append((a, d, m))
        if a == 0x14 and not self.b31:
            m &= ~0x000E
        old = self.r[a]
        new = (old & ~m) | (d & m)
        if a == 0x14 and not old & 1 and new & 1:
            self.edge_t = self.t
            for i in range(8):
                self.r[0x16 + i] = 0
        if a == 0x02 and self.wc:
            new &= ~1
        self.r[a] = new & 0xFFFF

    def wr_fields(self, d):
        for k, v in d.items():
            a, h, l = FIELDS[k]; m = ((1 << (h - l + 1)) - 1) << l
            self.wr_regfile(a, v << l, m)

    def rd_fields(self, names):
        out = {}
        for k in names:
            a, h, l = FIELDS[k]
            out[k] = (self.rd_regfile(a) >> l) & ((1 << (h - l + 1)) - 1)
        return out


class A(object):
    window, skip, no_loopback = 512, [], False


def go(chip, **kw):
    a = A(); a.__dict__.update(kw)
    return P.run(P.Io(chip, sleep=chip.sleep), a)


class Probe(unittest.TestCase):
    def test_dead_chip_finds_nothing_and_restores_every_word(self):
        c = Chip()
        keep = dict((w, c.r[w]) for w in P.KEEP)
        o = go(c)
        self.assertEqual(o['found'], [])
        for w, m in P.KEEP.items():
            self.assertEqual(c.r[w] & m, keep[w] & m, hex(w))
        self.assertEqual(o['tests']['h7']['verdict'], 'W/C OK')

    def test_h2_needs_a_wait_after_a_fresh_edge(self):
        o = go(Chip(rule=lambda c: True, delay=1.0), skip=['h3', 'h1'])
        self.assertEqual(o['found'], ['h2'])
        st = o['tests']['h2']['steps']
        self.assertFalse(any(st[0]['cnt']))           # read at once (old E7) -> 0
        self.assertTrue(any(st[3]['cnt']))            # 1 s -> counters

    def test_h3_reports_the_mode(self):
        o = go(Chip(rule=lambda c: (c.r[0x14] >> 1) & 7 == 2), skip=['h1'])
        self.assertEqual(o['found'], ['h3'])
        self.assertIn('[2]', o['tests']['h3']['verdict'])

    def test_h3_read_only_bits(self):
        o = go(Chip(bits31_rw=False), skip=['h2', 'h1'])
        self.assertIn('read-only', o['tests']['h3']['verdict'])

    def test_h1_prbs_reference(self):
        o = go(Chip(rule=lambda c: c.r[0x2A] & 0x10), skip=['h2', 'h3'])
        self.assertEqual(o['found'], ['h1'])
        self.assertIn('H1 confirmed', o['tests']['h1']['verdict'])

    def test_h1_without_prbs_lock_is_not_a_result(self):
        o = go(Chip(prbs_lock=False), skip=['h2', 'h3'])
        self.assertIn('NOT LOCKED', o['tests']['h1']['verdict'])

    def test_h7_stuck_strobe(self):
        o = go(Chip(wc_works=False), skip=['h2', 'h3', 'h1'])
        self.assertIn('STUCK', o['tests']['h7']['verdict'])

    def test_no_wc_bit_is_written_back(self):
        c = Chip(); go(c)
        restore = c.writes[-len(P.KEEP):]
        self.assertFalse([w for w in restore if w[0] == 0x2A and w[2] & (1 << 9)])   # RX_PRBS_CNT_RESET


if __name__ == '__main__':
    unittest.main()
