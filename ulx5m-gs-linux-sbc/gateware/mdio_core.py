#
# KSZ9031 MDIO controller in hardware (Migen port of the former gateware/verilog/mdio_core.v, TASK-4999/5032).
#
# The PHY must advertise 1000BASE-T FD before the CPU runs (the BIOS netboots right away), so it is configured
# here, without software. LiteEth only has a CSR bit-bang MDIO (liteeth/phy/common.py LiteEthPHYMDIO).
#
# - rst_n (PHY RESET_N) low for 2^19 cycles after configuration, then high; MDIO starts at 2^21 cycles.
# - MDC = clk/32. Every pass (~2^22 cycles apart): read reg 2 at PHYAD 0..7 (idm bit = 0x0022 there, addr = first
#   PHYAD that answered), once, in pass `write_after`, write reg9, reg4, reg0 to EVERY PHYAD 0..7, then read
#   regs 0, 1, 4, 5, 9, 0xA, 0x1F at `addr`.
# - RXC edges per 2^20 cycles (rfreq) and RX_CTL rising edges (frames), gray-coded into the main domain.
# - snap: {passes, idm, {wrote, 4'b0, addr}, r0, r1, r4, r5, r9, ra, rf, rfreq, frames, 80'h0}, as in the Verilog.
#
# Cycle-for-cycle the same as the Verilog (sim/tb_mdio_core_equiv.py). Differences: no UART line printer and no
# `dbg` input (the SoC left both unconnected). All registers are reset-less, like the Verilog, which has only
# initial values: the PHY reset counter starts with the configuration, not with the sys reset.
#
# SPDX-License-Identifier: BSD-2-Clause

from functools import reduce
from operator import xor

from migen import *

from litex.gen import LiteXModule


def _gray2bin(g):
    """b[i] = xor of g[i:] (comb expressions, no self-reference)."""
    return Cat(*[reduce(xor, [g[j] for j in range(i, len(g))]) for i in range(len(g))])


def _ext5(x):
    if isinstance(x, int):
        return C(x, 5)
    return Cat(x, C(0, 5 - len(x))) if len(x) < 5 else x[:5]


def _rframe(a, r):
    """{32'hFFFFFFFF, 4'b0110, a, r, 18'h3FFFF}: read frame, the master releases MDIO from bit 46."""
    return Cat(C(0x3FFFF, 18), _ext5(r), _ext5(a), C(0b0110, 4), C(0xFFFFFFFF, 32))


def _wframe(a, r, d):
    """{32'hFFFFFFFF, 4'b0101, a, r, 2'b10, d}."""
    return Cat(C(d, 16), C(0b10, 2), _ext5(r), _ext5(a), C(0b0101, 4), C(0xFFFFFFFF, 32))


class MDIOCore(LiteXModule):
    def __init__(self, pads, write_after=6, reg9=0x0000, reg4=0x0101, reg0=0x1200, rxc_domain="grx", rx_ctl=0):
        R = lambda *a, **k: Signal(*a, reset_less=True, **k)
        self.passes, self.idm, self.wrote, self.addr = R(8), R(8), R(), R(3)
        self.r0, self.r1, self.r4, self.r5, self.r9, self.ra, self.rf = [R(16) for _ in range(7)]
        self.rfreq, self.frames = R(24), R(16)
        self.snap = Signal(256)

        # # #

        # Reset / timing.
        up = R(22)
        self.sync += If(~up[21], up.eq(up + 1))
        self.comb += pads.rst_n.eq(up[19] | up[20] | up[21])
        mdio_en = up[21]

        # MDIO bit engine (MDC = clk/32).
        ph  = R(5)
        mdc = R()
        mdo = R(reset=1, name="mdo")
        moe = R(name="moe")
        self.sync += ph.eq(ph + 1)
        self.comb += pads.mdc.eq(mdc)
        t = TSTriple()
        self.specials += t.get_tristate(pads.mdio)
        self.comb += [t.o.eq(mdo), t.oe.eq(moe)]
        mi1, mi2 = R(reset=1), R(reset=1)
        self.sync += [mi1.eq(t.i), mi2.eq(mi1)]

        fr, bitn, busy, rd, rx = R(64), R(7), R(), R(), R(17)
        start, fr_in, rd_in = R(), R(64), R()
        self.sync += [
            If(ph == 0, mdc.eq(0)),
            If(ph == 16, mdc.eq(busy)),
            If(start & ~busy & (ph == 0),
                fr.eq(fr_in), rd.eq(rd_in), bitn.eq(0), busy.eq(1), rx.eq(0)
            ).Elif(busy & (ph == 1),                        # drive after MDC falls
                If(rd & (bitn >= 46), moe.eq(0)).Else(moe.eq(1), mdo.eq(fr[63])),
                fr.eq(Cat(C(1, 1), fr[:63])),
            ).Elif(busy & (ph == 15),                       # sample before MDC rises
                # MDC rises at ph 16 of every bit 0..63 -> 64 edges (a frame with 63 edges is dropped by the PHY).
                If(rd & (bitn >= 47) & (bitn <= 63), rx.eq(Cat(mi2, rx[:16]))),
                If(bitn == 64, busy.eq(0), moe.eq(0)),
                bitn.eq(bitn + 1),
            ),
        ]

        # Sequencer.
        step, found, waddr = R(5), R(), R(3)
        wst, gap = R(2), R(23)
        do_write = Signal()
        self.comb += do_write.eq((self.passes == write_after) & ~self.wrote)
        reads = {11: 0, 12: 1, 13: 4, 14: 5, 15: 9, 16: 10}
        frame_sel = {
            8:  [fr_in.eq(_wframe(waddr, 9, reg9)), rd_in.eq(0)],
            9:  [fr_in.eq(_wframe(waddr, 4, reg4)), rd_in.eq(0)],
            10: [fr_in.eq(_wframe(waddr, 0, reg0)), rd_in.eq(0)],
            "default": [fr_in.eq(_rframe(self.addr, 31)), rd_in.eq(1)],
        }
        frame_sel.update({s: [fr_in.eq(_rframe(self.addr, r)), rd_in.eq(1)] for s, r in reads.items()})
        results = {11: self.r0, 12: self.r1, 13: self.r4, 14: self.r5, 15: self.r9, 16: self.ra, 17: self.rf}
        self.sync += If(mdio_en, Case(wst, {
            0: If(gap[22] | (step != 0),                    # ~3 passes / s at 25 MHz
                   gap.eq(0),
                   If(step < 8, fr_in.eq(_rframe(step, 2)), rd_in.eq(1)).Else(Case(step, frame_sel)),
                   If((step >= 8) & (step <= 10) & ~do_write, step.eq(11)).Else(start.eq(1), wst.eq(1)),
               ).Else(gap.eq(gap + 1)),
            1: If(busy, start.eq(0), wst.eq(2)),
            2: If(~busy,
                   If(step < 8,
                       Case(step[:3], {i: self.idm[i].eq(~rx[16] & (rx[:16] == 0x0022)) for i in range(8)}),
                       If(~found & ~rx[16], found.eq(1), self.addr.eq(step[:3])),
                   ),
                   Case(step, {s: reg.eq(rx[:16]) for s, reg in results.items()}),
                   If((step == 10) & (waddr == 7), self.wrote.eq(1)),
                   If(step == 17,
                       step.eq(0), self.passes.eq(self.passes + 1), found.eq(0)
                   ).Elif((step == 10) & (waddr != 7),
                       waddr.eq(waddr + 1), step.eq(8)
                   ).Else(step.eq(step + 1)),
                   wst.eq(0),
               ),
        }))

        # RXC frequency + RX_CTL frames, gray-coded across to the main domain.
        rc, fc, ctl_d = R(24), R(16), R()
        getattr(self.sync, rxc_domain).__iadd__([rc.eq(rc + 1), ctl_d.eq(rx_ctl), If(rx_ctl & ~ctl_d, fc.eq(fc + 1))])
        rcg1, rcg2, fcg1, fcg2 = R(24), R(24), R(16), R(16)
        self.sync += [rcg1.eq(rc ^ (rc >> 1)), rcg2.eq(rcg1), fcg1.eq(fc ^ (fc >> 1)), fcg2.eq(fcg1)]
        win, rc_prev = R(20), R(24)
        self.sync += [
            win.eq(win + 1),
            If(win == 0,
                self.rfreq.eq(_gray2bin(rcg2) - rc_prev), rc_prev.eq(_gray2bin(rcg2)), self.frames.eq(_gray2bin(fcg2))),
        ]

        self.comb += self.snap.eq(Cat(C(0, 80), self.frames, self.rfreq, self.rf, self.ra, self.r9, self.r5, self.r4,
                                      self.r1, self.r0, self.addr, C(0, 4), self.wrote, self.idm, self.passes))
