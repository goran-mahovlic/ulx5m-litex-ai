#!/usr/bin/env python3
"""TASK-5234: SD pin tables (gateware/sd_pins.py) against the schematics.

Netlists (tools/hardver/kicad_netlist.py --json):
  docs/sd/ulx5m-gs-hw_61b6709_netlist.json  ULX5M-GS (ulx5m-gs-hw @ 61b6709): U4 = FPGA, J2 = CM4 GPIO connector
  docs/sd/cm5-io-base-a_netlist.json        CM5-IO-BASE-A: Module1 = CM4/CM5 connector, J8 = 40-pin header
Checks, per pin of the "j8" table: the FPGA ball is on a 1.8 V bank (VDD_NA/VDD_NB = SDRAM_VCC), its net reaches
the expected CM4 GPIO on J2, the carrier routes that GPIO straight to the expected J8 pin, and the ball is not used
by the np1817 Linux SoC (serial, SDRAM, the old slot). The "slot" table must match the SD_* nets of the old slot.
Run: python3 sim/test_sd_pins.py
"""
import json, os, re, sys, unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "gateware"))
from sd_pins import SD_PINS, J8_WIRING  # noqa: E402

ULX = json.load(open(os.path.join(ROOT, "docs/sd/ulx5m-gs-hw_61b6709_netlist.json")))["nets"]
CM5 = json.load(open(os.path.join(ROOT, "docs/sd/cm5-io-base-a_netlist.json")))["nets"]
NP1817_CCF = os.path.join(ROOT, "build/s_usb5_pll60_s2_np1817/gateware/intergalaktik_ulx5m_gs.ccf")


def ball_net(ball):
    """FPGA pad name (IO_NB_B3) -> (net, U4 pin number, other pins on the net)."""
    for net, pins in ULX.items():
        for ref, num, name, *_ in pins:
            if ref == "U4" and name == ball:
                return net, num, [(r, n) for r, n, *_ in pins if r != "U4"]
    raise KeyError(ball)


def bank_supply(ball):
    bank = ball.split("_")[1]                       # IO_NB_B3 -> NB
    return {net for net, pins in ULX.items() for ref, _, name, *_ in pins
            if ref == "U4" and name == "VDD_" + bank}


class SDPins(unittest.TestCase):
    def test_j8_on_1v8_bank_and_header(self):
        for sig, ball in SD_PINS["j8"].items():
            gpio, j8 = J8_WIRING[sig]
            with self.subTest(sig=sig, ball=ball):
                self.assertEqual(bank_supply(ball), {"SDRAM_VCC"}, "bank must be the 1.8 V SDRAM_VCC bank")
                net, _, others = ball_net(ball)
                self.assertEqual(net, gpio)
                j2 = [n for r, n in others if r == "J2"]
                self.assertEqual(len(j2), 1, others)
                self.assertEqual([r for r, _ in others if r != "J2"], [], "no resistor/other load on the net")
                cm = CM5[gpio]
                self.assertIn(["Module1", j2[0]], [p[:2] for p in cm], "carrier net must come from the same J2 pin")
                self.assertEqual(sorted(p[:2] for p in cm), sorted([["Module1", j2[0]], ["J8", str(j8)]]),
                                 "GPIO goes straight to the 40-pin header, nothing else")

    def test_slot_table_matches_old_sd_nets(self):
        for sig, ball in SD_PINS["slot"].items():
            net = {"clk": "SD_CLK", "mosi": "SD_CMD", "miso": "SD_DAT0", "cs_n": "SD_DAT3",
                   "dat1": "SD_DAT1", "dat2": "SD_DAT2"}[sig]
            self.assertEqual(ball_net(ball)[0], net, sig)

    def test_j8_free_in_np1817_soc(self):
        if not os.path.exists(NP1817_CCF):
            self.skipTest("np1817 build not present")
        with open(NP1817_CCF) as f:
            used = set(re.findall(r'Loc\s*=\s*"(IO_\w+)"', f.read()))
        self.assertEqual(used & set(SD_PINS["j8"].values()), set())

    def test_power_pins_on_header(self):
        self.assertIn(["J8", "1"], [p[:2] for p in CM5["+3.3v"]])
        self.assertIn(["J8", "17"], [p[:2] for p in CM5["+3.3v"]])
        self.assertIn(["J8", "25"], [p[:2] for p in CM5["GND"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
