#!/usr/bin/env python3
"""Read the fabric JTAG mailbox (gateware/verilog/jtag_mailbox.v) and PLL status over DirtyJTAG.

Runs on the Pi next to /home/pi/serdestool.py and /home/pi/dirtyjtag_engine.py (TASK-4999).
Only TAP instructions are used (STATUS_PLLx, WR/RD_SERDES_REGFILE): no user IO, no reset.

    python3 jtag_mailbox.py pll                 # PLL0..3 lock state
    python3 jtag_mailbox.py snap                # the snapshot: w16[0..5], w15[0..8]
    python3 jtag_mailbox.py raw 0x00 0x31       # raw regfile words

The FIRST regfile access freezes the fabric side (measured), so `snap` reads everything once;
a new snapshot needs a new configuration (`openFPGALoader -c dirtyJtag <bit> -r`).
"""
import argparse
import importlib.util
import sys
import time

sys.path.insert(0, "/home/pi")
from dirtyjtag_engine import DirtyJtagEngine  # noqa: E402
import usb.util  # noqa: E402

W16_ADDRS = (0x01, 0x03, 0x08, 0x0A, 0x31, 0x35)
W15_ADDRS = (0x30, 0x32, 0x33, 0x34, 0x36, 0x37, 0x38, 0x3A, 0x3B)
PLL_STATES = {0: "IDLE", 1: "LOCK_IN", 2: "LOCKED", 3: "FAST_LOCK"}


def load_tool():
    spec = importlib.util.spec_from_file_location("serdestool", "/home/pi/serdestool.py")
    st = importlib.util.module_from_spec(spec)
    sys.modules["serdestool"] = st
    spec.loader.exec_module(st)
    st.args = argparse.Namespace(idx=0)
    eng = DirtyJtagEngine(freq_khz=6000)
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        tool = st.JtagTool(eng)
    return eng, tool


def rd(tool, addr):
    tool.wr_serdes_regfile(addr=addr, data=0, mask=0, wren=0)
    return int(tool.rd_serdes_regfile())


def wr(tool, addr, data):
    tool.wr_serdes_regfile(addr=addr, data=data, mask=0xFFFF, wren=1)
    tool.rd_serdes_regfile()


def pll(tool):
    out = []
    for p in range(4):
        tool.write_ir(__import__("serdestool").BitSequence(("011100", "011101", "011110", "011111")[p], msb=True))
        v = int(tool.read_dr(17))
        tool._engine.go_idle()
        out.append("PLL%d=0x%05X %s%s" % (p, v, PLL_STATES[(v >> 12) & 3], " OVF" if v & 1 else ""))
    return " ".join(out)


def snap(tool):
    """Returns (consistent, seq, w16 list, w15 list, packed int: w16 then w15, LSB first)."""
    t0 = rd(tool, 0x00)
    w16 = [rd(tool, a) for a in W16_ADDRS]
    w15 = [rd(tool, a) & 0x7FFF for a in W15_ADDRS]
    t1 = rd(tool, 0x39)
    packed, sh = 0, 0
    for w in w16:
        packed |= w << sh; sh += 16
    for w in w15:
        packed |= w << sh; sh += 15
    return t0 == t1, t0, w16, w15, packed


def decode_eth(w16, w15):
    """Layout of gateware/jtag_probe.py (EthJTAGProbe)."""
    f = w16[0]
    names = ["pll_tx", "pll_sys", "rst_sys", "rst_eth_tx", "rst_eth_rx", "phy_in_reset", "mdio_done",
             "link"]
    out = ["flags=0x%04X: %s speed=%d rxctl=%d last_err=%d" % (
        f, " ".join("%s=%d" % (n, (f >> i) & 1) for i, n in enumerate(names)), (f >> 8) & 3,
        (f >> 10) & 1, (f >> 11) & 1)]
    hi = lambda w: (w >> 8) & 0xFF
    lo = lambda w: w & 0xFF
    out.append("PHY frames: rx=%d tx=%d | MAC err: preamble=%d crc=%d | ARP rx=%d tx=%d" % (
        hi(w16[1]), lo(w16[1]), hi(w16[2]), lo(w16[2]), hi(w16[3]), lo(w16[3])))
    out.append("ICMP rx=%d tx=%d | MAC frames tx(into datapath)=%d rx(out of datapath)=%d" % (
        (w15[6] >> 7) & 0xFF, w15[6] & 0x7F, (w15[8] >> 7) & 0xFF, w15[8] & 0x7F))
    out.append("last PHY-RX frame: len=%d bytes0-3=%02X %02X %02X %02X b6-7=%02X(7b) %02X b8-9=%02X(7b) %02X b20-21=%02X(7b) %02X" % (
        w15[7], hi(w16[4]), lo(w16[4]), hi(w16[5]), lo(w16[5]),
        (w15[0] >> 8) & 0x7F, w15[0] & 0xFF, (w15[1] >> 8) & 0x7F, w15[1] & 0xFF,
        (w15[2] >> 8) & 0x7F, w15[2] & 0xFF))
    mhz = lambda v: 25.0 * v / 16384
    out.append("freq (vs 25 MHz osc): RXC=%.2f MHz eth_tx=%.2f MHz sys=%.2f MHz" % (
        mhz(w15[3]), mhz(w15[4]), mhz(w15[5])))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pll", "snap", "raw"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--eth", action="store_true", help="decode the EthJTAGProbe layout")
    a = ap.parse_args()
    eng, tool = load_tool()
    try:
        if a.cmd == "pll":
            print(pll(tool))
        elif a.cmd == "raw":
            for x in a.args:
                print("0x%02X = 0x%04X" % (int(x, 0), rd(tool, int(x, 0))))
        else:
            ok, seq, w16, w15, packed = snap(tool)
            print("SNAP %s seq=%04X" % ("OK" if ok else "INCONSISTENT", seq))
            print("w16: " + " ".join("%04X" % w for w in w16))
            print("w15: " + " ".join("%04X" % w for w in w15))
            print("packed=0x%X" % packed)
            if a.eth:
                print(decode_eth(w16, w15))
    finally:
        usb.util.release_interface(eng.dev, 0)


if __name__ == "__main__":
    main()
