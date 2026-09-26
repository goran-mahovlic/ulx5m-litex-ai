#!/usr/bin/env python3
"""TASK-4999: time level changes of PLL0/PLL1 flags against the Pi clock.
python3 pll_period.py <seconds> [thr]  -> per PLL: transitions, mean/min/max level duration"""
import sys, time
sys.path.insert(0, "/tmp"); sys.path.insert(0, "/home/pi")
import jtag_mailbox as jm
import pll_serial_rx as pr
T = float(sys.argv[1]); THR = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x100
eng, t = jm.load_tool(); st = sys.modules["serdestool"]
last = {0: None, 1: None}; edges = {0: [], 1: []}; t0 = time.time()
try:
    while time.time() - t0 < T:
        for p in (0, 1):
            lv = ((pr.status(t, st, p) >> 2) & 0x3FF) > THR
            if last[p] is not None and lv != last[p]:
                edges[p].append((time.time() - t0, int(lv)))
            last[p] = lv
finally:
    jm.usb.util.release_interface(eng.dev, 0)
for p in (0, 1):
    e = edges[p]
    # use rising->rising (full periods): relock delay is the same at every rising edge
    r = [x for x, v in e if v == 1]
    per = [b - a for a, b in zip(r, r[1:])]
    print("PLL%d: %d edges, rising %d, full period mean %.3f s (min %.3f max %.3f) -> f = 2^25/period = %.2f MHz" % (
        p, len(e), len(r), sum(per)/len(per) if per else 0, min(per) if per else 0, max(per) if per else 0,
        (2**25 / (sum(per)/len(per)) / 1e6) if per else 0))
