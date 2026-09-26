#!/usr/bin/env python3
# Minimal UART probe for the ULX5M-GS (TASK-4999): no Ethernet, no PLL, clk25/2 domain.
# --pll: clock the UART from a GateMate PLL instead of clk25/2 through fabric.
# Prints "U4999 0123456789ABCDEF =/ FFFF <counter>" once per 0.25 s on IO_NA_A4 + IO_NB_B5.
# Separates "UART path / board state broken" from "big design broken".
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateware"))
from migen import *
from litex.gen import *
from litex.build.generic_platform import Pins
from litex_boards.platforms import intergalaktik_ulx5m_gs
from mdio_diag import UARTLineDumper, hexf
from litex.soc.cores.clock.colognechip import GateMatePLL

class Top(LiteXModule):
    def __init__(self, platform, drive_phy_reset_low=False, use_pll=False):
        clk25 = platform.request("clk25")
        if use_pll:
            # sys = PLL(clk25) 12.5 MHz: the PLL input uses the dedicated clock path.
            self.cd_sys = ClockDomain()
            self.pll = pll = GateMatePLL(perf_mode="lowpower")
            pll.register_clkin(clk25, 25e6)
            pll.create_clkout(self.cd_sys, 12.5e6)
        else:
            self.cd_osc = ClockDomain(reset_less=True)
            self.comb += self.cd_osc.clk.eq(clk25)
            div = Signal()
            self.sync.osc += div.eq(~div)
            self.cd_sys = ClockDomain(reset_less=True)
            self.comb += self.cd_sys.clk.eq(div)
        cnt = Signal(16)
        self.sync += cnt.eq(cnt + 1)
        tpl = ["\r\nU4999 0123456789ABCDEF =/ FFFF ", *hexf(cnt, 4)]
        self.uart = UARTLineDumper(12.5e6, tpl, baud=115200, period=0.25)
        platform.add_extension([("u_tx", 0, Pins("IO_NA_A4")), ("u_tx", 1, Pins("IO_NB_B5")),
                                ("phy_rst_n", 0, Pins("IO_EB_B3"))])
        for n in range(2):
            self.comb += platform.request("u_tx", n).eq(self.uart.tx)
        # Hold the KSZ9031 in reset (RESET_N low): isolates the PHY from the experiment.
        self.comb += platform.request("phy_rst_n").eq(0 if drive_phy_reset_low else 1)

if __name__ == "__main__":
    platform = intergalaktik_ulx5m_gs.Platform("peppercorn")
    platform.toolchain._pnr_opts += " --vopt fpga_mode=1 "
    top = Top(platform, drive_phy_reset_low="--phy-reset" in sys.argv, use_pll="--pll" in sys.argv)
    out = sys.argv[1]
    platform.build(top, build_dir=out, build_name="uart_probe")
