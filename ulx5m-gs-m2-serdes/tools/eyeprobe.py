#!/usr/bin/env python3
"""One-shot probe for the dead RX_EYE_MEAS counters (TASK-5488, hypotheses H7/H2/H3/H1 of docs/EYE_SCAN_ISTRAZIVANJE.md).

No public tool starts the GateMate eye measurement (pu-cc gm_serdes_lb tc_eyemeas is an empty stub at 56aa48b, the
only fork / PR #1 adds nothing for the eye, TASK-5488 §6). This script runs the cheap hypothesis tests in one go on ONE
board, prints what happened and restores every word it touched:

    fpga-jtag m2 run python3 eyeprobe.py --out probe_m2.json              # H7 + H2 + H3 + H1 (near-end PMA loopback)
    fpga-jtag m2 run python3 eyeprobe.py --skip h1 --out probe_m2.json    # leave the link alone (no PRBS, no loopback)

    H7  w/c strobe works over JTAG at all (RX_CALIB_EN self-clears)
    H2  0x14[0] is a level/edge: fresh 0->1 edge, wait 0..5 s, then EN=0, counters after every step
    H3  0x14[3:1] writable -> repeat the H2 edge for mode m = 1..7 (tc_eyemeas has monitor=2, sel_tap=0)
    H1  hard PRBS-7 checker as the reference: near-end PMA loopback + TX/RX PRBS-7, then the H2 edge; control without PRBS

Verdict line per test: COUNTERS!=0 is the one we are looking for. Python 3.7 (Pi, armv7l), no numpy.
Needs SERDES_TESTMODE=1 and a bitstream with EYE_EN=0 (the ber_* bits, not the E7 one).
"""
import argparse
import json
import sys
import time

CNT0 = 0x16                                   # 0x16..0x1D correct/wrong 11S, 00S, 001S, 110S
EYE = 0x14                                    # [0] RX_EYE_MEAS_EN, [3:1] ?, [15:4] window
H2_WAITS = (0, 0.01, 0.1, 1, 5)
# words the probe may change and the bits it restores (w/c bits are never written back)
KEEP = {0x04: 0xFFFF, 0x05: 0xFFFF, 0x06: 0xFFFF, 0x14: 0xFFFF, 0x15: 0xFFFF,
        0x2A: 0x00F0,                         # RX_PRBS_OVR [4], RX_PRBS_SEL [7:5]
        0x40: 0x05E3}                         # TX_PMA_LOOPBACK [1:0], TX_PRBS_OVR [5], TX_PRBS_SEL [8:6], TX_LOOPBACK_OVR [10]


class Io(object):
    """R/W/fields/sleep over a serdestool.SerdesTool; the tests only see this, so they run against a fake in tests."""

    def __init__(self, s, sleep=time.sleep):
        self.s, self.sleep = s, sleep

    def R(self, a):
        return int(self.s.rd_regfile(a))

    def W(self, a, d, m):
        self.s.wr_regfile(a, d, m)

    def fset(self, d):
        self.s.wr_fields(d)

    def fget(self, names):
        return self.s.rd_fields(names)

    def cnt(self):
        return [self.R(CNT0 + i) for i in range(8)]


def nonzero(c):
    return any(c)


def edge(io, window, mode=0, wait=1.0):
    """EN 0 -> window/mode -> EN 1 (fresh rising edge), wait, read 0x14 and counters."""
    io.W(EYE, 0, 0x0001)
    io.W(EYE, (window << 4) | ((mode & 7) << 1), 0xFFFE)
    io.W(EYE, 1, 0x0001)
    io.sleep(wait)
    return {'mode': mode, 'wait_s': wait, 'reg14': io.R(EYE), 'cnt': io.cnt()}


def h7(io):
    io.fset({'RX_CALIB_EN': 1})
    f = io.fget(['RX_CALIB_EN', 'RX_CALIB_DONE'])
    return {'fields': f, 'verdict': 'W/C OK' if f['RX_CALIB_EN'] == 0 else 'W/C STUCK (strobes not executed?)'}


def h2(io, window):
    r = {'reg14_before': io.R(EYE)}
    io.W(EYE, 0, 0xFFFF)
    r['reg14_after_0'] = io.R(EYE)                 # 0 -> bit 0 is r/w (level); 1 -> pure status
    r['steps'] = [edge(io, window, 0, t) for t in H2_WAITS]
    io.W(EYE, 0, 0x0001)
    io.sleep(0.5)
    r['after_en0'] = {'reg14': io.R(EYE), 'cnt': io.cnt()}
    hit = any(nonzero(s['cnt']) for s in r['steps']) or nonzero(r['after_en0']['cnt'])
    r['en_is_level'] = (r['reg14_after_0'] & 1) == 0 and all(s['reg14'] & 1 for s in r['steps'])
    r['verdict'] = 'COUNTERS!=0' if hit else 'counters 0'
    return r


def h3(io, window):
    io.W(EYE, 0b1110, 0x000E)
    rb = io.R(EYE)
    r = {'reg14_readback': rb, 'bits31_writable': (rb >> 1) & 7 == 7, 'modes': []}
    if r['bits31_writable']:
        r['modes'] = [edge(io, window, m, 1.0) for m in range(1, 8)]
    io.W(EYE, 0, 0x000F)
    hit = [m['mode'] for m in r['modes'] if nonzero(m['cnt'])]
    r['verdict'] = ('COUNTERS!=0 for mode %s' % hit) if hit else ('counters 0' if r['bits31_writable']
                                                                 else '[3:1] read-only -> H3 out')
    return r


PRBS_ON = {'TX_LOOPBACK_OVR': 1, 'TX_PMA_LOOPBACK': 1, 'TX_PRBS_OVR': 1, 'TX_PRBS_SEL': 1,
           'RX_PRBS_OVR': 1, 'RX_PRBS_SEL': 1}
LINK = ['RX_PRBS_LOCKED', 'RX_PRBS_ERR_CNT', 'RX_CDR_LOCKED', 'RX_EQA_LOCKED']


def h1(io, window, loopback=True):
    on = dict(PRBS_ON) if loopback else {k: v for k, v in PRBS_ON.items() if 'LOOPBACK' not in k}
    io.fset(on)
    io.sleep(0.5)
    io.fset({'RX_PRBS_CNT_RESET': 1})
    io.sleep(0.2)
    r = {'loopback': loopback, 'link_prbs': io.fget(LINK)}
    r['prbs'] = edge(io, window, 0, 1.0)
    io.fset({'RX_PRBS_OVR': 0})                   # control: same edge, checker off
    io.sleep(0.2)
    r['control'] = edge(io, window, 0, 1.0)
    p, c = nonzero(r['prbs']['cnt']), nonzero(r['control']['cnt'])
    if not r['link_prbs']['RX_PRBS_LOCKED']:
        r['verdict'] = 'PRBS NOT LOCKED - H1 not tested'
    elif p and not c:
        r['verdict'] = 'COUNTERS!=0 only with PRBS -> H1 confirmed'
    elif p:
        r['verdict'] = 'COUNTERS!=0 with and without PRBS -> H1 not needed'
    else:
        r['verdict'] = 'counters 0'
    return r


TESTS = (('h7', lambda io, a: h7(io)), ('h2', lambda io, a: h2(io, a.window)),
         ('h3', lambda io, a: h3(io, a.window)), ('h1', lambda io, a: h1(io, a.window, not a.no_loopback)))


def run(io, a):
    """All selected tests in order H7 -> H2 -> H3 -> H1 (H1 last: it is the only one that touches the link)."""
    keep = dict((w, io.R(w)) for w in KEEP)
    out = {'keep': keep, 'tests': {}}
    try:
        for name, fn in TESTS:
            if name in a.skip:
                continue
            t = time.time()
            out['tests'][name] = fn(io, a)
            out['tests'][name]['secs'] = round(time.time() - t, 2)
    finally:
        for w, m in KEEP.items():
            io.W(w, keep[w] & m, m)
    out['found'] = [n for n, r in out['tests'].items() if 'COUNTERS!=0' in r['verdict']]
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--window', type=int, default=512)
    p.add_argument('--skip', default='', help='comma list of h7,h2,h3,h1')
    p.add_argument('--no-loopback', action='store_true', help='H1 with the partner TX instead of near-end PMA loopback')
    p.add_argument('--no-recal', action='store_true', help='skip eyescan.do_recal after H1')
    p.add_argument('--out')
    a = p.parse_args(argv)
    a.skip = [x for x in a.skip.split(',') if x]
    from serdes_jtag import Serdes
    sd = Serdes()
    if sd.field('SERDES_TESTMODE') != 1:
        print('board=%s: SERDES_TESTMODE=0, regfile writes are ignored' % sd.board)
        return 1
    io = Io(sd.s)
    out = run(io, a)
    if 'h1' in out['tests'] and not a.no_recal:
        from eyescan import do_recal
        out['recal'] = do_recal(sd.s)
    out.update(board=sd.board, time=time.strftime('%F %T'), window=a.window)
    for n, r in out['tests'].items():
        print('%s board=%s %-3s %s  (%.1fs)' % ('!!' if n in out['found'] else '  ', sd.board, n.upper(), r['verdict'],
                                              r['secs']))
    if a.out:
        json.dump(out, open(a.out, 'w'), indent=1)
    sd.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
