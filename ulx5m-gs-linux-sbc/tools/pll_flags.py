#!/usr/bin/env python3
"""TASK-4999: read PLLLevelBits flags (ECONOMY, ft > thr = 1) from PLL0/PLL1 status over JTAG.
    python3 pll_flags.py [seconds] [thr]   -> fraction of samples at 1 per PLL + ft range"""
import sys, time
sys.path.insert(0, "/tmp"); sys.path.insert(0, "/home/pi")
import jtag_mailbox as jm
import pll_serial_rx as pr
T = float(sys.argv[1]) if len(sys.argv) > 1 else 4
THR = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x100
eng, t = jm.load_tool(); st = sys.modules["serdestool"]
res = {0: [], 1: []}
t0 = time.time()
try:
    while time.time() - t0 < T:
        for p in (0, 1):
            res[p].append((pr.status(t, st, p) >> 2) & 0x3FF)
finally:
    jm.usb.util.release_interface(eng.dev, 0)
for p in (0, 1):
    v = res[p]; ones = sum(1 for x in v if x > THR)
    print("PLL%d: %d/%d high (ft %03X..%03X) -> %s" % (p, ones, len(v), min(v), max(v),
          "1" if ones == len(v) else "0" if ones == 0 else "MIXED"))
