#!/usr/bin/env python3
# StickyLock (TASK-4999, new board): LiteX GateMatePLL resets its clock domain from the RAW
# USR_PLL_LOCKED. Measured on the new board (24.9.): ECONOMY sys PLL LOCKED only 24/29 JTAG samples,
# so every lock glitch reset sys -> restarted the PHY hardware reset counter + MDIO sequencer -> the
# KSZ9031 never got the 100FD writes and linked at 1G (RXC 125 MHz).
# Checks, in the PLL-free reference domain:
#   1) no lock while the raw flag chatters (stable run < stable_cycles),
#   2) lock after stable_cycles consecutive 1s,
#   3) once locked, later glitches (raw 0 pulses) do NOT clear it.
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

tb_lock()
print("RESULT:", "ALL PASS" if not fails else "%d FAIL" % len(fails))
sys.exit(1 if fails else 0)
