#!/usr/bin/env python3
# StickyLock (TASK-4999, new board): LiteX GateMatePLL resets its clock domain from the RAW
# USR_PLL_LOCKED. Measured on the new board (24.9.): ECONOMY sys PLL LOCKED only 24/29 JTAG samples,
# so every lock glitch reset sys -> restarted the PHY hardware reset counter + MDIO sequencer -> the
# KSZ9031 never got the 100FD writes and linked at 1G (RXC 125 MHz).
# Checks, in the PLL-free reference domain:
#   1) no lock while the raw flag chatters (stable run < stable_cycles),
#   2) lock after stable_cycles consecutive 1s,
#   3) once locked, later glitches (raw 0 pulses) do NOT clear it,
#   4) the PHY control (hw reset + MDIO sequencer) in that domain completes although the raw
#      lock keeps glitching -> MDIO frames are really shifted out.
#
# Run:  source ./env.sh && python3 sim/tb_sticky_lock.py
#
# SPDX-License-Identifier: BSD-2-Clause
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateware"))
from migen import *
from litex.gen.sim import run_simulation

from sticky_lock import StickyLock

N = 16
fails = []

def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)

def tb_lock():
    raw = Signal()
    dut = StickyLock(raw, stable_cycles=N)
    trace = []
    def gen():
        # 1) chatter: runs of 1 shorter than N
        for k in range(10):
            yield raw.eq(1)
            for _ in range(N // 2):
                yield
                trace.append(("chatter", (yield dut.locked)))
            yield raw.eq(0)
            yield
            trace.append(("chatter", (yield dut.locked)))
        # 2) stable
        yield raw.eq(1)
        for _ in range(N + 6):
            yield
            trace.append(("stable", (yield dut.locked)))
        # 3) glitches after lock
        for k in range(20):
            yield raw.eq(0)
            yield
            yield raw.eq(1)
            for _ in range(3):
                yield
                trace.append(("glitch", (yield dut.locked)))
    run_simulation(dut, gen())
    check(not any(v for p, v in trace if p == "chatter"), "no lock while raw lock chatters (runs < %d)" % N)
    st = [v for p, v in trace if p == "stable"]
    check(st[-1] == 1, "locked after %d stable cycles" % N)
    check(st.index(1) >= N - 1, "not earlier than %d cycles (first at %d)" % (N, st.index(1)))
    check(all(v for p, v in trace if p == "glitch"), "glitches after lock do not clear it")

def tb_phy_ctrl():
    # PHY control in the reference domain is independent of the (glitching) PLL lock.
    from mdio_sequencer import MDIOWriteSequencer
    from liteeth.phy.common import LiteEthPHYHWReset
    class Pads:
        def __init__(self):
            self.mdc = Signal(); self.mdio = Signal()
    class DUT(Module):
        def __init__(self):
            self.submodules.hw_reset = LiteEthPHYHWReset(cycles=50)
            self.submodules.seq = MDIOWriteSequencer(pads=None, clk_freq=25e6, phy_reset=self.hw_reset.reset,
                                                     settle_time=2e-6)
    dut = DUT()
    res = {}
    def gen():
        mdc_edges, prev = 0, 0
        for _ in range(60000):
            yield
            m = (yield dut.seq.mdc)
            if m and not prev:
                mdc_edges += 1
            prev = m
            if (yield dut.seq.done):
                break
        res["done"] = (yield dut.seq.done)
        res["edges"] = mdc_edges
    run_simulation(dut, gen())
    check(res["done"] == 1, "MDIO sequencer in the reference domain finishes (done=1)")
    check(res["edges"] >= 64 * 24, "all 24 write frames clocked out (%d MDC edges)" % res["edges"])

tb_lock()
tb_phy_ctrl()
print("RESULT:", "ALL PASS" if not fails else "%d FAIL" % len(fails))
sys.exit(1 if fails else 0)
