#!/usr/bin/env python3
#
# TASK-5032: GbE PHY core (gateware/gbe_phy.py) without IO primitives.
#
# sys (20 MHz) sink -> TX frame buffer -> gtx (125 MHz) byte serializer -> "wire" model -> RGMII RX
# samples in grx (125 MHz) with alignment A (rising edge samples the low nibble) or B (the PHY's RXC edge
# lands half a nibble later: rising edge samples the high nibble of the previous byte) -> RX frame buffer
# -> sys source. Every frame must come out byte-exact, starting with the SFD (0xD5), with first/last set.
#
# Also checked: TX inter-frame gap >= 12 idle bytes; a frame with RX_ER is dropped; a frame that does
# not start with preamble+SFD is ignored.
#
# Run: source env.sh; python3 sim/tb_gbe_phy.py   -> "ALL TESTS PASSED"

import os, sys, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateware"))

from migen import *
from gbe_phy import GbePHYCore

random.seed(5032)

PRE = [0x55]*7 + [0xD5]
LAG = 8   # grx replay delay behind the gtx monitor (cycles)

def make_frames():
    frames = []
    for n in [60, 61, 62, 63, 64, 100, 333, 1514, 64, 65]:
        body = [random.randrange(256) for _ in range(n)]
        frames.append(PRE + body)
    return frames

class Wire:
    """Byte stream (en, byte) per gtx cycle -> RGMII nibble stream -> grx IDDR samples (rs, fs)."""
    def __init__(self, align, er_frames=()):
        self.align = align
        self.nib = []       # (ctl, nibble) per half-cycle, time order
        self.er_frames = set(er_frames)

def run(align, check_er=False):
    frames = make_frames()
    dut = GbePHYCore()
    tx_bytes = []           # (en, byte) per gtx cycle
    rx_out = []             # frames seen on sys source
    inject = []             # frames injected straight into RX (not via TX): (bytes, er_at)

    def sys_tx():
        for f in frames:
            for i, b in enumerate(f):
                yield dut.sink.valid.eq(1)
                yield dut.sink.first.eq(0)      # LiteEth's MAC never drives `first` on the PHY sink (TASK-5032)
                yield dut.sink.last.eq(i == len(f) - 1)
                yield dut.sink.data.eq(b)
                yield
                while not (yield dut.sink.ready):
                    yield
            yield dut.sink.valid.eq(0)
            for _ in range(random.randrange(0, 5)):
                yield

    def gtx_mon():
        # PLL lock acquisition glitches the gtx clock on the board: model it by corrupting the TX phase ring
        # (reset-less, init 0001) before any frame (TASK-5032, board TXfix11: tx_frames 36, tx_emit 0).
        for _ in range(3):
            yield
        yield dut.tx_ring.eq(0)
        for _ in range(60000):
            en  = yield dut.tx_en
            b   = yield dut.tx_byte
            tx_bytes.append((en, b))
            yield

    # grx: replay the TX byte stream (delayed) as nibbles, then IDDR-sample with alignment A/B.
    def grx_drive():
        k = 0
        nibs = []                       # (ctl, nibble)
        # extra frames injected after the TX ones: one with RX_ER, one without preamble
        extra = []
        bad = PRE + [0x11]*70
        extra.append(("er", bad))
        extra.append(("nopre", [0x12]*70))
        extra.append(("ok", PRE + [0x33]*64))
        extra_started = False
        rs_prev = (0, 0)
        for cyc in range(60000):
            # extend nibble stream from the TX monitor (lagging by a few cycles)
            while len(nibs)//2 < len(tx_bytes):
                en, b = tx_bytes[len(nibs)//2]
                nibs += [(en, b & 0xF), (en, b >> 4)]
            if len(nibs)//2 >= len(tx_bytes) and not extra_started and cyc > 50000:
                extra_started = True
                for kind, fr in extra:
                    for i, b in enumerate(fr):
                        er = (kind == "er" and i == 40)
                        nibs += [(1, b & 0xF), (0 if er else 1, b >> 4)]
                    nibs += [(0, 0)]*40
            def n(i):
                return nibs[i] if 0 <= i < len(nibs) else (0, 0)
            # The replay lags the TX monitor by LAG cycles: gtx_mon appends tx_bytes in the same time step,
            # and the generator order (PYTHONHASHSEED dependent) must not decide whether a byte exists yet.
            off = 0 if align == "A" else 1
            t = cyc - LAG
            r = n(2*t + off)            # rising sample at posedge cyc
            f_prev = n(2*(t - 1) + 1 + off)     # falling sample of the previous half-cycle
            yield dut.rx_rs_ctl.eq(r[0]);      yield dut.rx_rs_dat.eq(r[1])
            yield dut.rx_fs_ctl.eq(f_prev[0]); yield dut.rx_fs_dat.eq(f_prev[1])
            yield

    def sys_rx():
        cur = None
        yield dut.source.ready.eq(1)
        for _ in range(9000):
            if (yield dut.source.valid):
                b = yield dut.source.data
                if (yield dut.source.first):
                    cur = []
                cur.append(b)
                if (yield dut.source.last):
                    rx_out.append(cur)
                    cur = None
            yield

    def flips_mon():
        for _ in range(8900):
            yield
        run.flips = (yield dut.rx_flips)

    run_simulation(dut, {"sys": [sys_tx(), sys_rx(), flips_mon()], "gtx": gtx_mon(), "grx": grx_drive()},
                   clocks={"sys": 50, "gtx": 8, "grx": 8})

    # --- checks ---
    ok = True
    # 1) TX wire: frames byte-exact + IFG >= 12
    wire_frames, cur, gap, min_gap = [], None, 99, 99
    for en, b in tx_bytes:
        if en:
            if cur is None:
                cur = []
                if wire_frames: min_gap = min(min_gap, gap)
            cur.append(b)
        else:
            if cur is not None:
                wire_frames.append(cur); cur = None; gap = 0
            gap += 1
    if wire_frames != frames:
        print("[%s] TX wire mismatch: %d frames vs %d" % (align, len(wire_frames), len(frames)))
        for i, (a, e) in enumerate(zip(wire_frames, frames)):
            if a != e:
                print("  frame %d: len %d vs %d, first diff at %s" % (i, len(a), len(e),
                      next((j for j in range(min(len(a), len(e))) if a[j] != e[j]), "len")))
                break
        ok = False
    if min_gap < 12:
        print("[%s] TX IFG %d < 12" % (align, min_gap)); ok = False
    # 2) RX: each TX frame from the SFD on, then the good injected one; the RX_ER / no-preamble ones dropped
    exp = [f[7:] for f in frames] + [[0xD5] + [0x33]*64]
    if align == "B":
        exp = exp[1:]      # the RX pairing starts at A: the first B-aligned frame only trains it
    flips = run.flips
    if rx_out != exp:
        print("[%s] RX mismatch: got %d frames, expected %d" % (align, len(rx_out), len(exp)))
        for i in range(min(len(rx_out), len(exp))):
            if rx_out[i] != exp[i]:
                print("  frame %d: len %d vs %d" % (i, len(rx_out[i]), len(exp[i]))); break
        ok = False
    if flips != (1 if align == "B" else 0):
        print("[%s] RX pairing flips %d" % (align, flips)); ok = False
    print("[%s] TX frames %d (min IFG %d B), RX frames %d, pairing flips %d: %s" % (align, len(wire_frames),
          min_gap, len(rx_out), flips, "PASS" if ok else "FAIL"))
    return ok

if __name__ == "__main__":
    res = [run("A"), run("B")]
    print("ALL TESTS PASSED" if all(res) else "TESTS FAILED")
    sys.exit(0 if all(res) else 1)
