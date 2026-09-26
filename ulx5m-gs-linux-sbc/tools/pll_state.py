#!/usr/bin/env python3
"""TASK-4999: robust PLL flags (OUT 100 MHz, '0' = stopped ref). 1 = LOCKED (status bits 13:12 == 2).
   python3 pll_state.py [seconds]"""
import sys, time
sys.path.insert(0, "/tmp"); sys.path.insert(0, "/home/pi")
import jtag_mailbox as jm
import pll_serial_rx as pr
T = float(sys.argv[1]) if len(sys.argv) > 1 else 4
eng, t = jm.load_tool(); st = sys.modules["serdestool"]
res = {p: [] for p in range(4)}
t0 = time.time()
try:
    while time.time() - t0 < T:
        for p in range(4):
            res[p].append(pr.status(t, st, p))
finally:
    jm.usb.util.release_interface(eng.dev, 0)
for p in range(4):
    v = res[p]; lk = sum(1 for x in v if ((x >> 12) & 3) == 2)
    ft = [(x >> 2) & 0x3FF for x in v]
    print("PLL%d: LOCKED %d/%d  ft %03X..%03X  last=0x%05X -> %s" % (p, lk, len(v), min(ft), max(ft), v[-1],
          "1" if lk == len(v) else "0" if lk == 0 else "MIXED"))
