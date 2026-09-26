#!/usr/bin/env python3
"""Decode gateware/pll_serial.py frames from PLL STATUS over DirtyJTAG (runs on the Pi).

    python3 pll_serial_rx.py scan                 # 4 x status, find the two serial PLLs
    python3 pll_serial_rx.py rx --clk 2 --dat 3 --frames 1 [--bytes 8] [--raw]

Level: fine-tune (status bits 11:2) > THRESH -> 1 (/2 ref, ~0x096), else 0 (/3 ref, ~0x018).
"""
import argparse
import sys
import time

sys.path.insert(0, "/home/pi")
import jtag_mailbox as jm  # noqa: E402  (loads serdestool + DirtyJTAG engine)

THRESH = 0x57
IR = ("011100", "011101", "011110", "011111")


def status(t, st, pll):
    t.write_ir(st.BitSequence(IR[pll], msb=True))
    v = int(t.read_dr(17))
    t._engine.go_idle()
    return v


STATE_MODE = False
STATE_THR = 0x100


def level(v):
    if STATE_MODE:
        # 1.1 V, ECONOMY meter (TASK-4999 fab3/s8): /2 -> ft 0x190..0x29x (all slots); /8 -> underflow
        # ft 0x004 while re-acquiring, but given ~0.5 s it LOCKS at ft ~0x07E (PLL0) -> threshold 0x100.
        return 1 if ((v >> 2) & 0x3FF) > STATE_THR else 0
    return 1 if ((v >> 2) & 0x3FF) > THRESH else 0


DIAG_REGS = [0x02, 0x03, 0x00, 0x01, 0x04, 0x05, 0x09, 0x0A, 0x1F, 0x13, 0x15, 0x1C]


def decode_diag(b):
    """target_eth.py add_diag(pll_serial=...) frame: passes, SYS, RXC, TX, REF (24 bit), flags, TXF, RXF,
    then 16-bit MDIO reads (PHYAD given by --diag-phyads, DIAG order)."""
    u24 = lambda i: b[i] | (b[i + 1] << 8) | (b[i + 2] << 16)
    f = b[13]
    mhz = lambda v: 12.5 * v / 2**20
    out = ["passes=%d SYS=%06X(%.2f MHz) RXC=%06X(%.2f) TX=%06X(%.2f) REF=%06X(%.2f)" % (
        b[0], u24(1), mhz(u24(1)), u24(4), mhz(u24(4)), u24(7), mhz(u24(7)), u24(10), mhz(u24(10))),
        "flags=%02X: L=%d S=%d D=%d PR=%d TXF=%d RXF=%d" % (f, f & 1, (f >> 1) & 3, (f >> 3) & 1,
                                                           (f >> 4) & 1, b[14], b[15])]
    regs = []
    for i, r in enumerate(DIAG_REGS):
        if 16 + 2 * i + 1 < len(b):
            regs.append("%02X=%04X" % (r, b[16 + 2 * i] | (b[17 + 2 * i] << 8)))
    out.append("MDIO " + " ".join(regs))
    return "\n".join(out)


def value2(v):
    """PLLStaticBits 4-level value: 3=/2 (~0x09A), 2=/2.5 (~0x046), 1=/3 (~0x01A), 0=/4 (~0x004)."""
    ft = (v >> 2) & 0x3FF
    return 3 if ft > 0x70 else 2 if ft > 0x30 else 1 if ft > 0x0E else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["scan", "rx", "bits"])
    ap.add_argument("--pll", type=int, default=0, help="bits: PLLn of pllbit0 (routed JSON NEXTPNR_BEL)")
    ap.add_argument("--clk", type=int, default=2)
    ap.add_argument("--dat", type=int, default=3)
    ap.add_argument("--frames", type=int, default=1)
    ap.add_argument("--bytes", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--state", action="store_true", help="level = PLL LOCKED state (1.1 V, div0=8)")
    ap.add_argument("--thr", default="0x100", help="--state: fine-tune threshold for level 1")
    ap.add_argument("--diag", action="store_true", help="decode the add_diag frame (34 bytes)")
    a = ap.parse_args()
    global STATE_MODE, STATE_THR
    STATE_MODE = a.state
    STATE_THR = int(a.thr, 0)
    eng, t = jm.load_tool()
    st = sys.modules["serdestool"]
    try:
        if a.cmd == "bits":
            vals = []
            for i in range(10):
                vals.append(status(t, st, a.pll))
                time.sleep(0.05)
            vs = [value2(v) for v in vals]
            v = max(set(vs), key=vs.count)
            print("PLL%d fine-tune %s -> value %d: bit1=%d bit0=%d (%d/%d samples agree)" % (
                a.pll, " ".join("%03X" % ((x >> 2) & 0x3FF) for x in vals[:5]), v, v >> 1, v & 1,
                vs.count(v), len(vs)))
            return
        if a.cmd == "scan":
            for i in range(int(a.timeout) if a.timeout < 100 else 6):
                print(" ".join("PLL%d=0x%05X(ft=%03X)" % (p, v, (v >> 2) & 0x3FF)
                               for p, v in ((p, status(t, st, p)) for p in range(4))))
                time.sleep(0.2)
            return
        bits, cur_clk, votes = [], None, []
        frames, t0 = 0, time.time()
        nbits_frame = 13 + 9 * a.bytes
        while frames < a.frames and time.time() - t0 < a.timeout:
            c = level(status(t, st, a.clk))
            d = level(status(t, st, a.dat))
            if cur_clk is None:
                cur_clk = c
            if c != cur_clk:                      # bit boundary: close the previous bit
                if votes:
                    bits.append(1 if 2 * sum(votes) > len(votes) else 0)
                    if a.raw:
                        print("bit %d (%d/%d)" % (bits[-1], sum(votes), len(votes)), flush=True)
                votes, cur_clk = [], c
                # search for sync + a complete frame
                s = "".join(map(str, bits))
                k = s.find("1" * 12 + "0")
                if k >= 0 and len(s) - k >= nbits_frame:
                    fb = s[k + 13:k + nbits_frame]
                    out, ok = [], True
                    for i in range(a.bytes):
                        g = fb[9 * i:9 * i + 9]
                        if g[0] != "0":
                            ok = False
                        out.append(int(g[1:][::-1], 2))
                    print("FRAME %s t=%.1fs bytes=%s" % ("OK" if ok else "BADSTART", time.time() - t0,
                          " ".join("%02X" % x for x in out)), flush=True)
                    if a.diag:
                        print(decode_diag(out), flush=True)
                    frames += 1
                    bits = bits[k + nbits_frame:]
            else:
                votes.append(d)
        if frames < a.frames:
            print("TIMEOUT after %.0fs, %d bits: %s" % (time.time() - t0, len(bits), "".join(map(str, bits))))
    finally:
        jm.usb.util.release_interface(eng.dev, 0)


if __name__ == "__main__":
    main()
