#!/usr/bin/env python3
"""TASK-4999: watch two PLL level flags over time. python3 pll_watch.py <seconds> [thr]
Prints one line per ~1 s: time, PLL0 level/ft, PLL1 level/ft."""
import sys, time, datetime
sys.path.insert(0, "/tmp"); sys.path.insert(0, "/home/pi")
import jtag_mailbox as jm
import pll_serial_rx as pr
T = float(sys.argv[1]); THR = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x100
eng, t = jm.load_tool(); st = sys.modules["serdestool"]
t0 = time.time(); last = 0
try:
    while time.time() - t0 < T:
        a = (pr.status(t, st, 0) >> 2) & 0x3FF; b = (pr.status(t, st, 1) >> 2) & 0x3FF
        if time.time() - last >= 1.0:
            last = time.time()
            print("%s P0=%d(%03X) P1=%d(%03X)" % (datetime.datetime.now().strftime("%H:%M:%S"),
                  a > THR, a, b > THR, b), flush=True)
finally:
    jm.usb.util.release_interface(eng.dev, 0)
