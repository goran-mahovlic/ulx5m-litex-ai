#
# Clock and reset generation for RGMII Ethernet on the Radiona ULX5M-GS
# (CologneChip GateMate CCGM1A1).
#
# Two GateMate PLLs off the 25 MHz oscillator (clk25, IO_SB_A8), per the
# hardware-verified split-clock architecture in docs/GATEMATE_CLOCKING.md:
#   PLL#1  25 -> 25 MHz  -> eth_tx line clock (thin RGMII TX serdes only,
#                           forwarded to the PHY as TXC via DDROutput/CC_ODDR).
#   PLL#2  25 -> sys_clk_freq (16 MHz default) -> fabric clock, runs the whole
#                           LiteEth "sys" datapath and the application logic.
# RXC (IO_EB_A7) is NOT touched here -- it is wired directly into the PHY's
# cd_eth_rx by LiteEthPHYRGMII_GateMate's CRG (raw fabric routing, no BUFG,
# per trap #1 in docs/GATEMATE_CLOCKING.md).
#
# A single 25 MHz fabric clock never closes worst-corner timing on this board
# (measured 16-19 MHz Fmax). Splitting the thin 25 MHz TX serdes onto its own
# PLL and running the fabric at 16 MHz is what makes the design close.
#
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.soc.cores.clock.colognechip import GateMatePLL

from sticky_lock import StickyLock


class EthCRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq, tx_clk_freq=25e6, tx_clk_src="pll", perf_mode="speed", single_pll=False,
                 tx_perf_mode=None, sys_src="pll", txc_delay_luts=0):
        # tx_perf_mode: PERF_MD of the eth_tx PLL only (default = perf_mode). TASK-4999 measured the
        # LOWPOWER 25->25 PLL output at <= 12.5 MHz (PLL used as a frequency meter over JTAG).
        tx_perf_mode = tx_perf_mode or perf_mode
        # perf_mode must match the board's VDD_CORE jumper (open=0.9 V lowpower, 1-2=1.0 V
        # economy, 2-3=1.1 V speed). A SPEED-configured PLL on a 0.9 V core is a candidate for
        # the intermittent "PLL#1 dead" measurement (TASK-4999).
        self.rst     = Signal()
        rst_n        = Signal()
        self.cd_sys  = ClockDomain()
        self.cd_tx25 = ClockDomain()  # PLL#1 output; fed into the PHY as eth_tx.
        self.tx_clk90 = None          # tx_clk_src="pll90": same 25 MHz, +90 deg, for TXC only.
        self.tx_clk180 = None         # tx_clk_src="io50": eth_tx = 50 MHz, CLK180 clocks the TXC IO FF.

        clk25 = platform.request("clk25")
        self.clk25 = clk25  # exposed: the target forwards it to the PHY's XI pin.
        self.specials += Instance("CC_USR_RSTN", o_USR_RSTN=rst_n)
        self.rst_n = rst_n  # exposed: the PLL-free diag domain resets on it.
        # "ref": the raw 25 MHz oscillator, reset ONLY by CC_USR_RSTN. Hosts the PLL lock filters and
        # (in the PHY) the KSZ9031 hardware reset + MDIO sequencer, so a chattering PLL lock flag can
        # never restart the PHY bring-up (TASK-4999, new board).
        self.cd_ref = ClockDomain()
        self.comb += self.cd_ref.clk.eq(clk25)
        self.specials += AsyncResetSynchronizer(self.cd_ref, ~rst_n)

        if tx_clk_src == "clk25" and txc_delay_luts:
            # PLL-free TXC (TASK-4999): clk25 through a chain of identity LUTs (CC_LUT1, kept), so
            # TXC rises a few ns after TXD/TX_CTL change on clk25. At 100M the PHY samples TXD on
            # the TXC rising edge and TX_CTL on both edges; any delay d in (2, 18) ns keeps both
            # samples away from the data transitions at 0/40 ns. ~2 ns per LUT+route on LOWPOWER.
            self.cd_tx25_90 = ClockDomain(reset_less=True)
            chain = clk25
            for i in range(txc_delay_luts):
                nxt = Signal(name="txc_dly%d" % i)
                nxt.attr.add("keep")
                self.specials += Instance("CC_LUT1", attr={("keep", "true")}, p_INIT=0b10,
                                          i_I0=chain, o_O=nxt)
                chain = nxt
            self.tx_clk90 = chain
        if tx_clk_src == "clk25":
            # eth_tx = the 25 MHz oscillator itself (no PLL#1). TASK-4999 measured PLL#1's
            # output as DEAD on hardware (in-fabric counter: 0 cycles), so nothing was ever
            # transmitted. clk25 is also the PHY XI reference -> TXC is frequency-locked to
            # the PHY by construction.
            assert tx_clk_freq == 25e6
            self.comb += self.cd_tx25.clk.eq(clk25)
            self.specials += AsyncResetSynchronizer(self.cd_tx25, ~rst_n | self.rst)
        elif tx_clk_src == "io50":
            # PLL#1: CLK0 = 50 MHz eth_tx, CLK180 = 50 MHz inverted. The PHY paces the 100M datapath
            # every 2nd cycle and drives TXD/TX_CTL from posedge IOSEL FFs and TXC from an IOSEL FF on
            # CLK180 -> TXC is 90 deg after the data by construction (no fabric-routed clock to a pad).
            # Proven on hardware with the standalone beacon eb50 (TASK-4999, 24.9. 20:21: frames on the
            # wire, where the CLK90-through-fabric TXC gave none).
            assert tx_clk_freq == 50e6
            self.cd_tx50_180 = ClockDomain(reset_less=True)
            self.pll_tx = pll_tx = GateMatePLL(perf_mode=tx_perf_mode)
            self.comb += pll_tx.reset.eq(~rst_n | self.rst)
            pll_tx.register_clkin(clk25, 25e6)
            pll_tx.create_clkout(self.cd_tx25,      tx_clk_freq, with_reset=False)
            pll_tx.create_clkout(self.cd_tx50_180, tx_clk_freq, phase=180, with_reset=False)
            self._pll_reset(pll_tx, [self.cd_tx25], "tx")
            self.tx_clk180 = self.cd_tx50_180.clk
        elif tx_clk_src == "pll90":
            # PLL#1: CLK0 = eth_tx (TXD/TX_CTL), CLK90 = TXC. KSZ9031 adds no TX input delay,
            # so the MAC must place TXC in the middle of the data eye (TASK-4999).
            assert tx_clk_freq == 25e6
            self.cd_tx25_90 = ClockDomain(reset_less=True)
            self.pll_tx = pll_tx = GateMatePLL(perf_mode=tx_perf_mode)
            self.comb += pll_tx.reset.eq(~rst_n | self.rst)
            pll_tx.register_clkin(clk25, 25e6)
            pll_tx.create_clkout(self.cd_tx25,    tx_clk_freq, with_reset=False)
            pll_tx.create_clkout(self.cd_tx25_90, tx_clk_freq, phase=90, with_reset=False)
            self._pll_reset(pll_tx, [self.cd_tx25], "tx")
            self.tx_clk90 = self.cd_tx25_90.clk
        else:
            # PLL#1: 25 -> 25 MHz, eth_tx line clock.
            # perf_mode="speed" per docs/GATEMATE_CLOCKING.md (required for the
            # 1.1 V hardware 100 Mbps target).
            self.pll_tx = pll_tx = GateMatePLL(perf_mode=tx_perf_mode)
            self.comb += pll_tx.reset.eq(~rst_n | self.rst)
            pll_tx.register_clkin(clk25, 25e6)
            pll_tx.create_clkout(self.cd_tx25, tx_clk_freq, with_reset=False)
            self._pll_reset(pll_tx, [self.cd_tx25], "tx")

        # PLL#2: 25 -> sys_clk_freq, fabric clock (LiteEth sys datapath).
        #
        # KNOWN FOLLOW-UP (docs/GATEMATE_CLOCKING.md trap #2): LiteX's
        # GateMatePLL (litex/soc/cores/clock/colognechip.py) leaves the CC_PLL
        # `USR_PLL_LOCKED_STDY` output unconnected (Open()) and derives `locked`
        # from the raw, non-steady `USR_PLL_LOCKED` output. This can reproduce a
        # seed-dependent bring-up hang. For a hardened bring-up, instantiate
        # CC_PLL directly with `o_USR_PLL_LOCKED_STDY` wired and gate reset on the
        # STEADY lock of both PLLs, 2-FF synced per domain. GateMatePLL is used
        # as-is here for simplicity; harden before relying on cold-boot recovery.
        if sys_src == "div2":
            # PLL-free sys (TASK-4999): clk25/2 from a toggle flop on a global buffer. The on-board
            # PLLs were measured wrong (LOWPOWER 25->25 locks at <= 12.5 MHz; SPEED/ECONOMY do not lock).
            assert sys_clk_freq == 12.5e6
            div = Signal()
            self.cd_div = ClockDomain(reset_less=True)
            self.comb += self.cd_div.clk.eq(clk25)
            self.sync.div += div.eq(~div)
            sys_bufg = Signal()
            self.specials += Instance("CC_BUFG", i_I=div, o_O=sys_bufg)
            self.comb += self.cd_sys.clk.eq(sys_bufg)
            self.specials += AsyncResetSynchronizer(self.cd_sys, ~rst_n | self.rst)
            self.pll_sys = type("NoPLL", (), {"locked": C(1, 1)})()
            return
        if single_pll:
            # TASK-4999 isolation: only ONE CC_PLL in the design (eth_tx CLK0 + TXC CLK90);
            # sys = clk25/2 from a toggle flop, no PLL. Rules out a second-PLL lock problem.
            assert tx_clk_src == "pll90" and sys_clk_freq == 12.5e6
            div = Signal()
            self.cd_div = ClockDomain(reset_less=True)
            self.comb += self.cd_div.clk.eq(clk25)
            self.sync.div += div.eq(~div)
            self.comb += self.cd_sys.clk.eq(div)
            self.specials += AsyncResetSynchronizer(self.cd_sys, ~rst_n | self.rst)
            self.pll_sys = type("NoPLL", (), {"locked": C(1, 1)})()
            return
        self.pll_sys = pll_sys = GateMatePLL(perf_mode=perf_mode)
        self.comb += pll_sys.reset.eq(~rst_n | self.rst)
        pll_sys.register_clkin(clk25, 25e6)
        pll_sys.create_clkout(self.cd_sys, sys_clk_freq, with_reset=False)
        self._pll_reset(pll_sys, [self.cd_sys], "sys")

    def _pll_reset(self, pll, cds, name):
        """Hold `cds` in reset until `pll` has been locked for 1 ms without a break (StickyLock in
        the ref domain), then never again (raw USR_PLL_LOCKED chatters on this board)."""
        sl = ClockDomainsRenamer("ref")(StickyLock(pll.locked, stable_cycles=int(25e6*1e-3)))
        setattr(self, "lock_" + name, sl)
        for cd in cds:
            self.specials += AsyncResetSynchronizer(cd, ~self.rst_n | self.rst | ~sl.locked)
        return sl
