#
# DVI output + 2x-scaled framebuffer for the ULX5M-GS standalone computer (TASK-5040).
#
# DVI:    TMDS 640x480@60 on IO_SB_A4..B7 (DDMI0). hdmi5x = 125 MHz from its own PLL, hdmi = 25 MHz from a
#         divide-by-5 flop chain (GateMate PLL outputs are one frequency with 4 phases, so 25 and 125 MHz cannot
#         share one PLL). PHY and divider are copied from GateMate_demos/LiteX_DVI (Miodrag Milanovic, 2025),
#         which is proven on this board (README: "DVI - tested and works" from v004).
#
# Framebuffer: LiteX VideoFrameBuffer at 640x480 rgb565 needs 36.9 MB/s = 92 % of the 16-bit SDRAM peak
#         (40 MB/s at 20 MHz), so the CPU would starve. FrameBuffer2x reads a 320x240 rgb565 frame (9.2 MB/s, 23 %)
#         and doubles every pixel and every line in hardware: even lines are taken from the DMA and written into a
#         320x16 line buffer, odd lines are replayed from it. Linux sees a plain 320x240 r5g6b5 simple-framebuffer.
#
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen import *

from litex.build.io import DDROutput
from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import CSRStatus
from litex.soc.cores.code_tmds import TMDSEncoder
from litex.soc.cores.video import video_timing_layout, video_data_layout, _dvi_c2d


class Divide5(LiteXModule):
    """50 % duty cycle clk/5 (flop chain + one negedge flop), from LiteX_DVI."""
    def __init__(self, clock_domain):
        self.clk_o = Signal()
        # load: high in the fast cycle before the edge that is 3 fast cycles after the divided clock rises
        # (states 000 001 010 011 110; clk_o rises entering 010) -> serializer word load with 2-3 fast cycles
        # of margin on both sides, no hdmi->hdmi5x sampling of a toggle (TASK-5040, drop-outs under SDRAM load).
        self.load = Signal()
        d, q, qbar = Signal(3), Signal(3), Signal(3)
        qtemp = Signal(reset_less=True)
        self.comb += [
            qbar[0].eq(~q[2]), qbar[1].eq(~q[1]), qbar[2].eq(~q[0]),
            d[0].eq(qbar[2] & qbar[0]),
            d[1].eq((q[1] & qbar[0]) | (qbar[1] & q[0])),
            d[2].eq(q[1] & q[0]),
        ]
        sync = getattr(self.sync, clock_domain)
        sync += q.eq(d)
        self.specials += Instance("CC_DFF", p_CLK_INV=1, p_EN_INV=0, p_SR_INV=0, p_SR_VAL=0,
                                  i_D=q[1], i_CLK=ClockSignal(clock_domain), i_EN=1, i_SR=0, o_Q=qtemp)
        self.comb += [self.clk_o.eq(q[1] | qtemp), self.load.eq(q == 0b110)]


class _Serializer10to2(LiteXModule):
    """10:1 TMDS serializer: 10-bit word in pix, shifted out 2 bits per 5x cycle through CC_ODDR (LiteX_DVI custom).
    With `ce` (single-clock mode) the word is loaded in the fast domain whenever ce is high (1 cycle in 5)."""
    def __init__(self, data_i, data_o, pix, fast, ce=None):
        dat = Signal(10)
        sf = getattr(self.sync, fast)
        if ce is None:
            tog, tog_d, edge = Signal(), Signal(), Signal()
            sp = getattr(self.sync, pix)
            sp += tog.eq(~tog)
            sf += [tog_d.eq(tog), edge.eq(tog_d ^ tog)]
        else:
            edge = ce
        sf += If(edge, dat.eq(data_i)).Else(dat.eq(Cat(dat[2:10], C(0, 2))))
        self.specials += DDROutput(clk=ClockSignal(fast), i1=dat[0], i2=dat[1], o=data_o)


class DVIPHY(LiteXModule):
    """clock_domain = pixel clock, clock_domain+"5x" = bit clock/2 (two clocks, two global nets).
    ce_domain: single-clock mode - everything runs in ce_domain (125 MHz) and the pixel logic advances when ce is
    high (1 cycle in 5); the TMDS clock pair is a 2-high/3-low pattern through CC_ODDR (no pixel-clock net)."""
    def __init__(self, pads, clock_domain="hdmi", ce_domain=None, ce=None, neg_sync=False, ser_load=None):
        # ce: Signal, or a factory returning a fresh ce register per call (CE tree: a single ce net with fanout
        # ~150 reached the FF enables after 10.9 ns > 8 ns at 125 MHz -> sporadic TMDS/sync errors, TASK-5040).
        mk = ce if callable(ce) else (lambda: ce)
        self.sink = sink = stream.Endpoint(video_data_layout)
        self.comb += sink.ready.eq(1)
        fast = ce_domain or clock_domain + "5x"
        if ce_domain is None:
            self.specials += Instance("CC_LVDS_OBUF", i_A=ClockSignal(clock_domain), o_O_P=pads.clk_p, o_O_N=pads.clk_n)
        else:
            # 10-bit clock word 0b0000011111 shifted out like the data: 5 bits high, 5 low per pixel.
            clk_o = Signal()
            self.clk_serializer = _Serializer10to2(C(0b0000011111, 10), clk_o, None, fast, mk())
            self.specials += Instance("CC_LVDS_OBUF", i_A=clk_o, o_O_P=pads.clk_p, o_O_N=pads.clk_n)
        for color, channel in _dvi_c2d.items():
            if ce_domain is None:
                enc = ClockDomainsRenamer(clock_domain)(TMDSEncoder())
            else:
                enc = ClockDomainsRenamer(ce_domain)(CEInserter()(TMDSEncoder()))
                self.comb += enc.ce.eq(mk())
            self.add_module(name=f"{color}_encoder", module=enc)
            self.comb += [enc.d.eq(getattr(sink, color)), enc.de.eq(sink.de),
                          enc.c.eq((Cat(~sink.hsync, ~sink.vsync) if neg_sync else Cat(sink.hsync, sink.vsync))
                                   if channel == 0 else 0)]    # neg_sync: VESA 640x480 (both negative)
            o = Signal()
            self.add_module(name=f"{color}_serializer", module=_Serializer10to2(enc.out, o, clock_domain, fast,
                            mk() if ce is not None else ser_load))    # ser_load: Divide5.load (two-clock mode)
            self.specials += Instance("CC_LVDS_OBUF", i_A=o,
                                      o_O_P=getattr(pads, f"data{channel}_p"), o_O_N=getattr(pads, f"data{channel}_n"))


class ResyncWatchdog(LiteXModule):
    """TASK-5047: wd = 1 after `n` resyncs with no good frame in between; stays 1 until this domain is reset.
    A clock disturbance can leave the never-reset CE video path (ce counters, VTG, CDC read side) misaligned for
    good: every frame then ends without the DMA `last` (black picture with valid sync, resyncs == frames)."""
    def __init__(self, n=4):
        self.resync   = Signal()
        self.frame_ok = Signal()
        self.wd       = Signal()
        cnt = Signal(max=n + 1)
        self.sync += If(cnt != n, If(self.frame_ok, cnt.eq(0)).Elif(self.resync, cnt.eq(cnt + 1)))
        self.comb += self.wd.eq(cnt == n)


class FrameBuffer2x(LiteXModule):
    """hres/2 x vres/2 rgb565 frame from a LiteDRAM port, shown pixel- and line-doubled at hres x vres.

    CSRs (LiteX DMA reader): dma_base, dma_length, dma_enable, dma_loop. Scan-out is enabled at reset
    (enable=1), so the BIOS and Linux simplefb only write pixels into main RAM."""
    def __init__(self, port, hres=640, vres=480, base=0, clock_domain="hdmi", fifo_depth=2048, enable=1, ce=None,
                 hdouble=True, cdc_from="sys"):
        # cdc_from: domain of the CDC write side (same clock as sys; "vsys" = sys with the video recovery reset).
        self.vtg_sink = stream.Endpoint(video_timing_layout)
        self.source   = stream.Endpoint(video_data_layout)
        self.fb_width = hres//2 if hdouble else hres
        self.size = self.fb_width*(vres//2)*2

        from litedram.frontend.dma import LiteDRAMDMAReader
        assert port.data_width == 16, "FrameBuffer2x: one rgb565 pixel per DRAM word"
        self.dma = LiteDRAMDMAReader(port, fifo_depth=fifo_depth//2, fifo_buffered=True)
        self.dma.add_csr(default_base=base, default_length=self.size, default_enable=enable, default_loop=1)
        self.cdc = stream.ClockDomainCrossing([("data", 16)], cd_from=cdc_from, cd_to=clock_domain, depth=8)
        self.comb += self.dma.source.connect(self.cdc.sink)
        dma_reset = Signal()
        self.specials += MultiReg(self.dma.fsm.reset, dma_reset, clock_domain)
        mk = ce if callable(ce) else (lambda: ce)
        if ce is None:
            self.scaler = ClockDomainsRenamer(clock_domain)(Scaler2x(self.fb_width, hdouble))
            self.comb += self.cdc.source.connect(self.scaler.pix)
        else:
            # single-clock mode: the scaler advances on ce only, so it may pop the CDC FIFO only on ce cycles.
            # ready is registered (stable for the whole 5-cycle window): the unregistered scaler ready -> FIFO
            # gray counter path took 18 ns, a true 1-cycle path at 125 MHz.
            ce_sc = mk()
            ready_q = Signal()
            self.scaler = ClockDomainsRenamer(clock_domain)(CEInserter()(Scaler2x(self.fb_width, hdouble)))
            sd = getattr(self.sync, clock_domain)
            sd += ready_q.eq(self.scaler.pix.ready)
            self.comb += [
                self.scaler.ce.eq(ce_sc),
                self.scaler.we_ce.eq(ce_sc),
                self.cdc.source.connect(self.scaler.pix, omit={"ready"}),
                self.cdc.source.ready.eq(ready_q & mk()),
            ]
        self.comb += [
            self.scaler.reset.eq(dma_reset),
            self.vtg_sink.connect(self.scaler.vtg),
            self.scaler.source.connect(self.source),
        ]
        self.underflow = self.scaler.underflow
        # Recovery request (TASK-5047), in the video domain; the SoC resets the whole video path on it.
        self.watchdog = ClockDomainsRenamer(clock_domain)(ResyncWatchdog(4))
        en_wd = (lambda: 1) if ce is None else mk
        self.comb += [self.watchdog.resync.eq(en_wd() & self.scaler.resync),
                      self.watchdog.frame_ok.eq(en_wd() & self.scaler.frame_ok)]
        self.wd = self.watchdog.wd

        # Diagnostics (TASK-5040 uputa #59): counters in the video domain, read through MultiReg (a torn read is
        # possible but harmless for a slowly moving counter). frames = VTG frame ends, underflows = pixels the
        # scaler needed but the DMA FIFO did not have, resyncs = frames that ended without the DMA `last`.
        self._frames    = CSRStatus(32, description="VTG frames shown (video domain)")
        self._underflow = CSRStatus(32, description="scaler underflow pixels")
        self._resyncs   = CSRStatus(32, description="frames that lost DMA alignment")
        frames, underflows, resyncs = Signal(32), Signal(32), Signal(32)
        sv = getattr(self.sync, clock_domain)
        en = (lambda: 1) if ce is None else mk
        sv += If(en() & self.scaler.frame_end, frames.eq(frames + 1))
        sv += If(en() & self.scaler.underflow, underflows.eq(underflows + 1))
        sv += If(en() & self.scaler.resync, resyncs.eq(resyncs + 1))
        self.specials += [MultiReg(frames, self._frames.status), MultiReg(underflows, self._underflow.status),
                          MultiReg(resyncs, self._resyncs.status)]


class Scaler2x(LiteXModule):
    """Pixel/line doubler (single clock domain, testable in migen sim, test/test_scaler2x.py).

    vtg: LiteX VideoTimingGenerator stream (de high for hcount 1..hres, vcount 1..vres -> pixel (hcount-1, vcount-1)).
    pix: rgb565 stream, one frame of sw x (vres/2) pixels, `last` on the final pixel.
    Even output lines take a new pixel at every even x and store it in a sw x 16 line buffer; odd lines replay it.
    Frame alignment as in LiteX VideoFrameBuffer: wait for the end of a VTG frame, consume one frame, repeat; the
    first frame after reset is discarded (the DMA may have started mid-frame)."""
    def __init__(self, sw, hdouble=True):
        # hdouble=False (TASK-5047): sw = hres, only lines are doubled (640x240 frame -> 640x480, 8x16 px glyphs).
        self.vtg    = vtg = stream.Endpoint(video_timing_layout)
        self.pix    = pix = stream.Endpoint([("data", 16)])
        self.source = src = stream.Endpoint(video_data_layout)
        self.reset  = Signal()
        self.underflow = Signal()
        self.frame_end = Signal()
        self.resync    = Signal()
        self.frame_ok  = Signal()
        self.we_ce  = Signal(reset=1)   # CE mode: memory ports are not gated by CEInserter -> write enable and
                                        # read enable of the line buffer follow ce (else dat_r runs 1 pixel ahead)

        mem = Memory(16, sw)
        wr = mem.get_port(write_capable=True)
        rd = mem.get_port(has_re=True)
        self.specials += mem, wr, rd

        px, py = Signal(len(vtg.hcount)), Signal(len(vtg.vcount))
        self.comb += [px.eq(vtg.hcount - 1), py.eq(vtg.vcount - 1)]
        x2 = px[1:] if hdouble else px
        even_x, even_y = (~px[0] if hdouble else 1), ~py[0]

        # first: drain the (possibly mid-frame) DMA frame after reset up to `last`, then wait for a VTG frame end.
        # running: aligned to VTG frames; done: this frame's pixels are consumed (the rest of the frame is shown).
        # A frame that ends without `last` (underflow/misalignment) drops back to `first` and resyncs.
        running, first, done = Signal(), Signal(reset=1), Signal()
        take, frame_end = Signal(), Signal()
        self.comb += [
            vtg.ready.eq(1),
            frame_end.eq(vtg.valid & vtg.last),
            self.frame_end.eq(frame_end),
            self.resync.eq(running & ~first & frame_end & ~(done | (take & pix.valid & pix.last))),
            self.frame_ok.eq(running & ~first & frame_end & (done | (take & pix.valid & pix.last))),
            take.eq(running & ~first & ~done & vtg.valid & vtg.de & even_x & even_y),
            pix.ready.eq(take | first),
            wr.adr.eq(x2), wr.dat_w.eq(pix.data), wr.we.eq(take & pix.valid & self.we_ce),
            rd.adr.eq(x2), rd.re.eq(self.we_ce),
        ]
        self.sync += [
            If(self.reset,
                running.eq(0), first.eq(1), done.eq(0)
            ).Elif(first,
                running.eq(0), done.eq(0),
                If(pix.valid & pix.last, first.eq(0))
            ).Elif(~running,
                If(frame_end, running.eq(1))
            ).Else(
                If(take & pix.valid & pix.last, done.eq(1)),
                If(frame_end,
                    If(done | (take & pix.valid & pix.last), done.eq(0)).Else(first.eq(1), running.eq(0))
                )
            ),
        ]

        # One register stage: even line = the DMA pixel (held for the odd x), odd line = line buffer.
        hold = Signal(16)
        cur  = Signal(16)
        de_d, hs_d, vs_d, ev_y_d, show = Signal(), Signal(), Signal(), Signal(), Signal()
        self.sync += [
            If(take, hold.eq(Mux(pix.valid, pix.data, 0))),
            de_d.eq(vtg.valid & vtg.de), hs_d.eq(vtg.hsync), vs_d.eq(vtg.vsync), ev_y_d.eq(even_y),
            show.eq(running & ~first),
        ]
        self.comb += [
            cur.eq(Mux(ev_y_d, hold, rd.dat_r)),
            src.valid.eq(1),
            src.de.eq(de_d), src.hsync.eq(hs_d), src.vsync.eq(vs_d),
            If(de_d & show,
                src.r.eq(Cat(C(0, 3), cur[11:16])),
                src.g.eq(Cat(C(0, 2), cur[5:11])),
                src.b.eq(Cat(C(0, 3), cur[0:5])),
            ),
            self.underflow.eq(take & ~pix.valid & ~first),
        ]
