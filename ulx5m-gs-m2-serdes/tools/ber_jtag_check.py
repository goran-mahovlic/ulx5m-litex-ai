#!/usr/bin/env python3
"""READ-ONLY JTAG view of ONE board running ber_top.v: whose data does its receiver get?

    fpga-jtag m2 run python3 ber_jtag_check.py [--samples 20] [--expect peer|down]

PEER = K28.5 + id of the OTHER board (data came over the cable), SELF = own id (a loop),
IDLE_FF/ZERO/OTHER = no valid data. Also prints LOOPBACK_SEL. Exit 0 if the expectation holds:
  --expect peer : every sample PEER, LOOPBACK_SEL=0 and at least 2 distinct words (data moves)
  --expect down : no sample PEER"""
import argparse
import collections
import sys

from ber_rx80 import classify_ber
from loopback import loopback_line
from serdes_jtag import Serdes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--samples', type=int, default=20)
    ap.add_argument('--expect', choices=('peer', 'down'), default='peer')
    a = ap.parse_args()
    sd = Serdes()
    raw = [sd.rx80() for _ in range(a.samples)]
    lb = sd.loopback()
    c = collections.Counter(classify_ber(r, sd.board) for r in raw)
    moving = len(set(raw))
    if a.expect == 'peer':
        ok = c['PEER'] == a.samples and not lb['any_loopback'] and moving >= 2
    else:
        ok = c['PEER'] == 0
    print('board=%s PLL_LOCKED=%d CDR=%d  %s  rx: %s distinct=%d  expect=%s -> %s' % (
        sd.board, sd.field('PLL_LOCKED'), sd.field('RX_CDR_LOCKED'), loopback_line(lb),
        ' '.join('%s %d/%d' % (k, v, a.samples) for k, v in sorted(c.items())), moving, a.expect,
        'PASS' if ok else 'FAIL'))
    sd.close()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
