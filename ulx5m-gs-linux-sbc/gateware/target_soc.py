#!/usr/bin/env python3
#
# Full LiteX SoC for the Radiona ULX5M-GS (GateMate CCGM1A1), TASK-5032 phase 2:
#   VexRiscv + BIOS on the GPIO4/GPIO5 serial (TX = IO_NB_B5 = GPIO5, RX = IO_NA_B6 = GPIO4, DirtyJTAG UART),
#   64 MB SDRAM (IS42VM16320E-75BLI, 1.8 V mobile SDR, 32M x 16) through LiteDRAM GENSDRPHY,
#   Ethernet: gateware/gbe_phy.py at 1000 Mb/s + hardware ARP/ICMP (ping without the CPU) + Etherbone,
#   SD card (LiteSDCard, IO_NA_* at 1.8 V).
#
# Global clock nets (4 on the CCGM1A1, lesson B10): sys, gtx (125 MHz TX), TXC (CLK90) and grx (RXC). The SDRAM
# clock therefore does not get its own PLL phase: --sdram-clk inv drives it from the sys DDR output as ~sys
# (180 deg); --sdram-clk ps90 uses a sys_ps PLL output (5th net, only without Ethernet).
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
from litex.soc.cores.clock.colognechip import GateMatePLL

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
    def __init__(self, platform, sys_clk_freq, perf_mode="economy", sdram_clk="inv", with_gbe=False, with_video=False,
                 with_usb=False, pll_lock_req=1, video_pix_freq=25e6):
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
        if sdram_clk == "ps90":
            self.cd_sys_ps = ClockDomain(reset_less=True)
            pll.create_clkout(self.cd_sys_ps, sys_clk_freq, phase=90, with_reset=False)
        self.lock_sys = ClockDomainsRenamer("ref")(StickyLock(pll.locked, int(25e6*1e-3)))
        self.specials += AsyncResetSynchronizer(self.cd_sys, ~rst_n | self.rst | ~self.lock_sys.locked)

        sdram_clock = platform.request("sdram_clock")
        if sdram_clk == "ps90":
            self.specials += DDROutput(1, 0, sdram_clock, ClockSignal("sys_ps"))
        else:
            # ~sys: the SDRAM samples commands/data half a sys period after the FPGA launches them.
            self.specials += DDROutput(0, 1, sdram_clock, ClockSignal("sys"))

        if with_gbe:
            self.cd_gtx0  = ClockDomain()
            self.cd_gtx90 = ClockDomain(reset_less=True)
            self.pll_tx = pll_tx = GateMatePLL(perf_mode=perf_mode)
            self.comb += pll_tx.reset.eq(~rst_n)
            pll_tx.register_clkin(clk25, 25e6)
            pll_tx.create_clkout(self.cd_gtx0,  125e6, with_reset=False)
            pll_tx.create_clkout(self.cd_gtx90, 125e6, phase=90, with_reset=False)
            self.lock_tx = ClockDomainsRenamer("ref")(StickyLock(pll_tx.locked, int(25e6*1e-3)))
            self.eth_rst = Signal()
            self.comb += self.eth_rst.eq(~rst_n | ~self.lock_sys.locked | ~self.lock_tx.locked)

        if with_video and not with_gbe:
            # DVI (TASK-5040): hdmi5x 125 MHz from its own PLL, hdmi 25 MHz = hdmi5x/5 (flop divider) -> 2 global
            # nets. With 1G Ethernet (sys, gtx0, TXC, grx) that is 6 > 4, so video excludes --with-gbe.
            from video_sbc import Divide5
            self.cd_hdmi   = ClockDomain()
            self.cd_hdmi5x = ClockDomain()
            self.pll_video = pll_v = GateMatePLL(perf_mode=perf_mode)
            self.comb += pll_v.reset.eq(~rst_n)
            pll_v.register_clkin(clk25, 25e6)
            pll_v.create_clkout(self.cd_hdmi5x, 5*video_pix_freq, with_reset=False)
            self.lock_video = ClockDomainsRenamer("ref")(StickyLock(pll_v.locked, int(25e6*1e-3)))
            self.specials += AsyncResetSynchronizer(self.cd_hdmi5x, ~rst_n | ~self.lock_video.locked)
            self.div5 = Divide5("hdmi5x")
            self.comb += self.cd_hdmi.clk.eq(self.div5.clk_o)
            self.specials += AsyncResetSynchronizer(self.cd_hdmi, ~rst_n | ~self.lock_video.locked)
            platform.add_period_constraint(self.cd_hdmi.clk,   1e9/video_pix_freq)
            platform.add_period_constraint(self.cd_hdmi5x.clk, 1e9/(5*video_pix_freq))

        if with_usb:
            # USB OHCI PHY clock 48 MHz: 3rd PLL, 4th global net (sys, hdmi, hdmi5x, usb).
            self.cd_usb = ClockDomain()
            self.pll_usb = pll_u = GateMatePLL(perf_mode=perf_mode)
            self.comb += pll_u.reset.eq(~rst_n)
            pll_u.register_clkin(clk25, 25e6)
            pll_u.create_clkout(self.cd_usb, 48e6, with_reset=False)
            self.lock_usb = ClockDomainsRenamer("ref")(StickyLock(pll_u.locked, int(25e6*1e-3)))
            self.specials += AsyncResetSynchronizer(self.cd_usb, ~rst_n | ~self.lock_usb.locked)


class ULX5MSoC(SoCCore):
    def __init__(self, sys_clk_freq=20e6, perf_mode="economy", pnr_mode="speed", sdram_clk="inv",
                 with_gbe=False, with_sdcard=False, sdcard="none", ip_address="192.168.10.212", mac_address=0x10e2d5000000,
                 sdram_cl=2, l2_size=0, boot="none", cpu_mac_address=0x10e2d5000001,
                 local_ip="192.168.10.213", remote_ip="192.168.10.14", eth_mode="hwstack", with_video=False,
                 fb_base=0x43f00000, with_usb=False, video_terminal=False, video_ce_rep=False, video_neg_sync=False, sdram_drive=None, video_det_load=False,
                 pll_lock_req=1, sdram_slew=None, video_pix_freq=25e6, video_640x240=False, with_usb_hid=False, video_recover=False, **kwargs):
        platform = intergalaktik_ulx5m_gs.Platform("peppercorn")
        # nextpnr timing model = VDD_CORE 1.1 V (SPEED); PLLs stay ECONOMY (lessons B3, I9).
        platform.toolchain._pnr_opts += " --vopt fpga_mode=%d " % {"lowpower": 1, "economy": 2, "speed": 3}[pnr_mode]
        platform.toolchain._packer_opts = "--reset " + platform.toolchain._packer_opts     # CMD_CFGRST (lesson H1)
        platform.add_extension(_status_leds)
        if sdram_drive is not None:
            # TASK-5040: weaker SDRAM IO drive (CCF DRIVE in mA: 3, 6, 9, 12) to test whether SDRAM bus switching noise
            # disturbs the DVI output under load. Applied to every sdram Subsignal before it is requested.
            for i, e in enumerate(platform.constraint_manager.available):
                if e[0] == "sdram":
                    for sub in e[2:]:
                        sub.constraints.append(Misc("DRIVE=%d" % sdram_drive))
        if sdram_slew is not None:
            # TASK-5047: SDRAM command/address/DQ slew rate (CCF SLEW; default UNDEFINED = toolchain choice).
            # sdram_clock keeps its platform SLEW=fast.
            for i, e in enumerate(platform.constraint_manager.available):
                if e[0] == "sdram":
                    for sub in e[2:]:
                        sub.constraints.append(Misc("SLEW=%s" % sdram_slew))

        self.crg = crg = SoCCRG(platform, sys_clk_freq, perf_mode, sdram_clk, with_gbe, with_video, with_usb,
                                   pll_lock_req=pll_lock_req, video_pix_freq=video_pix_freq)
        kwargs.setdefault("uart_name", "serial")
        # The BIOS prints the ident in its banner: name every address and MAC the SoC answers on (uputa #32 -
        # "Local IP: .213" from the netboot while ping only works on .212 confused the user).
        fmt_mac = lambda m: ":".join("%02x" % ((m >> (8*i)) & 0xff) for i in reversed(range(6)))
        ident = "ULX5M-GS SoC"
        if with_gbe and eth_mode == "hwstack":
            ident += " | HW ping/Etherbone %s (%s)" % (ip_address, fmt_mac(mac_address))
        if with_gbe and (eth_mode == "mac" or boot in ["netboot", "sdnet"]):
            ident += " | CPU/TFTP %s (%s)" % (local_ip, fmt_mac(cpu_mac_address))
        SoCCore.__init__(self, platform, sys_clk_freq, ident=ident, **kwargs)
        if with_gbe:
            # BIOS prints the ident in its SoC section (local LiteX patch docs/litex-bios-print-ident.patch)
            self.add_config("BIOS_PRINT_IDENT")

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
            platform.add_extension(_hdmi)
            if video_terminal:
                # LiteX VideoTerminal (Goran, uputa #57): 80x60 text mirror of the UART TX stream, font + text in
                # BRAM, no SDRAM DMA, no kernel support needed. Two-clock mode only (its memories are not CE-safe).
                assert not with_gbe, "--video-terminal: two-clock video only (no --with-gbe)"
                self.videophy = DVIPHY(platform.request("hdmi"), clock_domain="hdmi", neg_sync=video_neg_sync)
                self.add_video_terminal(phy=self.videophy, timings="640x480@60Hz", clock_domain="hdmi")
            elif not with_gbe:
                # two clocks: hdmi 25 MHz + hdmi5x 125 MHz (2 global nets)
                vcd, ce = "hdmi", None
                self.videophy = DVIPHY(platform.request("hdmi"), clock_domain="hdmi", neg_sync=video_neg_sync,
                                       ser_load=crg.div5.load if video_det_load else None)
                self.video_vtg = ClockDomainsRenamer("hdmi")(VideoTimingGenerator(default_video_timings="640x480@60Hz"))
            else:
                # 1G Ethernet uses all 4 global nets (sys, gtx0, TXC, grx). gtx0 is 125 MHz = hdmi5x, so the whole
                # video path runs in gtx0 and the pixel logic advances on ce = 1 cycle in 5 (25 MHz): no new net.
                # The pixel paths are 5-cycle paths that nextpnr checks as 1-cycle (reported FAIL at 125 MHz is
                # expected; the real requirement is 25 MHz, as for the hdmi domain in the two-clock build).
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
            if not video_terminal:
                port = self.sdram.crossbar.get_port(mode="read", data_width=16)
                self.video_fb2x = fb = FrameBuffer2x(port, hres=640, vres=480, base=fb_base, clock_domain=vcd, ce=ce,
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

        # USB 1.1 host (TASK-5040): SpinalHDL OHCI (as linux-on-litex / digilent_arty --with-usb); needs the
        # VexRiscv-SMP coherent DMA port (main() selects the _Cdma netlist). Linux needs CONFIG_USB_OHCI_HCD_PLATFORM,
        # which the prebuilt 5.14 kernel does not have.
        if with_usb:
            from litex.soc.cores.usb_ohci import USBOHCI
            from litex.soc.integration.soc import SoCRegion
            platform.add_extension(_usb_host)
            self.usb_ohci = USBOHCI(platform, platform.request("usb_host"), usb_clk_freq=int(48e6))
            pull = platform.request("usb_pull")
            self.comb += [pull.p.eq(0), pull.n.eq(0)]    # host: 12k1 pull-downs on D+ and D-
            self.bus.add_slave("usb_ohci_ctrl", self.usb_ohci.wb_ctrl,
                               region=SoCRegion(origin=0xc0000000, size=0x1000, cached=False))
            self.dma_bus.add_master("usb_ohci_dma", master=self.usb_ohci.wb_dma)
            self.comb += self.cpu.interrupt[16].eq(self.usb_ohci.interrupt)

        # USB 1.1 low-speed HID host (TASK-5047): Emard's usbh_host_hid, 6 MHz = 125 MHz/21 on local routing.
        if with_usb_hid:
            from usb_hid import USBHIDHost
            assert with_gbe or with_video, "--with-usb-hid needs a 125 MHz domain (gtx0 or hdmi5x)"
            platform.add_extension(_usb_host)
            self.usb_hid = USBHIDHost(platform, platform.request("usb_host"), platform.request("usb_pull"),
                                      src_domain="gtx0" if with_gbe else "hdmi5x", rst=~crg.rst_n)

        # Ethernet 1000 Mb/s: hardware ARP/ICMP (ping without the CPU) + Etherbone on UDP 1234 -------
        if with_gbe:
            from gbe_phy import GbePHY
            from eth_stack import EthUDPStack
            from liteeth.frontend.etherbone import LiteEthEtherbone
            from target_gbe import eth_io
            # RGMII + MDIO pins (docs/PINMAP.md); mdio_core_uart is dropped: IO_NB_B5 is the BIOS serial TX here.
            platform.add_extension([r for r in eth_io() if r[0] != "mdio_core_uart"])
            clock_pads = platform.request("eth_clocks")
            pads       = platform.request("eth")
            self.ethphy = phy = GbePHY(clock_pads, pads, clk_tx=crg.cd_gtx0.clk,
                                       txc_clks=[crg.cd_gtx0.clk, crg.cd_gtx90.clk], txc_sel=2, rst=crg.eth_rst,
                                       txc_bufg=True)
            phy.tx_clk_freq = phy.rx_clk_freq = sys_clk_freq
            platform.add_period_constraint(clock_pads.rx, 1e9/125e6)
            if eth_mode == "mac":
                # CPU-only MAC (Linux SoC, TASK-5033): no hardware ARP/ICMP/UDP/Etherbone (~ -9k CPE_LT, lesson J7);
                # the CPU answers ping (Linux) and does TFTP (BIOS netboot) itself, on local_ip.
                # 8-bit MAC in sys, exactly like the proven hardware/hybrid path. add_ethernet(data_width=32) was
                # tried first: TX works but RX never delivers a frame to the CPU (ARP reply lost, TASK-5033).
                from liteeth.mac import LiteEthMAC
                self.ethmac = LiteEthMAC(phy=phy, dw=8, interface="wishbone", endianness=self.cpu.endianness,
                                         with_preamble_crc=True, with_sys_datapath=True)
                self.add_cpu_mac_regions(self.ethmac, cpu_mac_address, local_ip, remote_ip)
            else:
                with_cpu_mac = boot in ["netboot", "sdnet"]
                self.ethcore = EthUDPStack(phy, mac_address, ip_address, sys_clk_freq, with_sys_datapath=True,
                                           tx_last_be_fix=False, interface="hybrid" if with_cpu_mac else "crossbar",
                                           endianness=self.cpu.endianness if with_cpu_mac else "big")
                if with_cpu_mac:
                    self.add_cpu_mac(self.ethcore.core, cpu_mac_address, local_ip, remote_ip)
                self.etherbone = LiteEthEtherbone(self.ethcore.core.udp, 1234, buffer_depth=16, cd="sys")
                self.bus.add_master(name="etherbone", master=self.etherbone.wishbone.bus)
            # KSZ9031: RESET_N + advertisement 1000FD on the first MDIO pass (lessons I2/I3). Its UART is not
            # connected (the pins belong to the BIOS serial).
            platform.add_source(os.path.join(os.path.dirname(__file__), "..", "tools", "uhello", "mdio_core.v"))
            snap = Signal(256)
            self.specials += Instance("mdio_core",
                p_WRITE_AFTER = 0, p_REG9 = 0x0200, p_REG4 = 0x0001, p_REG0 = 0x1200,
                p_BAUD = int(round(sys_clk_freq/115200)) - 1,
                i_clk25 = ClockSignal("sys"), o_uart_a = Signal(), o_uart_b = Signal(),
                o_mdc = pads.mdc, io_mdio = pads.mdio, o_rst_n = pads.rst_n,
                i_rxc = ClockSignal("grx"), i_rx_ctl = 0, i_dbg = 0, o_snap_bus = snap)
            # KSZ9031 registers for the CPU / Etherbone: phy_status0 = {R1, R1F}, phy_status1 = {RA, RXC count/2^8}
            # snap_bus = {passes, idm, {wrote,addr}, r0, r1, r4, r5, r9, ra, rf, rfreq(24), frames(16), 80'h0}
            f = lambda hi, n: snap[256 - hi - n:256 - hi]
            self.phy_status0 = CSRStatus(32, description="KSZ9031 R1 (bits 31:16) and R1F (15:0); R1F bit 6 = 1000 Mb/s")
            self.phy_status1 = CSRStatus(32, description="KSZ9031 RA (31:16), RXC edges per 2^20 sys cycles >> 8 (15:0)")
            self.comb += [self.phy_status0.status.eq(Cat(f(120, 16), f(40, 16))),
                          self.phy_status1.status.eq(Cat(f(136, 24)[8:24], f(104, 16)))]

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
            plls = [("sys", crg.pll_sys)] + ([("tx", crg.pll_tx)] if with_gbe else []) + \
                   ([("video", crg.pll_video)] if not with_gbe else [])
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
        if with_video and not with_gbe:
            self.comb += leds[5].eq(crg.lock_video.locked)


    def add_cpu_mac(self, ethcore, mac_address, local_ip, remote_ip):
        """CPU port of the hybrid MAC (as LiteX add_etherbone(with_ethmac=True)): SRAM slots + CSRs + IRQ."""
        ethcore.autocsr_exclude = {"mac"}
        self.ethmac = ethcore.mac
        self.add_cpu_mac_regions(self.ethmac, mac_address, local_ip, remote_ip)

    def add_cpu_mac_regions(self, ethmac, mac_address, local_ip, remote_ip):
        """Wishbone SRAM slots, IRQ and BIOS constants of a CPU MAC port (hybrid or wishbone-only)."""
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
        self.add_constant("ETH_PHY_NO_RESET")   # the BIOS must not reset the PHY under the hardware stack
        add_ip_address_constants(self, "LOCALIP", local_ip)
        add_ip_address_constants(self, "REMOTEIP", remote_ip)
        add_mac_address_constants(self, "MACADDR", mac_address)


BOOT_MODES   = ["none", "serial", "sdcard", "netboot", "sdnet"]
SDCARD_MODES = ["none", "native", "spi"]


def main():
    import argparse
    from litex.soc.integration.soc_core import soc_core_args, soc_core_argdict
    p = argparse.ArgumentParser(description="ULX5M-GS full LiteX SoC (TASK-5032 phase 2)")
    p.add_argument("--build",        action="store_true")
    p.add_argument("--output-dir",   default=None)
    p.add_argument("--sys-clk-freq", default=20e6, type=float)
    p.add_argument("--perf-mode",    default="economy", choices=["lowpower", "economy", "speed"], help="PLL PERF_MD")
    p.add_argument("--pnr-mode",     default="speed",   choices=["lowpower", "economy", "speed"])
    p.add_argument("--sdram-clk",    default="inv",     choices=["inv", "ps90"])
    p.add_argument("--sdram-cl",     default=2, type=int, choices=[2, 3])
    p.add_argument("--with-gbe",     action="store_true")
    p.add_argument("--with-sdcard",  action="store_true", help="= --sdcard native")
    p.add_argument("--sdcard",       default="none", choices=SDCARD_MODES, help="SD card core (see ULX5MSoC)")
    p.add_argument("--ip",           default="192.168.10.212")
    p.add_argument("--seed",         default=None, type=int)
    p.add_argument("--placer-timeout", default=None, type=int,
                   help="nextpnr --placer-heap-cell-placement-timeout (netboot SoC: 77%% LT, placer gives up)")
    p.add_argument("--synth-extra", default=None, help="extra synth_gatemate options, e.g. '-nomult' (lesson J7)")
    p.add_argument("--boot",         default="none", choices=BOOT_MODES, help="BIOS boot source (see ULX5MSoC)")
    p.add_argument("--eth-mode",     default="hwstack", choices=["hwstack", "mac"],
                   help="hwstack: hardware ARP/ICMP/Etherbone on --ip (+ CPU MAC for netboot); mac: CPU MAC only")
    p.add_argument("--local-ip",     default="192.168.10.213", help="CPU IP for --boot netboot")
    p.add_argument("--remote-ip",    default="192.168.10.14",  help="TFTP server for --boot netboot")
    p.add_argument("--with-video",   action="store_true", help="DVI 640x480@60, 320x240 rgb565 framebuffer (TASK-5040)")
    p.add_argument("--fb-base",      default=0x43f00000, type=lambda x: int(x, 0), help="framebuffer address")
    p.add_argument("--video-terminal", action="store_true", help="with --with-video: LiteX VideoTerminal (UART mirror) instead of the framebuffer")
    p.add_argument("--video-ce-rep", action="store_true", help="1G+DVI: one ce register per video block (fanout)")
    p.add_argument("--video-neg-sync", action="store_true", help="VESA 640x480: negative hsync/vsync")
    p.add_argument("--sdram-drive",  default=None, type=int, choices=[3, 6, 9, 12], help="CCF DRIVE (mA) of the SDRAM pins")
    p.add_argument("--video-det-load", action="store_true", help="two-clock DVI: serializer load from the /5 state")
    p.add_argument("--pll-lock-req", default=1, type=int, choices=[0, 1], help="CC_PLL LOCK_REQ (0: outputs run without lock, TASK-5047)")
    p.add_argument("--sdram-slew",   default=None, choices=["slow", "fast"], help="CCF SLEW of the SDRAM pins (TASK-5047)")
    p.add_argument("--video-pix-freq", default=25e6, type=float, help="two-clock DVI pixel clock (25.175e6 = VESA)")
    p.add_argument("--video-640x240", action="store_true", help="640x240 framebuffer, lines doubled only (80x30 text, 18.4 MB/s)")
    p.add_argument("--video-recover", action="store_true", help="1G+DVI: resettable video domain + resync watchdog (TASK-5047)")
    p.add_argument("--with-usb-hid", action="store_true", help="USB low-speed HID host (Emard) on J5, CSR usb_hid (TASK-5047)")
    p.add_argument("--with-usb",     action="store_true", help="USB 1.1 host OHCI on USB-C J5 (TASK-5040, P&R estimate)")
    soc_core_args(p)
    p.set_defaults(cpu_type="vexriscv", integrated_rom_size=0x10000, integrated_sram_size=0x2000, l2_size=0)
    args = p.parse_args()
    if args.with_usb:
        from litex.soc.cores.cpu.vexriscv_smp.core import VexRiscvSMP
        VexRiscvSMP.coherent_dma = True

    soc = ULX5MSoC(sys_clk_freq=args.sys_clk_freq, perf_mode=args.perf_mode, pnr_mode=args.pnr_mode,
                   sdram_clk=args.sdram_clk, sdram_cl=args.sdram_cl, with_gbe=args.with_gbe,
                   with_sdcard=args.with_sdcard, sdcard=args.sdcard, ip_address=args.ip, boot=args.boot, local_ip=args.local_ip,
                   remote_ip=args.remote_ip, eth_mode=args.eth_mode, with_video=args.with_video,
                   fb_base=args.fb_base, with_usb=args.with_usb,
                   video_terminal=args.video_terminal, video_ce_rep=args.video_ce_rep,
                   video_neg_sync=args.video_neg_sync, sdram_drive=args.sdram_drive,
                   video_det_load=args.video_det_load, pll_lock_req=args.pll_lock_req, sdram_slew=args.sdram_slew,
                   video_pix_freq=args.video_pix_freq, video_640x240=args.video_640x240,
                   with_usb_hid=args.with_usb_hid, video_recover=args.video_recover, **soc_core_argdict(args))
    if args.synth_extra:
        soc.platform.toolchain._synth_opts += " " + args.synth_extra + " "
    if args.placer_timeout:
        soc.platform.toolchain._pnr_opts += " --placer-heap-cell-placement-timeout %d " % args.placer_timeout
    builder = Builder(soc, output_dir=args.output_dir or os.path.join(os.path.dirname(__file__), "..", "build", "soc"))
    kw = {"seed": args.seed} if args.seed is not None else {}
    builder.build(run=args.build, **kw)


if __name__ == "__main__":
    main()
