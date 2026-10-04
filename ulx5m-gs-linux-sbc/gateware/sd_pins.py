#
# SD card pin tables for the ULX5M-GS (TASK-5234). Both are on 1.8 V banks (VDD_NA/VDD_NB = SDRAM_VCC).
#
# slot: the microSD slot of the CM5-IO-BASE-A carrier (CM4 SD_* pins). The carrier wires it straight to the card,
#       with no level translator, so a 3.3 V card never sees VIH (TASK-5039, docs/SPI_SD_TASK-5039.md).
# j8:   Raspberry Pi SPI0 pins of the carrier's 40-pin header J8 (GPIO8..11, + GPIO7/GPIO25 for 4-bit) for an
#       external microSD module behind a 1.8 V <-> 3.3 V translator (A side 1.8 V). Checked against the netlists
#       by sim/test_sd_pins.py.
#
# Keys follow the LiteX spisdcard resource: clk, mosi (= CMD), cs_n (= DAT3), miso (= DAT0); dat1/dat2 for 4-bit.

SD_PINS = {
    "slot": {"clk": "IO_NA_A3", "mosi": "IO_NA_B3", "cs_n": "IO_NA_A2", "miso": "IO_NA_A1",
             "dat1": "IO_NB_A5", "dat2": "IO_NA_B2"},
    "j8":   {"clk": "IO_NB_B3", "mosi": "IO_NB_B1", "cs_n": "IO_NB_B2", "miso": "IO_NB_A1",
             "dat1": "IO_NB_A2", "dat2": "IO_NB_A0"},
}

# j8 signal -> (CM4 GPIO net, J8 header pin)
J8_WIRING = {
    "clk":  ("GPIO11", 23),   # SPI0 SCLK
    "mosi": ("GPIO10", 19),   # SPI0 MOSI
    "miso": ("GPIO9",  21),   # SPI0 MISO
    "cs_n": ("GPIO8",  24),   # SPI0 CE0
    "dat1": ("GPIO7",  26),   # SPI0 CE1
    "dat2": ("GPIO25", 22),
}
