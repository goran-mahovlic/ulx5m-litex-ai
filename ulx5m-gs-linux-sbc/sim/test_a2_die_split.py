"""Tests for tools/a2_die_split.py (TASK-5092): which cells go to die 1B."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from a2_die_split import split


def cell(t, conns, dirs):
    return {"type": t, "connections": conns, "port_directions": dirs, "attributes": {}}


def netlist():
    # clk_fast = bit 2, clk_sys = bit 3
    # lut_f  -> ff_f (fast)                    : lut_f goes to 1B
    # lut_m  -> ff_f and ff_s (mixed sinks)    : stays 1A
    # ff_s (sys)                               : 1A
    # ram (CLKA=sys, CLKB=fast)                : 1B
    # ibuf                                     : untouched
    ff = {"D": "input", "CLK": "input", "EN": "input", "SR": "input", "Q": "output"}
    lut = {"I0": "input", "I1": "input", "O": "output"}
    return {"cells": {
        "ibuf":  cell("CC_IBUF", {"I": [20], "Y": [10]}, {"I": "input", "Y": "output"}),
        "lut_f": cell("CC_LUT2", {"I0": [10], "I1": [11], "O": [12]}, lut),
        "lut_m": cell("CC_LUT2", {"I0": [10], "I1": [11], "O": [13]}, lut),
        "ff_f":  cell("CC_DFF", {"D": [12], "CLK": [2], "EN": ["1"], "SR": ["0"], "Q": [14]}, ff),
        "ff_f2": cell("CC_DFF", {"D": [13], "CLK": [2], "EN": ["1"], "SR": ["0"], "Q": [15]}, ff),
        "ff_s":  cell("CC_DFF", {"D": [13], "CLK": [3], "EN": ["1"], "SR": ["0"], "Q": [16]}, ff),
        "ram":   cell("CC_BRAM_20K", {"CLKA": [3], "CLKB": [2], "DOA": [17]},
                      {"CLKA": "input", "CLKB": "input", "DOA": "output"}),
    }, "netnames": {}}


class TestSplit(unittest.TestCase):
    def setUp(self):
        self.mod = netlist()
        self.fast, self.count = split(self.mod, {2})

    def die(self, n):
        return self.mod["cells"][n]["attributes"].get("GATEMATE_DIE")

    def test_fast_registers_and_ram_on_1b(self):
        for n in ("ff_f", "ff_f2", "ram"):
            self.assertEqual(self.die(n), "1B", n)

    def test_lut_only_feeding_fast_on_1b(self):
        self.assertEqual(self.die("lut_f"), "1B")

    def test_lut_with_mixed_sinks_stays_1a(self):
        self.assertEqual(self.die("lut_m"), "1A")

    def test_sys_register_on_1a(self):
        self.assertEqual(self.die("ff_s"), "1A")

    def test_io_buffer_untouched(self):
        self.assertIsNone(self.die("ibuf"))

    def test_counts(self):
        self.assertEqual(self.count["1B"], 4)
        self.assertEqual(self.count["1A"], 2)


def netlist_io():
    # eth IDDR -> ff_e (fast) -> lut_e -> ff_e2 (fast)      : on 1B
    # dvi ODDR <- ff_v (fast clock, other block)           : stays 1A
    # ff_e2 -> ff_s (sys)                                  : ff_s stays 1A
    ff = {"D": "input", "CLK": "input", "EN": "input", "SR": "input", "Q": "output"}
    lut = {"I0": "input", "I1": "input", "O": "output"}
    ddr = {"D": "input", "CLK": "input", "Q0": "output", "Q1": "output"}
    oddr = {"D0": "input", "D1": "input", "CLK": "input", "Q": "output"}
    cells = {
        "iddr":  cell("CC_IDDR", {"D": [30], "CLK": [2], "Q0": [31], "Q1": [32]}, ddr),
        "ff_e":  cell("CC_DFF", {"D": [31], "CLK": [2], "EN": ["1"], "SR": ["0"], "Q": [33]}, ff),
        "lut_e": cell("CC_LUT2", {"I0": [33], "I1": [32], "O": [34]}, lut),
        "ff_e2": cell("CC_DFF", {"D": [34], "CLK": [2], "EN": ["1"], "SR": ["0"], "Q": [35]}, ff),
        "ff_s":  cell("CC_DFF", {"D": [35], "CLK": [3], "EN": ["1"], "SR": ["0"], "Q": [36]}, ff),
        "ff_v":  cell("CC_DFF", {"D": [37], "CLK": [2], "EN": ["1"], "SR": ["0"], "Q": [38]}, ff),
        "oddr":  cell("CC_ODDR", {"D0": [38], "D1": [38], "CLK": [2], "Q": [39]}, oddr),
    }
    names = {"eth_rx_data": {"bits": [30]}, "hdmi_d0": {"bits": [39]}}
    return {"cells": cells, "netnames": names}


class TestFromIO(unittest.TestCase):
    def setUp(self):
        self.mod = netlist_io()
        self.fast, _ = split(self.mod, {2}, from_io=True)

    def die(self, n):
        return self.mod["cells"][n]["attributes"].get("GATEMATE_DIE")

    def test_eth_path_on_1b(self):
        for n in ("ff_e", "lut_e", "ff_e2"):
            self.assertEqual(self.die(n), "1B", n)

    def test_other_block_on_same_clock_stays_1a(self):
        self.assertEqual(self.die("ff_v"), "1A")

    def test_sys_register_stays_1a(self):
        self.assertEqual(self.die("ff_s"), "1A")


if __name__ == "__main__":
    unittest.main()
