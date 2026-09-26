#!/usr/bin/env python3
# TASK-5051: stand-alone P&R of the USB host engine (gateware/usb_pnru.py) to measure its own Fmax and size,
# away from the full SoC: SoCMini (UART bridge, sys 20 MHz) + USBHostPNRU with the engine clock
#   pll48   48 MHz PLL output on fabric routing (clkbuf_inhibit)          - clock option a
#   gtx125  125 MHz PLL output on a global net                            - clock option b (engine in gtx0)
#   bufg48  48 MHz PLL output on a global net                             - clock option c
#
#   source tools/sbc_env.sh
#   python3 tools/usb_pnru_pnr.py --clk gtx125 --seed 1 --output-dir build/usbpnr_gtx125_s1
#
# SPDX-License-Identifier: BSD-2-Clause

import argparse
import os
import sys

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import LiteXModule
from litex_boards.platforms import intergalaktik_ulx5m_gs
from litex.soc.integration.soc_core import SoCMini
from litex.soc.integration.builder import Builder
from litex.soc.cores.clock.colognechip import GateMatePLL

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateware"))
from target_soc import _usb_host
from usb_pnru import USBHostPNRU

FREQ = {"pll48": 48e6, "gtx125": 125e6, "bufg48": 48e6, "none": 48e6}   # none: baseline without the USB core


class CRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq, usb_clk):
        self.cd_sys = ClockDomain()
        clk25 = platform.request("clk25")
        rst_n = Signal()
        self.specials += Instance("CC_USR_RSTN", o_USR_RSTN=rst_n)
        self.pll_sys = pll = GateMatePLL(perf_mode="economy")
        self.comb += pll.reset.eq(~rst_n)
        pll.register_clkin(clk25, 25e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        if usb_clk == "none":
            return
        self.cd_usb = ClockDomain()
        self.pll_usb = pll = GateMatePLL(perf_mode="economy")
        self.comb += pll.reset.eq(~rst_n)
        pll.register_clkin(clk25, 25e6)
        pll.create_clkout(self.cd_usb, FREQ[usb_clk])
        if usb_clk == "pll48":
            self.cd_usb.clk.attr.add(("clkbuf_inhibit", 1))


class USBPNRUTest(SoCMini):
    def __init__(self, usb_clk, sys_clk_freq=20e6):
        platform = intergalaktik_ulx5m_gs.Platform("peppercorn")
        platform.toolchain._pnr_opts += " --vopt fpga_mode=3 "
        platform.toolchain._packer_opts = "--reset " + platform.toolchain._packer_opts
        self.crg = CRG(platform, sys_clk_freq, usb_clk)
        SoCMini.__init__(self, platform, sys_clk_freq, ident="USB PNRU P&R test")
        self.add_uartbone(name="serial")
        if usb_clk != "none":
            platform.add_extension(_usb_host)
            self.usb_pnru = USBHostPNRU(platform.request("usb_host"), FREQ[usb_clk], sys_clk_freq,
                                        pull=platform.request("usb_pull"), with_detect=False, with_events=False)



def main():
    p = argparse.ArgumentParser()
    p.add_argument("--clk", default="pll48", choices=list(FREQ))
    p.add_argument("--seed", default=1, type=int)
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()
    soc = USBPNRUTest(args.clk)
    Builder(soc, output_dir=args.output_dir, compile_software=False).build(seed=args.seed)


if __name__ == "__main__":
    main()
