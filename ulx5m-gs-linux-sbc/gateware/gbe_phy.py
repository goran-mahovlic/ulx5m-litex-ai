#
# 1000 Mbps RGMII PHY for the Radiona ULX5M-GS (GateMate CCGM1A1 + KSZ9031), TASK-5032.
#
# Why not LiteEth's RGMII PHY: at 1G the PHY domains run at 125 MHz and LiteEth puts its async CDC
# FIFOs (gray counters -> BRAM address) there. On GateMate those paths close at only 52-65 MHz after
# routing (docs/GBE_FEASIBILITY_20260921_TASK-4961.md). Here the 125 MHz domains hold ONLY:
#   - the IO registers (CC_IDDR / CC_ODDR),
#   - a byte-wide RX aligner and a 4-byte shift register per direction,
#   - a word-wide (32 bit) BRAM port whose address moves at most once every 4 cycles.
# Everything else (LiteEth MAC/ARP/IP/ICMP/UDP) stays in sys, and the clock crossing happens per whole
# frame through a BRAM (store-and-forward in both directions): the sys side only ever sees complete
# frames, so sys may be much slower than the 125 MB/s line (ping only needs correctness, not rate).
#
# Word layout in both frame buffers (36 bits): data[31:0] (lane 0 = first byte), nv[33:32] = valid
# bytes in the last word (0 = 4), last[35].
#
# RX alignment: the KSZ9031 RXC edge lands ~1.2 ns after the data edge and reaches the IDDR through
# the non-clock pin IO_EB_A7 + CC_BUFG, so which half of the RXC period samples which nibble depends
# on that insertion delay. Both pairings are decoded in parallel and the one that shows the SFD (0xD5)
# first is locked for the frame (alignment A: rising edge = low nibble, B: rising edge = high nibble
# of the previous byte). Frames with RX_ER, without SFD, or not fitting the buffer are dropped.
#
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg
from functools import reduce
from operator import xor
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import LiteXModule
from litex.soc.interconnect import stream

from liteeth.common import eth_phy_description

AW   = 10       # 1024 words = 4 KiB per direction
MAXW = 384      # words reserved per frame (8 B preamble + 1522 B = 383 words); 384 = bits 8 & 7
TX_GAP_WORDS = 3  # idle words after a TX frame: 12 B inter-frame gap

# Timing rule for the 125 MHz domains (gtx, grx), measured on the first build (TASK-5032, rot1):
# GateMate routing costs 1.5-3.6 ns per hop, so at 8 ns only ONE LUT level (<= 4 inputs) fits between
# two flip-flops. Every gtx/grx register below is written so that its next-state function has at most
# 4 inputs (or is a plain shift / a carry-chain increment). No synchronous reset in those domains
# (a reset net is one more LUT input and a chip-wide route): they start from the configuration values
# (the PLL gates gtx until lock; RXC only runs once the KSZ9031 is out of reset).


def gray(x):
    return x ^ x[1:]


def gray2bin(g, b):
    """Statements b = gray2bin(g) (comb): b[i] = xor of g[i:] (no bit-level self-reference, which LiteX
    reports as a combinatorial cycle)."""
    n = len(g)
    return [b[i].eq(reduce(xor, [g[j] for j in range(i, n)])) for i in range(n)]


def _word(data, nv, last):
    return Cat(data, nv, C(0, 1), last)


def RL(*args, **kw):
    return Signal(*args, reset_less=True, **kw)


class GbePHYCore(LiteXModule):
    """PHY logic without IO primitives. Domains: sys (sink/source), gtx (TX 125 MHz), grx (RX 125 MHz).

    gtx outputs : tx_en, tx_byte (the byte on the wire this cycle).
    grx inputs  : rx_rs_ctl/rx_rs_dat = RGMII sample at the rising RXC edge of this cycle,
                  rx_fs_ctl/rx_fs_dat = sample at the falling edge of the PREVIOUS cycle.
    """
    def __init__(self, prim=False, diag=False):
        # prim: build duplicated registers from CC_DFF primitives (yosys opt_merge would fold plain copies
        # back into one flip-flop, even with (* keep *)); False = plain registers for the migen simulation.
        # diag (TASK-5094): extra RX state for a CSR (self.dbg): drops by cause, sys read/commit pointers, space.
        self.prim = prim
        self.diag = diag
        self.sink   = sink   = stream.Endpoint(eth_phy_description(8))
        self.source = source = stream.Endpoint(eth_phy_description(8))

        self.tx_en   = Signal()
        self.tx_byte = Signal(8)
        self.rx_rs_ctl, self.rx_rs_dat = RL(), RL(4)
        self.rx_fs_ctl, self.rx_fs_dat = RL(), RL(4)

        # Diagnostics (sampled quasi-statically by the beacon).
        self.rx_frames = Signal(16)   # sys: frames delivered to LiteEth
        self.tx_frames = Signal(16)   # sys: frames accepted from LiteEth
        self.rx_drops  = RL(8)        # grx: SFD'd frames not committed (RX_ER / too long / no space)
        self.rx_sel    = Signal()     # grx: current RX nibble pairing (0 = A, 1 = B), one cycle late
        self.rx_flips  = RL(8)        # grx: pairing changes
        self.tx_emit   = RL(16)       # gtx: frames put on the wire (falling edges of tx_en)

        self._tx()
        self._rx()

    def _dup(self, d, n, cd):
        """n copies of register(d) in domain cd, to split a wide fanout (TASK-5032: the RX BRAM write enable
        drives 36 per-bit WEA pins, 3.5 ns of routing from one flip-flop at 125 MHz)."""
        q = Signal(n)
        for i in range(n):
            if self.prim:
                self.specials += Instance("CC_DFF", p_CLK_INV=0, p_EN_INV=0, p_SR_INV=0, p_SR_VAL=0,
                                          i_D=d, i_CLK=ClockSignal(cd), i_EN=1, i_SR=0, o_Q=q[i])
            else:
                getattr(self.sync, cd).__iadd__(q[i].eq(d))
        return q

    # TX -------------------------------------------------------------------------------------------
    def _tx(self):
        sink = self.sink
        mem  = Memory(36, 2**AW)
        wp   = mem.get_port(write_capable=True, clock_domain="sys")
        rp   = mem.get_port(clock_domain="gtx")
        self.specials += mem, wp, rp

        # sys: frame writer (store-and-forward) --------------------------------------------------
        wa, wc = Signal(AW), Signal(AW)        # next write address, committed pointer
        wc_g   = Signal(AW)
        rd_g   = RL(AW)                        # gtx read pointer (gray)
        rr_g, rr = Signal(AW), Signal(AW)
        self.specials += MultiReg(rd_g, rr_g, "sys")
        self.comb += gray2bin(rr_g, rr)
        free   = Signal(AW)
        self.comb += free.eq(rr - wa - 1)

        word   = Signal(32)
        lane   = Signal(2)
        active = Signal()
        wpend, wlast, wnv = Signal(), Signal(), Signal(2)
        self.comb += [
            wp.adr.eq(wa),
            wp.dat_w.eq(_word(word, wnv, wlast)),
            wp.we.eq(wpend),
            # A frame starts with any beat accepted while not `active`: LiteEth's MAC does not drive `first` on
            # the PHY sink, so gating on it deadlocked TX on the board (TASK-5032, Diag13: tx_frames = 0).
            sink.ready.eq(active | (sink.valid & (free >= MAXW))),
        ]
        self.sync += [
            wpend.eq(0),
            If(wpend,
                wa.eq(wa + 1),
                If(wlast, wc.eq(wa + 1)),
            ),
            If(sink.valid & sink.ready,
                Case(lane, {i: word[8*i:8*i+8].eq(sink.data) for i in range(4)}),
                lane.eq(lane + 1),
                active.eq(~sink.last),
                If((lane == 3) | sink.last,
                    wpend.eq(1),
                    wlast.eq(sink.last),
                    wnv.eq(lane + 1),
                ),
                If(sink.last,
                    lane.eq(0),
                    self.tx_frames.eq(self.tx_frames + 1),
                ),
            ),
            wc_g.eq(gray(wc)),
        ]

        # gtx: word reader + byte serializer, 4-phase ring (p[k] = phase k) ------------------------
        #  p0: go     = inside a frame, or (gap over and a committed word available)
        #  p1: golast = go & last(word), gonl = go & ~last        (BRAM data for the new ra is valid)
        #  p2: mask   = valid lanes of the word, idle_nx = next idle-gap state, inc = go
        #  p3: load   sh/vb (<- word or zeros), fact, idle; ra += inc at the end of p3
        wc_gs = RL(AW)
        self.specials += MultiReg(wc_g, wc_gs, "gtx")
        p     = RL(4, reset=0b0001)
        self.tx_ring = p
        ra    = RL(AW)
        sh, vb = RL(32), RL(4)
        fact  = RL()                            # inside a frame
        idle  = RL(TX_GAP_WORDS)                # thermometer: idle words left (LSB = any left)
        idle_nx = RL(TX_GAP_WORDS)
        go, golast, gonl, inc = RL(), RL(), RL(), RL()
        mask  = RL(4)
        x, orq, avail = RL(AW), RL(3), RL()
        dat   = rp.dat_r
        nv    = dat[32:34]
        last  = dat[35]
        self.comb += rp.adr.eq(ra)
        ld = p[3]
        self.sync.gtx += [
            # self-correcting one-hot ring: p0 <- none of p0..p2 set. Any state (0000 after a PLL start-up clock
            # glitch, two hot bits, ...) converges to the single-hot sequence within 4 cycles (TASK-5032).
            p.eq(Cat(~(p[0] | p[1] | p[2]), p[:3])),
            # avail = (gray(ra) != committed gray pointer): xor -> 2-level OR tree, 3 stages
            x.eq(rd_g ^ wc_gs),
            orq[0].eq(x[0:4] != 0), orq[1].eq(x[4:8] != 0), orq[2].eq(x[8:10] != 0),
            avail.eq(orq != 0),
            If(p[0], go.eq(fact | (~idle[0] & avail))),
            If(p[1], golast.eq(go & last), gonl.eq(go & ~last)),
            If(p[2],
                Case(nv, {0: mask.eq(0b1111), 1: mask.eq(0b0001), 2: mask.eq(0b0011), 3: mask.eq(0b0111)}),
                inc.eq(go),
            ),
            If(p[2], *[idle_nx[i].eq(golast | (~go & (idle[i+1] if i + 1 < TX_GAP_WORDS else 0)))
                      for i in range(TX_GAP_WORDS)]),
            If(ld,
                fact.eq(gonl),
                idle.eq(idle_nx),
                ra.eq(ra + inc),
            ),
            rd_g.eq(gray(ra)),
        ]
        for i in range(32):
            self.sync.gtx += sh[i].eq(Mux(ld, dat[i] & go, sh[i+8] if i + 8 < 32 else 0))
        for i in range(4):
            self.sync.gtx += vb[i].eq(Mux(ld, mask[i] & go, vb[i+1] if i + 1 < 4 else 0))
        self.comb += [self.tx_en.eq(vb[0]), self.tx_byte.eq(sh[:8])]
        en_d = RL()
        self.sync.gtx += [en_d.eq(vb[0]), If(en_d & ~vb[0], self.tx_emit.eq(self.tx_emit + 1))]

    # RX -------------------------------------------------------------------------------------------
    def _rx(self):
        source = self.source
        mem = Memory(36, 2**AW)
        wp  = mem.get_port(write_capable=True, we_granularity=9, clock_domain="grx")   # 4 WE lanes
        rp  = mem.get_port(clock_domain="sys")
        self.specials += mem, wp, rp

        rs_c, rs_d, fs_c, fs_d = self.rx_rs_ctl, self.rx_rs_dat, self.rx_fs_ctl, self.rx_fs_dat
        sel = RL()          # local: the beacon (sys) reads the copy sel_d, so the placer keeps sel next to its mux

        # stage 1: previous rising sample; candidate bytes A/B (wiring) and the selected path S.
        rs_cp, rs_dp = RL(), RL(4)
        cA, cB, cS = RL(8), RL(8), RL(8)
        dvA, dvB, dvS, erS = RL(), RL(), RL(), RL()
        self.sync.grx += [
            rs_cp.eq(rs_c), rs_dp.eq(rs_d),
            cA.eq(Cat(rs_dp, fs_d)), dvA.eq(rs_cp),     # A: {fall(prev half), rise(prev cycle)}
            cB.eq(Cat(fs_d, rs_d)),  dvB.eq(fs_c),      # B: {rise(this cycle), fall(prev half)}
            cS.eq(Mux(sel, Cat(fs_d, rs_d), Cat(rs_dp, fs_d))),
            dvS.eq(Mux(sel, fs_c, rs_cp)),
            erS.eq(Mux(sel, fs_c ^ rs_c, rs_cp ^ fs_c)),
        ]
        # stage 2: nibble compares (low == 5, high == D) for A, B, S.
        def sfd_pipe(c, dv):
            lo, hi, dv2, sfd = RL(), RL(), RL(), RL()
            self.sync.grx += [lo.eq(c[:4] == 0x5), hi.eq(c[4:] == 0xD), dv2.eq(dv),
                              sfd.eq(dv2 & lo & hi)]              # stage 3
            return sfd
        sfdA = sfd_pipe(cA, dvA)
        sfdB = sfd_pipe(cB, dvB)
        sfdS = sfd_pipe(cS, dvS)
        cS2, cS3, dvS2, dvS3, erS2, erS3 = RL(8), RL(8), RL(), RL(), RL(), RL()
        self.sync.grx += [cS2.eq(cS), cS3.eq(cS2), dvS2.eq(dvS), dvS3.eq(dvS2), erS2.eq(erS), erS3.eq(erS2)]

        # stage 4: frame state on the selected path + pairing choice from the A/B SFD detectors.
        inf = RL()
        ob, ov, ofirst, oeof, oer = RL(8), RL(), RL(), RL(), RL()
        take = Mux(inf, dvS3, sfdS)
        self.sync.grx += [
            inf.eq(take),
            ov.eq(take),
            ofirst.eq(~inf & sfdS),
            oeof.eq(inf & ~dvS3),
            oer.eq(inf & erS3),
            If(~inf & sfdB & ~sfdA, sel.eq(1)).Elif(~inf & sfdA & ~sfdB, sel.eq(0)),
        ]
        for i in range(8):
            self.sync.grx += ob[i].eq(cS3[i] & take)
        sel_d = RL()
        self.sync.grx += [sel_d.eq(sel), If(sel != sel_d, self.rx_flips.eq(self.rx_flips + 1))]
        self.comb += self.rx_sel.eq(sel_d)

        # stage 5+: frame writer. sr/vv shift every cycle; ph counts from the SFD; a word is complete
        # when ph == 0 and it is written at the next edge (we_r).
        sr, vv = RL(32), RL(4)
        ph     = RL(2)
        we_r   = RL()
        acc, bad = RL(), RL()
        wa, wc = RL(AW), RL(AW)
        wcnt   = RL(9)
        ovf    = RL()
        commit, commit_ok = RL(), RL()
        space_ok = RL()
        space_sys = Signal()
        self.specials += MultiReg(space_sys, space_ok, "grx")
        we_nx = Signal()
        self.comb += we_nx.eq((ph == 3) & vv[1] & acc)
        we_lanes = self._dup(we_nx, 4, "grx")
        self.sync.grx += [
            sr.eq(Cat(sr[8:], ob)),
            vv.eq(Cat(vv[1:], ov)),
            ph.eq(Mux(ofirst, 1, ph + 1)),
            # write at the edge that ends the ph == 0 cycle (lane 0 = vv[1] one cycle before)
            we_r.eq(we_nx),
            acc.eq(Mux(ofirst, space_ok, acc & ~ovf)),
            bad.eq(Mux(ofirst, 0, bad | oer)),
            ovf.eq(wcnt[8] & wcnt[7]),
            wcnt.eq(Mux(ofirst, 0, wcnt + we_r)),
            commit.eq(we_r & ~(vv[3] & ov)),                 # the word just written was the last one
            commit_ok.eq(we_r & ~(vv[3] & ov) & ~bad),
            If(commit_ok, wc.eq(wa)),                        # wa already points past the last word
            wa.eq(Mux(ofirst, wc, wa + we_r)),               # a new frame always starts at wc
        ]
        wlast = Signal()
        wnv   = Signal(2)
        self.comb += [
            wlast.eq(~(vv[3] & ov)),
            Case(vv[1:4], {0b111: wnv.eq(0), 0b000: wnv.eq(1), 0b001: wnv.eq(2), 0b011: wnv.eq(3),
                           "default": wnv.eq(0)}),
            wp.adr.eq(wa),
            wp.dat_w.eq(_word(sr, wnv, wlast)),
            wp.we.eq(we_lanes),                              # = Replicate(we_r, 4), one flip-flop per lane
        ]
        drop = RL()
        self.sync.grx += [
            drop.eq((commit & bad) | (ofirst & ~space_ok)),
            If(drop, self.rx_drops.eq(self.rx_drops + 1)),
        ]
        if self.diag:
            self.dbg_drop_bad, self.dbg_drop_space = RL(8), RL(8)
            self.sync.grx += [If(commit & bad, self.dbg_drop_bad.eq(self.dbg_drop_bad + 1)),
                              If(ofirst & ~space_ok, self.dbg_drop_space.eq(self.dbg_drop_space + 1))]
        wc_g = RL(AW)
        self.sync.grx += wc_g.eq(gray(wc))

        # sys: frame reader.
        wc_gs, wc_s = Signal(AW), Signal(AW)
        self.specials += MultiReg(wc_g, wc_gs, "sys")
        self.comb += gray2bin(wc_gs, wc_s)
        ra = Signal(AW)
        free = Signal(AW)
        self.comb += free.eq(ra - wc_s - 1)
        self.sync += space_sys.eq(free >= MAXW)
        wd = Signal(36)
        ln = Signal(2)
        first = Signal(reset=1)
        self.comb += rp.adr.eq(ra)
        wlast_r = wd[35]
        nbm1 = Signal(2)
        self.comb += nbm1.eq(Mux(wlast_r, wd[32:34] - 1, 3))
        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(ra != wc_s, NextState("LOAD"))
        )
        fsm.act("LOAD",
            NextValue(wd, rp.dat_r),
            NextValue(ln, 0),
            NextState("EMIT"),
        )
        fsm.act("EMIT",
            source.valid.eq(1),
            source.first.eq(first & (ln == 0)),
            source.last.eq(wlast_r & (ln == nbm1)),
            source.last_be.eq(wlast_r & (ln == nbm1)),
            If(source.ready,
                NextValue(ln, ln + 1),
                If(ln == nbm1,
                    NextValue(ra, ra + 1),
                    NextValue(first, wlast_r),
                    NextState("IDLE"),
                )
            )
        )
        self.comb += source.data.eq(Array([wd[8*i:8*i+8] for i in range(4)])[ln])
        self.sync += If(source.valid & source.ready & source.last, self.rx_frames.eq(self.rx_frames + 1))
        if self.diag:
            # [7:0] drops with RX_ER, [15:8] drops without space, [25:16] ra, [35:26] wc_s, [36] space, [37] idle,
            # [38] source.valid, [39] source.ready (sys fields exact, grx fields quasi-static)
            self.dbg = Cat(self.dbg_drop_bad, self.dbg_drop_space, ra, wc_s, space_sys, fsm.ongoing("IDLE"),
                           source.valid, source.ready)


class GbePHY(LiteXModule):
    """RGMII 1000 Mbps PHY with GateMate IO primitives.

    clk_tx   : 125 MHz, CLK0 of the TX PLL (TXD/TX_CTL CC_ODDR + TX logic).
    txc_clks : list of clock signals selectable as TXC (e.g. [clk0, clk90]); txc_sel picks
               index = sel >> 1, inverted when sel & 1 (TXC goes straight to the pad through one LUT).
    RXC      : pad -> CC_BUFG -> grx (CC_IDDR + RX logic).
    LiteEth sees eth_tx/eth_rx = sys (the real clock crossing is the frame BRAM in GbePHYCore).
    """
    dw          = 8
    tx_clk_freq = 20e6     # overwritten by the target: LiteEth's eth_tx/eth_rx = sys
    rx_clk_freq = 20e6

    def __init__(self, clock_pads, pads, clk_tx, txc_clks, txc_sel, rst, txc_bufg=False):
        self.core = core = GbePHYCore(prim=True)
        self.sink, self.source = core.sink, core.source

        # Clock domains -----------------------------------------------------------------------
        self.cd_gtx = ClockDomain()
        self.cd_grx = ClockDomain()
        self.cd_eth_tx = ClockDomain()
        self.cd_eth_rx = ClockDomain()
        self.comb += [
            self.cd_gtx.clk.eq(clk_tx),
            self.cd_eth_tx.clk.eq(ClockSignal("sys")), self.cd_eth_tx.rst.eq(ResetSignal("sys")),
            self.cd_eth_rx.clk.eq(ClockSignal("sys")), self.cd_eth_rx.rst.eq(ResetSignal("sys")),
        ]
        rxc_buf = Signal()
        self.specials += Instance("CC_BUFG", i_I=clock_pads.rx, o_O=rxc_buf)
        self.comb += self.cd_grx.clk.eq(rxc_buf)
        self.specials += [
            AsyncResetSynchronizer(self.cd_gtx, rst),
            AsyncResetSynchronizer(self.cd_grx, rst),
        ]

        # TX IO: CC_ODDR per pin. D0 (rising half) from a posedge register, D1 (falling half) from a
        # NEGEDGE fabric register -> both IO flip-flops get a full-cycle path from the fabric
        # (LiteX's DDROutput gives the falling-half IO FF a half-cycle path). -------------------
        en_r, lo_r, hi_r = RL(), RL(4), RL(4)
        self.sync.gtx += [en_r.eq(core.tx_en), lo_r.eq(Mux(core.tx_en, core.tx_byte[:4], 0)),
                          hi_r.eq(Mux(core.tx_en, core.tx_byte[4:], 0))]
        def oddr(d0, d1_pos, pad):
            d1_neg = Signal()
            self.specials += [
                Instance("CC_DFF", p_CLK_INV=1, p_EN_INV=0, p_SR_INV=0, p_SR_VAL=0,
                         i_D=d1_pos, i_CLK=ClockSignal("gtx"), i_EN=1, i_SR=0, o_Q=d1_neg),
                Instance("CC_ODDR", p_CLK_INV=0, i_CLK=ClockSignal("gtx"), i_DDR=ClockSignal("gtx"),
                         i_D0=d0, i_D1=d1_neg, o_Q=pad),
            ]
        oddr(en_r, en_r, pads.tx_ctl)          # TX_CTL: TX_EN on rising, TX_EN ^ TX_ER on falling
        for i in range(4):
            oddr(lo_r[i], hi_r[i], pads.tx_data[i])

        # TXC: selectable clock to the pad. txc_bufg: through a CC_BUFG, i.e. the same kind of path as the ODDR
        # DDR select (global net -> CPE -> IOSEL), so TXC keeps the PLL phase relative to the data. Without it the
        # PLL output is fabric-routed from the PLL (X46) to the pad (X113): 5.8 ns (nextpnr, TASK-5032 p2_s13).
        # A clock through a LUT (inverted, or a runtime mux) to a pad crashes nextpnr's TimingAnalyser (dict::at),
        # so only a constant txc_sel selecting a non-inverted clock builds.
        opts = []
        for c in txc_clks:
            opts += [c, ~c]
        txc = Array(opts)[txc_sel]
        if txc_bufg:
            assert isinstance(txc_sel, int) and txc_sel % 2 == 0
            txc_g = Signal()
            self.specials += Instance("CC_BUFG", i_I=txc_clks[txc_sel // 2], o_O=txc_g)
            txc = txc_g
        self.comb += clock_pads.tx.eq(txc)

        # RX IO: CC_IDDR per pin. Q0 (rising) -> posedge reg; Q1 (falling) -> negedge reg -> posedge reg.
        # Result (one cycle late): rs = rising sample of cycle c, fs = falling sample before it. --
        def iddr(pad, rs, fs):
            q0, q1, q1n = Signal(), Signal(), Signal()
            self.specials += [
                Instance("CC_IDDR", p_CLK_INV=0, i_CLK=ClockSignal("grx"), i_D=pad, o_Q0=q0, o_Q1=q1),
                Instance("CC_DFF", p_CLK_INV=1, p_EN_INV=0, p_SR_INV=0, p_SR_VAL=0,
                         i_D=q1, i_CLK=ClockSignal("grx"), i_EN=1, i_SR=0, o_Q=q1n),
            ]
            self.sync.grx += [rs.eq(q0), fs.eq(q1n)]
        iddr(pads.rx_ctl, core.rx_rs_ctl, core.rx_fs_ctl)
        for i in range(4):
            iddr(pads.rx_data[i], core.rx_rs_dat[i], core.rx_fs_dat[i])


# 100 Mb/s over the same RGMII pins (TASK-5094) ---------------------------------------------------------------
# For the CCGM1A2 (A2): the RGMII balls are bonded only to die 1B, and at 1G the RX path from the IOSEL on 1B to
# logic on 1A needs ~12 ns in an 8 ns cycle (A2_CCGM1A2_TASK-5092.md §3). At 100 Mb/s the KSZ9031 runs RGMII at
# 25 MHz with ONE nibble per RXC/TXC cycle (the same nibble on both edges; RX_CTL = DV on the rising and DV ^ ER on
# the falling edge), so every path gets 40 ns. The PHY logic is GbePHYCore unchanged, under clock enables:
#   RX: grx = RXC (25 MHz); the falling-edge sample (mid-nibble, 20 ns from either data edge) is the nibble of the
#       cycle. The core advances every 2nd cycle and gets rs = this nibble, fs = the previous one, so its A/B
#       pairing = the two possible byte phases of the enable; the SFD picks one per frame, exactly as at 1G.
#       rx_ctl is DV ^ ER, so an RX_ER nibble ends the frame early (bad FCS, dropped by the MAC).
#   TX: gtx stays 125 MHz (it also clocks DVI/USB); the core advances every 10th cycle (80 ns = one byte), the output
#       stage sends the low nibble for 5 cycles, then the high one, and makes TXC itself: high 2 of 5 cycles
#       (25 MHz, 40 % duty), rising 16 ns after the nibble changed, falling 8 ns before the next change. TXC is a
#       register output, so it needs no global net (the 1G TXC takes one).
# The MDIO controller must advertise 100BASE-TX only (REG9 = 0, REG4 = 0x0101).

class Rgmii100Core(LiteXModule):
    """100 Mb/s PHY logic without IO primitives. Domains: sys (sink/source), gtx (125 MHz), grx (RXC, 25 MHz).

    grx inputs  : rx_ctl/rx_dat = falling-edge RGMII sample of this RXC cycle.
    gtx outputs : tx_ctl, tx_dat, txc (registered, straight to the pads).
    """
    def __init__(self, rx_ce_phase=0, diag=False):
        self.core = core = CEInserter(["gtx", "grx"])(GbePHYCore(prim=False, diag=diag))
        self.sink, self.source = core.sink, core.source
        self.rx_frames, self.tx_frames, self.rx_drops = core.rx_frames, core.tx_frames, core.rx_drops

        # RX -------------------------------------------------------------------------------------------
        # The enable phase is re-aligned on every SFD (nibbles 5 -> D while not in a frame): a free-running phase
        # would change against the nibble stream from frame to frame, and the core only re-trains its A/B pairing
        # on a pairing change, losing that frame. At the SFD's D nibble (cycle c) the enable is set so that the
        # core's current pairing sees 0xD5: B needs an enable at c ({nib c-1, nib c}), A one at c+1 ({last enabled
        # rising sample = preamble 5, nib c}); so the pairing never has to change.
        self.rx_ctl, self.rx_dat = RL(), RL(4)
        prev_c, prev_d = RL(), RL(4)
        ce_r = RL(reset=rx_ce_phase)
        infr = RL()
        ce, sfd = Signal(), Signal()
        self.comb += [
            sfd.eq(~infr & self.rx_ctl & prev_c & (self.rx_dat == 0xD) & (prev_d == 0x5)),
            ce.eq(Mux(sfd, core.rx_sel, ce_r)),
        ]
        self.sync.grx += [
            prev_c.eq(self.rx_ctl), prev_d.eq(self.rx_dat), ce_r.eq(~ce),
            infr.eq(self.rx_ctl & (infr | sfd)),
        ]
        self.comb += [
            core.ce_grx.eq(ce),
            core.rx_rs_ctl.eq(self.rx_ctl), core.rx_rs_dat.eq(self.rx_dat),
            core.rx_fs_ctl.eq(prev_c),      core.rx_fs_dat.eq(prev_d),
        ]

        # TX -------------------------------------------------------------------------------------------
        self.tx_ctl, self.tx_dat, self.txc = RL(), RL(4), RL()
        k = RL(4)      # 0..9; the core's byte changes at the edge that ends k = 9
        self.comb += core.ce_gtx.eq(k == 9)
        self.sync.gtx += [
            k.eq(Mux(k == 9, 0, k + 1)),
            self.tx_ctl.eq(core.tx_en),
            self.tx_dat.eq(Mux(k < 5, core.tx_byte[:4], core.tx_byte[4:]) & Replicate(core.tx_en, 4)),
            self.txc.eq((k == 2) | (k == 3) | (k == 7) | (k == 8)),
        ]


class Rgmii100PHY(LiteXModule):
    """100 Mb/s RGMII PHY with GateMate IO primitives (same pads and interface as GbePHY).

    clk_tx : 125 MHz (gtx0). RXC: pad -> CC_BUFG -> grx. LiteEth sees eth_tx/eth_rx = sys.
    """
    dw          = 8
    tx_clk_freq = 20e6     # overwritten by the target: LiteEth's eth_tx/eth_rx = sys
    rx_clk_freq = 20e6

    def __init__(self, clock_pads, pads, clk_tx, rst, rx_fabric=False, diag=False):
        # rx_fabric: sample RX_CTL/RXD with fabric flip-flops (CC_IBUF -> negedge CC_DFF) instead of CC_IDDR. On the
        # CCGM1A2 the CC_IDDR in the die-1B IOSEL never returns data (docs/nextpnr_a2_repro/rxprobe, TASK-5094),
        # while the pins themselves carry the frames; at 25 MHz the pad -> die 1A fabric path (~12 ns) fits.
        self.c = c = Rgmii100Core(diag=diag)
        self.sink, self.source = c.sink, c.source

        self.cd_gtx = ClockDomain()
        self.cd_grx = ClockDomain()
        self.cd_eth_tx = ClockDomain()
        self.cd_eth_rx = ClockDomain()
        self.comb += [
            self.cd_gtx.clk.eq(clk_tx),
            self.cd_eth_tx.clk.eq(ClockSignal("sys")), self.cd_eth_tx.rst.eq(ResetSignal("sys")),
            self.cd_eth_rx.clk.eq(ClockSignal("sys")), self.cd_eth_rx.rst.eq(ResetSignal("sys")),
        ]
        rxc_buf = Signal()
        self.specials += Instance("CC_BUFG", i_I=clock_pads.rx, o_O=rxc_buf)
        self.comb += self.cd_grx.clk.eq(rxc_buf)
        self.specials += [
            AsyncResetSynchronizer(self.cd_gtx, rst),
            AsyncResetSynchronizer(self.cd_grx, rst),
        ]

        # TX: the output stage is already registered in gtx; CC_ODDR with D0 = D1 puts that register in the IOSEL
        # (same value on both edges, as RGMII 10/100 wants).
        def oddr(d, pad):
            self.specials += Instance("CC_ODDR", p_CLK_INV=0, i_CLK=ClockSignal("gtx"), i_DDR=ClockSignal("gtx"),
                                      i_D0=d, i_D1=d, o_Q=pad)
        oddr(c.tx_ctl, pads.tx_ctl)
        for i in range(4):
            oddr(c.tx_dat[i], pads.tx_data[i])
        oddr(c.txc, clock_pads.tx)

        # RX: CC_IDDR Q1 (falling edge, mid-nibble) -> negedge reg -> posedge reg = sample of this RXC cycle.
        def iddr_fall(pad, out):
            q0, q1, q1n = Signal(), Signal(), Signal()
            if rx_fabric:
                q1 = pad            # the negedge CC_DFF samples the pad itself (mid-nibble)
            else:
                self.specials += Instance("CC_IDDR", p_CLK_INV=0, i_CLK=ClockSignal("grx"), i_D=pad, o_Q0=q0, o_Q1=q1)
            self.specials += Instance("CC_DFF", p_CLK_INV=1, p_EN_INV=0, p_SR_INV=0, p_SR_VAL=0,
                                      i_D=q1, i_CLK=ClockSignal("grx"), i_EN=1, i_SR=0, o_Q=q1n)
            self.sync.grx += out.eq(q1n)
        iddr_fall(pads.rx_ctl, c.rx_ctl)
        for i in range(4):
            iddr_fall(pads.rx_data[i], c.rx_dat[i])
