#
# LiteEth RGMII PHY for CologneChip GateMate (Radiona ULX5M-GS + KSZ9031).
#
# Modeled on liteeth/phy/ecp5rgmii.py but GateMate-specific:
#  - NO Lattice DELAYG anywhere. GateMate does have a programmable pad delay
#    (`CC_IBUF(DELAY_IBF=n)` / `CC_OBUF(DELAY_OBF=n)`, 16 taps, 30/38/50 ps per tap
#    best/typ/worst in SPEED mode -> max ~0.5-0.8 ns), but that is far short of the
#    2 ns RGMII needs, so we connect the DDR I/O directly to the pads and leave the
#    2 ns to the PHY's own RGMII-ID. Cologne Chip's own reference does the same
#    (pu-cc/liteeth `gatematergmii`: tx_delay=rx_delay=0).
#    Corrected 2026-09-21, TASK-4961.
#  - Uses LiteX generic DDROutput/DDRInput (litex.build.io); the CologneChip
#    backend (litex/build/colognechip/common.py) auto-lowers these to
#    CC_ODDR/CC_IDDR. We never hand-instantiate CC_ODDR/CC_IDDR here.
#  - Reuses LiteEth's datapath/clock/link-state helpers by importing them
#    from liteeth.phy.ecp5rgmii (not copying them): LiteEthRGMIITXClock,
#    LiteEthRGMIITXDatapath, LiteEthRGMIIRXDatapath, LiteEthRGMIILinkState.
#    Only the pad-facing TX, RX and CRG are reimplemented here.
#  - CRG:
#      * cd_eth_rx.clk = clock_pads.rx (PHY RXC, IO_EB_A7 on the ULX5M-GS).
#        This pin is non-clock-capable. CC_BUFG on it BUILDS FINE (measured
#        2026-09-21, TASK-4961) but costs a third global clock net and makes some
#        seeds unroutable, so the default keeps it on fabric routing
#        (`clkbuf_inhibit`); `rxc_global=True` opts into the global net.
#      * cd_eth_tx.clk = a tx_clk Signal supplied by the target (the 25 MHz
#        PLL#1 output per docs/GATEMATE_CLOCKING.md), falling back to
#        cd_eth_rx.clk if none is given.
#      * TXC is forwarded to clock_pads.tx via DDROutput (no DELAYG).
#      * PHY reset = LiteEthPHYHWReset (CPU-less power-on pulse) ORed with a
#        _reset CSRStorage; pads.rst_n driven active-low if present.
#        AsyncResetSynchronizer on both domains (lowers to CC_DFF-based reset
#        sync on CologneChip, see litex/build/colognechip/common.py).
#
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import *

from litex.build.io import DDROutput, DDRInput

from liteeth.common import *
from litex.soc.interconnect.packet import PacketFIFO
from liteeth.phy.common import LiteEthPHYHWReset, LiteEthPHYMDIO

from mdio_sequencer import MDIOWriteSequencer
from liteeth.phy.ecp5rgmii import (
    LiteEthRGMIILinkState,
    LiteEthRGMIITXClock,
    LiteEthRGMIITXDatapath,
    LiteEthRGMIIRXDatapath,
)

# Fixed 100 Mbps link state -------------------------------------------------------------------------

def fixed_100m_link_state(module):
    """Link state tied to 100 Mbps. The board only ever runs 100M; deriving link_1G from the
    RGMII in-band status lets a garbled/absent status word (measured S=2/S=3, TASK-4999) flip
    the TX/RX datapath into gigabit byte framing -> zero valid frames."""
    ls = LiteEthRGMIILinkState()
    module.comb += [ls.link_up.eq(1), ls.link_10M.eq(0), ls.link_100M.eq(1), ls.link_1G.eq(0)]
    return ls

# LiteEth RGMII 100M TX core (GateMate) ------------------------------------------------------------

class LiteEthRGMIITX100MCore(LiteXModule):
    """Pad-independent 100M TX logic: optional store-and-forward FIFO + 10/100 nibble datapath.

    store_forward: buffer each whole frame before it goes on the wire. The sys domain may be
    no faster than the 12.5 MB/s line rate (12.5 MHz sys on a 0.9 V core), so the TX CDC can
    run dry mid-frame; a gap in TX_EN corrupts the frame. Verified by sim/tb_rgmii_tx_sf.py.
    """
    def __init__(self, store_forward=True, depth=2048, tx_enable=1):
        # tx_enable: 1 = one nibble per eth_tx cycle (25 MHz); a toggling signal = one nibble per
        # two cycles (eth_tx = 50 MHz, io50 mode).
        self.sink    = sink = stream.Endpoint(eth_phy_description(8))
        self.tx_ctl  = Signal(2)
        self.tx_data = Signal(8)

        # # #

        self.datapath = datapath = LiteEthRGMIITXDatapath(fixed_100m_link_state(self), tx_enable=tx_enable)
        if store_forward:
            self.fifo = fifo = PacketFIFO(eth_phy_description(8), payload_depth=depth,
                                          param_depth=4, buffered=True)
            self.comb += [sink.connect(fifo.sink), fifo.source.connect(datapath.sink)]
        else:
            self.comb += sink.connect(datapath.sink)
        self.comb += [self.tx_ctl.eq(datapath.tx_ctl), self.tx_data.eq(datapath.tx_data)]

# LiteEth PHY RGMII TX (GateMate) -------------------------------------------------------------------

class LiteEthPHYRGMIITX_GateMate(LiteXModule):
    """RGMII TX pad interface. Thin DDR serdes only, no delay primitive."""
    def __init__(self, pads, link_state=None, tx_enable=1, core_100m=None, sdr_tx=False, io_ff=False):
        self.sink = sink = stream.Endpoint(eth_phy_description(8))
        self.tx_ctl_readback = None

        # # #

        tx_ctl  = Signal(2)
        tx_data = Signal(8)

        if core_100m is not None:
            self.core = core_100m
            self.comb += [
                sink.connect(core_100m.sink),
                tx_ctl.eq(core_100m.tx_ctl),
                tx_data.eq(core_100m.tx_data),
            ]
        elif link_state is None:
            self.comb += [
                sink.ready.eq(1),
                tx_ctl.eq(Cat(sink.valid, sink.valid)),
                tx_data.eq(sink.data),
            ]
        else:
            self.datapath = datapath = LiteEthRGMIITXDatapath(link_state, tx_enable)
            self.comb += [
                sink.connect(datapath.sink),
                tx_ctl.eq(datapath.tx_ctl),
                tx_data.eq(datapath.tx_data),
            ]

        if io_ff:
            # io50 (TASK-4999): one posedge flip-flop per pin, packed into the IOSEL (FF_OBF=true in the
            # .ccf; reset_less + single fanout, as the packer requires). eth_tx = 50 MHz, the datapath
            # changes every 2nd cycle, TXC comes from the CRG's CLK180 IO FF.
            ctl_io, dat_io = Signal(reset_less=True), Signal(4, reset_less=True)
            self.sync += [ctl_io.eq(tx_ctl[0]), dat_io.eq(tx_data[0:4])]
            self.comb += [pads.tx_ctl.eq(ctl_io), pads.tx_data.eq(dat_io)]
            return
        if sdr_tx:
            # TASK-4999 isolation: no CC_ODDR. At 100M the datapath already repeats the nibble on
            # both edges (tx_data = {n, n}, tx_ctl = {v, v}), so a plain eth_tx register is the
            # same waveform. TX_CTL goes through a CC_IOBUF so the pad is read back.
            from migen.fhdl.specials import Tristate
            ctl_r, dat_r, oe = Signal(), Signal(4), Signal()
            self.sync.eth_tx += [ctl_r.eq(tx_ctl[0]), dat_r.eq(tx_data[0:4]), oe.eq(1)]
            self.tx_ctl_readback = Signal()
            self.specials += Tristate(pads.tx_ctl, ctl_r, oe, self.tx_ctl_readback)
            self.comb += pads.tx_data.eq(dat_r)
            return
        # DDR outputs drive the pads directly -- no DELAYG (GateMate has none).
        self.specials += DDROutput(
            clk = ClockSignal("eth_tx"),
            i1  = tx_ctl[0],
            i2  = tx_ctl[1],
            o   = pads.tx_ctl,
        )
        for i in range(4):
            self.specials += DDROutput(
                clk = ClockSignal("eth_tx"),
                i1  = tx_data[i],
                i2  = tx_data[4 + i],
                o   = pads.tx_data[i],
            )

# LiteEth PHY RGMII RX (GateMate) -------------------------------------------------------------------

class LiteEthPHYRGMIIRX_GateMate(LiteXModule):
    """RGMII RX pad interface. Thin DDR capture only, no delay primitive."""
    def __init__(self, pads, with_inband_status=True, link_state=None, fixed_link=False, rx_off=False,
                 sdr_rx=False):
        self.source = source = stream.Endpoint(eth_phy_description(8))

        if with_inband_status:
            self.inband_status = CSRStatus(fields=[
                CSRField("link_status", size=1, description="Link status.", values=[
                    ("``0b0``", "Link down."),
                    ("``0b1``", "Link up."),
                ]),
                CSRField("clock_speed", size=2, description="Clock speed.", values=[
                    ("``0b00``", "2.5MHz   (10Mbps)."),
                    ("``0b01``", "25MHz   (100MBps)."),
                    ("``0b10``", "125MHz (1000MBps)."),
                ]),
                CSRField("duplex_status", size=1, description="Duplex status.", values=[
                    ("``0b0``", "Half-duplex."),
                    ("``0b1``", "Full-duplex."),
                ]),
            ], description="RGMII in-band status.")

        # # #

        rx_ctl  = Signal(2)
        rx_data = Signal(8)

        if sdr_rx:
            # TASK-4999 isolation: no CC_IDDR (the vendor p_r reports "IDDR input pin could not be
            # routed" on this bank). At 100M the 10/100 datapath only uses the rising-edge half
            # (rx_ctl[0], rx_data[0:4]), so a plain fabric register on RXC is equivalent.
            ctl_s, dat_s = Signal(), Signal(4)
            self.sync += [ctl_s.eq(pads.rx_ctl), dat_s.eq(pads.rx_data)]
            self.comb += [rx_ctl.eq(Cat(ctl_s, ctl_s)), rx_data.eq(Cat(dat_s, dat_s))]
        else:
          # DDR inputs sample the pads directly -- no DELAYG (GateMate has none).
          self.specials += DDRInput(
            clk = ClockSignal("eth_rx"),
            i   = pads.rx_ctl,
            o1  = rx_ctl[0],
            o2  = rx_ctl[1],
          )
          for i in range(4):
            self.specials += DDRInput(
                clk = ClockSignal("eth_rx"),
                i   = pads.rx_data[i],
                o1  = rx_data[i],
                o2  = rx_data[i + 4],
            )

        self.datapath = datapath = LiteEthRGMIIRXDatapath(link_state)
        self.comb += [
            # rx_off (TASK-4999 isolation): the MAC never sees a received frame.
            datapath.rx_ctl.eq(0 if rx_off else rx_ctl),
            datapath.rx_data.eq(rx_data),
        ]
        self.comb += datapath.source.connect(source)

        if with_inband_status:
            inband_status = [
                self.inband_status.fields.link_status.eq(  rx_data[0]),
                self.inband_status.fields.clock_speed.eq(  rx_data[1:3]),
                self.inband_status.fields.duplex_status.eq(rx_data[3]),
            ]
            if link_state is not None and not fixed_link:
                inband_status += [
                    link_state.link_up.eq(rx_data[0]),
                    link_state.link_10M.eq(rx_data[1:3] == 0b00),
                    link_state.link_100M.eq(rx_data[1:3] == 0b01),
                    link_state.link_1G.eq(rx_data[1:3] == 0b10),
                ]
            self.sync += [
                If(rx_ctl == 0b00,
                    *inband_status
                )
            ]

# LiteEth PHY RGMII CRG (GateMate) ------------------------------------------------------------------

class LiteEthPHYRGMIICRG_GateMate(LiteXModule):
    def __init__(self, clock_pads, pads, with_hw_init_reset, tx_clk=None, link_state=None,
                 fixed_100m=False, rxc_global=False, tx_clk90=None, hw_reset_cycles=256, txc_readback=False,
                 ctrl_cd="sys", tx_clk180=None):
        self._reset = CSRStorage(description="PHY reset.")
        self.tx_enable     = Signal(reset=1)
        self.tx_gap_cycles = Signal(max=eth_interpacket_gap*100 + 1, reset=eth_interpacket_gap)

        # # #

        # RX Clock: RXC is non-clock-capable on this board (IO_EB_A7). Default keeps
        # it on fabric routing; see rxc_global below.
        self.cd_eth_rx = ClockDomain()
        self.comb += self.cd_eth_rx.clk.eq(clock_pads.rx)
        # RXC clock routing. Two options:
        #  rxc_global=False (default): inhibit clock-buffer insertion -> RXC stays on general
        #    fabric routing. Skew-prone, so RX capture can be marginal (some frame loss
        #    possible), but it always routes.
        #  rxc_global=True: let Yosys CLKBUFMAP promote RXC onto a global clock net via CC_BUFG
        #    (deterministic low-skew capture; required for 1 Gbps). Measured 2026-09-21: this
        #    does NOT crash nextpnr -- it builds to a bitstream -- but the third global clock
        #    makes routing seed-fragile (seeds that previously routed can fail with
        #    "Failed to route arc ... GLBOUT0"). Sweep seeds if you enable it.
        if not rxc_global:
            self.cd_eth_rx.clk.attr.add(("clkbuf_inhibit", 1))

        # TX Clock: supplied by the target (25 MHz PLL output), fallback to
        # looping RXC back if none given.
        self.cd_eth_tx = ClockDomain()
        if isinstance(tx_clk, Signal):
            self.comb += self.cd_eth_tx.clk.eq(tx_clk)
        else:
            self.comb += self.cd_eth_tx.clk.eq(self.cd_eth_rx.clk)

        # TX-clock / datapath pacing.
        # fixed_100m: the split-clock CRG already supplies eth_tx = 25 MHz = the 100 Mbps line
        # rate, so TXC is a straight pass-through (rising=1/falling=0) and the RGMII datapath is
        # paced every clock (tx_enable=1) => one nibble per 25 MHz clock, one byte over two
        # clocks. Do NOT use LiteEthRGMIITXClock, whose 100M mode divides an assumed-125 MHz
        # eth_tx by 5 (would give a wrong 5 MHz TXC here).
        self.tx_phase = None
        if fixed_100m and tx_clk180 is not None:
            # io50: eth_tx = 50 MHz. tx_phase toggles every cycle; the datapath advances when it is 1,
            # so every nibble lasts 2 cycles (40 ns). The TXC IO FF samples tx_phase on CLK180 (the
            # falling edge of eth_tx): TXC rises 10 ns after the TXD/TX_CTL IO FFs change and falls
            # 30 ns after -> both RGMII sample edges see the same nibble with 10 ns margins
            # (sim: tools/uhello/tb_eb50.v and sim/tb_io50.py).
            self.tx_phase = ph = Signal()
            self.sync.eth_tx += ph.eq(~ph)
            self.comb += [
                self.tx_enable.eq(ph),
                self.tx_gap_cycles.eq(eth_interpacket_gap*4),
            ]
            txc_rising, txc_falling = 1, 0
        elif fixed_100m:
            self.comb += [
                self.tx_enable.eq(1),
                self.tx_gap_cycles.eq(eth_interpacket_gap*2),
            ]
            txc_rising, txc_falling = 1, 0
        else:
            self.tx_clock = tx_clock = LiteEthRGMIITXClock(
                link_state      = link_state,
                external_tx_clk = isinstance(tx_clk, Signal),
            )
            self.comb += [
                self.tx_enable.eq(tx_clock.tx_enable),
                self.tx_gap_cycles.eq(tx_clock.gap_cycles),
            ]
            txc_rising, txc_falling = tx_clock.rising, tx_clock.falling

        # Forward TXC to the PHY -- no DELAYG.
        # KSZ9031 adds NO delay on its TX inputs (DS00002117F p.22: "expects the GTX_CLK delay to
        # be provided on-chip by the MAC"). A TXC from the same DDR clock as TXD/TX_CTL puts its
        # edges exactly on the data transitions. tx_clk90 = same 25 MHz, +90 deg (PLL CLK90):
        # TXC rises 10 ns after the data changes and falls 10 ns before the next change, so
        # both RGMII sample edges (TX_EN on rise, TX_EN^TX_ER on fall) see >=10 ns setup/hold.
        # The CLK90 net goes straight to the pad (not through CC_ODDR): GateMate allows only one
        # DDR clock source per IO bank and TXD/TX_CTL already use eth_tx there ("DDR port use
        # signal different than already occupied DDR source"). A few ns of fabric delay is well
        # inside the 10 ns margin.
        self.txc_readback = None
        if tx_clk180 is not None:
            assert fixed_100m and tx_clk90 is None
            self.cd_eth_tx180 = ClockDomain(reset_less=True)
            self.comb += self.cd_eth_tx180.clk.eq(tx_clk180)
            txc_io = Signal(reset_less=True)
            self.sync.eth_tx180 += txc_io.eq(self.tx_phase)
            self.comb += clock_pads.tx.eq(txc_io)
        elif tx_clk90 is not None:
            assert fixed_100m
            if txc_readback:
                # TASK-4999: drive TXC through a CC_IOBUF and read the pad back (Y), so the design
                # can prove the pin really toggles. T is a live register (constant T hits the
                # nextpnr pack_io const-T bug, memory: gatemate-iobuf-workaround).
                from migen.fhdl.specials import Tristate
                txc_oe = Signal()
                self.txc_readback = Signal()
                self.sync += txc_oe.eq(1)
                self.specials += Tristate(clock_pads.tx, tx_clk90, txc_oe, self.txc_readback)
            else:
                self.comb += clock_pads.tx.eq(tx_clk90)
        else:
            self.specials += DDROutput(
                clk = ClockSignal("eth_tx"),
                i1  = txc_rising,
                i2  = txc_falling,
                o   = clock_pads.tx,
            )

        # Reset.
        self.reset = reset = Signal()
        if with_hw_init_reset:
            # KSZ9031 tSR >= 10 ms (DS Table 7-4). XI comes from the FPGA and only starts at
            # configuration, so hold RESET_N well past that; 256 cycles (16 us) was far too short.
            # ctrl_cd: a PLL-free domain (target: "ref" = raw 25 MHz, reset only by CC_USR_RSTN), so a
            # PLL lock glitch cannot re-reset the PHY (TASK-4999, new board).
            self.hw_reset = ClockDomainsRenamer(ctrl_cd)(LiteEthPHYHWReset(cycles=hw_reset_cycles))
            self.comb += reset.eq(self._reset.storage | self.hw_reset.reset)
        else:
            self.comb += reset.eq(self._reset.storage)
        if hasattr(pads, "rst_n"):
            self.comb += pads.rst_n.eq(~reset)
        self.specials += [
            AsyncResetSynchronizer(self.cd_eth_tx, reset),
            AsyncResetSynchronizer(self.cd_eth_rx, reset),
        ]

# LiteEth PHY RGMII (GateMate) -----------------------------------------------------------------------

class LiteEthPHYRGMII_GateMate(LiteXModule):
    dw          = 8
    tx_clk_freq = 25e6
    rx_clk_freq = 25e6
    def __init__(self, clock_pads, pads, with_hw_init_reset=True,
        with_inband_status = True,
        tx_clk             = None,
        with_dynamic_link  = False,
        fixed_100m         = False,
        rxc_global         = False,
        line_rate_1g       = False,
        mdio_sequencer_clk_freq = None,
        with_mdio          = True,
        tx_clk90           = None,
        txc_readback       = False,
        sdr_tx             = False,
        mdio_writes        = None,
        rx_off             = False,
        sdr_rx             = False,
        hw_reset_cycles    = 256,
        tx_store_forward   = False,
        ctrl_cd            = "sys",
        tx_clk180          = None,
        ):
        # tx_clk180 (io50, TASK-4999): tx_clk is 50 MHz; all TX pins are IOSEL flip-flops.
        if tx_clk180 is not None:
            self.tx_clk_freq = 50e6
        # mdio_sequencer_clk_freq: when set (to the frequency of the clock domain this
        # PHY is instantiated in, i.e. sys), the CSR bit-bang LiteEthPHYMDIO -- dead
        # weight in a CPU-less design, nothing ever writes its CSRs -- is replaced by
        # a hardware MDIOWriteSequencer that forces the KSZ9031 advertisement to
        # 100BASE-TX FD after reset (see gateware/mdio_sequencer.py). Only one of the
        # two may own the mdc/mdio pads.
        # line_rate_1g: the link may come up at 1000 Mbps -> eth_tx/eth_rx are 125 MHz, not
        # 25 MHz. Only advertises the rates to the LiteEth standalone core generator
        # (liteeth/gen.py period constraints); the datapath gearing itself is chosen at
        # runtime from the RGMII in-band status (with_dynamic_link).
        if line_rate_1g:
            self.tx_clk_freq = 125e6
            self.rx_clk_freq = 125e6
        # fixed_100m: run the RGMII datapath in 100 Mbps mode. Gigabit does not close timing on
        # this board (measured ~2x deficit, see docs/GBE_FEASIBILITY_20260921_TASK-4961.md), so
        # the link runs at 100 Mbps and the
        # datapath MUST use the 10/100 nibble gearing (otherwise the default gigabit DDR framing
        # is wrong on the wire -> zero valid frames). We reuse LiteEth's speed-adaptive datapath
        # by enabling dynamic link (in-band status drives link_100M; no MDIO needed) and tell the
        # CRG to forward the 25 MHz eth_tx as TXC without dividing.
        if fixed_100m:
            with_dynamic_link = True
        assert not (with_dynamic_link and not with_inband_status)

        link_state_rx = None
        link_state_tx = None
        if fixed_100m:
            # Constant 100M on both sides; in-band status is still captured for the LEDs only.
            self.link_state_rx = link_state_rx = fixed_100m_link_state(self)
            self.link_state_tx = link_state_tx = fixed_100m_link_state(self)
        elif with_dynamic_link:
            self.link_state_rx = link_state_rx = LiteEthRGMIILinkState()
            self.link_state_tx = link_state_tx = LiteEthRGMIILinkState()
            self.specials += link_state_rx.synchronize(link_state_tx, "eth_tx")

        self.crg = LiteEthPHYRGMIICRG_GateMate(
            clock_pads,
            pads,
            with_hw_init_reset,
            tx_clk,
            link_state = link_state_tx,
            fixed_100m = fixed_100m,
            rxc_global = rxc_global,
            tx_clk90   = tx_clk90,
            txc_readback = txc_readback,
            hw_reset_cycles = hw_reset_cycles,
            ctrl_cd    = ctrl_cd,
            tx_clk180  = tx_clk180,
        )
        self.tx  = ClockDomainsRenamer("eth_tx")(LiteEthPHYRGMIITX_GateMate(
            pads,
            link_state = link_state_tx,
            tx_enable  = self.crg.tx_enable,
            core_100m  = LiteEthRGMIITX100MCore(store_forward=tx_store_forward,
                                                tx_enable=self.crg.tx_enable) if fixed_100m else None,
            sdr_tx     = sdr_tx,
            io_ff      = tx_clk180 is not None,
        ))
        self.rx  = ClockDomainsRenamer("eth_rx")(LiteEthPHYRGMIIRX_GateMate(
            pads,
            with_inband_status,
            link_state = link_state_rx,
            fixed_link = fixed_100m,
            rx_off     = rx_off,
            sdr_rx     = sdr_rx,
        ))
        self.sink, self.source = self.tx.sink, self.rx.source
        if with_dynamic_link:
            self.tx_gap_cycles = self.crg.tx_gap_cycles

        # with_mdio=False: the target owns mdc/mdio (e.g. MDIODiagEngine, TASK-4999).
        if hasattr(pads, "mdc") and with_mdio:
            if mdio_sequencer_clk_freq is not None:
                # mdio_sequencer_clk_freq = frequency of ctrl_cd.
                self.mdio_sequencer = ClockDomainsRenamer(ctrl_cd)(MDIOWriteSequencer(
                    pads      = pads,
                    clk_freq  = mdio_sequencer_clk_freq,
                    phy_reset = self.crg.hw_reset.reset if with_hw_init_reset else self.crg.reset,
                    writes    = mdio_writes,
                ))
            else:
                self.mdio = LiteEthPHYMDIO(pads)
