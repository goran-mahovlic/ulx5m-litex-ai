#!/usr/bin/env python3
#
# Testbench for gateware/mdio_diag.py (TASK-4999).
#
# A behavioural KSZ9031 model on the MDIO line (samples on MDC rising edge, answers
# clause-22 reads at one PHYAD, drives TA=0 + data after the rising edge) checks that
# MDIODiagEngine:
#   1. writes reg9=0, reg4=0x0101, reg0=0x1200 before any read,
#   2. reads back the PHY ID and the written registers at the model's address with TA=0,
#   3. reports TA=1 / 0xFFFF (pull-up) at absent addresses,
#   4. reports drive_err=0 (FPGA-driven bits read back correctly),
#   5. keeps looping reads (passes > 1).
# Then checks that UARTLineDumper emits the template with hex fields filled in (8N1).
#
# Run:  python3 sim/tb_mdio_diag.py
#
# SPDX-License-Identifier: BSD-2-Clause

import sys, os

from migen import *
from migen.sim import run_simulation

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateware"))
from mdio_diag import MDIODiagEngine, UARTLineDumper, hexf

PHY_AD = 3
PHYADS = [0, 3]
REGS   = {0: 0x1140, 1: 0x7949, 2: 0x0022, 3: 0x1622, 4: 0x01E1, 5: 0x0000, 9: 0x0300,
          10: 0x0000, 31: 0x0000}


class Top(Module):
    def __init__(self):
        self.submodules.dut = MDIODiagEngine(None, clk_freq=1e6, phyads=PHYADS,
                                             mdc_freq=62.5e3, settle_time=20e-6)


def phy_model(dut, log, fails):
    regs = dict(REGS)
    ones, state, hdr = 0, "idle", []
    out_q = []               # values the PHY presents on the following sample slots
    phy_oe, phy_out = 0, 1
    prev_mdc = 0
    for _ in range(240000):
        oe = yield dut.mdio_oe
        o  = yield dut.mdio_o
        if oe and phy_oe:
            fails.append("bus contention")
        line = o if oe else (phy_out if phy_oe else 1)
        yield dut.mdio_i.eq(line)
        mdc = yield dut.mdc
        if mdc and not prev_mdc:
            b = line
            # PHY output changes right after the rising edge.
            if out_q:
                phy_oe, phy_out = 1, out_q.pop(0)
            else:
                phy_oe = 0
            if state == "idle":
                if b == 1:
                    ones += 1
                elif ones >= 32:
                    state, hdr = "st", [b]
                else:
                    ones = 0
            elif state == "st":
                hdr.append(b)
                if len(hdr) == 2 + 2 + 5 + 5:
                    op  = hdr[2]*2 + hdr[3]
                    ad  = int("".join(map(str, hdr[4:9])), 2)
                    reg = int("".join(map(str, hdr[9:14])), 2)
                    if op == 0b10:
                        if ad == PHY_AD:
                            v = regs.get(reg, 0)
                            # slot 46 Hi-Z (queue empty now), slot 47 = 0, then D15..D0
                            out_q = [None, 0] + [(v >> (15 - k)) & 1 for k in range(16)]
                        log.append(("r", ad, reg))
                        state, dcnt = "skip", 18
                    else:
                        state, data = "wdata", []
                        wad, wreg = ad, reg
            elif state == "wdata":
                data.append(b)
                if len(data) == 18:
                    v = int("".join(map(str, data[2:])), 2)
                    log.append(("w", wad, wreg, v))
                    if wad == PHY_AD:
                        regs[wreg] = v & ~0x0200 if wreg == 0 else v
                    state, ones = "idle", 0
            elif state == "skip":
                dcnt -= 1
                if dcnt == 0:
                    state, ones = "idle", 0
            if out_q and out_q[0] is None:
                out_q.pop(0)
                phy_oe = 0
        prev_mdc = mdc
        yield
        if (yield dut.passes) >= 2:
            break


def uart_tb(dut, template_text, got):
    bit = 4
    # wait for the start bit, then sample mid-bit
    for _ in range(200):
        if (yield dut.tx) == 0:
            break
        yield
    chars = []
    while len(chars) < len(template_text):
        for _ in range(bit // 2):
            yield
        assert (yield dut.tx) == 0, "bad start bit"
        v = 0
        for k in range(8):
            for _ in range(bit):
                yield
            v |= (yield dut.tx) << k
        for _ in range(bit):
            yield
        assert (yield dut.tx) == 1, "bad stop bit"
        chars.append(chr(v))
        for _ in range(bit * 3):
            if (yield dut.tx) == 0:
                break
            yield
    got.append("".join(chars))


def main():
    ok = True
    top = Top()
    dut = top.dut
    log, fails = [], []
    run_simulation(top, phy_model(dut, log, fails))
    res = {}
    def check(name, cond):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name)
        ok &= bool(cond)
    for i, (a, r) in enumerate(dut.reads):
        pass
    writes = [e for e in log if e[0] == "w"]
    first_read = next(i for i, e in enumerate(log) if e[0] == "r")
    check("writes before reads (6 writes)", len(writes) == 6 and all(e[0] == "w" for e in log[:first_read]))
    check("write order reg9,reg4,reg0", [(e[2], e[3]) for e in writes[:3]] == [(9, 0), (4, 0x0101), (0, 0x1200)])
    check("no bus contention", not fails)
    # results are sampled after the sim; re-run is not needed: read final values
    top2 = top
    vals = {}
    def reader():
        for i, (a, r) in enumerate(dut.reads):
            vals[(a, r)] = ((yield dut.results[i]), (yield dut.ta[i]))
        vals["derr"] = yield dut.drive_err
        vals["passes"] = yield dut.passes
    # run_simulation resets state, so collect inside a combined generator instead
    top = Top(); dut = top.dut; log2, fails2 = [], []
    def combined():
        yield from phy_model(dut, log2, fails2)
        yield from reader()
    run_simulation(top, combined())
    check("PHY ID at PHYAD 3 = 0022:1622 with TA=0",
          vals[(3, 2)] == (0x0022, 0) and vals[(3, 3)] == (0x1622, 0))
    check("reg4 readback 0x0101, reg9 readback 0x0000",
          vals[(3, 4)][0] == 0x0101 and vals[(3, 9)][0] == 0x0000)
    check("absent PHYAD 0 -> TA=1, 0xFFFF", vals[(0, 2)] == (0xFFFF, 1))
    check("drive_err == 0", vals["derr"] == 0)
    check("read loop repeats (passes >= 2)", vals["passes"] >= 2)

    # UART dumper
    class U(Module):
        def __init__(self):
            self.sig = Signal(16, reset=0xBEEF)
            self.submodules.dut = UARTLineDumper(4e5, ["ID=", *hexf(self.sig, 4), "\r\n"],
                                                 baud=1e5, period=10e-6)
    u = U(); got = []
    run_simulation(u, uart_tb(u.dut, "ID=BEEF\r\n", got))
    check("UART line = 'ID=BEEF\\r\\n' (got %r)" % got[0], got[0] == "ID=BEEF\r\n")
    print("RESULT:", "ALL PASS" if ok else "FAILURES")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
