#!/usr/bin/env python3
#
# TASK-5094: 100 Mb/s over the RGMII pins (gateware/gbe_phy.py Rgmii100Core), without IO primitives.
#
# sys (20 MHz) sink -> GbePHYCore TX under a 1-in-10 gtx clock enable -> nibble/TXC output stage (gtx 125 MHz)
# -> "wire": the nibble the PHY sees at every rising TXC edge -> 25 MHz RGMII RX stream (one nibble per RXC cycle,
# as the KSZ9031 sends it at 100 Mb/s) -> falling-edge samples in grx (40 ns) -> GbePHYCore RX under a 1-in-2 clock
# enable -> sys source. Every frame must come out byte-exact from the SFD on, with first/last.
#
# Checked as well: TXC is a 25 MHz square wave with 40 % duty and the TX nibble is stable from >= 16 ns before a
# rising TXC edge to the falling edge; inter-frame gap >= 12 bytes; both phases of the RX clock enable (the frame's
# SFD nibble lands on either); a frame with a dropped RX_DV nibble (RX_ER at 100 Mb/s) is not delivered intact.
#
# Run: source tools/sbc_env.sh; python3 sim/tb_rgmii100.py   -> "ALL TESTS PASSED"

import os, sys, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateware"))

from migen import *
from gbe_phy import Rgmii100Core

random.seed(5094)
PRE = [0x55]*7 + [0xD5]


def make_frames():
    return [PRE + [random.randrange(256) for _ in range(n)] for n in [60, 61, 64, 65, 100, 333, 64]]


def run(ce_phase, nib_lag, ctl_skew=0):
    frames = make_frames()
    dut = Rgmii100Core(rx_ce_phase=ce_phase)
    wire = []           # (ctl, nibble) sampled by the PHY at every rising TXC edge
    txc_log = []        # (txc, ctl, nib) per gtx cycle, for the timing checks
    rx_out = []

    def sys_tx():
        for f in frames:
            for i, b in enumerate(f):
                yield dut.sink.valid.eq(1)
                yield dut.sink.last.eq(i == len(f) - 1)
                yield dut.sink.data.eq(b)
                yield
                while not (yield dut.sink.ready):
                    yield
            yield dut.sink.valid.eq(0)
            for _ in range(random.randrange(0, 5)):
                yield

    def gtx_mon():
        prev = 0
        for _ in range(25000):
            c, ctl, d = (yield dut.txc), (yield dut.tx_ctl), (yield dut.tx_dat)
            txc_log.append((c, ctl, d))
            if c and not prev:
                wire.append((ctl, d))
            prev = c
            yield

    def grx_drive():
        # the PHY sends one nibble per RXC cycle; we hand the core the falling-edge sample of each cycle.
        # An injected frame with RX_ER (falling RX_CTL = DV ^ ER = 0 for one nibble) follows the TX frames.
        extra, extra_at = [], None
        for cyc in range(5000):
            t = cyc - 20 - nib_lag
            if extra_at is None and cyc > 3500:
                extra_at = cyc
                fr = PRE + [0x11]*64
                for i, b in enumerate(fr):
                    extra += [(0 if i == 30 else 1, b & 0xF), (1, b >> 4)]
                extra += [(0, 0)]*20
            if extra_at is not None:
                j = cyc - extra_at
                ctl, d = extra[j] if j < len(extra) else (0, 0)
            else:
                ctl, d = wire[t] if 0 <= t < len(wire) else (0, 0)
                if ctl_skew:        # RX_CTL sampled ctl_skew nibbles later than RXD (different pad -> fabric paths)
                    tc = t - ctl_skew
                    ctl = wire[tc][0] if 0 <= tc < len(wire) else 0
            yield dut.rx_ctl.eq(ctl)
            yield dut.rx_dat.eq(d)
            yield

    def sys_rx():
        cur = None
        yield dut.source.ready.eq(1)
        for _ in range(4000):
            if (yield dut.source.valid):
                b = yield dut.source.data
                if (yield dut.source.first):
                    cur = []
                cur.append(b)
                if (yield dut.source.last):
                    rx_out.append(cur)
                    cur = None
            yield

    run_simulation(dut, {"sys": [sys_tx(), sys_rx()], "gtx": gtx_mon(), "grx": grx_drive()},
                   clocks={"sys": 50, "gtx": 8, "grx": 40})

    ok = True
    name = "ce%d lag%d skew%+d" % (ce_phase, nib_lag, ctl_skew)
    # 1) TX wire (nibbles at rising TXC) -> bytes, IFG
    wire_frames, cur, gap, min_gap = [], None, 99, 99
    for i in range(0, len(wire) - 1, 2):
        (c0, lo), (c1, hi) = wire[i], wire[i + 1]
        if c0 and c1:
            if cur is None:
                cur = []
                if wire_frames:
                    min_gap = min(min_gap, gap)
            cur.append(lo | hi << 4)
        else:
            if c0 != c1:
                print("[%s] TX_CTL changes inside a byte at nibble %d" % (name, i)); ok = False
            if cur is not None:
                wire_frames.append(cur); cur = None; gap = 0
            gap += 1
    if wire_frames != frames:
        print("[%s] TX wire mismatch: %d frames vs %d" % (name, len(wire_frames), len(frames))); ok = False
    if min_gap < 12:
        print("[%s] TX IFG %d < 12" % (name, min_gap)); ok = False
    # 2) TXC 25 MHz, 40 % duty; data stable 2 cycles (16 ns) before a rising edge until the falling edge
    rises = [i for i in range(1, len(txc_log)) if txc_log[i][0] and not txc_log[i - 1][0]]
    periods = {rises[i + 1] - rises[i] for i in range(len(rises) - 1)}
    highs = {sum(1 for k in range(r, r + 5) if txc_log[k][0]) for r in rises[:-1]}
    if periods != {5} or highs != {2}:
        print("[%s] TXC periods %s, high cycles %s (want {5}, {2})" % (name, periods, highs)); ok = False
    unstable = sum(1 for r in rises[1:-1] if len({txc_log[k][1:] for k in range(r - 2, r + 2)}) != 1)
    if unstable:
        print("[%s] TX nibble not stable around %d rising TXC edges" % (name, unstable)); ok = False
    # 3) RX: all TX frames from the SFD on; the RX_ER frame must not arrive intact
    exp = [f[7:] for f in frames]
    er_frame = [0xD5] + [0x11]*64
    good = [f for f in rx_out if f[:3] != er_frame[:3]]     # the RX_ER frame may arrive truncated: not a TX frame
    if good != exp:
        print("[%s] RX mismatch: got %d frames, expected %d" % (name, len(good), len(exp)))
        for i in range(min(len(good), len(exp))):
            if good[i] != exp[i]:
                print("  frame %d: len %d vs %d" % (i, len(good[i]), len(exp[i]))); break
        ok = False
    if er_frame in rx_out:
        print("[%s] frame with RX_ER delivered intact" % name); ok = False
    print("[%s] TX frames %d (min IFG %d B), RX frames %d: %s" % (name, len(wire_frames), min_gap, len(good),
          "PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--skew":     # hypothesis check, not part of the pass criterion
        for sk in (1, -1):
            run(0, 0, sk)
        sys.exit(0)
    res = [run(p, lag) for p in (0, 1) for lag in (0, 1)]
    print("ALL TESTS PASSED" if all(res) else "TESTS FAILED")
    sys.exit(0 if all(res) else 1)
