"""Tests for tools/a2_iddr_to_fabric.py (TASK-5092)."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from a2_iddr_to_fabric import convert


def mod():
    iddr = lambda d, q0, q1: {"type": "CC_IDDR", "parameters": {"CLK_INV": "0"}, "attributes": {},
                              "port_directions": {"D": "input", "CLK": "input", "Q0": "output", "Q1": "output"},
                              "connections": {"D": [d], "CLK": [2], "Q0": [q0], "Q1": [q1]}}
    return {"cells": {"rx": iddr(10, 11, 12), "other": iddr(20, 21, 22)},
            "netnames": {"eth_rx_data": {"bits": [10]}, "sd_dat": {"bits": [20]}}}


class T(unittest.TestCase):
    def test_only_matching_iddr_converted(self):
        m = mod()
        self.assertEqual(convert(m, "eth_rx"), ["rx"])
        self.assertIn("other", m["cells"])
        self.assertNotIn("rx", m["cells"])

    def test_edges_and_ports(self):
        m = mod(); convert(m, "eth_rx")
        q0, q1 = m["cells"]["rx$q0"], m["cells"]["rx$q1"]
        self.assertEqual((q0["type"], q0["parameters"]["CLK_INV"], q0["connections"]["Q"]), ("CC_DFF", "0", [11]))
        self.assertEqual((q1["parameters"]["CLK_INV"], q1["connections"]["Q"]), ("1", [12]))
        for c in (q0, q1):
            self.assertEqual((c["connections"]["D"], c["connections"]["CLK"]), ([10], [2]))


if __name__ == "__main__":
    unittest.main()
