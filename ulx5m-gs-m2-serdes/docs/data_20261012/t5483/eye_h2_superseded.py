#!/usr/bin/env python3
"""TASK-5487: Manda's H2 (EYE_SCAN_ISTRAZIVANJE.md §2): is RX_EYE_MEAS EN (0x14[0]) an edge/level, counters 0x16..0x1D read too early?
Run in tools/: fpga-jtag m2 run python3 /home/pi/ulx5m-serdes/t5483/eye_h2.py"""
import sys, time
sys.path.insert(0, "/home/pi/ulx5m-serdes/tools")
from serdes_jtag import Serdes
sd = Serdes(); s = sd.s
R = lambda a: int(s.rd_regfile(a)); W = lambda a, d, m: s.wr_regfile(a, d, m)
cnt = lambda: [R(0x16 + i) for i in range(8)]
print('0x14 before', hex(R(0x14)), 'cnt', cnt())
W(0x14, 0, 0xFFFF); print('after write 0:', hex(R(0x14)))
W(0x14, 512 << 4, 0xFFF0); print('window 512, EN=0:', hex(R(0x14)))
for t in (0, 0.01, 0.1, 1, 5):
    W(0x14, 0, 1); W(0x14, 1, 1); time.sleep(t)
    print('edge 0->1 wait', t, hex(R(0x14)), cnt())
W(0x14, 0, 1); time.sleep(0.5); print('after EN=0', hex(R(0x14)), cnt())
sd.close()
