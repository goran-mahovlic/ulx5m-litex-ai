#!/usr/bin/env python3
#
# 1000 Mbps Ethernet on the Radiona ULX5M-GS (GateMate CCGM1A1 + KSZ9031), TASK-5032.
#
# CPU-less UDP/IP endpoint (LiteEth MAC/ARP/IP/ICMP/UDP + UDP echo) behind gateware/gbe_phy.py.
#
# Clocks (4 global nets, the whole budget of the CCGM1A1):
#   PLL_TX  25 -> 125 MHz: CLK0 = gtx (TXD/TX_CTL CC_ODDR + TX serializer), CLK90 = TXC candidate
#   PLL_SYS 25 -> sys (20 MHz): LiteEth + application + mdio_core
#   RXC (IO_EB_A7, non-clock pin) -> CC_BUFG -> grx (CC_IDDR + RX aligner)
#   clk25 itself stays OFF the global nets (clkbuf_inhibit): it only feeds the PLLs and the tiny
#   PLL-lock filters in "ref".
# TXC = one of {CLK0, ~CLK0, CLK90, ~CLK90} through one LUT. --txc-sel picks it; --txc-rotate cycles
# through all four every ~1.7 s and the L2 beacon carries the current index, so one bitstream +
# tcpdump shows which TXC phase the KSZ9031 accepts (it adds no TX delay, DS00002117F p. 22).
#
# Build:
#   python3 gateware/target_gbe.py --build --ip 192.168.10.212 [--txc-rotate | --txc-sel N] [--seed S]
#
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys

from migen import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import *
from litex.build.generic_platform import Pins, Misc, Subsignal

from litex_boards.platforms import intergalaktik_ulx5m_gs
from litex.soc.integration.soc_core import SoCMini
from litex.soc.integration.builder import Builder
from litex.soc.cores.clock.colognechip import GateMatePLL

sys.path.insert(0, os.path.dirname(__file__))
from gbe_phy import GbePHY
from eth_stack import EthUDPStack, UDPEcho
from sticky_lock import StickyLock
from l2_beacon import L2Beacon, ETHERTYPE_L2BEACON

_status_leds = [("status_led", i, Pins(p), Misc("DRIVE=3")) for i, p in enumerate(
    ["IO_SB_A0", "IO_SB_B0", "IO_SB_A1", "IO_SB_B1", "IO_SB_B2", "IO_SB_A2", "IO_SB_B3", "IO_SB_A3"])]


def eth_io(txc_delay=0, tx_delay=0, rx_delay=0, drive=6):
    """RGMII + MDIO pins (docs/PINMAP.md). No eth_refclk: the new board has X1 on XI and E16 cut (A5)."""
    txm = [Misc("SLEW=fast"), Misc("DRIVE=%d" % drive)]
    dl  = lambda k, v: [Misc("%s=%d" % (k, v))] if v else []
    return [
        ("eth_clocks", 0,
            Subsignal("tx", Pins("IO_EB_B2"), *txm, *dl("DELAY_OBF", txc_delay)),
            Subsignal("rx", Pins("IO_EB_A7")),
        ),
        ("eth", 0,
            Subsignal("rst_n",   Pins("IO_EB_B3"), Misc("SLEW=slow"), Misc("DRIVE=3")),
            Subsignal("mdio",    Pins("IO_EB_A6")),
            Subsignal("mdc",     Pins("IO_EB_B6")),
            Subsignal("rx_ctl",  Pins("IO_EB_A8"), *dl("DELAY_IBF", rx_delay)),
            Subsignal("rx_data", Pins("IO_EB_A0 IO_EB_B0 IO_EB_A1 IO_EB_B1"), *dl("DELAY_IBF", rx_delay)),
            Subsignal("tx_ctl",  Pins("IO_EB_A2"), *txm, *dl("DELAY_OBF", tx_delay)),
            Subsignal("tx_data", Pins("IO_EB_B5 IO_EB_A5 IO_EB_B4 IO_EB_A4"), *txm, *dl("DELAY_OBF", tx_delay)),
        ),
        ("mdio_core_uart", 0, Pins("IO_NA_A4")),
        ("mdio_core_uart", 1, Pins("IO_NB_B5")),
    ]


class GbeCRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq, perf_mode="economy", txc_phase=90):
        self.cd_sys   = ClockDomain()
        self.cd_gtx0  = ClockDomain()
        self.cd_gtx90 = ClockDomain(reset_less=True)
        self.cd_ref   = ClockDomain()

        clk25 = platform.request("clk25")
        clk25.attr.add(("clkbuf_inhibit", 1))
        rst_n = Signal()
        self.specials += Instance("CC_USR_RSTN", o_USR_RSTN=rst_n)
        self.comb += self.cd_ref.clk.eq(clk25)
        # LiteX >= 2026.08 feeds the PLL through its own clkin_signal, so the pad attribute alone no longer keeps
        # clk25 off the global nets: the few "ref" flip-flops took the 4th CC_BUFG, which TXC needs (TASK-5032).
        self.cd_ref.clk.attr.add(("clkbuf_inhibit", 1))
        self.specials += AsyncResetSynchronizer(self.cd_ref, ~rst_n)

        self.pll_tx = pll_tx = GateMatePLL(perf_mode=perf_mode)
        self.comb += pll_tx.reset.eq(~rst_n)
        pll_tx.register_clkin(clk25, 25e6)
        pll_tx.create_clkout(self.cd_gtx0,  125e6, with_reset=False)
        pll_tx.create_clkout(self.cd_gtx90, 125e6, phase=txc_phase, with_reset=False)   # TXC source

        self.pll_sys = pll_sys = GateMatePLL(perf_mode=perf_mode)
        self.comb += pll_sys.reset.eq(~rst_n)
        pll_sys.register_clkin(clk25, 25e6)
        pll_sys.create_clkout(self.cd_sys, sys_clk_freq, with_reset=False)

        # Sticky, debounced lock (raw USR_PLL_LOCKED chatters on this board: lessons B5/B6).
        self.lock_sys = ClockDomainsRenamer("ref")(StickyLock(pll_sys.locked, int(25e6*1e-3)))
        self.lock_tx  = ClockDomainsRenamer("ref")(StickyLock(pll_tx.locked,  int(25e6*1e-3)))
        self.specials += AsyncResetSynchronizer(self.cd_sys, ~rst_n | ~self.lock_sys.locked)
        self.eth_rst = Signal()
        self.comb += self.eth_rst.eq(~rst_n | ~self.lock_sys.locked | ~self.lock_tx.locked)


class GbeSoC(SoCMini):
    def __init__(self, sys_clk_freq=20e6, ip_address="192.168.10.212", mac_address=0x10e2d5000000,
                 udp_port=7000, perf_mode="economy", txc_sel=2, txc_rotate=False, txc_delay=0, tx_delay=0,
                 rx_delay=0, beacon=True, beacon_hz=8, adv="1000", seed=None, cfgrst=True, pnr_mode="speed",
                 last_be_fix=False, txc_phase=90, txc_bufg=True, **kwargs):
        platform = intergalaktik_ulx5m_gs.Platform("peppercorn")
        # pnr_mode = nextpnr timing model only (fpga_mode), independent of the PLL PERF_MD (perf_mode). The board
        # runs VDD_CORE = 1.1 V (J3 2-3), i.e. the SPEED voltage, so the SPEED model is the physically right one;
        # the PLLs stay ECONOMY because only ECONOMY locks 4/4 at 1.1 V (lesson B3).
        platform.toolchain._pnr_opts += " --vopt fpga_mode=%d " % {"lowpower": 1, "economy": 2, "speed": 3}[pnr_mode]
        if cfgrst:   # CMD_CFGRST first (lesson H1): never load on top of the previous configuration
            platform.toolchain._packer_opts = "--reset " + platform.toolchain._packer_opts
        platform.add_extension(eth_io(txc_delay, tx_delay, rx_delay))
        platform.add_extension(_status_leds)

        self.crg = crg = GbeCRG(platform, sys_clk_freq, perf_mode, txc_phase)
        SoCMini.__init__(self, platform, clk_freq=sys_clk_freq,
                         ident="ULX5M-GS GbE LiteEth UDP echo (TASK-5032)", **kwargs)

        clock_pads = platform.request("eth_clocks")
        pads       = platform.request("eth")

        # TXC select: fixed, or rotating every 2^25 sys cycles (1.7 s @ 20 MHz).
        sel = Signal(2, reset=txc_sel)
        if txc_rotate:
            rot = Signal(25)
            self.sync += [rot.eq(rot + 1), If(rot == 0, sel.eq(sel + 1))]
        self.txc_sel = sel

        self.ethphy = phy = GbePHY(clock_pads, pads, clk_tx=crg.cd_gtx0.clk,
                                   txc_clks=[crg.cd_gtx0.clk, crg.cd_gtx90.clk],
                                   txc_sel=sel if txc_rotate else txc_sel, rst=crg.eth_rst,
                                   txc_bufg=txc_bufg and not txc_rotate)
        phy.tx_clk_freq = phy.rx_clk_freq = sys_clk_freq
        platform.add_period_constraint(clock_pads.rx, 1e9/125e6)

        # last_be_fix: only for the old LiteX 52f183ef6 tree; LiteX >= 7fca6dba sets last_be itself (sim/tb_lastbe.py).
        self.stack = EthUDPStack(phy, mac_address, ip_address, sys_clk_freq, with_sys_datapath=True,
                                 tx_last_be_fix=last_be_fix)
        self.echo  = UDPEcho(self.stack, udp_port)

        # KSZ9031: RESET_N + MDIO writes (AN) + register dump on the DirtyJTAG UART, in sys.
        reg9, reg4 = {"1000": (0x0200, 0x0001), "100": (0x0000, 0x0101), "all": (0x0200, 0x01E1)}[adv]
        snap = Signal(256)
        platform.add_source(os.path.join(os.path.dirname(__file__), "..", "tools", "uhello", "mdio_core.v"))
        self.specials += Instance("mdio_core",
            # WRITE_AFTER = 0: the advertisement (+ AN restart) goes out on the first MDIO pass, ~0.1 s after reset,
            # before the power-on AN completes. At the default 6 passes the restart came ~2 s later and cost a
            # second 1000BASE-T negotiation: first ping reply 12.2 / 6.9 / 7.1 s (Ring10, TASK-5032).
            p_WRITE_AFTER = 0,
            p_REG9 = reg9, p_REG4 = reg4, p_REG0 = 0x1200, p_BAUD = int(round(sys_clk_freq/115200)) - 1,
            i_clk25   = ClockSignal("sys"),
            o_uart_a  = platform.request("mdio_core_uart", 0),
            o_uart_b  = platform.request("mdio_core_uart", 1),
            o_mdc     = pads.mdc,
            io_mdio   = pads.mdio,
            o_rst_n   = pads.rst_n,
            i_rxc     = ClockSignal("grx"),
            i_rx_ctl  = phy.core.rx_rs_ctl,     # F= RX_CTL rising edges (frames at the RGMII pins)
            # D= tx_frames(sys) | tx_emit(gtx) | rx_frames(sys) | rx_drops(grx) | lock_sys lock_tx rx_sel flips[4:0]
            i_dbg     = Cat(phy.core.rx_flips[:5], phy.core.rx_sel, crg.lock_tx.locked, crg.lock_sys.locked,
                            phy.core.rx_drops, phy.core.rx_frames, phy.core.tx_emit, phy.core.tx_frames),
            o_snap_bus = snap)
        # snap_bus = {passes, idm, {wrote,addr}, r0, r1, r4, r5, r9, ra, rf, rfreq(24), frames(16), 80'h0}
        f = lambda hi, n: snap[256 - hi - n:256 - hi]
        mdio_passes, r1, ra, rf, rfreq = f(0, 8), f(40, 16), f(104, 16), f(120, 16), f(136, 24)

        # L2 beacon (ethertype 0x88B5), payload after the header:
        #   txc_sel, rx_frames(2), rx_drops, rx_sel, rx_flips, tx_frames(2), mdio_passes, R1(2), RA(2), RF(2),
        #   RXC count per 2^20 sys cycles (3).
        core = phy.core
        if beacon:
            # the beacon packs LSB first: build a big-endian byte list
            def be(s):
                n = (len(s) + 7)//8
                return [s[8*(n-1-i):8*(n-i)] for i in range(n)]
            b = []
            b += [Cat(sel, C(0, 6))]
            for s in [core.rx_frames, core.rx_drops, Cat(core.rx_sel, C(0, 7)), core.rx_flips, core.tx_frames,
                      mdio_passes, r1, ra, rf, rfreq]:
                b += be(s)
            snapshot = Cat(*b)
            self.l2_beacon = L2Beacon(self.stack.core.mac.crossbar.get_port(ETHERTYPE_L2BEACON, dw=8),
                                      mac_address, snapshot, period=int(sys_clk_freq // beacon_hz), tag=0x32)

        # LEDs: 7 heartbeat, 6 RX frame (stretched), 5 TX frame, 4 link (R1 bit 2), 3..2 TXC sel, 1 R1F=1000,
        # 0 PLL locks.
        leds = [platform.request("status_led", i) for i in range(8)]
        hb = Signal(25)
        self.sync += hb.eq(hb + 1)
        def stretch(ev):
            cnt = Signal(22)
            self.sync += If(ev, cnt.eq(2**22 - 1)).Elif(cnt != 0, cnt.eq(cnt - 1))
            return cnt != 0
        prev_rx, prev_tx = Signal(16), Signal(16)
        self.sync += [prev_rx.eq(core.rx_frames), prev_tx.eq(core.tx_frames)]
        rx_led, tx_led = stretch(prev_rx != core.rx_frames), stretch(prev_tx != core.tx_frames)
        self.comb += [
            leds[7].eq(hb[24]),
            leds[6].eq(rx_led),
            leds[5].eq(tx_led),
            leds[4].eq(r1[2]),
            leds[3].eq(sel[1]), leds[2].eq(sel[0]),
            leds[1].eq(rf[6]),      # KSZ9031 reg 0x1F bit 6 = speed 1000
            leds[0].eq(crg.lock_sys.locked & crg.lock_tx.locked),
        ]


def main():
    import argparse
    p = argparse.ArgumentParser(description="ULX5M-GS GbE (TASK-5032)")
    p.add_argument("--build",      action="store_true")
    p.add_argument("--output-dir", default=None)
    p.add_argument("--sys-clk-freq", default=20e6, type=float)
    p.add_argument("--ip",         default="192.168.10.212")
    p.add_argument("--perf-mode",  default="economy", choices=["lowpower", "economy", "speed"], help="PLL PERF_MD")
    p.add_argument("--pnr-mode",   default="speed", choices=["lowpower", "economy", "speed"],
                   help="nextpnr timing model (VDD_CORE 1.1 V = speed)")
    p.add_argument("--last-be-fix", action="store_true", help="TXLastBE8 (only needed with LiteX < 7fca6dba)")
    p.add_argument("--txc-sel",    default=2, type=int, help="0 CLK0, 1 ~CLK0, 2 CLK<txc-phase>, 3 ~CLK<txc-phase>")
    p.add_argument("--txc-phase",  default=90, type=int, choices=[90, 180, 270], help="PLL output used as TXC")
    p.add_argument("--no-txc-bufg", action="store_true", help="TXC straight from the PLL output (fabric route)")
    p.add_argument("--txc-rotate", action="store_true", help="cycle TXC through 0..3 every 1.7 s")
    p.add_argument("--txc-delay",  default=0, type=int, help="DELAY_OBF taps on TXC (0..15)")
    p.add_argument("--tx-delay",   default=0, type=int, help="DELAY_OBF taps on TXD/TX_CTL")
    p.add_argument("--rx-delay",   default=0, type=int, help="DELAY_IBF taps on RXD/RX_CTL")
    p.add_argument("--adv",        default="1000", choices=["1000", "100", "all"])
    p.add_argument("--no-beacon",  action="store_true")
    p.add_argument("--seed",       default=None, type=int)
    args = p.parse_args()

    soc = GbeSoC(sys_clk_freq=args.sys_clk_freq, ip_address=args.ip, perf_mode=args.perf_mode,
                 txc_sel=args.txc_sel, txc_rotate=args.txc_rotate, txc_delay=args.txc_delay,
                 tx_delay=args.tx_delay, rx_delay=args.rx_delay, adv=args.adv, beacon=not args.no_beacon,
                 pnr_mode=args.pnr_mode, last_be_fix=args.last_be_fix,
                 txc_phase=args.txc_phase, txc_bufg=not args.no_txc_bufg)
    builder = Builder(soc, csr_csv=None,
        output_dir=args.output_dir or os.path.join(os.path.dirname(__file__), "..", "build", "gbe"))
    kw = {"seed": args.seed} if args.seed is not None else {}
    builder.build(run=args.build, **kw)


if __name__ == "__main__":
    main()
