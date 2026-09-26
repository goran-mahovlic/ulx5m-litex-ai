#
# Hardware MDIO write sequencer for the KSZ9031 on the Radiona ULX5M-GS.
#
# Why this exists: LiteEth's LiteEthPHYMDIO is a CSR bit-bang bridge -- in this
# CPU-less design nothing ever writes those CSRs, so the KSZ9031 stays at its
# power-on defaults and auto-negotiates GIGABIT, whose 125 MHz RXC this board
# cannot clock (RXC on non-clock-capable IO_EB_A7; see docs/LITEETH_INTEGRATION.md
# and docs/GBE_FEASIBILITY_20260921_TASK-4961.md). This module is a pure-hardware
# clause-22 write engine that, once after PHY reset, forces the advertisement
# down to 100BASE-TX full-duplex:
#
#   reg 9 (1000BASE-T Control)     = 0x0000  do not advertise 1000BASE-T
#   reg 4 (AN Advertisement)       = 0x0101  802.3 selector + 100BASE-TX FD only
#   reg 0 (Basic Control)          = 0x1200  AN enable + AN restart
#
# The KSZ9031 PHY address is a 3-bit strap (PHYAD[2:0]) not documented for this
# board revision, so the sequence is replayed at every address 0..7. The KSZ9031
# is the only device on this MDIO bus and clause-22 writes to absent addresses
# are ignored, so the sweep is harmless and strap-proof.
#
# NEVER add MMD2 pad-skew writes here: observed to kill line transmission on
# this board revision (docs/LITEETH_INTEGRATION.md).
#
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.specials import Tristate

from litex.gen import *

# Clause-22 write frame ------------------------------------------------------------------------------

def mdio_write_frame(phyad, reg, data):
    """64-bit clause-22 WRITE frame, transmitted MSB first.

    <32x preamble=1> <ST=01> <OP=01(write)> <PHYAD[4:0]> <REGAD[4:0]> <TA=10> <DATA[15:0]>
    """
    return (0xFFFFFFFF << 32) | (0b0101 << 28) | ((phyad & 0x1F) << 23) | \
           ((reg & 0x1F) << 18) | (0b10 << 16) | (data & 0xFFFF)

# Default bring-up: 100BASE-TX FD only, restart AN. Order matters: advertisement
# registers first, AN restart (reg0) last so the new advertisement is used.
KSZ9031_100M_FD_WRITES = [
    (9, 0x0000),  # 1000BASE-T Control: advertise no gigabit modes.
    (4, 0x0101),  # AN Advertisement: 802.3 selector + 100BASE-TX full-duplex only.
    (0, 0x1200),  # Basic Control: auto-negotiation enable + restart.
]

# MDIOWriteSequencer ---------------------------------------------------------------------------------

class MDIOWriteSequencer(LiteXModule):
    """One-shot hardware MDIO write engine (clause 22, write-only).

    Waits for `phy_reset` to deassert, then a strap-latch settle delay, then
    shifts out every frame in `writes` for every address in `phyads`.
    MDIO is driven during frames (write frames need no turnaround read) and
    released (Hi-Z) between frames and when done. MDC idles low.

    Runs in the clock domain it is instantiated in (`sys` by default);
    `clk_freq` must match that domain.
    """
    def __init__(self, pads, clk_freq, phy_reset=None,
                 writes        = None,
                 phyads        = None,
                 mdc_freq      = 1.0e6,
                 settle_time   = 10e-3):
        self.done = Signal()  # All frames sent; bus released.

        # # #

        if writes is None:
            writes = KSZ9031_100M_FD_WRITES
        if phyads is None:
            phyads = range(8)  # KSZ9031 PHYAD[2:0] strap -> 0..7 covers all straps.

        frames = [mdio_write_frame(phyad, reg, data)
                  for phyad in phyads
                  for reg, data in writes]
        frame_rom = Array([Constant(f, bits_sign=64) for f in frames])

        # MDC timing: one `tick` per MDC half-period.
        half_div = max(int(clk_freq // (2*mdc_freq)), 1)
        div_cnt  = Signal(max=half_div + 1)
        tick     = Signal()
        self.sync += [
            If(div_cnt == half_div - 1,
                div_cnt.eq(0)
            ).Else(
                div_cnt.eq(div_cnt + 1)
            ),
        ]
        self.comb += tick.eq(div_cnt == half_div - 1)

        # Pad drivers. MDIO data changes while MDC is low; PHY samples on rising edge.
        # Kept as attributes so a testbench can observe them (pads=None skips the
        # Tristate special, which the migen simulator cannot model).
        self.mdc     = mdc     = Signal()
        self.mdio_o  = mdio_o  = Signal(reset=1)
        self.mdio_oe = mdio_oe = Signal()
        if pads is not None:
            self.comb += pads.mdc.eq(mdc)
            self.specials += Tristate(pads.mdio, mdio_o, mdio_oe)

        settle_cycles = int(clk_freq * settle_time)
        settle_cnt    = Signal(max=settle_cycles + 1)
        frame_idx     = Signal(max=len(frames) + 1 if len(frames) > 1 else 2)
        bit_cnt       = Signal(6)   # 0..63
        shreg         = Signal(64)
        gap_cnt       = Signal(4)   # inter-frame idle, in MDC half-periods.

        if phy_reset is None:
            phy_reset = Signal()  # constant 0: start immediately.

        self.fsm = fsm = FSM(reset_state="SETTLE")
        fsm.act("SETTLE",
            # Hold until PHY reset is over and straps have latched.
            NextValue(mdc, 0),
            NextValue(mdio_oe, 0),
            If(phy_reset,
                NextValue(settle_cnt, 0)
            ).Elif(settle_cnt == settle_cycles,
                NextValue(frame_idx, 0),
                NextState("LOAD")
            ).Else(
                NextValue(settle_cnt, settle_cnt + 1)
            )
        )
        fsm.act("LOAD",
            NextValue(shreg, frame_rom[frame_idx]),
            NextValue(bit_cnt, 0),
            NextValue(mdc, 0),
            NextValue(mdio_oe, 0),
            NextState("SHIFT-LOW")
        )
        fsm.act("SHIFT-LOW",
            # MDC low half: present the current bit (shreg MSB).
            NextValue(mdio_oe, 1),
            NextValue(mdio_o, shreg[63]),
            If(tick,
                NextValue(mdc, 1),
                NextState("SHIFT-HIGH")
            )
        )
        fsm.act("SHIFT-HIGH",
            # MDC high half: PHY has sampled on the rising edge; advance on the fall.
            If(tick,
                NextValue(mdc, 0),
                NextValue(shreg, Cat(Signal(), shreg[:63])),  # shift left
                If(bit_cnt == 63,
                    NextValue(mdio_oe, 0),
                    NextValue(gap_cnt, 0),
                    NextState("GAP")
                ).Else(
                    NextValue(bit_cnt, bit_cnt + 1),
                    NextState("SHIFT-LOW")
                )
            )
        )
        fsm.act("GAP",
            # >= 8 MDC half-periods of released bus between frames.
            If(tick,
                If(gap_cnt == 7,
                    If(frame_idx == len(frames) - 1,
                        NextState("DONE")
                    ).Else(
                        NextValue(frame_idx, frame_idx + 1),
                        NextState("LOAD")
                    )
                ).Else(
                    NextValue(gap_cnt, gap_cnt + 1)
                )
            )
        )
        fsm.act("DONE",
            self.done.eq(1),
            NextValue(mdc, 0),
            NextValue(mdio_oe, 0)
        )
