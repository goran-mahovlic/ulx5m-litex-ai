#!/usr/bin/env python3
"""READ-ONLY link check for ONE board running serdes_dut (serdes_lb.v, K28.5 + D10.2).

    fpga-jtag gs run python3 serdes_link_check.py [--samples 50]

Counts how many RX_DATA reads decode to the transmitted pattern (DATA_OK), to the
polarity-inverted pattern (DATA_INVERTED), idle (IDLE_FF), zero or other. Exit 0 only if
every sample is DATA_OK. CDR/ALIGNED flags are printed but are NOT the verdict: they stay 1
while the far TX is in electrical idle (measured 26.09.2026)."""
import argparse
import collections
import sys

from loopback import loopback_line
from rx_decode import classify
from serdes_jtag import Serdes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--samples', type=int, default=50)
    a = ap.parse_args()
    sd = Serdes()
    c = collections.Counter(classify(sd.rx80()) for _ in range(a.samples))
    flags = ' '.join('%s=%d' % (n, sd.field(n)) for n in
                     ('PLL_LOCKED', 'RX_CDR_LOCKED', 'RX_BYTE_IS_ALIGNED', 'RX_POLARITY'))
    lb = sd.loopback()
    flags += '  ' + loopback_line(lb)
    ok = c['DATA_OK'] == a.samples and not lb['any_loopback']
    print('board=%s %s  rx: %s  -> %s' % (sd.board, flags,
          ' '.join('%s %d/%d' % (k, v, a.samples) for k, v in sorted(c.items())), 'PASS' if ok else 'FAIL'))
    sd.close()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
