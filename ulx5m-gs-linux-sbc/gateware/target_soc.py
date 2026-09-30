#!/usr/bin/env python3
#
# Full LiteX SoC for the Radiona ULX5M-GS (GateMate CCGM1A1), TASK-5032 phase 2:
#   VexRiscv + BIOS on the GPIO4/GPIO5 serial (TX = IO_NB_B5 = GPIO5, RX = IO_NA_B6 = GPIO4, DirtyJTAG UART),
#   64 MB SDRAM (IS42VM16320E-75BLI, 1.8 V mobile SDR, 32M x 16) through LiteDRAM GENSDRPHY,
#   Ethernet: gateware/gbe_phy.py at 1000 Mb/s + LiteEth MAC for the CPU (BIOS netboot, Linux),
#   DVI 640x480 from a 320x240 framebuffer (gateware/video_sbc.py), optional USB HID keyboard, SD card.
#
# Global clock nets (4 on the CCGM1A1, lesson B10): sys, gtx (125 MHz TX), TXC (CLK90) and grx (RXC). The SDRAM
# clock therefore does not get its own PLL phase: it is driven from the sys DDR output as ~sys (180 deg), and the
# DVI path runs in gtx0 with a 1-in-5 clock enable instead of its own 25 MHz net.
#
# Build: tools/soc_build.sh <name> [args]   (LiteX tree ~/app/litex-1g-deps)
#
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import *
from litex.build.io import DDROutput
from litex.build.generic_platform import Pins, Misc, Subsignal

from litex_boards.platforms import intergalaktik_ulx5m_gs
from litex.soc.integration.soc_core import SoCCore
from litex.soc.integration.builder import Builder
from litex.soc.interconnect.csr import CSRStatus

from litedram.modules import SDRModule, _TechnologyTimings, _SpeedgradeTimings
from litedram.phy import GENSDRPHY

sys.path.insert(0, os.path.dirname(__file__))
from sticky_lock import StickyLock

_status_leds = [("status_led", i, Pins(p), Misc("DRIVE=3")) for i, p in enumerate(
    ["IO_SB_A0", "IO_SB_B0", "IO_SB_A1", "IO_SB_B1", "IO_SB_B2", "IO_SB_A2", "IO_SB_B3", "IO_SB_A3"])]

# DDMI0 (DVI, TMDS) - GateMate_demos/LiteX_DVI intergalaktik_ulx5m_gs_platform.py (README: tested from v004).
_hdmi = [("hdmi", 0,
    Subsignal("clk_p",   Pins("IO_SB_A7")), Subsignal("clk_n",   Pins("IO_SB_B7")),
    Subsignal("data0_p", Pins("IO_SB_A4")), Subsignal("data0_n", Pins("IO_SB_B4")),
    Subsignal("data1_p", Pins("IO_SB_A5")), Subsignal("data1_n", Pins("IO_SB_B5")),
    Subsignal("data2_p", Pins("IO_SB_A6")), Subsignal("data2_n", Pins("IO_SB_B6")))]

# USB-C J5 as a USB 1.1 host (TASK-5040, schematic ethernet.kicad_sch): D+ = USB25_P (IO_EA_A0, IO_EA_A1 in
# parallel), D- = USB25_N (IO_EA_B0, IO_EA_B1), 27R series. USB_PULL_P/N (IO_EA_A2/B2) drive the ULX3S-style
# diode+resistor network: high = 1k pull-up (device), low = 12k1 pull-down (host). VBUS is not powered by the
# board (J5.VBUS only), so a keyboard needs 5 V from outside (powered hub / Y cable).
_usb_host = [("usb_host", 0, Subsignal("dp", Pins("IO_EA_A0")), Subsignal("dm", Pins("IO_EA_B0"))),
             ("usb_pull", 0, Subsignal("p", Pins("IO_EA_A2")), Subsignal("n", Pins("IO_EA_B2")))]

# KSZ9031 RGMII + MDIO (docs/PINMAP.md). No eth_refclk: the board has X1 on XI.
_txm = [Misc("SLEW=fast"), Misc("DRIVE=6")]
_eth = [
    ("eth_clocks", 0,
        Subsignal("tx", Pins("IO_EB_B2"), *_txm),
        Subsignal("rx", Pins("IO_EB_A7")),
    ),
    ("eth", 0,
        Subsignal("rst_n",   Pins("IO_EB_B3"), Misc("SLEW=slow"), Misc("DRIVE=3")),
        Subsignal("mdio",    Pins("IO_EB_A6")),
        Subsignal("mdc",     Pins("IO_EB_B6")),
        Subsignal("rx_ctl",  Pins("IO_EB_A8")),
        Subsignal("rx_data", Pins("IO_EB_A0 IO_EB_B0 IO_EB_A1 IO_EB_B1")),
        Subsignal("tx_ctl",  Pins("IO_EB_A2"), *_txm),
        Subsignal("tx_data", Pins("IO_EB_B5 IO_EB_A5 IO_EB_B4 IO_EB_A4"), *_txm),
    ),
]


class IS42VM16320(SDRModule):
    """ISSI IS42VM16320E-75BLI: 1.8 V mobile SDR, 4 banks x 8192 rows x 1024 columns x 16 bit = 64 MB.
    Timings of the -75 grade (conservative, rounded up)."""
    nbanks = 4
    nrows  = 8192
    ncols  = 1024
    # tREFI: LiteDRAM rounds UP (64 ms/8192 = 7812.5 ns -> 157 x 50 ns = 7.85 us, 0.5 % over the spec, TASK-5047
    # review); 7.6 us keeps 8192 refreshes inside 64 ms at any sys clock >= 10 MHz.
    technology_timings = _TechnologyTimings(tREFI=7.6e3, tWTR=(2, None), tCCD=(1, None), tRRD=None)
    speedgrade_timings = {"default": _SpeedgradeTimings(tRP=22.5, tRCD=22.5, tWR=15, tRFC=(None, 80), tFAW=None,
                                                        tRAS=45)}


class SoCCRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq, perf_mode="economy", with_gbe=False, pll_lock_req=1,
                 usb48=None, gtx270=False, usb_freq=48e6):
        # TASK-5047: every PLL is a GateMatePLLStdy (USR_PLL_LOCKED_STDY wired out). pll_lock_req=0: the PLL keeps
        # its clock outputs running while the raw lock flag is low (DS1001 Table 2.19); LiteX default is 1.
        from pll_stdy import GateMatePLLStdy
        GateMatePLL = lambda perf_mode: GateMatePLLStdy(perf_mode=perf_mode, lock_req=pll_lock_req)
        self.rst    = Signal()
        self.cd_sys = ClockDomain()
        self.cd_ref = ClockDomain()

        clk25 = platform.request("clk25")
        rst_n = Signal()
        self.specials += Instance("CC_USR_RSTN", o_USR_RSTN=rst_n)
        self.rst_n = rst_n
        self.comb += self.cd_ref.clk.eq(clk25)
        self.cd_ref.clk.attr.add(("clkbuf_inhibit", 1))     # lesson I14: keep the 4 global nets for real clocks
        self.specials += AsyncResetSynchronizer(self.cd_ref, ~rst_n)

        self.pll_sys = pll = GateMatePLL(perf_mode=perf_mode)
        self.comb += pll.reset.eq(~rst_n | self.rst)
        pll.register_clkin(clk25, 25e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq, with_reset=False)
        self.lock_sys = ClockDomainsRenamer("ref")(StickyLock(pll.locked, int(25e6*1e-3)))
        self.specials += AsyncResetSynchronizer(self.cd_sys, ~rst_n | self.rst | ~self.lock_sys.locked)

        # SDRAM clock = ~sys: the SDRAM samples commands/data half a sys period after the FPGA launches them.
        # (The litex-boards target uses a sys_ps PLL output; with 1G Ethernet that would be a 5th global net.)
        self.specials += DDROutput(0, 1, platform.request("sdram_clock"), ClockSignal("sys"))

        if with_gbe:
            self.cd_gtx0  = ClockDomain()
            self.cd_gtx90 = ClockDomain(reset_less=True)
            self.pll_tx = pll_tx = GateMatePLL(perf_mode=perf_mode)
            self.comb += pll_tx.reset.eq(~rst_n)
            pll_tx.register_clkin(clk25, 25e6)
            pll_tx.create_clkout(self.cd_gtx0,  125e6, with_reset=False)
            pll_tx.create_clkout(self.cd_gtx90, 125e6, phase=90, with_reset=False)
            if gtx270:
                # TASK-5051 clock option c: TXC = CLK270 over fabric routing (no BUFG), see ULX5MSoC.
                self.cd_gtx270 = ClockDomain(reset_less=True)
                pll_tx.create_clkout(self.cd_gtx270, 125e6, phase=270, with_reset=False)
            self.lock_tx = ClockDomainsRenamer("ref")(StickyLock(pll_tx.locked, int(25e6*1e-3)))
            self.eth_rst = Signal()
            self.comb += self.eth_rst.eq(~rst_n | ~self.lock_sys.locked | ~self.lock_tx.locked)

        # TASK-5051: 48 MHz for the USB host engine from a third PLL. usb48 = "local": fabric routing (no global
        # net, clkbuf_inhibit as the ref domain), "bufg": a global net (needs one free CC_BUFG).
        if usb48 is not None:
            self.cd_usb = ClockDomain()
            self.pll_usb = pll_usb = GateMatePLL(perf_mode=perf_mode)
            self.comb += pll_usb.reset.eq(~rst_n)
            pll_usb.register_clkin(clk25, 25e6)
            pll_usb.create_clkout(self.cd_usb, usb_freq, with_reset=False)
            if usb48 == "local":
                self.cd_usb.clk.attr.add(("clkbuf_inhibit", 1))
            self.lock_usb = ClockDomainsRenamer("ref")(StickyLock(pll_usb.locked, int(25e6*1e-3)))
            self.specials += AsyncResetSynchronizer(self.cd_usb, ~rst_n | ~self.lock_usb.locked)


class ULX5MSoC(SoCCore):
    def __init__(self, sys_clk_freq=20e6, perf_mode="economy", pnr_mode="speed",
                 with_gbe=False, with_sdcard=False, sdcard="none",
                 sdram_cl=2, l2_size=0, boot="none", cpu_mac_address=0x10e2d5000001,
                 local_ip="192.168.10.213", remote_ip="192.168.10.14", with_video=False,
                 fb_base=0x43f00000, video_ce_rep=False, video_neg_sync=False,
                 pll_lock_req=1, video_640x240=False, with_usb_hid=False, video_recover=False,
                 phy_write_after=0, phy_reg4=0x0001, phy_snap_csr=False, with_usb_pnru=False,
                 usb_pnru_clk="pll48", usb_pnru_freq=48e6, eth_100m=False, phy_diag_csr=False, eth_rx_fabric=False, **kwargs):
        platform = intergalaktik_ulx5m_gs.Platform("peppercorn")
        # nextpnr timing model = VDD_CORE 1.1 V (SPEED); PLLs stay ECONOMY (lessons B3, I9).
        platform.toolchain._pnr_opts += " --vopt fpga_mode=%d " % {"lowpower": 1, "economy": 2, "speed": 3}[pnr_mode]
        platform.toolchain._packer_opts = "--reset " + platform.toolchain._packer_opts     # CMD_CFGRST (lesson H1)
        platform.add_extension(_status_leds)

        assert usb_pnru_clk in USB_PNRU_CLKS, usb_pnru_clk
        usb48 = {"pll48": "local", "bufg48": "bufg"}.get(usb_pnru_clk) if with_usb_pnru else None
        gtx270 = with_usb_pnru and usb_pnru_clk == "bufg48"
        self.crg = crg = SoCCRG(platform, sys_clk_freq, perf_mode, with_gbe, pll_lock_req=pll_lock_req,
                                usb48=usb48, gtx270=gtx270, usb_freq=usb_pnru_freq)
        kwargs.setdefault("uart_name", "serial")
        # The ident names the address and MAC the CPU answers on (BIOS `ident` command, csr.json).
        fmt_mac = lambda m: ":".join("%02x" % ((m >> (8*i)) & 0xff) for i in reversed(range(6)))
        ident = "ULX5M-GS SoC"
        if with_gbe:
            ident += " | CPU/TFTP %s (%s)" % (local_ip, fmt_mac(cpu_mac_address))
        SoCCore.__init__(self, platform, sys_clk_freq, ident=ident, **kwargs)

        # SDRAM ------------------------------------------------------------------------------------
        if not self.integrated_main_ram_size:
            self.sdrphy = GENSDRPHY(platform.request("sdram"), sys_clk_freq, cl=sdram_cl)
            self.add_sdram("sdram",
                phy           = self.sdrphy,
                module        = IS42VM16320(sys_clk_freq, "1:1"),
                # l2_size 0: the LiteX L2 tag memory (write-first, constant bits) gets a yosys SRST on its output
                # register, memory_dff then finds no output FF and maps 512x22 bits to 11k flip-flops (TASK-5032 s1).
                l2_cache_size = l2_size,
            )

        # DVI framebuffer 640x480@60 (TASK-5040): 320x240 rgb565 in SDRAM at fb_base, doubled in hardware ----
        if with_video:
            from litex.soc.cores.video import VideoTimingGenerator
            # Not named video_framebuffer: the LiteX BIOS/json2dts would expect the VideoFrameBuffer CSRs (vtg_enable).
            from video_sbc import DVIPHY, FrameBuffer2x
            if not with_gbe:
                raise ValueError("--with-video runs in the 125 MHz gtx0 domain of --with-gbe")
            platform.add_extension(_hdmi)
            # 1G Ethernet uses all 4 global nets (sys, gtx0, TXC, grx). gtx0 is 125 MHz = 5x the pixel clock, so
            # the whole video path runs in gtx0 and the pixel logic advances on ce = 1 cycle in 5 (25 MHz): no
            # new net. The pixel paths are 5-cycle paths that nextpnr checks as 1-cycle (a reported FAIL at
            # 125 MHz is expected; the real requirement is 25 MHz).
            vcd = "gtx0"
            vrst = None
            if video_recover:
                # TASK-5047: cd_gtx0 has NO reset, so the CE video path (ce counters, VTG, CDC read side) was never
                # reset after configuration; a clock disturbance could leave it misaligned for good (black picture,
                # resyncs == frames). "vid" = gtx0 clock (same net, no BUFG) reset by the tx PLL lock and by the
                # FrameBuffer2x watchdog; "vsys" = sys clock, same reset, for the CDC write side.
                vcd = "vid"
                vrst = Signal()
                self.cd_vid, self.cd_vsys = ClockDomain("vid"), ClockDomain("vsys")
                self.comb += [self.cd_vid.clk.eq(ClockSignal("gtx0")), self.cd_vsys.clk.eq(ClockSignal("sys"))]
                self.specials += [AsyncResetSynchronizer(self.cd_vid, ~crg.lock_tx.locked | vrst),
                                  AsyncResetSynchronizer(self.cd_vsys, ResetSignal("sys") | vrst)]
            ce_idx = [0]
            def mk_ce():
                # One ce register per video block (CE tree, --video-ce-rep): each from its own mod-5 counter,
                # stored XOR K (K unique, fsm_encoding none) so yosys can neither merge nor re-encode them;
                # all pulse in the same cycle. Without it the single ce net (fanout ~150) arrived after 10.9 ns.
                K = ce_idx[0] & 0xf
                ce_idx[0] += 1
                st, c = Signal(4, reset=K), Signal()
                st.attr.add(("fsm_encoding", "none"))
                cnt = st ^ K
                getattr(self.sync, vcd).__iadd__([st.eq(Mux(cnt == 4, 0, cnt + 1) ^ K), c.eq(cnt == 3)])
                return c
            if video_ce_rep:
                ce, ce_vtg, ce_phy = mk_ce, mk_ce(), mk_ce
            else:
                ce = ce_vtg = ce_phy = mk_ce()
            self.videophy = DVIPHY(platform.request("hdmi"), ce_domain=vcd, ce=ce_phy, neg_sync=video_neg_sync)
            self.video_vtg = ClockDomainsRenamer(vcd)(CEInserter()(
                VideoTimingGenerator(default_video_timings="640x480@60Hz")))
            self.comb += self.video_vtg.ce.eq(ce_vtg)
            port = self.sdram.crossbar.get_port(mode="read", data_width=16)
            self.video_fb2x = fb = FrameBuffer2x(port, ce, vcd, hres=640, vres=480, base=fb_base,
                                                      hdouble=not video_640x240,
                                                      cdc_from="vsys" if vcd == "vid" else "sys")
            if vcd == "vid":
                # watchdog -> 128 sys cycles (6.4 us) of reset on vid + vsys; count the recoveries.
                from migen.genlib.cdc import MultiReg as _MR2
                wd_s, hold, nrec = Signal(), Signal(8), Signal(16)
                hold.attr.add("keep")
                self.specials += _MR2(fb.wd, wd_s)
                self.sync += If(hold != 0, hold.eq(hold - 1)).Elif(wd_s, hold.eq(128), nrec.eq(nrec + 1))
                self.comb += vrst.eq(hold != 0)
                self.video_recoveries = CSRStatus(16, name="video_recoveries")
                self.comb += self.video_recoveries.status.eq(nrec)
            self.comb += [self.video_vtg.source.connect(fb.vtg_sink), fb.source.connect(self.videophy.sink)]
            self.add_constant("VIDEO_FB_BASE",   fb_base)
            self.add_constant("VIDEO_FB_WIDTH",  fb.fb_width)
            self.add_constant("VIDEO_FB_HEIGHT", 240)

        # USB 1.1 low-speed HID host (TASK-5047): Emard's usbh_host_hid, 6 MHz = 125 MHz/21 on local routing.
        if with_usb_hid:
            from usb_hid import USBHIDHost
            if not with_gbe:
                raise ValueError("--with-usb-hid needs the 125 MHz gtx0 domain of --with-gbe")
            platform.add_extension(_usb_host)
            self.usb_hid = USBHIDHost(platform, platform.request("usb_host"), platform.request("usb_pull"),
                                      src_domain="gtx0", rst=~crg.rst_n)

        # USB 1.1 LS/FS host (TASK-5051): PNRU PHY/SIE ported to Migen (gateware/usb_pnru.py), CSR usb_pnru, on J5
        # and, on the CM4 IO board, the USB2514B hub (CM4 pins 103/105 are in parallel with J5). Clock options:
        #   pll48  (a) 48 MHz from a third PLL on fabric routing, no global net;
        #   gtx125 (b) the engine runs in gtx0 (125 MHz), the PHY oversamples 10.42x (NCO), no new clock;
        #   bufg48 (c) 48 MHz on a global net, freed by moving TXC (CLK90 over a BUFG) to CLK270 over fabric
        #              routing: the ~5.8 ns route adds to 270 deg, about the 90 deg of the BUFG path.
        if with_usb_pnru:
            from usb_pnru import USBHostPNRU
            if with_usb_hid:
                raise ValueError("--with-usb-pnru and --with-usb-hid use the same pins (J5)")
            if not with_gbe and usb_pnru_clk != "pll48":
                raise ValueError("--usb-pnru-clk gtx125/bufg48 need --with-gbe")
            platform.add_extension(_usb_host)
            if usb_pnru_clk == "gtx125":
                self.cd_usb = ClockDomain("usb")
                self.comb += self.cd_usb.clk.eq(ClockSignal("gtx0"))
                self.specials += AsyncResetSynchronizer(self.cd_usb, crg.eth_rst)
            # No connect detect and no EventManager: the userspace driver polls and debounces stat.dp/dn itself
            # (-~150 LT; the full SoC is at the placer limit, lesson J7).
            self.usb_pnru = USBHostPNRU(platform.request("usb_host"), 125e6 if usb_pnru_clk == "gtx125" else usb_pnru_freq,
                                        sys_clk_freq, pull=platform.request("usb_pull"),
                                        with_detect=False, with_events=False)

        # Ethernet 1000 Mb/s: own RGMII PHY (gateware/gbe_phy.py) + LiteEth MAC for the CPU -----------------------
        if with_gbe:
            from gbe_phy import GbePHY
            from liteeth.mac import LiteEthMAC
            platform.add_extension(_eth)
            clock_pads = platform.request("eth_clocks")
            pads       = platform.request("eth")
            if hasattr(crg, "cd_gtx270"):
                txc = dict(txc_clks=[crg.cd_gtx0.clk, crg.cd_gtx90.clk, crg.cd_gtx270.clk], txc_sel=4, txc_bufg=False)
            else:
                txc = dict(txc_clks=[crg.cd_gtx0.clk, crg.cd_gtx90.clk], txc_sel=2, txc_bufg=True)
            if eth_100m:
                # TASK-5094: 100 Mb/s on the same pins (gbe_phy.Rgmii100PHY): 40 ns per RGMII cycle, for the CCGM1A2
                # where the RGMII balls are on die 1B and the logic on 1A (A2_CCGM1A2_TASK-5092.md §3). TXC is a
                # register output (no global net), gtx0 stays 125 MHz for DVI/USB.
                from gbe_phy import Rgmii100PHY
                self.ethphy = phy = Rgmii100PHY(clock_pads, pads, clk_tx=crg.cd_gtx0.clk, rst=crg.eth_rst,
                                                rx_fabric=eth_rx_fabric, diag=phy_diag_csr)
                platform.add_period_constraint(clock_pads.rx, 1e9/25e6)
            else:
                self.ethphy = phy = GbePHY(clock_pads, pads, clk_tx=crg.cd_gtx0.clk, rst=crg.eth_rst, **txc)
                platform.add_period_constraint(clock_pads.rx, 1e9/125e6)
            phy.tx_clk_freq = phy.rx_clk_freq = sys_clk_freq
            # CPU-only MAC (TASK-5033): the CPU answers ping (Linux) and does TFTP (BIOS netboot) itself, on local_ip.
            # 8-bit MAC in sys; add_ethernet(data_width=32) was tried first: TX works but RX never delivers a frame
            # to the CPU (ARP reply lost, TASK-5033).
            self.ethmac = LiteEthMAC(phy=phy, dw=8, interface="wishbone", endianness=self.cpu.endianness,
                                     with_preamble_crc=True, with_sys_datapath=True)
            self.add_cpu_mac_regions(self.ethmac, cpu_mac_address, local_ip, remote_ip)
            # KSZ9031: RESET_N + advertisement 1000FD on the first MDIO pass (lessons I2/I3), in hardware.
            from mdio_core import MDIOCore
            # 100 Mb/s: advertise 100BASE-TX FD only (REG9 = 0: no 1000BASE-T, REG4 = 0x0101).
            # phy_diag_csr: MDIOCore also counts RX_CTL rising edges of the IDDR sample (m.frames; 0 without it).
            core = phy.c.core if eth_100m else phy.core
            self.phy_mdio = m = MDIOCore(pads, write_after=phy_write_after, reg9=0x0000 if eth_100m else 0x0200,
                                         reg4=0x0101 if eth_100m else phy_reg4, reg0=0x1200,
                                         rxc_domain="grx", rx_ctl=core.rx_rs_ctl if phy_diag_csr else 0)
            self.phy_status0 = CSRStatus(32, description="KSZ9031 R1 (bits 31:16) and R1F (15:0); R1F bit 6 = 1000 Mb/s")
            self.phy_status1 = CSRStatus(32, description="KSZ9031 RA (31:16), RXC edges per 2^20 sys cycles >> 8 (15:0)")
            self.comb += [self.phy_status0.status.eq(Cat(m.rf, m.r1)),
                          self.phy_status1.status.eq(Cat(m.rfreq[8:24], m.ra))]
            if phy_snap_csr:
                # Board test of the MDIO controller: {passes, idm, {wrote, addr}, r0, r1, r4, r5, r9, ra, rf, ...}
                self.phy_snap = CSRStatus(256, description="MDIOCore snap (gateware/mdio_core.py)")
                self.comb += self.phy_snap.status.eq(m.snap)

        # SD card ----------------------------------------------------------------------------------
        # native: LiteSDCard (4-bit, DMA); with SMP + 1G MAC it reaches 77 % CPE_LT and the placer fails (J7).
        # spi:    SPI master on the same slot (CLK, CMD=MOSI, DAT3=CS, DAT0=MISO), as Machdyne Kolsch
        #         (linux-on-litex-vexriscv soc_capabilities "spisdcard"); Linux: litex,litespi + mmc_spi.
        if with_sdcard:
            sdcard = "native"
        assert sdcard in SDCARD_MODES, sdcard
        if sdcard == "native":
            self.add_sdcard()
        if sdcard == "spi":
            self.add_spi_sdcard()

        # BIOS boot source (--boot) ------------------------------------------------------------------
        # none:    console only (BIOS_NO_BOOT). With no card the SD boot hangs at "Booting from boot.json..."
        #          and never reaches the console (TASK-5032 S4); the card is tested with `sdcard_init`.
        # serial:  serialboot (litex_term --kernel) only, then the console.
        # sdcard:  SD card first (boot.json / boot.bin), then serial.
        # netboot: TFTP from remote_ip (boot.json / boot.bin) first, then serial; the CPU has its own MAC/IP.
        # sdnet:   SD card (boot.json on FAT) first, then TFTP, then serial (TASK-5039, SPI-SD: without a card
        #          spisdcard_init only times out, so the BIOS falls through to netboot).
        assert boot in BOOT_MODES, boot
        if boot == "none":
            self.add_config("BIOS_NO_BOOT")
        if boot in ["serial", "netboot"]:
            self.add_constant("SDCARD_BOOT_DISABLE")
        if boot == "sdnet":
            if not (with_gbe and sdcard != "none"):
                raise ValueError("--boot sdnet needs --with-gbe and an SD card core")
            self.add_constant("SDCARD_BOOT_PRIORITY", -2)
            self.add_constant("NET_BOOT_PRIORITY", -1)
        if boot in ["serial", "sdcard"]:
            self.add_constant("NET_BOOT_DISABLE")
        if boot == "sdcard":
            self.add_constant("SDCARD_BOOT_PRIORITY", -1)
        if boot == "netboot":
            if not with_gbe:
                raise ValueError("--boot netboot needs --with-gbe")
            self.add_constant("NET_BOOT_PRIORITY", -1)

        # PLL lock-loss counters (TASK-5040): falling edges of the RAW USR_PLL_LOCKED, counted in the PLL-free
        # ref domain. The DVI picture drops out under SDRAM load even without CE/1G; is it a PLL losing lock?
        if with_video:
            from migen.genlib.cdc import MultiReg as _MR
            from litex.soc.interconnect.csr import CSRStatus as _CS
            plls = [("sys", crg.pll_sys), ("tx", crg.pll_tx)]
            for name, pll in plls:
                lk, lk_d, n = Signal(), Signal(), Signal(16)
                self.specials += _MR(pll.locked, lk, "ref")
                self.sync.ref += [lk_d.eq(lk), If(lk_d & ~lk, n.eq(n + 1))]
                st = _CS(16, name="pll_%s_unlocks" % name)
                setattr(self, "pll_%s_unlocks" % name, st)
                self.specials += _MR(n, st.status)
            # TASK-5047: the silicon's sticky lock flag (1 = lock never lost since the last re-arm), bit i = plls[i],
            # and a re-arm register (write 1, then 0; USR_LOCKED_STDY_RST needs >= 2 clk25 cycles, a CSR write
            # pair is microseconds apart).
            from litex.soc.interconnect.csr import CSRStorage as _CSt
            self.pll_stdy     = _CS(len(plls), name="pll_stdy")
            self.pll_stdy_rst = _CSt(1, name="pll_stdy_rst")
            for i, (name, pll) in enumerate(plls):
                self.specials += _MR(pll.locked_stdy, self.pll_stdy.status[i])
                self.comb += pll.stdy_rst.eq(self.pll_stdy_rst.storage)

        # LEDs: 7 heartbeat, 6 sys PLL lock, 5 TX PLL lock --------------------------------------------
        leds = [platform.request("status_led", i) for i in range(8)]
        hb = Signal(25)
        self.sync += hb.eq(hb + 1)
        self.comb += [leds[7].eq(hb[24]), leds[6].eq(crg.lock_sys.locked)]
        if with_gbe:
            self.comb += leds[5].eq(crg.lock_tx.locked)

        # TASK-5094: RX path counters for the A2 (1G and 100 Mb/s both end in "ARP failed" with MDIO/link/RXC fine).
        # CSR name sorts last in the main block, so no existing CSR moves (rv32_k612.dtb stays valid).
        # [15:0] frames delivered to LiteEth, [31:16] frames accepted for TX (sys), [47:32] RX_CTL rising edges of
        # the IDDR sample (MDIOCore, sys), [55:48] RX frames dropped by the PHY (RX_ER/overflow), [63:56] pairing
        # changes (grx), [79:64] frames the TX serializer put out (gtx); grx/gtx fields are read quasi-statically.
        if with_gbe and phy_diag_csr:
            dbg = core.dbg if getattr(core, "diag", False) else C(0, 40)
            self.zdiag = CSRStatus(128, name="zdiag", description="PHY RX/TX counters (TASK-5094)")
            self.comb += self.zdiag.status.eq(Cat(core.rx_frames, core.tx_frames, m.frames, core.rx_drops,
                                                  core.rx_flips, core.tx_emit, dbg))   # [119:80] = GbePHYCore.dbg


    def add_cpu_mac_regions(self, ethmac, mac_address, local_ip, remote_ip):
        """Wishbone SRAM slots, IRQ and BIOS constants of the CPU MAC (as LiteX SoC.add_ethernet)."""
        from litex.soc.integration.soc import SoCRegion
        from litex.soc.integration.soc import add_ip_address_constants, add_mac_address_constants
        rx_size = ethmac.rx_slots.constant*ethmac.slot_size.constant
        tx_size = ethmac.tx_slots.constant*ethmac.slot_size.constant
        self.bus.add_region("ethmac", SoCRegion(origin=self.mem_map.get("ethmac", None), size=rx_size + tx_size,
                                                linker=True, cached=False))
        origin = self.bus.regions["ethmac"].origin
        self.bus.add_slave(name="ethmac_rx", slave=ethmac.bus_rx,
                           region=SoCRegion(origin=origin, size=rx_size, mode="r", linker=False, cached=False))
        self.bus.add_slave(name="ethmac_tx", slave=ethmac.bus_tx,
                           region=SoCRegion(origin=origin + rx_size, size=tx_size, linker=False, cached=False))
        if self.irq.enabled:
            self.irq.add("ethmac", use_loc_if_exists=True)
        self.add_constant("ETH_PHY_NO_RESET")   # the PHY has no MDIO CSRs: mdio_core configures it in hardware
        add_ip_address_constants(self, "LOCALIP", local_ip)
        add_ip_address_constants(self, "REMOTEIP", remote_ip)
        add_mac_address_constants(self, "MACADDR", mac_address)


BOOT_MODES     = ["none", "serial", "sdcard", "netboot", "sdnet"]
USB_PNRU_CLKS  = ["pll48", "gtx125", "bufg48"]
SDCARD_MODES   = ["none", "native", "spi"]


def main():
    import argparse
    from litex.soc.integration.soc_core import soc_core_args, soc_core_argdict
    p = argparse.ArgumentParser(description="ULX5M-GS Linux SoC (VexRiscv, 64 MB SDRAM, 1G Ethernet, DVI)")
    p.add_argument("--build",        action="store_true")
    p.add_argument("--output-dir",   default=None)
    p.add_argument("--sys-clk-freq", default=20e6, type=float)
    p.add_argument("--perf-mode",    default="economy", choices=["lowpower", "economy", "speed"], help="PLL PERF_MD")
    p.add_argument("--pnr-mode",     default="speed",   choices=["lowpower", "economy", "speed"])
    # --sdram-clk and --eth-mode have one value left; they stay so the documented build command keeps working.
    p.add_argument("--sdram-clk",    default="inv",     choices=["inv"], help="SDRAM clock = ~sys (DDR output)")
    p.add_argument("--sdram-cl",     default=2, type=int, choices=[2, 3])
    p.add_argument("--with-gbe",     action="store_true")
    p.add_argument("--eth-mode",     default="mac", choices=["mac"], help="LiteEth MAC for the CPU (BIOS netboot, Linux)")
    p.add_argument("--with-sdcard",  action="store_true", help="= --sdcard native")
    p.add_argument("--sdcard",       default="none", choices=SDCARD_MODES, help="SD card core (see ULX5MSoC)")
    p.add_argument("--seed",         default=None, type=int)
    p.add_argument("--placer-timeout", default=None, type=int,
                   help="nextpnr --placer-heap-cell-placement-timeout (netboot SoC: 77%% LT, placer gives up)")
    p.add_argument("--synth-extra", default=None, help="extra synth_gatemate options, e.g. '-nomult' (lesson J7)")
    p.add_argument("--boot",         default="none", choices=BOOT_MODES, help="BIOS boot source (see ULX5MSoC)")
    p.add_argument("--local-ip",     default="192.168.10.213", help="CPU IP for --boot netboot")
    p.add_argument("--remote-ip",    default="192.168.10.14",  help="TFTP server for --boot netboot")
    p.add_argument("--with-video",   action="store_true", help="DVI 640x480@60, 320x240 rgb565 framebuffer (needs --with-gbe)")
    p.add_argument("--fb-base",      default=0x43f00000, type=lambda x: int(x, 0), help="framebuffer address")
    p.add_argument("--video-ce-rep", action="store_true", help="one ce register per video block (fanout)")
    p.add_argument("--video-neg-sync", action="store_true", help="VESA 640x480: negative hsync/vsync")
    p.add_argument("--pll-lock-req", default=1, type=int, choices=[0, 1], help="CC_PLL LOCK_REQ (0: outputs run without lock, TASK-5047)")
    p.add_argument("--video-640x240", action="store_true", help="640x240 framebuffer, lines doubled only (80x30 text, 18.4 MB/s)")
    p.add_argument("--video-recover", action="store_true", help="resettable video domain + resync watchdog (TASK-5047)")
    p.add_argument("--with-usb-hid", action="store_true", help="USB low-speed HID host (Emard) on J5, CSR usb_hid (TASK-5047)")
    p.add_argument("--with-usb-pnru", action="store_true", help="USB 1.1 LS/FS host (PNRU port), CSR usb_pnru (TASK-5051)")
    p.add_argument("--usb-pnru-freq", type=float, default=48e6,
                   help="USB engine clock for pll48/bufg48 (60e6: 5x oversampling, robust to D+ duty-cycle distortion)")
    p.add_argument("--usb-pnru-clk", default="pll48", choices=USB_PNRU_CLKS, help="USB engine clock (see ULX5MSoC)")
    # MDIO controller board test (docs/REVIEW_LITEX_DUPLICATES.md): later write, other REG4, full snap as a CSR.
    p.add_argument("--phy-write-after", default=0, type=int, help="MDIO pass in which REG9/4/0 are written")
    p.add_argument("--phy-reg4", default=0x0001, type=lambda x: int(x, 0), help="KSZ9031 REG4 written by MDIOCore")
    p.add_argument("--phy-snap-csr", action="store_true", help="CSR phy_snap = MDIOCore snap (256 bit)")
    p.add_argument("--eth-100m", action="store_true", help="100 Mb/s RGMII (gbe_phy.Rgmii100PHY) instead of 1G (TASK-5094, A2)")
    p.add_argument("--phy-diag-csr", action="store_true", help="CSR zdiag: PHY RX/TX frame counters (TASK-5094)")
    p.add_argument("--eth-rx-fabric", action="store_true", help="--eth-100m: RX sampled by fabric FFs, not CC_IDDR (A2)")
    soc_core_args(p)
    p.set_defaults(cpu_type="vexriscv", integrated_rom_size=0x10000, integrated_sram_size=0x2000, l2_size=0)
    args = p.parse_args()

    soc = ULX5MSoC(sys_clk_freq=args.sys_clk_freq, perf_mode=args.perf_mode, pnr_mode=args.pnr_mode,
                   sdram_cl=args.sdram_cl, with_gbe=args.with_gbe,
                   with_sdcard=args.with_sdcard, sdcard=args.sdcard, boot=args.boot, local_ip=args.local_ip,
                   remote_ip=args.remote_ip, with_video=args.with_video, fb_base=args.fb_base,
                   video_ce_rep=args.video_ce_rep, video_neg_sync=args.video_neg_sync, pll_lock_req=args.pll_lock_req,
                   video_640x240=args.video_640x240, with_usb_hid=args.with_usb_hid, video_recover=args.video_recover,
                   phy_write_after=args.phy_write_after, phy_reg4=args.phy_reg4, phy_snap_csr=args.phy_snap_csr,
                   with_usb_pnru=args.with_usb_pnru, usb_pnru_clk=args.usb_pnru_clk,
                   usb_pnru_freq=args.usb_pnru_freq, eth_100m=args.eth_100m, phy_diag_csr=args.phy_diag_csr, eth_rx_fabric=args.eth_rx_fabric,
                   **soc_core_argdict(args))
    if args.synth_extra:
        soc.platform.toolchain._synth_opts += " " + args.synth_extra + " "
    if args.placer_timeout:
        soc.platform.toolchain._pnr_opts += " --placer-heap-cell-placement-timeout %d " % args.placer_timeout
    builder = Builder(soc, output_dir=args.output_dir or os.path.join(os.path.dirname(__file__), "..", "build", "soc"))
    kw = {"seed": args.seed} if args.seed is not None else {}
    builder.build(run=args.build, **kw)


if __name__ == "__main__":
    main()
