#!/usr/bin/env python3
#
# TASK-5094: 100 Mb/s with the RX pins oversampled by gtx (gateware/gbe_phy.py Rgmii100OSCore).
#
# TX side as tb_rgmii100.py (nibbles at the rising TXC edges = the wire). The RX pins are driven as LEVELS in the gtx
# domain (125 MHz): RXC with periods of 4/5/6 gtx cycles (the PHY's recovered clock drifts against ours), RXD/RX_CTL
# changing at the RXC rise, optionally RX_CTL one sample late or early (pad-to-fabric skew on the A2). Every TX frame
# must come back byte-exact from the SFD on; a frame with a dropped RX_DV nibble must not arrive intact.
#
# Run: source tools/sbc_env.sh; python3 sim/tb_rgmii100_os.py   -> "ALL TESTS PASSED"

import os, sys, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateware"))

from migen import *
from gbe_phy import Rgmii100OSCore

PRE = [0x55]*7 + [0xD5]


def make_frames(rng):
    return [PRE + [rng.randrange(256) for _ in range(n)] for n in [60, 61, 64, 65, 100, 333, 64]]


def run(periods, ctl_skew, seed):
    rng = random.Random(seed)
    frames = make_frames(rng)
    dut = Rgmii100OSCore()
    wire, rx_out = [], []

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
            for _ in range(rng.randrange(0, 5)):
                yield

    def gtx():
        prev, nib, extra = 0, [], None
        t_rx, k, ph, per = 0, 0, 0, periods[0]
        hist = []                       # (ctl, dat) of the current nibble per gtx cycle, for the skew
        for cyc in range(40000):
            c, ctl, d = (yield dut.txc), (yield dut.tx_ctl), (yield dut.tx_dat)
            if c and not prev:
                wire.append((ctl, d))
            prev = c
            # RX: a new nibble starts every `per` cycles; RXC high for the first per//2 cycles of it
            if ph == 0:
                if cyc > 30000 and extra is None:
                    extra = []
                    for i, b in enumerate(PRE + [0x11]*64):
                        extra += [(0 if i == 30 else 1, b & 0xF), (1, b >> 4)]
                    extra += [(0, 0)]*20
                    k = 0
                if extra is not None:
                    cur = extra[k] if k < len(extra) else (0, 0)
                else:
                    j = k - 40              # lag behind the TX wire
                    cur = wire[j] if 0 <= j < len(wire) else (0, 0)
                k += 1
                per = periods[k % len(periods)]
            hist = (hist + [cur])[-3:]
            ctl_now = hist[-1 - ctl_skew][0] if ctl_skew > 0 and len(hist) > ctl_skew else cur[0]
            if ctl_skew < 0:                # RX_CTL one sample early: it already shows the next nibble's value
                nxt = (extra[k] if extra is not None and k < len(extra) else
                       (wire[k - 40] if extra is None and 0 <= k - 40 < len(wire) else (0, 0)))
                ctl_now = nxt[0] if ph == per - 1 else cur[0]
            yield dut.os_rxc.eq(1 if ph < per // 2 else 0)
            yield dut.os_ctl.eq(ctl_now)
            yield dut.os_dat.eq(cur[1])
            ph = (ph + 1) % per
            yield

    def sys_rx():
        cur = None
        yield dut.source.ready.eq(1)
        for _ in range(6300):
            if (yield dut.source.valid):
                b = yield dut.source.data
                if (yield dut.source.first):
                    cur = []
                cur.append(b)
                if (yield dut.source.last):
                    rx_out.append(cur)
                    cur = None
            yield

    run_simulation(dut, {"sys": [sys_tx(), sys_rx()], "gtx": gtx()}, clocks={"sys": 50, "gtx": 8})

    name = "periods %s ctl_skew %+d" % ("/".join(map(str, periods)), ctl_skew)
    exp = [f[7:] for f in frames]
    er = [0xD5] + [0x11]*64
    good = [f for f in rx_out if f[:3] != er[:3]]
    ok = good == exp and er not in rx_out
    if good != exp:
        print("[%s] RX got %d frames, expected %d" % (name, len(good), len(exp)))
        for i in range(min(len(good), len(exp))):
            if good[i] != exp[i]:
                print("  frame %d: len %d vs %d" % (i, len(good[i]), len(exp[i]))); break
    if er in rx_out:
        print("[%s] RX_ER frame delivered intact" % name)
    print("[%s] RX frames %d: %s" % (name, len(good), "PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    cases = [([5], 0), ([5, 5, 6, 5, 4], 0), ([5, 6, 5, 5, 4, 5], 1), ([5, 4, 5, 6], -1)]
    res = [run(p, sk, 5094 + i) for i, (p, sk) in enumerate(cases)]
    print("ALL TESTS PASSED" if all(res) else "TESTS FAILED")
    sys.exit(0 if all(res) else 1)
