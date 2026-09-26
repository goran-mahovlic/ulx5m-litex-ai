#
# Platform IO helper for RGMII Ethernet on the Radiona ULX5M-GS.
#
# Adds the eth_clocks/eth IO groups via platform.add_extension() -- the
# installed litex-boards platform is never modified. Pin/attribute data is
# taken from docs/PINMAP.md ("LiteX `_io` extension fragment" section),
# verified against the board schematic and known-good constraints.
#
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import Subsignal, Pins, Misc

# _eth_io --------------------------------------------------------------------------------------------
# Verbatim from docs/PINMAP.md.

_eth_io = [
    ("eth_clocks", 0,
        Subsignal("tx", Pins("IO_EB_B2"), Misc("SLEW=fast"), Misc("DRIVE=6")),
        Subsignal("rx", Pins("IO_EB_A7")),
    ),
    # KSZ9031 XI (pin 46, net ETH_CLK) -- the 25 MHz reference clock the PHY runs on.
    # X1 (ECS-2520MV-250) and its series resistor R104 are BOTH marked `dnp` on the
    # ULX5M-GS, so the only possible source of this clock is the FPGA:
    #   U14.46 XI <-> ETH_CLK <-> U4.E16 = IO_EB_A3       (schematic netlist, ulx5m-gs-hw)
    #   schematic note: "Use EB-A3 as clock source. Or use EB-A3 as input and place X1,
    #                    C118, R104"
    # Without it the PHY's internal PLL never starts: no link, no RXC, MDIO reads 0x0000.
    # DRIVE=6 (6 mA, consistent with TX data/clk on EB bank) -- DRIVE=3 proven
    # insufficient to reliably start the PHY's internal crystal oscillator circuit
    # (traced as root cause of MDIO reads 0x0000 / persistent 1G link; TASK-4999).
    ("eth_refclk", 0, Pins("IO_EB_A3"), Misc("SLEW=fast"), Misc("DRIVE=6")),
    ("eth", 0,
        Subsignal("rst_n",   Pins("IO_EB_B3"), Misc("SLEW=slow"), Misc("DRIVE=3")),
        Subsignal("mdio",    Pins("IO_EB_A6")),
        Subsignal("mdc",     Pins("IO_EB_B6")),
        Subsignal("rx_ctl",  Pins("IO_EB_A8")),
        Subsignal("rx_data", Pins("IO_EB_A0 IO_EB_B0 IO_EB_A1 IO_EB_B1")),
        Subsignal("tx_ctl",  Pins("IO_EB_A2"), Misc("SLEW=fast"), Misc("DRIVE=6")),
        Subsignal("tx_data", Pins("IO_EB_B5 IO_EB_A5 IO_EB_B4 IO_EB_A4"), Misc("SLEW=fast"), Misc("DRIVE=6")),
    ),
]

def add_eth_io(platform, refclk_drive=6, refclk_slew="fast", tx_io_ff=False):
    """Register the RGMII/MDIO IO extension on `platform` (non-destructive).

    refclk_drive/refclk_slew override the IO_EB_A3 (PHY XI) pad attributes.
    tx_io_ff: FF_OBF=true on TXC/TX_CTL/TXD -> nextpnr packs the driving flip-flop into the IOSEL
    (global clock, ~0.3 ns), so TXC-to-data skew no longer depends on placement (TASK-4999, eb50).
    """
    io = []
    for entry in _eth_io:
        if tx_io_ff and entry[0] in ("eth_clocks", "eth"):
            subs = []
            for sub in entry[2:]:
                if sub.name in ("tx", "tx_ctl", "tx_data"):
                    sub = Subsignal(sub.name, *sub.constraints, Misc("FF_OBF=true"))
                subs.append(sub)
            entry = (entry[0], entry[1], *subs)
        if entry[0] == "eth_refclk":
            entry = ("eth_refclk", 0, Pins("IO_EB_A3"),
                     Misc("SLEW=%s" % refclk_slew), Misc("DRIVE=%d" % refclk_drive))
        io.append(entry)
    platform.add_extension(io)
    return platform
