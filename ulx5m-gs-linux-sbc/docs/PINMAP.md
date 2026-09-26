# ULX5M-GS Ethernet Pin Map (RGMII + MDIO)

Verified against the board schematic and known-good CologneChip constraints for
the ULX5M-GS. This is the same mapping applied by
`gateware/ulx5m_eth_platform.py`.

Bank EB = **1.8 V** (hardware-set; not expressed via any IOSTANDARD token in CologneChip CCF).

| Logical RGMII signal | IO_* ball | Misc attrs |
|---|---|---|
| tx_clk (rgmii_txc)   | IO_EB_B2 | SLEW=fast, DRIVE=6 |
| txd[0] | IO_EB_B5 | SLEW=fast, DRIVE=6 |
| txd[1] | IO_EB_A5 | SLEW=fast, DRIVE=6 |
| txd[2] | IO_EB_B4 | SLEW=fast, DRIVE=6 |
| txd[3] | IO_EB_A4 | SLEW=fast, DRIVE=6 |
| tx_ctl (tx_en) | IO_EB_A2 | SLEW=fast, DRIVE=6 |
| rx_clk (rgmii_rxc)   | IO_EB_A7 | none (non-clock-capable -> fabric routing) |
| rxd[0] | IO_EB_A0 | none |
| rxd[1] | IO_EB_B0 | none |
| rxd[2] | IO_EB_A1 | none |
| rxd[3] | IO_EB_B1 | none |
| rx_ctl (rx_dv) | IO_EB_A8 | none |
| rst_n | IO_EB_B3 | SLEW=slow, DRIVE=3 |
| mdc   | IO_EB_B6 | none |
| mdio  | IO_EB_A6 | none (board 4.7k pull-up) |
| int_n (optional) | IO_EB_B7 | none |
| eth_clk / refclk out | IO_EB_A3 | SLEW=fast, DRIVE=6 (X1/R104 dnp; FPGA must drive this) |
| eth_rgmii_refclk (optional) | IO_EB_B8 | none |

## LiteX `_io` extension fragment (added via platform.add_extension; installed platform untouched)
```python
_eth_io = [
    ("eth_clocks", 0,
        Subsignal("tx", Pins("IO_EB_B2"), Misc("SLEW=fast"), Misc("DRIVE=6")),
        Subsignal("rx", Pins("IO_EB_A7")),
    ),
    # PHY reference clock output (X1/R104 are dnp; FPGA must drive this pin).
    # DRIVE=6 required -- DRIVE=3 fails to start PHY internal PLL (TASK-4999).
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
```

## Notes / gotchas
- `clk25` = **IO_SB_A8** on v0.4 (NOT IO_SA_A8). The litex-boards platform already uses
  IO_SB_A8, so `platform.request("clk25")` is correct.
- RXC on IO_EB_A7 is non-clock-capable -> clocking handled per GATEMATE_CLOCKING.md.
