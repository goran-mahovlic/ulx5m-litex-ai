#
# StickyLock: debounced, sticky PLL lock for GateMate (TASK-4999).
#
# LiteX GateMatePLL resets its clock domains from the RAW USR_PLL_LOCKED (it leaves
# USR_PLL_LOCKED_STDY unconnected, see docs/GATEMATE_CLOCKING.md, trap 2). On the ULX5M-GS the
# raw flag chatters (24.9.: ECONOMY sys PLL LOCKED in 24/29 JTAG samples), and every chatter
# re-reset the whole sys domain -- including the KSZ9031 hardware-reset counter and the MDIO
# sequencer, so the PHY never received its 100BASE-TX FD writes and linked at 1G.
#
# The raw flag is synchronised into the calling (PLL-free) domain, must stay 1 for
# `stable_cycles` consecutive cycles, and then stays 1 until that domain is reset
# (CC_USR_RSTN). A chattering indicator no longer resets running logic.
#
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen import LiteXModule


class StickyLock(LiteXModule):
    def __init__(self, raw_locked, stable_cycles):
        self.locked = Signal()

        # # #

        raw_s = Signal()
        self.specials += MultiReg(raw_locked, raw_s, "sys")
        cnt = Signal(max=stable_cycles + 1)
        self.sync += If(~self.locked,
            If(raw_s,
                cnt.eq(cnt + 1),
                If(cnt == stable_cycles - 1, self.locked.eq(1))
            ).Else(cnt.eq(0))
        )
