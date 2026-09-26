#!/usr/bin/env python3
#
# Testbench for gateware/mdio_sequencer.py.
#
# Instantiates MDIOWriteSequencer with a short settle time, samples the MDIO
# line on every MDC rising edge (exactly what the PHY does), reassembles the
# clause-22 frames and checks:
#   1. frame count = len(phyads) * 3 writes,
#   2. every frame decodes as preamble/ST=01/OP=write/TA=10,
#   3. per PHY address, the write order is reg9=0x0000, reg4=0x0101, reg0=0x1200,
#   4. the bus is released (oe=0) between frames and after DONE,
#   5. nothing is shifted while phy_reset is asserted.
#
# Run:  python3 sim/tb_mdio_sequencer.py
#
# SPDX-License-Identifier: BSD-2-Clause

import sys
import os

from migen import *
from migen.sim import run_simulation

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateware"))
from mdio_sequencer import MDIOWriteSequencer, KSZ9031_100M_FD_WRITES, mdio_write_frame

CLK_FREQ = 1e6          # pretend sys clock (Hz); scaled down to keep the sim short
MDC_FREQ = 250e3        # -> half_div = 2 sys clocks per MDC half period
SETTLE   = 20e-6        # 20 sys clocks of settle
PHYADS   = [0, 3, 7]    # a representative strap subset keeps runtime low


def testbench(dut, phy_reset, results):
    # Hold the PHY in reset for a while; the sequencer must not start.
    yield phy_reset.eq(1)
    for _ in range(50):
        yield
        assert (yield dut.mdio_oe) == 0, "sequencer drove MDIO during PHY reset"
    yield phy_reset.eq(0)

    frames = []
    bits = []
    prev_mdc = 0
    gap_oe_seen_low = True
    for _ in range(40000):
        yield
        mdc = yield dut.mdc
        oe  = yield dut.mdio_oe
        if mdc and not prev_mdc:          # MDC rising edge = PHY sample point
            if oe:
                bits.append((yield dut.mdio_o))
            else:
                assert not bits or len(bits) == 64, \
                    "bus released mid-frame after %d bits" % len(bits)
        if not oe and len(bits) == 64:    # frame complete, bus released
            frames.append(int("".join(str(b) for b in bits), 2))
            bits = []
        prev_mdc = mdc
        if (yield dut.done):
            break
    assert (yield dut.done) == 1, "sequencer never reached DONE"
    assert (yield dut.mdio_oe) == 0, "bus not released after DONE"
    assert (yield dut.mdc) == 0, "MDC not idle-low after DONE"
    results.extend(frames)


def main():
    dut = MDIOWriteSequencer(
        pads        = None,
        clk_freq    = CLK_FREQ,
        phy_reset   = (phy_reset := Signal()),
        phyads      = PHYADS,
        mdc_freq    = MDC_FREQ,
        settle_time = SETTLE,
    )
    results = []
    run_simulation(dut, testbench(dut, phy_reset, results))

    expected = [mdio_write_frame(phyad, reg, data)
                for phyad in PHYADS
                for reg, data in KSZ9031_100M_FD_WRITES]
    n_ok = 0
    assert len(results) == len(expected), \
        "frame count %d != expected %d" % (len(results), len(expected))
    for i, (got, exp) in enumerate(zip(results, expected)):
        phyad = (got >> 23) & 0x1F
        reg   = (got >> 18) & 0x1F
        data  = got & 0xFFFF
        assert (got >> 32) == 0xFFFFFFFF,        "frame %d: bad preamble" % i
        assert (got >> 28) & 0xF == 0b0101,      "frame %d: not ST=01/OP=write" % i
        assert (got >> 16) & 0x3 == 0b10,        "frame %d: bad TA" % i
        assert got == exp, \
            "frame %d: phyad=%d reg=%d data=0x%04x != expected 0x%016x" % (
                i, phyad, reg, data, exp)
        n_ok += 1
    # Explicit register-order check per PHY address.
    per_ad = {ad: [] for ad in PHYADS}
    for got in results:
        per_ad[(got >> 23) & 0x1F].append(((got >> 18) & 0x1F, got & 0xFFFF))
    for ad in PHYADS:
        assert per_ad[ad] == KSZ9031_100M_FD_WRITES, \
            "phyad %d: wrong write order %r" % (ad, per_ad[ad])
    print("PASS: %d/%d MDIO write frames correct (phyads=%r; "
          "order reg9,reg4,reg0 verified; bus released between frames)"
          % (n_ok, len(expected), PHYADS))


if __name__ == "__main__":
    main()
