#!/usr/bin/env python3
#
# LiteX Ethernet on the Radiona ULX5M-GS (CologneChip GateMate CCGM1A1).
#
# A CPU-less UDP/IP endpoint:
#   GateMate RGMII PHY (100 Mbps) -> LiteEth MAC/ARP/IP/ICMP/UDP core -> a UDP
#   echo engine. ICMP ping is answered automatically by the core; any UDP
#   datagram sent to <ip>:<UDP_ECHO_PORT> is echoed back to its sender.
#
# Toolchain: fully open (Yosys -> nextpnr-himbaechel -> gmpack/peppercorn).
# No vendor tools, no CPU, no BIOS.
#
# Build:
#   source ./env.sh
#   python3 gateware/target_eth.py --build
#   # bitstream -> build/eth/gateware/intergalaktik_ulx5m_gs.bit
#
# The design listens at IP 10.10.10.50 by default (override with --ip),
# UDP echo on port 7000 (override with --udp-port).
#
# SPDX-License-Identifier: BSD-2-Clause

import sys
import os

from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.fhdl.specials import Tristate
from litex.build.io import DDROutput

from litex.gen import *
from litex.build.generic_platform import Pins, Misc

from litex_boards.platforms import intergalaktik_ulx5m_gs
from litex.soc.integration.soc_core import SoCMini
from litex.soc.integration.builder import Builder

sys.path.insert(0, os.path.dirname(__file__))                        # gateware/ (local modules)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))    # repo root: `gateware` package
from ulx5m_eth_platform import add_eth_io
from phy_rgmii_gatemate import LiteEthPHYRGMII_GateMate
from eth_stack import EthUDPStack, UDPEcho
from status_leds import StatusLeds
from crg import EthCRG
from beacon import UDPBeacon
from jtag_probe import EthJTAGProbe
from l2_beacon import L2Beacon, ETHERTYPE_L2BEACON
from pll_serial import PLLStaticBits, PLLFreqProbe, PLLSerialOut, PLLLevelBits
from raw_tx import RawTXFrames, build_frame
from mdio_diag import MDIODiagEngine, FreqMeter, UARTLineDumper, hexf, DIAG_READ_REGS

# ULX5M-GS LED ball map (active-high). The litex-boards `user_led_n` mapping is
# active-low and has the wrong A/B order for bits 4-7 on this board; use this
# verified map and drive the pads directly (no inversion).
_status_leds = [
    ("status_led", 0, Pins("IO_SB_A0"), Misc("DRIVE=3")),
    ("status_led", 1, Pins("IO_SB_B0"), Misc("DRIVE=3")),
    ("status_led", 2, Pins("IO_SB_A1"), Misc("DRIVE=3")),
    ("status_led", 3, Pins("IO_SB_B1"), Misc("DRIVE=3")),
    ("status_led", 4, Pins("IO_SB_B2"), Misc("DRIVE=3")),
    ("status_led", 5, Pins("IO_SB_A2"), Misc("DRIVE=3")),
    ("status_led", 6, Pins("IO_SB_B3"), Misc("DRIVE=3")),
    ("status_led", 7, Pins("IO_SB_A3"), Misc("DRIVE=3")),
]


class EthEchoSoC(SoCMini):
    def __init__(self, sys_clk_freq=16e6, tx_clk_freq=25e6, toolchain="peppercorn",
                 ip_address="10.10.10.50", mac_address=0x10e2d5000000, udp_port=7000,
                 build_id=1, gbe=False, with_phy_refclk=True, diag=False,
                 refclk_drive=6, refclk_slew="fast", tx_clk_src="clk25", refclk_mode="comb",
                 diag_phyads=None, perf_mode="speed", phy_reset_ms=20.0, tx_store_forward=False,
                 beacon_port=None, beacon_tag=0, single_pll=False, jtag_probe=False, l2_beacon=False, pll_bits=None, raw_tx=False, sdr_tx=False, raw_bits=None, phy_loopback=False, raw_bad_fcs=False, raw_no_tx=False, no_echo=False, synth_extra=None, beacon_period=None, pnr_mode=None, pnr_extra=None, rx_off=False, mb_clk25=False, pll_freq=None, tx_pll_mode=None, sys_src="pll", txc_delay_luts=0, sdr_rx=False, pll_serial=None, pll_flags=None, mdio_core=False, cfgrst=True, **kwargs):
        platform = intergalaktik_ulx5m_gs.Platform(toolchain)
        if synth_extra:
            platform.toolchain._synth_opts += " " + synth_extra
        # nextpnr timing/PLL model must match the real VDD_CORE (jumper; TASK-4999).
        if toolchain == "peppercorn":
            platform.toolchain._pnr_opts += " --vopt fpga_mode=%d " % {
                "lowpower": 1, "economy": 2, "speed": 3}[pnr_mode or perf_mode]
            if pnr_extra:
                platform.toolchain._pnr_opts += " " + pnr_extra + " "
            # gmpack --reset (TASK-4999, 24.9. 20:50): the bitstream starts with CMD_CFGRST, which clears ALL
            # configuration latches. Without it the (sparse) bitstream is written over the previous
            # design's configuration -- the DirtyJTAG SRST pulse of `openFPGALoader -r` does not reset the
            # device -- and designs "stop working" after other loads (stuck UART bits, 0 frames). Proven:
            # eb50 without --reset 0 frames / 0 B UART, the same .txt with --reset 58 frames + clean UART.
            if cfgrst:
                platform.toolchain._packer_opts = "--reset " + platform.toolchain._packer_opts

        self.sys_clk_freq = sys_clk_freq
        # CRG: two PLLs off clk25 (split-clock; see gateware/crg.py). --------------
        self.crg = EthCRG(platform, sys_clk_freq, tx_clk_freq, tx_clk_src=tx_clk_src,
                          perf_mode=perf_mode, single_pll=single_pll, tx_perf_mode=tx_pll_mode,
                          sys_src=sys_src, txc_delay_luts=txc_delay_luts)

        SoCMini.__init__(self, platform, clk_freq=sys_clk_freq,
            ident="LiteX GateMate RGMII + LiteEth UDP echo (no CPU)", **kwargs)

        # Ethernet IO + PHY. -------------------------------------------------------
        add_eth_io(platform, refclk_drive=refclk_drive, refclk_slew=refclk_slew, tx_io_ff=(tx_clk_src == "io50"))
        # PHY reference clock: 25 MHz out on IO_EB_A3 -> KSZ9031 XI. Mandatory on this
        # board (X1/R104 are dnp); see gateware/ulx5m_eth_platform.py.
        refclk_rb = None
        if with_phy_refclk:
            refclk_pad = platform.request("eth_refclk")
            if refclk_mode == "ddr":
                # Forward clk25 through the IO-cell DDR register (1 on rise, 0 on fall):
                # the pin toggles from a global-clocked register, not a fabric-routed net.
                self.specials += DDROutput(i1=1, i2=0, o=refclk_pad, clk=ClockSignal("tx25"))
            elif diag:
                # Same drive, but through a CC_IOBUF so the pad level is read back (Y) and
                # its frequency measured in fabric -- proves the pin really toggles at 25 MHz.
                # T is a live register (sys reset -> 0 -> 1): a constant T hits the
                # nextpnr pack_io const-T bug (memory: gatemate-iobuf-workaround).
                # OE lives on clk25 and resets ONLY on CC_USR_RSTN: in the sys domain it was held
                # at 0 by the LiteX PLL reset (~locked) -> no XI whenever the sys PLL did not lock
                # (1.1 V SPEED: PLL0 OVF) -> PHY dead, ref_any=0, ta_id=1 (TASK-4999, 24.9.).
                refclk_oe = Signal()
                refclk_rb = Signal()
                self.cd_refoe = ClockDomain()
                self.comb += self.cd_refoe.clk.eq(self.crg.clk25)
                self.specials += AsyncResetSynchronizer(self.cd_refoe, ~self.crg.rst_n)
                self.sync.refoe += refclk_oe.eq(1)
                self.specials += Tristate(refclk_pad, self.crg.clk25, refclk_oe, refclk_rb)
            else:
                self.comb += refclk_pad.eq(self.crg.clk25)
        eth_clocks = platform.request("eth_clocks")
        eth_pads   = platform.request("eth")
        # tx_clk MUST be the actual PLL#1 clock Signal (not a ClockSignal); the PHY
        # CRG's `isinstance(tx_clk, Signal)` check decides whether PLL#1 is used as
        # the TX line clock vs. looping RXC back.
        # gbe=False (default): 100 Mbps only; eth_tx = 25 MHz, TXC = straight pass-through.
        # gbe=True: speed-adaptive datapath (LiteEthRGMIITXClock, external_tx_clk). eth_tx MUST
        # then be 125 MHz -- TXC is passed through at 1G and divided by 5 at 100M. RXC (125 MHz
        # at 1G) is promoted onto a global clock net (rxc_global).
        self.ethphy = LiteEthPHYRGMII_GateMate(
            clock_pads        = eth_clocks,
            pads              = eth_pads,
            tx_clk            = self.crg.cd_tx25.clk,
            fixed_100m        = not gbe,  # board runs 100 Mbps RGMII; use the 10/100 datapath.
            with_dynamic_link = gbe,
            rxc_global        = gbe,
            line_rate_1g      = gbe,
            # HW MDIO sequencer: force the KSZ9031 to advertise 100BASE-TX FD only
            # (reg9=0, reg4=0x0101, reg0=0x1200). Without it the PHY negotiates
            # gigabit (power-on default) whose 125 MHz RXC this board cannot clock.
            # PHY hardware reset + MDIO sequencer run in the PLL-free "ref" domain (25 MHz osc).
            ctrl_cd           = "ref",
            mdio_sequencer_clk_freq = None if gbe else 25e6,
            with_mdio         = not (diag or mdio_core),
            tx_clk90          = self.crg.tx_clk90,
            tx_clk180         = self.crg.tx_clk180,
            txc_readback      = raw_tx,
            sdr_tx            = sdr_tx,
            rx_off            = rx_off,
            sdr_rx            = sdr_rx,
            # --phy-loopback (TASK-4999): KSZ9031 near-end loopback, 100M FD, AN off (reg0 =
            # 0x6100: bit14 loopback, bit13 speed100, bit8 full duplex) -> RGMII TX comes back on
            # RGMII RX without the line/switch: proves whether the PHY receives our TX correctly.
            mdio_writes       = [(9, 0x0000), (4, 0x0101), (0, 0x6100)] if phy_loopback else None,
            hw_reset_cycles   = max(256, int(25e6*phy_reset_ms/1e3)),
            tx_store_forward  = tx_store_forward,
        )

        # --raw-tx (TASK-4999): NO MAC/ARP/IP. A constant, build-time frame (preamble+SFD+frame+FCS)
        # goes straight into the PHY sink 4x/s -> isolates PHY TX/TXC/pins/link from LiteEth.
        # PLL bits: bit0 = a whole frame accepted by the PHY sink, bit1 = PHY sink ever valid.
        if raw_tx:
            frame = build_frame(mac_address, tag=beacon_tag, bad_fcs=raw_bad_fcs)
            self.raw = RawTXFrames(self.ethphy.sink, frame, period=int(25e6 // 4), cd="eth_tx",
                                   enable=not raw_no_tx)
            self.comb += self.ethphy.source.ready.eq(1)
            # PLL bits: bit0 = TXC pad (read back through CC_IOBUF) toggles at ~25 MHz,
            #           bit1 = RXC ~25 MHz (PHY RX clock in 100M mode). Meters count per 2**14
            #           eth_tx cycles (25 MHz -> 16384), accepted within +-10 %.
            from mdio_diag import FreqMeter
            self.cd_txcrb = ClockDomain(reset_less=True)
            self.comb += self.cd_txcrb.clk.eq(self.ethphy.crg.txc_readback)
            self.cd_txcrb.clk.attr.add(("clkbuf_inhibit", 1))
            to_tx = ClockDomainsRenamer({"sys": "eth_tx"})
            self.fm_txc = to_tx(FreqMeter("txcrb", gate_bits=14, width=16))
            self.fm_rxc = to_tx(FreqMeter("eth_rx", gate_bits=14, width=16))
            ok = lambda v: (v > 14745) & (v < 18022)
            fl = {n: Signal(name="rawflag_" + n) for n in
                  ("txc", "rxc", "done", "rxany", "rxpre", "ctl")}
            self.sync.eth_tx += [fl["txc"].eq(ok(self.fm_txc.value)), fl["rxc"].eq(ok(self.fm_rxc.value))]
            snk, src = self.ethphy.sink, self.ethphy.source
            self.sync.eth_tx += If(snk.valid & snk.ready & snk.last, fl["done"].eq(1))
            # RX side (eth_rx): any frame; a frame whose byte 0 is 0x55 and byte 7 is 0xD5.
            rx_idx, rx_b0, rxany, rxpre = Signal(12), Signal(8), Signal(), Signal()
            rx_b20, rxown = Signal(8), Signal()
            # rxexact: a received frame identical, byte for byte (preamble..FCS), to the one we send.
            rom_rx = Array([C(b, 8) for b in frame])
            rx_mis, rxexact = Signal(), Signal()
            rxarp = Signal()   # a frame from the network: ethertype 0x0806 (ARP) at bytes 20-21
            self.sync.eth_rx += If(src.valid & src.ready,
                rx_idx.eq(rx_idx + 1),
                If(rx_idx == 0, rx_b0.eq(src.data)),
                If((rx_idx == 7) & (rx_b0 == 0x55) & (src.data == 0xD5), rxpre.eq(1)),
                If(rx_idx == 20, rx_b20.eq(src.data)),
                If((rx_idx == 21) & (rx_b20 == 0x88) & (src.data == 0xB6), rxown.eq(1)),
                If((rx_idx == 21) & (rx_b20 == 0x08) & (src.data == 0x06), rxarp.eq(1)),
                If((rx_idx >= len(frame)) | (src.data != rom_rx[rx_idx[:7]]), rx_mis.eq(1)),
                If(src.last,
                    rx_mis.eq(0),
                    If(~rx_mis & (rx_idx == len(frame) - 1) & (src.data == frame[-1]), rxexact.eq(1))),
                If(src.last, rx_idx.eq(0), rxany.eq(1)))
            self.specials += MultiReg(rxany, fl["rxany"], "eth_tx")
            self.specials += MultiReg(rxpre, fl["rxpre"], "eth_tx")
            # Echo latency: eth_tx cycles from our frame start to RX_DV of the next RX frame start.
            rxdv_s, rxdv_d = Signal(), Signal()
            self.specials += MultiReg(src.valid, rxdv_s, "eth_tx")
            lat, lat_run, lat_lt8, lat_lt64 = Signal(12), Signal(), Signal(), Signal()
            self.sync.eth_tx += [
                rxdv_d.eq(rxdv_s),
                If(self.raw.start, lat.eq(0), lat_run.eq(1)
                ).Elif(lat_run,
                    lat.eq(lat + 1),
                    If(rxdv_s & ~rxdv_d,
                        lat_run.eq(0),
                        If(lat < 8, lat_lt8.eq(1)),
                        If(lat < 64, lat_lt64.eq(1))),
                    If(lat == 4095, lat_run.eq(0)))
            ]
            fl["lat8"], fl["lat64"] = lat_lt8, lat_lt64
            fl["rxarp"] = Signal(name="rawflag_rxarp")
            self.specials += MultiReg(rxarp, fl["rxarp"], "eth_tx")
            fl["rxexact"] = Signal(name="rawflag_rxexact")
            self.specials += MultiReg(rxexact, fl["rxexact"], "eth_tx")
            fl["rxown"] = Signal(name="rawflag_rxown")
            self.specials += MultiReg(rxown, fl["rxown"], "eth_tx")
            ctl_s = Signal()
            if self.ethphy.tx.tx_ctl_readback is not None:
                self.specials += MultiReg(self.ethphy.tx.tx_ctl_readback, ctl_s, "eth_tx")
                self.sync.eth_tx += If(ctl_s, fl["ctl"].eq(1))
            # The PLL-bit domain must NOT share eth_tx's reset: with eth_tx held in reset the
            # reference stops and the PLL status freezes (read as a constant ft ~0x09C = false "3";
            # caught by the b30 no-TX control, TASK-4999). rawmb = eth_tx clock + its own POR.
            self.cd_rawmb = ClockDomain()
            por = Signal(4)
            self.cd_rawpor = ClockDomain(reset_less=True)
            self.comb += [self.cd_rawmb.clk.eq(ClockSignal("eth_tx")),
                          self.cd_rawpor.clk.eq(ClockSignal("eth_tx")),
                          self.cd_rawmb.rst.eq(~por[3])]
            self.sync.rawpor += If(~por[3], por.eq(por + 1))
            txrst_s = Signal()
            self.specials += MultiReg(ResetSignal("eth_tx"), txrst_s, "rawmb")
            fl["txrun"] = Signal(name="rawflag_txrun")
            self.sync.rawmb += If(~txrst_s, fl["txrun"].eq(1))
            fl["zero"], fl["one"] = C(0, 1), C(1, 1)
            sysrst_s, phyrst_s = Signal(), Signal()
            self.specials += MultiReg(ResetSignal("sys"), sysrst_s, "rawmb")
            self.specials += MultiReg(self.ethphy.crg.reset, phyrst_s, "rawmb")
            fl["sysrun"], fl["phyrel"] = Signal(name="rawflag_sysrun"), Signal(name="rawflag_phyrel")
            self.sync.rawmb += [If(~sysrst_s, fl["sysrun"].eq(1)), If(~phyrst_s, fl["phyrel"].eq(1))]
            names = (raw_bits or "txc,rxc").split(",")
            bits_mb = []
            for n in names:
                b = Signal(name="rawbit_" + n)
                self.specials += MultiReg(fl[n], b, "rawmb")
                bits_mb.append(b)
            self.pll_bits = PLLStaticBits(bits_mb, cd="rawmb")
            if toolchain == "peppercorn":
                platform.toolchain._pnr_opts += " --write routed.json "
            platform.add_extension(_status_leds)
            led = Cat(*[platform.request("status_led", i) for i in range(8)])
            self.comb += led.eq(self.pll_bits.load << 7)
            platform.add_period_constraint(eth_clocks.rx, 1e9/25e6)
            return

        # Full L2-L4 stack (MAC/ARP/IP/ICMP/UDP), sys datapath. --------------------
        self.stack = EthUDPStack(
            phy               = self.ethphy,
            mac_address       = mac_address,
            ip_address        = ip_address,
            clk_freq          = sys_clk_freq,
            dw                = 8,
            with_icmp         = True,   # ping answered in hardware, no CPU.
            with_sys_datapath = True,
        )

        # UDP echo engine on `udp_port`. A packet FIFO buffers each datagram so RX
        # is never back-pressured by TX-side ARP resolution. -----------------------
        if not no_echo:
            self.echo = UDPEcho(self.stack, udp_port, dw=8)

        # Bring-up status LEDs. link_up/speed come from the RGMII RX in-band status
        # CDC'd into sys; stay 0 if the field is absent. mdio_done confirms the HW
        # MDIO sequencer finished its KSZ9031 100-FD bring-up writes. ---------------
        link_up_sys = Signal()
        speed_sys   = Signal(2)
        _rx = self.ethphy.rx
        if hasattr(_rx, "inband_status") and hasattr(_rx.inband_status, "fields") \
           and hasattr(_rx.inband_status.fields, "link_status"):
            self.specials += MultiReg(_rx.inband_status.fields.link_status, link_up_sys, "sys")
            self.specials += MultiReg(_rx.inband_status.fields.clock_speed, speed_sys, "sys")
        mdio_done = Signal()
        if hasattr(self.ethphy, "mdio_sequencer"):
            self.comb += mdio_done.eq(self.ethphy.mdio_sequencer.done)
        if diag:
            self.add_diag(platform, eth_pads, sys_clk_freq, refclk_rb, link_up_sys, speed_sys,
                          diag_phyads, pll_serial=pll_serial, pll_flags=pll_flags)
            self.comb += mdio_done.eq(self.mdio_diag.done)
        if mdio_core:
            # --mdio-core (TASK-4999): the standalone tools/uhello/mdio_core.v that brought the new board
            # up to 100FD (mp2/eb50: MDIO 64 MDC edges, AN 100FD write burst to PHYAD 0..7) replaces
            # MDIOWriteSequencer, and prints PHY registers + RXC freq over the DirtyJTAG UART
            # (IO_NA_A4/IO_NB_B5, 115200): "P=.. A=3 R0= R1= R4= R5= R9= RA= RF= C= F=".
            # PHY RESET_N stays with the LiteEth PHY CRG (20 ms, ref domain); mdio_core only starts
            # MDIO at 84 ms. rx_ctl is not shared (the IDDR packer needs a single-user input net).
            import os as _os
            platform.add_source(_os.path.join(_os.path.dirname(__file__), "..", "tools", "uhello", "mdio_core.v"))
            platform.add_extension([("mdio_core_uart", 0, Pins("IO_NA_A4")), ("mdio_core_uart", 1, Pins("IO_NB_B5"))])
            self.specials += Instance("mdio_core",
                i_clk25   = self.crg.clk25,
                o_uart_a  = platform.request("mdio_core_uart", 0),
                o_uart_b  = platform.request("mdio_core_uart", 1),
                o_mdc     = eth_pads.mdc,
                io_mdio   = eth_pads.mdio,
                o_rst_n   = Signal(),
                i_rxc     = ClockSignal("eth_rx"),
                i_rx_ctl  = 0,
                i_dbg     = 0,
                o_snap_bus = Signal(256))

        # LED4/LED5 = a whole frame crossed the PHY boundary (RX from the wire / TX to the wire),
        # not just UDP-echo traffic: during `ping` LED4 shows the ARP requests arriving and LED5
        # shows the ARP/ICMP replies leaving -- readable by eye, no UART needed (TASK-4999).
        from migen.genlib.cdc import PulseSynchronizer
        rx_frame_sys, tx_frame_sys = Signal(), Signal()
        for cd, ep, out in [("eth_rx", self.ethphy.source, rx_frame_sys),
                            ("eth_tx", self.ethphy.sink,   tx_frame_sys)]:
            ps = PulseSynchronizer(cd, "sys")
            self.submodules += ps
            self.comb += [ps.i.eq(ep.valid & ep.ready & ep.last), out.eq(ps.o)]
        self.status_leds = StatusLeds(
            sys_clk_freq = sys_clk_freq,
            rx_active    = rx_frame_sys,
            tx_active    = tx_frame_sys,
            link_up      = link_up_sys,
            speed        = speed_sys,
            mdio_done    = mdio_done,
        )
        # UDP broadcast beacon (TASK-4999): 1/s to <subnet>.255:<beacon_port>, received on the LAN
        # with a plain socket (no root) -> proves the TX path and reports internal state.
        # Payload after magic/tag/seq: flags, RX frames, TX frames (8-bit wrap).
        #   flags: b0 PLL eth_tx locked, b1 PLL sys locked, b2 MDIO done, b3 in-band link,
        #          b4-5 in-band speed, b6 PHY reset released.
        if beacon_port is not None:
            flags, rxf, txf = Signal(8), Signal(8), Signal(8)
            pll_tx_locked, pll_sys_locked, phy_run = Signal(reset=1), Signal(), Signal()
            if hasattr(self.crg, "pll_tx"):
                self.specials += MultiReg(self.crg.pll_tx.locked, pll_tx_locked, "sys")
            self.specials += MultiReg(self.crg.pll_sys.locked, pll_sys_locked, "sys")
            self.specials += MultiReg(~self.ethphy.crg.reset, phy_run, "sys")
            self.comb += flags.eq(Cat(pll_tx_locked, pll_sys_locked, mdio_done, link_up_sys,
                                      speed_sys, phy_run))
            self.sync += [If(rx_frame_sys, rxf.eq(rxf + 1)), If(tx_frame_sys, txf.eq(txf + 1))]
            ip = [int(x) for x in ip_address.split(".")]
            bcast = (ip[0] << 24) | (ip[1] << 16) | (ip[2] << 8) | 0xFF
            self.beacon = UDPBeacon(self.stack, udp_port=beacon_port, dst_ip=bcast,
                                    period=int(sys_clk_freq), tag=beacon_tag,
                                    fields=[flags, rxf, txf])

        # JTAG snapshot probe (TASK-4999): internal state read over the JTAG TAP (CC_SERDES regfile).
        if jtag_probe or l2_beacon or pll_bits:
            self.probe_mdio_done, self.probe_link_up, self.probe_speed = mdio_done, link_up_sys, speed_sys
            self.jtag_probe = EthJTAGProbe(platform, self, self.crg.clk25, with_mailbox=jtag_probe,
                                           mb_clk=ClockSignal("eth_tx") if (pll_bits and not mb_clk25) else None)
        # L2 beacon (TASK-4999): raw broadcast frame, ethertype 0x88B5, 2/s, carrying the probe
        # snapshot -> TX-path proof + observation channel over the wire (tcpdump on the Pi).
        if l2_beacon:
            snap_sys = Signal(len(self.jtag_probe.snapshot))
            self.specials += MultiReg(self.jtag_probe.snapshot, snap_sys, "sys")
            self.l2_beacon = L2Beacon(self.stack.core.mac.crossbar.get_port(ETHERTYPE_L2BEACON, dw=8),
                                      mac_address, snap_sys,
                                      period=beacon_period or int(sys_clk_freq // 2),
                                      tag=beacon_tag)

        # PLL static bits (TASK-4999): 2 live yes/no answers readable over JTAG (STATUS_PLLx).
        pll_load = C(0, 1)
        if pll_freq:
            # --pll-freq <domain>[/2]: spare PLL reference = that clock (or its /2 toggle).
            dom, _, div = pll_freq.partition("/")
            if div == "2":
                tg = Signal(name="pllfreq_toggle")
                getattr(self.sync, dom).__iadd__(tg.eq(~tg))
                ref = tg
            elif div:
                # /N (N >= 3): one rising edge per N cycles (TASK-5007: meter calibration at 1.1 V).
                n = int(div)
                cnt = Signal(max=n, name="pllfreq_cnt")
                tg = Signal(name="pllfreq_divn")
                getattr(self.sync, dom).__iadd__([
                    cnt.eq(Mux(cnt == n - 1, 0, cnt + 1)),
                    tg.eq(cnt < n // 2),
                ])
                ref = tg
            else:
                ref = ClockSignal(dom)
            self.pll_bits = PLLFreqProbe(ref)
            pll_load = self.pll_bits.load
            if toolchain == "peppercorn":
                platform.toolchain._pnr_opts += " --write routed.json "
        elif pll_bits:
            if l2_beacon:
                for name, cond in (("l2_valid", self.l2_beacon.sink_valid),
                                   ("l2_ready", self.l2_beacon.sink_valid & self.l2_beacon.sink_ready),
                                   ("l2_last", self.l2_beacon.sink_valid & self.l2_beacon.sink_ready &
                                               self.l2_beacon.sink_last)):
                    f, fm = Signal(), Signal()
                    self.sync += If(cond, f.eq(1))
                    self.specials += MultiReg(f, fm, "mb")
                    self.jtag_probe.flags_mb[name] = fm
            self.pll_bits = PLLStaticBits([self.jtag_probe.flag(n) for n in pll_bits.split(",")])
            pll_load = self.pll_bits.load
            if toolchain == "peppercorn":
                platform.toolchain._pnr_opts += " --write routed.json "

        platform.add_extension(_status_leds)
        led = Cat(*[platform.request("status_led", i) for i in range(8)])
        # active-high (verified on hardware); LED7 also carries the PLL-bit load (see pll_serial.py)
        if hasattr(self, "pll_serial"):
            # every serial/flag PLL output must stay loaded (pll_serial.py): even ones XOR'd onto
            # LED6, odd ones onto LED7 (up to 4 flags when sys and eth_tx are PLL-free).
            lo = self.pll_serial.loads
            l6, l7 = lo[0], lo[1]
            for x in lo[2::2]:
                l6 = l6 ^ x
            for x in lo[3::2]:
                l7 = l7 ^ x
            pll_load = pll_load | l7
            self.comb += led.eq(self.status_leds.led ^ (pll_load << 7) ^ (l6 << 6))
        else:
            self.comb += led.eq(self.status_leds.led ^ (pll_load << 7))

        # Constrain only the PHY-sourced RXC (25 MHz). PLL-derived clocks are left
        # unconstrained: nextpnr-himbaechel crashes on duplicate create_clock for
        # them and CDC is handled in RTL by LiteEth async FIFOs. -------------------
        platform.add_period_constraint(eth_clocks.rx, 1e9/(125e6 if gbe else 25e6))

    def add_diag(self, platform, eth_pads, sys_clk_freq, refclk_rb, link_up, speed, phyads=None,
                 pll_serial=None, pll_flags=None):
        # MDIO read-back + frequency meters, dumped once a second over UART (TASK-4999).
        # Everything here runs in "diag" = the raw 25 MHz oscillator, NO PLL: the UART and the
        # MDIO reads keep working even when a PLL does not lock, and the sys clock itself is
        # measured (SYS field). Counts are cycles per 2**20 diag cycles (12.5 MHz diag:
        # 25 MHz = 0x200000, 12.5 MHz = 0x100000).
        # clk25/2 from a toggle flop: the diag logic does not close 25 MHz on a 0.9 V core
        # (measured 17 MHz), 12.5 MHz does. Still PLL-free.
        diag_clk_freq = 12.5e6
        self.cd_osc   = ClockDomain(reset_less=True)
        self.comb += self.cd_osc.clk.eq(self.crg.clk25)
        diag_div      = Signal()
        self.sync.osc += diag_div.eq(~diag_div)
        self.cd_diag  = ClockDomain()
        # The toggle output is a fabric net: put it on a global clock buffer, otherwise the
        # diag domain runs on local routing with unanalysed skew -> hold failures that corrupt
        # every computed hex digit while template constants stay intact (TASK-4999, 23.9.).
        if type(self.crg.pll_sys).__name__ == "NoPLL" and sys_clk_freq == 12.5e6:
            # --sys-src div2: sys already IS clk25/2 on a global buffer; a third BUFG breaks
            # nextpnr ("Cell type 'CC_BUFG' is unsupported"), so share it.
            self.comb += self.cd_diag.clk.eq(ClockSignal("sys"))
        else:
            diag_bufg = Signal()
            self.specials += Instance("CC_BUFG", i_I=diag_div, o_O=diag_bufg)
            self.comb += self.cd_diag.clk.eq(diag_bufg)
        self.specials += AsyncResetSynchronizer(self.cd_diag, ~self.crg.rst_n)
        self.cd_sysm  = ClockDomain(reset_less=True)
        self.comb += self.cd_sysm.clk.eq(ClockSignal("sys"))
        phy_reset_d = Signal(reset=1)
        self.specials += MultiReg(self.ethphy.crg.reset, phy_reset_d, "diag", reset=1)
        to_diag = ClockDomainsRenamer({"sys": "diag"})
        self.mdio_diag = diag = to_diag(MDIODiagEngine(eth_pads, diag_clk_freq,
                                               phy_reset=phy_reset_d,
                                               reads=None if phyads is None else
                                                   [(a, r) for a in phyads for r in DIAG_READ_REGS]))
        self.fm_rxc = to_diag(FreqMeter("eth_rx"))
        self.fm_tx  = to_diag(FreqMeter("eth_tx"))
        self.fm_sys = to_diag(FreqMeter("sysm"))
        # Frame counters (start-of-frame events) in the PHY clock domains, 8 bit.
        txf, rxf = Signal(8), Signal(8)
        txf_s, rxf_s = Signal(8), Signal(8)
        for cd, ep, cnt, cnt_s in [("eth_tx", self.ethphy.sink, txf, txf_s),
                                   ("eth_rx", self.ethphy.source, rxf, rxf_s)]:
            first = Signal(reset=1)
            getattr(self.sync, cd).__iadd__(If(ep.valid & ep.ready,
                first.eq(ep.last),
                If(first, cnt.eq(cnt + 1))))
            self.specials += MultiReg(cnt, cnt_s, "diag")
        fm_ref = Signal(24)
        if refclk_rb is not None:
            self.cd_refrb = ClockDomain(reset_less=True)
            self.comb += self.cd_refrb.clk.eq(refclk_rb)
            self.cd_refrb.clk.attr.add(("clkbuf_inhibit", 1))
            self.fm_ref = to_diag(FreqMeter("refrb"))
            fm_ref = self.fm_ref.value
        phy_reset_raw_d = Signal()
        self.specials += MultiReg(self.ethphy.crg.reset, phy_reset_raw_d, "diag")
        dbg_alive = Signal(24)
        self.sync.diag += dbg_alive.eq(dbg_alive + 1)
        tpl = ["\r\nT4999 P=", *hexf(diag.passes, 2), " DE=", *hexf(diag.drive_err, 4),
               " SYS=", *hexf(self.fm_sys.value, 6), " PR=", *hexf(phy_reset_d, 1),
               " RXC=", *hexf(self.fm_rxc.value, 6), " REF=", *hexf(fm_ref, 6),
               " TX=", *hexf(self.fm_tx.value, 6), " L=", *hexf(link_up, 1),
               " S=", *hexf(speed, 1), " D=", *hexf(diag.done, 1),
               " TXF=", *hexf(txf_s, 2), " RXF=", *hexf(rxf_s, 2),
               # TASK-4999 (new board): is the MDIO engine stuck in SETTLE, and why?
               " ST=", *hexf(Cat(diag.fsm.ongoing("SETTLE"), phy_reset_raw_d), 1),
               " SC=", *hexf(diag.settle_cnt[-8:], 2), " AL=", *hexf(dbg_alive[16:24], 2), "\r\n"]
        for i, (a, r) in enumerate(diag.reads):
            if r == DIAG_READ_REGS[0]:
                tpl += ["A%d" % a]
            tpl += [" %02X=" % r, *hexf(diag.results[i], 4), "/", *hexf(diag.ta[i], 1)]
            if r == DIAG_READ_REGS[-1]:
                tpl += ["\r\n"]
        self.uart_dump = to_diag(UARTLineDumper(diag_clk_freq, tpl, baud=115200, period=1.0))
        platform.add_extension([
            ("diag_uart_tx", 0, Pins("IO_NA_A4")),
            ("diag_uart_tx", 1, Pins("IO_NB_B5")),
        ])
        for n in range(2):
            self.comb += platform.request("diag_uart_tx", n).eq(self.uart_dump.tx)

        # --pll-serial <bit_log2>: the same readings over two spare PLLs, read over JTAG
        # (tools/pll_serial_rx.py rx --state). The UART link to the DirtyJTAG went silent on
        # 24.9. (0 B even from a UART-only probe), JTAG is the only channel left (TASK-4999).
        # Frame (LSB first): passes, SYS[23:0], RXC[23:0], TX[23:0], REF[23:0],
        # {PR,D,S[1:0],L}, TXF, RXF, then per MDIO read 16-bit value (DIAG order).
        if pll_flags:
            # --pll-flags a,b: live 1-bit answers on two ECONOMY PLLs (pll_serial.PLLLevelBits).
            ri = {r: i for i, (a, r) in enumerate(diag.reads)}
            avail = {
                "link":     diag.results[ri[1]][2],                  # reg1 bit2 (latched low)
                "an_done":  diag.results[ri[1]][5],                  # reg1 bit5
                "partner":  diag.results[ri[5]] != 0,                # reg5 != 0
                "id_ok":    diag.results[ri[2]] == 0x0022,           # reg2
                "spd100":   diag.results[ri[31]][5],                 # reg31 bit5
                "fd":       diag.results[ri[31]][3],                 # reg31 bit3
                "done":     diag.done,
                "rxf_any":  rxf_s != 0,
                "txf_any":  txf_s != 0,
                "pr":       phy_reset_d,                             # PHY RESET_N asserted
                "passes_any": diag.passes != 0,
                "ta_id":    diag.ta[ri[2]],                          # 0 = a PHY answered reg2
                "de_any":   diag.drive_err != 0,
                "settle":   diag.fsm.ongoing("SETTLE"),
                "ref_ok":   (fm_ref > 0x180000) & (fm_ref < 0x280000),   # IO_EB_A3 read-back 18.75..31.25 MHz
                "ref_any":  fm_ref != 0,
                "rxc_any":  self.fm_rxc.value != 0,                  # PHY RX_CLK toggles at all
                "rxc_25":   (self.fm_rxc.value > 0x180000) & (self.fm_rxc.value < 0x280000),
                "sys_ok":   (self.fm_sys.value > 0x0C0000) & (self.fm_sys.value < 0x140000),  # 12.5 MHz = 0x100000
                "tx_ok":    (self.fm_tx.value > 0x180000) & (self.fm_tx.value < 0x280000),    # 25 MHz = 0x200000
                "one":      C(1, 1),
                "zero":     C(0, 1),
            }
            alive = Signal(24, name="pllflag_alive")
            self.sync.diag += alive.eq(alive + 1)
            avail["diag_alive"] = alive[23]                          # toggles every 0.67 s at 12.5 MHz
            fl = [avail[n] for n in pll_flags.split(",")]
            fl_osc = [Signal(name="pllflag_in%d" % i) for i in range(len(fl))]
            for i, f in enumerate(fl):
                fs = Signal(name="pllflag_diag%d" % i)
                self.comb += fs.eq(f)
                self.specials += MultiReg(fs, fl_osc[i], "osc")
            # PLL mode for the flags: ECONOMY/LOWPOWER drift with die temperature (24.9.: ECONOMY /2 fell out
            # of range after ~1.5 h, LOWPOWER started to lock) -> selectable, always pair a flag with 'one'.
            self.pll_serial = PLLLevelBits(fl_osc, cd="osc", perf_md=os.environ.get("PLLFLAG_MD", "ECONOMY"),
                                           out_clk=os.environ.get("PLLFLAG_OUT", "25.0"),
                                           zero_stop=os.environ.get("PLLFLAG_ZERO", "div8") == "stop")
            if " --write routed.json " not in getattr(platform.toolchain, "_pnr_opts", " --write routed.json "):
                platform.toolchain._pnr_opts += " --write routed.json "
        if pll_serial:
            flags = Signal(8)
            self.comb += flags.eq(Cat(link_up, speed[:2], diag.done, phy_reset_d))
            fields = [diag.passes, self.fm_sys.value, self.fm_rxc.value, self.fm_tx.value, fm_ref,
                      flags, txf_s, rxf_s] + [diag.results[i] for i in range(len(diag.reads))]
            data_diag = Cat(*fields)
            data_osc = Signal(len(data_diag))
            self.specials += MultiReg(data_diag, data_osc, "osc")
            # --pll-serial N[:div1:div0] (default levels /2 and /8)
            ps = [int(x) for x in str(pll_serial).split(":")]
            div1, div0 = (ps[1], ps[2]) if len(ps) == 3 else (2, 8)
            self.pll_serial = PLLSerialOut(data_osc, cd="osc", bit_log2=ps[0], div1=div1, div0=div0,
                                           perf_md="ECONOMY")
            if " --write routed.json " not in getattr(platform.toolchain, "_pnr_opts", " --write routed.json "):
                platform.toolchain._pnr_opts += " --write routed.json "


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LiteX GateMate RGMII + LiteEth UDP echo (no CPU)")
    parser.add_argument("--build",        action="store_true", help="Build the bitstream.")
    parser.add_argument("--sys-clk-freq", default=16e6, type=float, help="Fabric (sys) clock frequency.")
    parser.add_argument("--tx-clk-freq",  default=25e6, type=float, help="eth_tx line clock frequency.")
    parser.add_argument("--ip",           default="10.10.10.50",    help="Design IP address.")
    parser.add_argument("--udp-port",     default=7000, type=int,   help="UDP echo port.")
    parser.add_argument("--build-id",     default=1, type=int,      help="(unused since the LED ladder rework; kept for CLI compatibility)")
    parser.add_argument("--seed",         default=None, type=int,   help="nextpnr placement seed (peppercorn only).")
    parser.add_argument("--toolchain",    default="peppercorn", choices=["peppercorn", "colognechip"],
                        help="P&R flow: peppercorn (nextpr-himbaechel) or colognechip (proprietary p_r; needs yosys+p_r on PATH).")
    parser.add_argument("--gbe",          action="store_true",      help="1 Gbps (speed-adaptive) RGMII datapath; forces eth_tx = 125 MHz.")
    parser.add_argument("--no-cfgrst",    action="store_true",      help="Do NOT prepend CMD_CFGRST (gmpack --reset). Default: reset all config latches first.")
    parser.add_argument("--mdio-core",    action="store_true",      help="PHY MDIO by tools/uhello/mdio_core.v (proven on the new board) + register dump on the DirtyJTAG UART.")
    parser.add_argument("--diag",         action="store_true",      help="MDIO read-back + freq meters dumped over UART (IO_NA_A4/IO_NB_B5, 115200).")
    parser.add_argument("--refclk-drive", default=6, type=int, choices=[3, 6, 9, 12], help="IO_EB_A3 (PHY XI) drive strength, mA.")
    parser.add_argument("--refclk-slew",  default="fast", choices=["fast", "slow"], help="IO_EB_A3 slew.")
    parser.add_argument("--tx-clk-src",   default="clk25", choices=["clk25", "pll", "pll90", "io50"], help="eth_tx source: 25 MHz osc directly (default), PLL#1, PLL#1 with CLK90 as TXC, or io50 (PLL#1 50 MHz, all TX pins IOSEL FFs, TXC on CLK180).")
    parser.add_argument("--refclk-mode",  default="comb", choices=["comb", "ddr"], help="IO_EB_A3 driven by fabric-routed clk25 (comb) or a CC_ODDR (ddr).")
    parser.add_argument("--diag-phyads",  default=None,             help="Comma list of PHYADs to read in --diag (default 0..7).")
    parser.add_argument("--perf-mode",    default="speed", choices=["lowpower", "economy", "speed"],
                        help="GateMate operating mode = VDD_CORE jumper (0.9/1.0/1.1 V): PLL PERF_MD + nextpnr timing model.")
    parser.add_argument("--phy-reset-ms", default=20.0, type=float, help="KSZ9031 RESET_N hold after configuration, ms (DS tSR >= 10 ms; 0.016 = old 256-cycle pulse).")
    parser.add_argument("--tx-store-forward", action="store_true", help="Buffer whole TX frames in eth_tx (needed when sys <= 12.5 MHz).")
    parser.add_argument("--beacon-port",  default=None, type=int,   help="Send a 1/s UDP status beacon to <subnet>.255:<port> (TASK-4999).")
    parser.add_argument("--beacon-tag",   default=0, type=int,      help="Build tag byte carried in the beacon.")
    parser.add_argument("--single-pll",   action="store_true",      help="Only one PLL (eth_tx/TXC90); sys = clk25/2 fabric (needs --tx-clk-src pll90, --sys-clk-freq 12.5e6).")
    parser.add_argument("--jtag-probe",   action="store_true",      help="JTAG snapshot probe (CC_SERDES regfile; read with tools/jtag_mailbox.py snap --eth).")
    parser.add_argument("--l2-beacon",    action="store_true",      help="Raw L2 broadcast beacon (ethertype 0x88B5) with the probe snapshot, 2/s.")
    parser.add_argument("--pll-bits",     default=None,             help="Two probe flags on spare PLLs, e.g. 'phy_tx_any,phy_rx_any' (see jtag_probe.flag).")
    parser.add_argument("--raw-tx",       action="store_true",      help="No MAC: constant frame straight into the PHY sink 4x/s (ethertype 0x88B6); PLL bits = PHY sink done/valid.")
    parser.add_argument("--sdr-tx",       action="store_true",      help="TX pins from plain eth_tx registers instead of CC_ODDR (100M only); TX_CTL read back.")
    parser.add_argument("--raw-bits",     default=None,             help="--raw-tx PLL bits: two of txc,rxc,done,rxany,rxpre,ctl (bit0,bit1).")
    parser.add_argument("--phy-loopback", action="store_true",      help="KSZ9031 near-end loopback (reg0=0x6100) instead of AN 100FD.")
    parser.add_argument("--raw-bad-fcs",  action="store_true",      help="--raw-tx frame with a deliberately wrong FCS (a switch drops it; a local TX->RX path does not).")
    parser.add_argument("--raw-no-tx",    action="store_true",      help="--raw-tx control: never assert the PHY sink valid.")
    parser.add_argument("--no-echo",      action="store_true",      help="Leave out the UDP echo engine (its 2048-deep FIFO).")
    parser.add_argument("--synth-extra",  default=None,             help="Extra synth_gatemate options, e.g. '-nobram'.")
    parser.add_argument("--beacon-period", default=None, type=int,  help="L2 beacon period in sys cycles (default sys_clk_freq/2; small for post-synth sim).")
    parser.add_argument("--gen-only",     action="store_true",      help="Generate Verilog/scripts only (no yosys/nextpnr run).")
    parser.add_argument("--pnr-mode",     default=None, choices=["lowpower", "economy", "speed"], help="nextpnr fpga_mode override (PLL PERF_MD stays --perf-mode).")
    parser.add_argument("--pnr-extra",    default=None,             help="Extra nextpnr options, e.g. '--vopt no-bridges'.")
    parser.add_argument("--rx-off",       action="store_true",      help="Isolation: the MAC never sees received frames (RX_CTL forced 0).")
    parser.add_argument("--mb-clk25",     action="store_true",      help="Probe/PLL-bit domain on the raw 25 MHz oscillator (needs a free global: use --tx-clk-src pll).")
    parser.add_argument("--pll-freq",     default=None,             help="Spare PLL as frequency meter of a clock domain, e.g. 'eth_tx/2' or 'sys'.")
    parser.add_argument("--tx-pll-mode",  default=None, choices=["lowpower", "economy", "speed"], help="PERF_MD of the eth_tx PLL only.")
    parser.add_argument("--sys-src",      default="pll", choices=["pll", "div2"], help="sys clock: PLL or clk25/2 toggle on a BUFG (PLL-free).")
    parser.add_argument("--txc-delay-luts", default=0, type=int,    help="With --tx-clk-src clk25: TXC = clk25 through N identity LUTs (PLL-free 'phase shift').")
    parser.add_argument("--pll-flags",    default=None,             help="With --diag: two live flags on ECONOMY PLLs (link,partner,an_done,id_ok,spd100,fd,done,rxf_any,txf_any,one,zero).")
    parser.add_argument("--pll-serial",   default=None,             help="With --diag: send the diag readings over two spare PLLs (bit period 2**N osc cycles), read over JTAG.")
    parser.add_argument("--sdr-rx",       action="store_true",      help="RX pins captured by plain RXC registers instead of CC_IDDR (100M only).")
    parser.add_argument("--output-dir",   default=None,             help="Build directory (default build/eth).")
    parser.add_argument("--no-phy-refclk", action="store_true",      help="Do NOT drive the 25 MHz PHY reference clock on IO_EB_A3.")
    args = parser.parse_args()

    # --gbe implies a 125 MHz eth_tx line clock unless --tx-clk-freq was overridden.
    tx_clk_freq = args.tx_clk_freq
    if args.tx_clk_src == "io50":
        tx_clk_freq = 50e6
    if args.gbe and tx_clk_freq == 25e6:
        tx_clk_freq = 125e6

    soc = EthEchoSoC(
        sys_clk_freq = args.sys_clk_freq,
        tx_clk_freq  = tx_clk_freq,
        toolchain    = args.toolchain,
        gbe          = args.gbe,
        with_phy_refclk = not args.no_phy_refclk,
        ip_address   = args.ip,
        udp_port     = args.udp_port,
        build_id     = args.build_id,
        diag         = args.diag,
        refclk_drive = args.refclk_drive,
        refclk_slew  = args.refclk_slew,
        tx_clk_src   = args.tx_clk_src,
        refclk_mode  = args.refclk_mode,
        diag_phyads  = None if args.diag_phyads is None else [int(a) for a in args.diag_phyads.split(",")],
        perf_mode    = args.perf_mode,
        phy_reset_ms = args.phy_reset_ms,
        tx_store_forward = args.tx_store_forward,
        beacon_port  = args.beacon_port,
        beacon_tag   = args.beacon_tag,
        single_pll   = args.single_pll,
        jtag_probe   = args.jtag_probe,
        l2_beacon    = args.l2_beacon,
        pll_bits     = args.pll_bits,
        raw_tx       = args.raw_tx,
        sdr_tx       = args.sdr_tx,
        raw_bits     = args.raw_bits,
        phy_loopback = args.phy_loopback,
        raw_bad_fcs  = args.raw_bad_fcs,
        raw_no_tx    = args.raw_no_tx,
        no_echo      = args.no_echo,
        synth_extra  = args.synth_extra,
        beacon_period = args.beacon_period,
        pnr_mode     = args.pnr_mode,
        pnr_extra    = args.pnr_extra,
        rx_off       = args.rx_off,
        mb_clk25     = args.mb_clk25,
        pll_freq     = args.pll_freq,
        tx_pll_mode  = args.tx_pll_mode,
        mdio_core    = args.mdio_core,
        cfgrst       = not args.no_cfgrst,
        sys_src      = args.sys_src,
        txc_delay_luts = args.txc_delay_luts,
        sdr_rx       = args.sdr_rx,
        pll_serial   = args.pll_serial,
        pll_flags    = args.pll_flags,
    )
    builder = Builder(soc,
        output_dir = args.output_dir or os.path.join(os.path.dirname(__file__), "..", "build", "eth"),
        csr_csv    = None)
    build_kwargs = {}
    if args.seed is not None:
        build_kwargs["seed"] = args.seed
    if args.build:
        builder.build(**build_kwargs)
    elif args.gen_only:
        builder.build(run=False, **build_kwargs)


if __name__ == "__main__":
    main()
