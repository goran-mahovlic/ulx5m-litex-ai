#
# MDIO read/write engine + UART status dumper for KSZ9031 bring-up diagnostics
# on the Radiona ULX5M-GS (TASK-4999).
#
# Why this exists: the write-only MDIOWriteSequencer gives no evidence that the
# PHY is alive. Without a logic analyser the only way to prove that the KSZ9031
# has its XI reference clock (IO_EB_A3) is to READ it back: a clocked PHY answers
# clause-22 reads (TA bit driven 0, PHY ID 0x0022/0x162x), an unclocked one does not.
#
# MDIODiagEngine
#   1. waits for PHY reset release + settle time,
#   2. issues the same 100BASE-TX FD writes as MDIOWriteSequencer (reg9=0,
#      reg4=0x0101, reg0=0x1200) at every PHYAD in `phyads`,
#   3. then loops forever over `reads` (phyad, reg), storing each 16-bit result
#      plus the turnaround bit (0 = a PHY answered) in `results[i]` / `ta[i]`.
#   `drive_err` counts MDC edges where the FPGA drove MDIO but read back the
#   opposite level (proves the pad input/output path works).
#
# UARTLineDumper: 8N1 transmit-only, prints a fixed text template in which
#   nibble placeholders are filled from live signals, every `period` seconds.
#
# FreqMeter: counts cycles of a foreign clock domain over a 2**gate_bits sys
#   cycle window (value latched in the foreign domain, stable for a whole window).
#
# NEVER add MMD2 pad-skew writes here (docs/LITEETH_INTEGRATION.md).
#
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.specials import Tristate
from migen.genlib.cdc import MultiReg

from litex.gen import *

from mdio_sequencer import KSZ9031_100M_FD_WRITES


def mdio_frame(op, phyad, reg, data=0):
    """64-bit clause-22 frame, MSB first. op: 'w' (OP=01, TA=10) or 'r' (OP=10, TA/data=1)."""
    if op == "w":
        return (0xFFFFFFFF << 32) | (0b0101 << 28) | ((phyad & 0x1F) << 23) | \
               ((reg & 0x1F) << 18) | (0b10 << 16) | (data & 0xFFFF)
    return (0xFFFFFFFF << 32) | (0b0110 << 28) | ((phyad & 0x1F) << 23) | \
           ((reg & 0x1F) << 18) | 0x3FFFF


DIAG_READ_REGS = [2, 3, 0, 1, 4, 5, 9, 10, 31]

# MDIODiagEngine -------------------------------------------------------------------------------------

class MDIODiagEngine(LiteXModule):
    def __init__(self, pads, clk_freq, phy_reset=None, writes=None, phyads=None, reads=None,
                 mdc_freq=1.0e6, settle_time=10e-3):
        if writes is None:
            writes = KSZ9031_100M_FD_WRITES
        if phyads is None:
            phyads = range(8)
        if reads is None:
            reads = [(a, r) for a in phyads for r in DIAG_READ_REGS]
        self.reads     = reads
        self.done      = Signal()                 # write phase finished (reads keep looping)
        self.results   = [Signal(16, name="mdio_rd%d" % i) for i in range(len(reads))]
        self.ta        = [Signal(reset=1, name="mdio_ta%d" % i) for i in range(len(reads))]
        self.drive_err = Signal(16)
        self.passes    = Signal(8)                # completed read passes (wraps)

        # # #

        wframes = [mdio_frame("w", a, r, d) for a in phyads for r, d in writes]
        rframes = [mdio_frame("r", a, r) for a, r in reads]
        frames  = wframes + rframes
        nw      = len(wframes)
        is_read = Array([Constant(0 if i < nw else 1, 1) for i in range(len(frames))])
        rom     = Array([Constant(f, bits_sign=64) for f in frames])

        half_div = max(int(clk_freq // (2*mdc_freq)), 1)
        div_cnt  = Signal(max=half_div + 1)
        tick     = Signal()
        self.sync += If(div_cnt == half_div - 1, div_cnt.eq(0)).Else(div_cnt.eq(div_cnt + 1))
        self.comb += tick.eq(div_cnt == half_div - 1)

        self.mdc     = mdc     = Signal()
        self.mdio_o  = mdio_o  = Signal(reset=1)
        self.mdio_oe = mdio_oe = Signal()
        self.mdio_i  = mdio_i  = Signal(reset=1)
        if pads is not None:
            self.comb += pads.mdc.eq(mdc)
            self.specials += Tristate(pads.mdio, mdio_o, mdio_oe, mdio_i)
        # 2-FF synchroniser on the asynchronous pad input (sampled >= 3 sys cycles
        # after the MDC edge, well inside the 1 us MDC low half).
        mdio_is = Signal(reset=1)
        self.specials += MultiReg(mdio_i, mdio_is, "sys")

        settle_cycles = int(clk_freq * settle_time)
        settle_cnt    = Signal(max=settle_cycles + 1)
        self.settle_cnt = settle_cnt              # exposed for UART debug (TASK-4999)
        frame_idx     = Signal(max=len(frames) + 1)
        bit_cnt       = Signal(6)
        shreg         = Signal(64)
        rx            = Signal(17)                # TA bit 47 + 16 data bits
        gap_cnt       = Signal(4)
        rd            = Signal()

        if phy_reset is None:
            phy_reset = Signal()

        store = [If(frame_idx == nw + i, self.results[i].eq(rx[:16]), self.ta[i].eq(rx[16]))
                 for i in range(len(reads))]

        self.fsm = fsm = FSM(reset_state="SETTLE")
        fsm.act("SETTLE",
            NextValue(mdc, 0), NextValue(mdio_oe, 0),
            If(phy_reset,
                NextValue(settle_cnt, 0)
            ).Elif(settle_cnt == settle_cycles,
                NextValue(frame_idx, 0), NextState("LOAD")
            ).Else(NextValue(settle_cnt, settle_cnt + 1))
        )
        fsm.act("LOAD",
            NextValue(shreg, rom[frame_idx]),
            NextValue(rd, is_read[frame_idx]),
            NextValue(bit_cnt, 0),
            NextValue(mdc, 0), NextValue(mdio_oe, 0),
            NextState("SHIFT-LOW")
        )
        fsm.act("SHIFT-LOW",
            # Present bit k while MDC is low. Reads release the bus from bit 46 (TA) on.
            NextValue(mdio_oe, ~(rd & (bit_cnt >= 46))),
            NextValue(mdio_o, shreg[63]),
            If(tick,
                # Sample point = MDC rising edge (end of the low half): bit k is valid.
                If(rd & (bit_cnt >= 47), NextValue(rx, Cat(mdio_is, rx[:16]))),
                If(mdio_oe & (mdio_is != mdio_o) & (self.drive_err != 0xFFFF),
                    NextValue(self.drive_err, self.drive_err + 1)),
                NextValue(mdc, 1),
                NextState("SHIFT-HIGH")
            )
        )
        fsm.act("SHIFT-HIGH",
            If(tick,
                NextValue(mdc, 0),
                NextValue(shreg, Cat(Signal(), shreg[:63])),
                If(bit_cnt == 63,
                    NextValue(mdio_oe, 0),
                    NextValue(gap_cnt, 0),
                    NextState("STORE")
                ).Else(
                    NextValue(bit_cnt, bit_cnt + 1),
                    NextState("SHIFT-LOW")
                )
            )
        )
        self.sync += If(fsm.ongoing("STORE") & rd, *store)
        fsm.act("STORE", NextState("GAP"))
        fsm.act("GAP",
            If(tick,
                If(gap_cnt == 7,
                    If(frame_idx == len(frames) - 1,
                        NextValue(frame_idx, nw),          # loop over the reads forever
                        NextValue(self.passes, self.passes + 1),
                    ).Else(
                        NextValue(frame_idx, frame_idx + 1)
                    ),
                    NextState("LOAD")
                ).Else(NextValue(gap_cnt, gap_cnt + 1))
            )
        )
        self.sync += If(fsm.ongoing("LOAD") & (frame_idx == nw), self.done.eq(1))

# FreqMeter ------------------------------------------------------------------------------------------

class FreqMeter(LiteXModule):
    """Cycles of clock domain `cd` per 2**gate_bits sys cycles. self.value is in sys."""
    def __init__(self, cd, gate_bits=20, width=24):
        self.value = Signal(width)
        gate_cnt   = Signal(gate_bits + 1)
        self.sync += gate_cnt.eq(gate_cnt + 1)
        gate_s     = Signal()
        gate_d     = Signal()
        cnt        = Signal(width)
        latched    = Signal(width)
        self.specials += MultiReg(gate_cnt[gate_bits], gate_s, cd)
        sync = getattr(self.sync, cd)
        sync += [
            gate_d.eq(gate_s),
            If(gate_s != gate_d,
                latched.eq(cnt), cnt.eq(1)
            ).Elif(cnt != (2**width - 1), cnt.eq(cnt + 1))
        ]
        self.specials += MultiReg(latched, self.value, "sys")

# UARTLineDumper -------------------------------------------------------------------------------------

def hexf(sig, digits):
    """Template item: `digits` hex nibbles of `sig`, most significant first."""
    return [("n", sig, d) for d in reversed(range(digits))]


class UARTLineDumper(LiteXModule):
    """template: list of str (literal text) and ('n', signal, nibble_index) items."""
    def __init__(self, clk_freq, template, baud=115200, period=0.5):
        self.tx = tx = Signal(reset=1)

        items = []
        for t in template:
            if isinstance(t, str):
                items += [("c", ord(ch)) for ch in t]
            else:
                items.append(t)
        self.nchars = len(items)

        idx    = Signal(max=len(items) + 1)
        is_hex = Signal()
        lit    = Signal(8)
        nib    = Signal(4)
        cases  = {}
        for i, it in enumerate(items):
            if it[0] == "c":
                cases[i] = [is_hex.eq(0), lit.eq(it[1])]
            else:
                _, sig, d = it
                s = Cat(sig, Constant(0, 4))
                cases[i] = [is_hex.eq(1), nib.eq(s[4*d:4*d + 4])]
        cases["default"] = [is_hex.eq(0), lit.eq(ord("?"))]
        self.comb += Case(idx, cases)
        char = Signal(8)
        self.comb += If(is_hex,
            If(nib < 10, char.eq(0x30 + nib)).Else(char.eq(0x37 + nib))
        ).Else(char.eq(lit))

        bit_div  = int(round(clk_freq / baud))
        per_cyc  = int(clk_freq * period)
        bdiv     = Signal(max=bit_div + 1)
        bitn     = Signal(4)
        shreg    = Signal(10)
        wait     = Signal(max=per_cyc + 1)

        self.fsm = fsm = FSM(reset_state="WAIT")
        fsm.act("WAIT",
            If(wait == per_cyc,
                NextValue(wait, 0), NextValue(idx, 0), NextState("LOAD")
            ).Else(NextValue(wait, wait + 1))
        )
        fsm.act("LOAD",
            NextValue(shreg, Cat(0, char, 1)),     # start, 8 data LSB first, stop
            NextValue(bitn, 0), NextValue(bdiv, 0),
            NextState("SEND")
        )
        fsm.act("SEND",
            tx.eq(shreg[0]),
            If(bdiv == bit_div - 1,
                NextValue(bdiv, 0),
                NextValue(shreg, shreg[1:]),
                If(bitn == 9,
                    If(idx == len(items) - 1,
                        NextState("WAIT")
                    ).Else(
                        NextValue(idx, idx + 1), NextState("LOAD")
                    )
                ).Else(NextValue(bitn, bitn + 1))
            ).Else(NextValue(bdiv, bdiv + 1))
        )
