#!/usr/bin/env python3
"""TASK-4999: JTAG bit-error test over the DirtyJTAG bulk XFER path (the path openFPGALoader loads
bitstreams with). IR = BYPASS (all ones), random TDI through the 1-bit bypass register, TDO must equal
TDI delayed by one bit.  python3 jtag_bert.py <khz> <kbytes>"""
import sys, os, random
sys.path.insert(0, "/home/pi")
import usb.util
from dirtyjtag_engine import DirtyJtagEngine, CMD_XFER, CMD_STOP, CMD_FREQ
from pyftdi.bits import BitSequence
khz = int(sys.argv[1]); kb = int(sys.argv[2])
e = DirtyJtagEngine(freq_khz=khz)
try:
    e.write_ir(BitSequence(0x3F, length=6))      # BYPASS
    e._goto_shift_dr()
    rnd = random.Random(khz)
    tx_bits, rx_bits = [], []
    CH = 240                                      # bits per XFER (30 bytes)
    for _ in range(kb * 1024 * 8 // CH):
        data = bytes(rnd.randrange(256) for _ in range(CH // 8))
        e._write(bytes([CMD_XFER, CH]) + data + bytes(32 - len(data)) )
        r = bytes(e._read(32))[:CH // 8]
        for byte_tx, byte_rx in zip(data, r):
            for b in range(7, -1, -1):           # DirtyJTAG shifts MSB first
                tx_bits.append((byte_tx >> b) & 1); rx_bits.append((byte_rx >> b) & 1)
    e._tms_seq([1, 1, 0]); e._state = 'RTI'
finally:
    usb.util.release_interface(e.dev, 0)
best = None
for d in range(0, 4):
    n = len(tx_bits) - d
    err = sum(1 for i in range(n) if rx_bits[i + d] != tx_bits[i])
    best = (err, d, n) if best is None or err < best[0] else best
print("f=%d kHz: %d bits, delay %d, bit errors %d (BER %.2e)" % (khz, best[2], best[1], best[0], best[0] / best[2]))
